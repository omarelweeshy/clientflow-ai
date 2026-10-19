"""Diagnosability guarantees: accurate failure causes, scrubbed logs, isolated ticks."""

import logging
import uuid
from sqlalchemy import select
from app import config, observability, service
from app.db import SessionLocal
from app.models import Event, FollowUp, Run, now
from test_workflow import get_lead, get_message, payload, submit


def test_failure_outside_extraction_is_not_blamed_on_the_model(admin, monkeypatch):
    def broken_draft(lead, rules, followup=False):
        raise RuntimeError("template rendering bug")

    monkeypatch.setattr(service, "draft_content", broken_draft)
    submit(admin)
    lead = get_lead()
    assert lead.status == "NEEDS_REVIEW" and not lead.processed
    with SessionLocal() as db:
        run = db.scalar(select(Run).where(Run.workflow == "intake", Run.status == "failed"))
        assert run.error_category == "draft"
        assert "AI extraction" not in run.error
        kinds = set(db.scalars(select(Event.kind).where(Event.lead_id == lead.id)).all())
        assert "processing_failed" in kinds and "ai_extraction_failed" not in kinds


def test_extraction_failure_still_reports_the_extraction_stage(admin, monkeypatch):
    from app import providers

    class BadProvider:
        def extract(self, lead):
            raise RuntimeError("provider unreachable")

    monkeypatch.setattr(providers, "extractor", lambda name: BadProvider())
    submit(admin)
    with SessionLocal() as db:
        run = db.scalar(select(Run).where(Run.workflow == "intake", Run.status == "failed"))
        assert run.error_category == "ai"
        kinds = set(db.scalars(select(Event.kind)).all())
        assert "ai_extraction_failed" in kinds


def test_swallowed_exceptions_are_logged_with_a_stack(admin, monkeypatch, caplog):
    monkeypatch.setattr(config, "EMAIL_PROVIDER", "invalid")
    submit(admin)
    msg = get_message()
    admin.post(f"/admin/messages/{msg.id}/approve")
    with caplog.at_level(logging.ERROR, logger="clientflow.service"):
        assert admin.post(f"/admin/messages/{msg.id}/send").json()["state"] == "failed"
    records = [r for r in caplog.records if r.message == "email delivery failed"]
    assert records and records[0].exc_info is not None
    assert records[0].context["message_id"] == msg.id


def test_log_output_redacts_sensitive_keys_and_secret_values(monkeypatch):
    monkeypatch.setenv("HUBSPOT_TOKEN", "pat-live-0123456789abcdef")
    formatter = observability.JsonFormatter()
    record = logging.LogRecord("t", logging.ERROR, __file__, 1, "provider rejected pat-live-0123456789abcdef", None, None)
    record.context = {"lead_id": "lead-1", "email": "someone@example.com", "token": "pat-live-0123456789abcdef"}
    line = formatter.format(record)
    assert "lead-1" in line
    assert "someone@example.com" not in line
    assert "pat-live-0123456789abcdef" not in line
    assert "[redacted]" in line


def test_responses_carry_a_correlation_id_header(client):
    supplied = str(uuid.uuid4())
    result = client.post(
        "/public/intake",
        json=payload(),
        headers={"Idempotency-Key": str(uuid.uuid4()), "X-Correlation-ID": supplied},
    )
    assert result.status_code == 201
    assert result.headers["x-correlation-id"] == supplied


def test_one_unprocessable_followup_does_not_stop_the_tick(admin, monkeypatch):
    submit(admin)
    msg = get_message()
    admin.post(f"/admin/messages/{msg.id}/approve")
    admin.post(f"/admin/messages/{msg.id}/send")
    with SessionLocal() as db:
        rows = db.scalars(select(FollowUp).order_by(FollowUp.position)).all()
        assert len(rows) == 2
        for row in rows:
            row.scheduled_at = now()
        db.commit()
        first_id, second_id = rows[0].id, rows[1].id

    real = service.prepare_followup
    calls = []

    def flaky(db, followup_id):
        calls.append(followup_id)
        if followup_id == first_id:
            raise RuntimeError("row is unprocessable")
        return real(db, followup_id)

    monkeypatch.setattr(service, "prepare_followup", flaky)
    with SessionLocal() as db:
        prepared = service.due_followups(db)
    # Ordered by position, so this also pins the processing order that PostgreSQL
    # previously left arbitrary. The tick reached the second row despite the
    # first raising; the second prepares nothing because position 2 waits for
    # position 1 to be delivered.
    assert calls == [first_id, second_id]
    assert prepared == 0
