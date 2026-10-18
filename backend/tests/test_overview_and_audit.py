"""Aggregates are computed in the database, and the audit log cannot lose entries."""

from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import func, select
from app import service
from app.db import SessionLocal, engine
from app.models import AuditEntry, Lead, Run
from app.schemas import SettingsBody
from test_workflow import submit


def test_overview_counts_match_the_stored_rows(admin):
    for index, (status, category) in enumerate([("NEW", "high"), ("NEEDS_REVIEW", "low"), ("BOOKED", "medium"), ("WON", "high")]):
        submit(admin, f"overview-{index}", email=f"lead{index}@example.com")
    with SessionLocal() as db:
        rows = db.scalars(select(Lead).order_by(Lead.created_at)).all()
        for row, (status, category) in zip(rows, [("NEW", "high"), ("NEEDS_REVIEW", "low"), ("BOOKED", "medium"), ("WON", "high")]):
            row.status, row.category = status, category
        db.commit()
    body = admin.get("/admin/overview").json()
    assert body["total"] == 4
    assert body["new"] == 1 and body["review"] == 1 and body["bookings"] == 1
    assert body["qualified"] == 2
    assert body["conversion"] == 25.0


def test_overview_reports_an_average_duration_from_sql(admin):
    submit(admin)
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Run.id)).where(Run.completed_at.is_not(None))) >= 1
        average = service.processing_duration_seconds(db)
    assert average >= 0
    assert admin.get("/admin/overview").json()["average_processing_seconds"] >= 0


def test_overview_on_an_empty_pipeline_does_not_divide_by_zero(admin):
    body = admin.get("/admin/overview").json()
    assert body["total"] == 0 and body["conversion"] == 0.0 and body["average_processing_seconds"] == 0.0


def test_settings_changes_append_audit_entries(admin):
    for flag in [True, False, True]:
        rules = SettingsBody(safe_automation=flag).model_dump()
        assert admin.put("/admin/settings", json=rules).status_code == 200
    entries = admin.get("/admin/audit").json()
    assert len(entries) == 3
    assert {entry["kind"] for entry in entries} == {"settings_changed"}
    assert [entry["detail"]["safe_automation"] for entry in entries] == [True, False, True]


def test_concurrent_settings_writes_keep_every_audit_entry(admin):
    if engine.dialect.name != "postgresql":
        import pytest

        pytest.skip("Concurrent write behaviour requires PostgreSQL")

    def change(flag):
        return admin.put("/admin/settings", json=SettingsBody(safe_automation=bool(flag % 2)).model_dump()).status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert all(code == 200 for code in pool.map(change, range(6)))
    with SessionLocal() as db:
        assert db.scalar(select(func.count(AuditEntry.id))) == 6


def test_audit_log_requires_authentication(client):
    assert client.get("/admin/audit").status_code == 401


def test_audit_entries_are_never_rewritten(admin):
    admin.put("/admin/settings", json=SettingsBody(safe_automation=True).model_dump())
    with SessionLocal() as db:
        first = db.scalar(select(AuditEntry))
        original = (first.id, first.detail, first.created_at)
    admin.put("/admin/settings", json=SettingsBody(safe_automation=False).model_dump())
    with SessionLocal() as db:
        kept = db.get(AuditEntry, original[0])
        assert (kept.id, kept.detail, kept.created_at) == original
        assert db.scalar(select(func.count(AuditEntry.id))) == 2
