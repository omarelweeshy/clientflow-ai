"""Idempotent fictional demo fixtures. Failures are labelled fixture events."""

from datetime import timedelta
from sqlalchemy import select
from .db import SessionLocal
from .models import Lead, Message, Opportunity, now, uid
from .schemas import Intake
from . import service, config

FIXTURES = [
    (
        "Nadia Farouk",
        "Atlas Studio",
        "AI automation",
        "2000-5000",
        "We need to automate enquiry triage and connect our forms to the studio CRM. We need a clear approval step and an audit trail.",
        "qualified",
    ),
    (
        "James Porter",
        "",
        "Custom internal tool",
        "unspecified",
        "I want an internal tool for organizing project requests. I am still exploring the scope and would appreciate guidance.",
        "incomplete",
    ),
    (
        "Maya Chen",
        "Fieldwork",
        "Workflow integration",
        "5000-plus",
        "Connect our support intake to our CRM and prepare a response for review. Our team processes fifty enquiries each week.",
        "duplicate",
    ),
    (
        "Alex Example",
        "Promo Example",
        "Other",
        "under-500",
        "Buy followers and get guaranteed profit. Click here to win a crypto giveaway with our promotional offer.",
        "spam",
    ),
    (
        "Youssef Salem",
        "Little Desk",
        "Dashboard development",
        "under-500",
        "We want a simple dashboard to track our project enquiries and decisions. Our budget is limited and scope is flexible.",
        "low",
    ),
    (
        "Sara Ibrahim",
        "Northline",
        "Document intelligence",
        "2000-5000",
        "Urgent: our team needs to search and summarize internal documents asap. We need citations and approval controls.",
        "urgent",
    ),
    (
        "Leo Martin",
        "Cedar Partners",
        "Document intelligence",
        "5000-plus",
        "We need a document search pilot for internal procedures with access controls and a clear citation trail.",
        "ai_failure",
    ),
    (
        "Amira Hassan",
        "Common Ground",
        "Workflow integration",
        "2000-5000",
        "Sync validated website enquiries to our CRM, de-duplicate contacts and prepare personalized replies for approval.",
        "crm_failure",
    ),
    (
        "Daniel Reed",
        "Paperplane",
        "AI automation",
        "2000-5000",
        "Our agency wants an enquiry qualification pipeline with structured extraction and a review queue before email.",
        "email_failure",
    ),
    (
        "Lina Mansour",
        "Studio Nine",
        "Custom internal tool",
        "5000-plus",
        "Build a small project operations tool for our consulting team. We need an overview and a complete enquiry timeline.",
        "replied",
    ),
    (
        "Oliver Brooks",
        "Evergreen",
        "Dashboard development",
        "2000-5000",
        "We need a control dashboard for incoming service requests, workflow failures, approvals and team follow-ups.",
        "booked",
    ),
    (
        "Hana Ali",
        "Bridge Lab",
        "AI automation",
        "5000-plus",
        "We are exploring a workflow automation pilot for our research office with human approval and transparent logs.",
        "opted_out",
    ),
]


def seed():
    if config.LLM_PROVIDER != "mock" or config.CRM_PROVIDER != "internal" or config.EMAIL_PROVIDER != "mock":
        raise SystemExit("Seeding requires mock/internal/mock adapters; never send fictional fixtures through real providers.")
    with SessionLocal() as db:
        for index, (name, company, service_name, budget, enquiry, scenario) in enumerate(FIXTURES):
            email = f"demo.{scenario}@example.com"
            if db.scalar(select(Lead).where(Lead.email == email)):
                continue
            payload = Intake(
                name=name,
                email=email,
                company=company,
                service=service_name,
                budget=budget,
                enquiry=enquiry,
                deadline="" if scenario == "incomplete" else "2026-12-15",
                consent=True,
                source="demo",
            )
            lead, _ = service.ingest(db, payload, f"demo-seed-{scenario}", uid())
            service.process(db, lead.id, "demo_seed")
            lead.created_at = now() - timedelta(hours=index * 3)
            service.event(db, lead, "demo_fixture", {"scenario": scenario, "simulated": scenario.endswith("failure")})
            if scenario == "duplicate":
                service.ingest(db, payload, "demo-seed-duplicate-redelivery", uid())
            if scenario == "ai_failure":
                lead.status, lead.processed = "NEEDS_REVIEW", False
                lead.requirements, lead.scoring, lead.score = {}, [], 0
                lead.category = "manual review"
                lead.review_reasons = ["Simulated AI provider timeout. Retry processing to recover."]
                for msg in db.scalars(select(Message).where(Message.lead_id == lead.id)):
                    db.delete(msg)
                run = service.make_run(db, lead, "intake", "demo_fixture")
                service.finish(run, "Simulated AI timeout. Original enquiry preserved.", "ai")
                service.event(db, lead, "ai_extraction_failed", {"error": run.error, "simulated": True})
            if scenario == "crm_failure":
                opp = db.scalar(select(Opportunity).where(Opportunity.lead_id == lead.id))
                opp.state, opp.error = "failed", "Simulated CRM outage. Retry to recover."
                run = service.make_run(db, lead, "crm_sync", "demo_fixture")
                service.finish(run, opp.error, "crm")
                service.event(db, lead, "crm_failed", {"error": opp.error, "simulated": True})
            if scenario in ["email_failure", "replied", "booked", "opted_out"]:
                msg = db.scalar(select(Message).where(Message.lead_id == lead.id))
                msg.approval, msg.approved_by = "approved", "demo_seed"
                if scenario == "email_failure":
                    msg.state, msg.error = "failed", "Simulated delivery failure. Retry to recover."
                    run = service.make_run(db, lead, "email_delivery", "demo_fixture")
                    service.finish(run, msg.error, "email")
                    service.event(db, lead, "email_failed", {"message_id": msg.id, "error": msg.error, "simulated": True})
                else:
                    db.commit()
                    service.send(db, msg.id, "demo_seed")
                    if scenario == "replied":
                        lead.replied = True
                    elif scenario == "booked":
                        lead.status = "BOOKED"
                    else:
                        lead.opted_out = True
                    service.event(db, lead, "booking_recorded" if scenario == "booked" else "status_changed", {"scenario": scenario}, "demo_seed")
                    service.cancel_followups(db, lead)
            db.commit()
        print("Demo fixtures ready (12 fictional leads; duplicate delivery creates no extra lead).")


if __name__ == "__main__":
    seed()
