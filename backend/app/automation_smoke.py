"""Local MOCK-only n8n verification fixture. Never touches real prospects."""

import sys
from datetime import timedelta
from sqlalchemy import select, func
from . import config, service
from .db import SessionLocal
from .models import Lead, Message, FollowUp, Opportunity, Delivery, uid, now
from .schemas import Intake

if config.LLM_PROVIDER != "mock" or config.CRM_PROVIDER != "internal" or config.EMAIL_PROVIDER != "mock":
    raise SystemExit("Automation smoke requires mock/internal/mock providers")
action = sys.argv[1]
with SessionLocal() as db:
    lead = db.scalar(select(Lead).where(Lead.email == "n8n.verification@example.com"))
    if action == "prepare":
        if lead:
            raise SystemExit("Verification fixture already exists; inspect it instead of resetting delivery state.")
        lead, _ = service.ingest(
            db,
            Intake(
                name="n8n Verification Prospect",
                email="n8n.verification@example.com",
                company="Fictional Automation Lab",
                service="AI automation",
                enquiry="Connect project enquiries to an internal CRM and prepare responses for human approval.",
                budget="2000-5000",
                deadline="2026-12-15",
                consent=True,
                source="demo-validation",
            ),
            "n8n-smoke-intake-key",
            uid(),
        )
        assert lead.status == "NEW" and not lead.processed
        print("Prepared one stored pending MOCK fixture for n8n intake.")
    elif action == "approve":
        assert lead.processed
        assert db.scalar(select(Opportunity).where(Opportunity.lead_id == lead.id)).state == "synced"
        msg = db.scalar(select(Message).where(Message.lead_id == lead.id, Message.kind == "initial"))
        assert msg.approval == "pending" and msg.state == "draft"
        msg.approval, msg.approved_by = "approved", "demo_verifier"
        service.event(db, lead, "response_approved", {"message_id": msg.id}, "demo_verifier")
        db.commit()
        print("Verified non-empty intake and prepared an explicitly approved MOCK response.")
    elif action == "due":
        msg = db.scalar(select(Message).where(Message.lead_id == lead.id, Message.kind == "initial"))
        assert msg.state == "sent"
        assert db.scalar(select(func.count(Delivery.message_id)).where(Delivery.message_id == msg.id)) == 1
        followups = db.scalars(select(FollowUp).where(FollowUp.lead_id == lead.id)).all()
        assert len(followups) == 2
        for followup in followups:
            followup.scheduled_at = now() - timedelta(days=1)
        db.commit()
        print("Verified exactly one mock delivery and two schedules after repeated email execution; made follow-ups due.")
    elif action == "stop":
        msg = db.scalar(select(Message).where(Message.lead_id == lead.id, Message.kind == "followup_1"))
        assert msg and msg.approval == "pending" and msg.state == "draft"
        assert not db.scalar(select(Message).where(Message.lead_id == lead.id, Message.kind == "followup_2"))
        lead.replied = True
        service.event(db, lead, "status_changed", {"replied": True}, "demo_verifier")
        service.cancel_followups(db, lead)
        db.commit()
        print("Verified due follow-up requires approval and final step waits; recorded reply.")
    elif action == "verify":
        assert all(f.state == "cancelled" for f in db.scalars(select(FollowUp).where(FollowUp.lead_id == lead.id)))
        assert db.scalar(select(func.count(Message.id)).where(Message.lead_id == lead.id)) == 2
        print("PASS: n8n non-empty intake, approved delivery idempotency, due draft approval, ordering and reply-stop behavior.")
