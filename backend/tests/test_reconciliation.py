"""An uncertain delivery must have an operator route out of it."""

from datetime import timedelta
import pytest
from sqlalchemy import func, select
from app import config, providers, service
from app.db import SessionLocal
from app.models import Delivery, Event, FollowUp, Message, Run, now
from test_workflow import get_message, submit


def approved_message(admin):
    submit(admin)
    msg = get_message()
    admin.post(f"/admin/messages/{msg.id}/approve")
    return msg


def crash_during_smtp(admin, monkeypatch):
    """Leave a message in `sending`, exactly as a process killed mid-delivery would."""
    monkeypatch.setattr(config, "EMAIL_PROVIDER", "smtp")

    def die(lead, message):
        raise KeyboardInterrupt("process killed mid-delivery")

    monkeypatch.setattr(providers, "smtp_send", die)
    msg = approved_message(admin)
    with pytest.raises(KeyboardInterrupt):
        with SessionLocal() as db:
            service.send(db, msg.id)
    return msg


def test_a_crash_mid_delivery_leaves_a_timestamped_send_intent(admin, monkeypatch):
    msg = crash_during_smtp(admin, monkeypatch)
    with SessionLocal() as db:
        stored = db.get(Message, msg.id)
        assert stored.state == "sending"
        assert stored.sending_since is not None


def test_stuck_send_intent_is_aged_into_unknown_and_surfaced(admin, monkeypatch):
    msg = crash_during_smtp(admin, monkeypatch)
    with SessionLocal() as db:
        db.get(Message, msg.id).sending_since = now() - timedelta(hours=1)
        db.commit()
        assert service.reap_stuck_sending(db) == 1
        assert db.get(Message, msg.id).state == "unknown"
        kinds = set(db.scalars(select(Event.kind)).all())
    assert "delivery_uncertain" in kinds
    listed = admin.get("/admin/messages/unresolved").json()
    assert [row["id"] for row in listed] == [msg.id]


def test_a_fresh_send_intent_is_not_aged_out(admin, monkeypatch):
    msg = crash_during_smtp(admin, monkeypatch)
    with SessionLocal() as db:
        assert service.reap_stuck_sending(db) == 0
        assert db.get(Message, msg.id).state == "sending"


def test_reconciling_as_delivered_completes_the_workflow(admin, monkeypatch):
    msg = crash_during_smtp(admin, monkeypatch)
    result = admin.post(f"/admin/messages/{msg.id}/reconcile", json={"outcome": "delivered", "provider_id": "<smtp-123@mail>", "note": "Found in sent items"})
    assert result.status_code == 200 and result.json()["state"] == "sent"
    with SessionLocal() as db:
        assert db.scalar(select(Message.reconciled_by).where(Message.id == msg.id)) == "admin"
        assert db.get(Delivery, msg.id).provider_id == "<smtp-123@mail>"
        # The initial message was delivered, so the follow-up schedule exists.
        assert db.scalar(select(func.count(FollowUp.id))) == 2
        kinds = set(db.scalars(select(Event.kind)).all())
        assert "delivery_reconciled" in kinds


def test_reconciling_as_not_delivered_allows_a_retry(admin, monkeypatch):
    msg = crash_during_smtp(admin, monkeypatch)
    assert admin.post(f"/admin/messages/{msg.id}/reconcile", json={"outcome": "not_delivered"}).json()["state"] == "failed"
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Delivery.message_id))) == 0
    monkeypatch.setattr(config, "EMAIL_PROVIDER", "mock")
    admin.post(f"/admin/messages/{msg.id}/approve")
    assert admin.post(f"/admin/messages/{msg.id}/send").json()["state"] == "sent"


def test_reconciliation_is_refused_for_a_settled_message(admin):
    msg = approved_message(admin)
    assert admin.post(f"/admin/messages/{msg.id}/send").json()["state"] == "sent"
    assert admin.post(f"/admin/messages/{msg.id}/reconcile", json={"outcome": "delivered"}).status_code == 409


def test_unknown_outcome_is_rejected(admin, monkeypatch):
    msg = crash_during_smtp(admin, monkeypatch)
    assert admin.post(f"/admin/messages/{msg.id}/reconcile", json={"outcome": "probably-fine"}).status_code == 422


def test_maintenance_tick_ages_stuck_deliveries(admin, monkeypatch):
    msg = crash_during_smtp(admin, monkeypatch)
    with SessionLocal() as db:
        db.get(Message, msg.id).sending_since = now() - timedelta(hours=1)
        db.commit()
    result = admin.post("/automation/maintenance/tick", headers={"Authorization": f"Bearer {config.AUTOMATION_SECRET}"})
    assert result.status_code == 200 and result.json()["deliveries_aged"] == 1


def test_reconciliation_requires_authentication(admin, monkeypatch):
    msg = crash_during_smtp(admin, monkeypatch)
    # A separate client: the admin fixture authenticates the shared one in place.
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as anonymous:
        assert anonymous.post(f"/admin/messages/{msg.id}/reconcile", json={"outcome": "delivered"}).status_code == 401
    with SessionLocal() as db:
        assert db.get(Message, msg.id).state == "sending"
        assert db.scalar(select(func.count(Run.id)).where(Run.workflow == "email_delivery")) >= 1
