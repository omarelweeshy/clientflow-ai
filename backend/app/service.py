import hashlib
import json
import re
from datetime import timedelta, timezone
from sqlalchemy import select
from fastapi import HTTPException
from . import config, providers
from .observability import get_logger, log_exception
from .models import Lead, IntakeKey, Event, Message, Opportunity, FollowUp, Run, Setting, Delivery, now, uid
from .schemas import SettingsBody, Extraction

logger = get_logger("clientflow.service")

# Stage -> (operator-safe run error, error category). The recorded cause must
# describe the step that actually failed, not the first step that was attempted.
STAGE_FAILURES = {
    "extraction": ("AI extraction failed or returned invalid structured output.", "ai"),
    "qualification": ("Qualification could not be calculated. Inspect the extracted requirements.", "qualification"),
    "crm_sync": ("CRM synchronization step failed before completion.", "crm"),
    "response_draft": ("Response draft could not be prepared.", "draft"),
    "notification": ("Notification failed. Check Slack configuration.", "notification"),
    "delivery": ("Automated delivery failed after approval. Inspect the message.", "email"),
    "persist": ("Processing could not be saved. Retry the lead.", "database"),
}


def settings(db):
    row = db.get(Setting, "business")
    return SettingsBody.model_validate(row.value if row else {}).model_dump()


def event(db, lead, kind, detail=None, actor="system"):
    db.add(Event(lead_id=lead.id, kind=kind, detail=detail or {}, actor=actor))


def locked_lead(db, lead_id):
    lead = db.scalar(select(Lead).where(Lead.id == lead_id).with_for_update().execution_options(populate_existing=True))
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead


def make_run(db, lead, workflow, trigger="intake"):
    previous = db.scalars(select(Run).where(Run.lead_id == lead.id, Run.workflow == workflow)).all()
    run = Run(
        id=uid(),
        lead_id=lead.id,
        workflow=workflow,
        trigger=trigger,
        correlation_id=lead.correlation_id,
        attempts=len(previous) + 1,
        sanitized_input={"lead_id": lead.id},
    )
    db.add(run)
    db.flush()
    return run


def finish(run, error=None, category=None):
    run.status = "failed" if error else "success"
    run.completed_at = now()
    run.error = error
    run.error_category = category
    run.retry_state = "available" if error else "none"
    run.sanitized_output = {"completed": not bool(error)}


def resolve_previous(db, run):
    previous = db.scalars(select(Run).where(Run.lead_id == run.lead_id, Run.workflow == run.workflow, Run.status == "failed")).all()
    for old in previous:
        old.retry_state = "resolved"


def ingest(db, payload, key, correlation_id):
    data = payload.model_dump(exclude={"honeypot"})
    data["email"] = str(data["email"]).lower()
    data["name"] = " ".join(data["name"].split())
    data["company"] = " ".join(data["company"].split())
    data["phone"] = re.sub(r"[^\d+]", "", data["phone"])
    data["website"] = data["website"].rstrip("/")
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    existing_key = db.get(IntakeKey, key)
    if existing_key:
        if existing_key.payload_hash != digest:
            raise HTTPException(409, "Idempotency key was already used for a different request")
        return db.get(Lead, existing_key.lead_id), True
    fingerprint = hashlib.sha256((data["email"] + "|" + re.sub(r"\s+", " ", data["enquiry"].lower()) + "|" + data["service"]).encode()).hexdigest()
    duplicate = db.scalar(select(Lead).where(Lead.fingerprint == fingerprint).with_for_update())
    if duplicate:
        db.add(IntakeKey(key=key, payload_hash=digest, lead_id=duplicate.id))
        event(db, duplicate, "duplicate_detected", {"match": "exact", "correlation_id": correlation_id})
        db.commit()
        return duplicate, True
    candidates = [Lead.email == data["email"]]
    if data["phone"]:
        candidates.append(Lead.phone == data["phone"])
    if data["website"] and data["company"]:
        candidates.append((Lead.website == data["website"]) & (Lead.company == data["company"]))
    from sqlalchemy import or_

    probable = db.scalar(select(Lead).where(or_(*candidates)).order_by(Lead.created_at.desc())) if settings(db)["probable_duplicates"] else None
    lead = Lead(id=uid(), **data, fingerprint=fingerprint, correlation_id=correlation_id, probable_duplicate=probable.id if probable else None)
    db.add(lead)
    db.flush()
    db.add(IntakeKey(key=key, payload_hash=digest, lead_id=lead.id))
    event(db, lead, "lead_received", {"source": lead.source, "correlation_id": correlation_id})
    event(db, lead, "validation_completed", {"result": "valid"})
    if probable:
        event(db, lead, "duplicate_detected", {"match": "probable", "lead_id": probable.id})
    db.commit()  # Original enquiry survives every downstream failure.
    return lead, False


def qualify(lead, rules):
    spam = any(x in lead.enquiry.lower() for x in ["buy followers", "crypto giveaway", "guaranteed profit", "click here to win"])
    factors = [
        ("Budget fit", rules["budget_weight"], {"unspecified": 0, "under-500": 0.1, "500-2000": 0.6, "2000-5000": 1, "5000-plus": 1}[lead.budget], lead.budget),
        ("Requested service", rules["service_weight"], int(lead.service in rules["supported_services"]), lead.service),
        ("Completeness", rules["completeness_weight"], max(0, 1 - len(lead.missing) / 3), f"{len(lead.missing)} missing fields"),
        ("Timeline", rules["timeline_weight"], 0.5 if lead.urgency == "urgent" else int(bool(lead.deadline)), lead.deadline or "Unspecified"),
        ("Business context", rules["business_weight"], int(bool(lead.company)), lead.company or "Unspecified"),
        (
            "Geographic availability",
            rules["geography_weight"],
            int(not rules["allowed_countries"] or lead.country.lower() in [c.lower() for c in rules["allowed_countries"]]),
            lead.country or "Unspecified",
        ),
    ]
    total_weight = sum(w for _, w, _, _ in factors) or 1
    breakdown = [{"rule": name, "weight": weight, "points": round(weight * ratio, 1), "reason": reason} for name, weight, ratio, reason in factors]
    score = round(sum(x["points"] for x in breakdown) / total_weight * 100)
    if lead.budget == "under-500" and score > rules["low_budget_cap"]:
        breakdown.append(
            {
                "rule": "Low-budget cap",
                "weight": 0,
                "points": rules["low_budget_cap"] - score,
                "reason": f"Demonstration budget policy caps this category at {rules['low_budget_cap']}",
            }
        )
        score = rules["low_budget_cap"]
    if spam:
        score -= rules["spam_penalty"]
        breakdown.append({"rule": "Spam indicators", "weight": rules["spam_penalty"], "points": -rules["spam_penalty"], "reason": "Known solicitation phrase"})
    review = []
    if lead.service not in rules["supported_services"]:
        review.append("Requested service requires scope and availability review")
    if lead.probable_duplicate:
        review.append("Probable duplicate: inspect previous opportunity")
    if lead.urgency == "urgent" and rules["review_urgent"]:
        review.append("Urgent request: confirm availability manually")
    if lead.missing:
        review.append("Missing information requires clarification")
    if rules["allowed_countries"] and not lead.country:
        review.append("Geographic availability needs confirmation")
    score = max(0, min(100, score))
    category = "manual review" if review else "high" if score >= rules["high_threshold"] else "medium" if score >= rules["medium_threshold"] else "low"
    lead.score, lead.scoring, lead.category, lead.review_reasons = score, breakdown, category, review
    lead.status = "DISQUALIFIED" if spam else "NEEDS_REVIEW" if review else "QUALIFIED" if category == "high" else "NURTURE"


def sync_crm(db, lead, trigger="intake"):
    opp = db.scalar(select(Opportunity).where(Opportunity.lead_id == lead.id))
    if not opp:
        opp = Opportunity(lead_id=lead.id)
        db.add(opp)
        db.flush()
    if opp.state == "synced":
        return opp
    run = make_run(db, lead, "crm_sync", trigger)
    opp.attempts += 1
    try:
        if config.CRM_PROVIDER == "internal":
            opp.external_id = opp.id
        elif config.CRM_PROVIDER == "hubspot":
            opp.external_id = providers.hubspot_sync(lead)
        else:
            raise ValueError("Unknown CRM provider")
        opp.state, opp.error = "synced", None
        finish(run)
        resolve_previous(db, run)
        event(db, lead, "crm_synchronized", {"provider": config.CRM_PROVIDER})
    except Exception:
        log_exception(logger, "crm sync failed", lead_id=lead.id, provider=config.CRM_PROVIDER, run_id=run.id, trigger=trigger)
        opp.state, opp.error = "failed", "CRM provider request failed. Check configuration and retry."
        finish(run, opp.error, "crm")
        event(db, lead, "crm_failed", {"error": opp.error})
    return opp


def draft_content(lead, rules, followup=False):
    if followup:
        return f"Hello {lead.name},\n\nFollowing up on your {lead.service.lower()} enquiry. Are you still considering this project? If so, please share any scope updates.\n\nThere is no need to reply if this is no longer relevant. You can opt out through the link below.\n\nOmar"
    clarification = "\n".join(f"- Could you confirm your {field.lower()}?" for field in lead.missing)
    booking = f"\nIf useful, choose a discovery call here: {rules['booking_url']}" if lead.category == "high" and rules["booking_url"] else ""
    return f"Hello {lead.name},\n\nThank you for your enquiry about {lead.service.lower()}. You described:\n“{lead.enquiry[:650]}”\n\nSuggested next step: confirm the project scope and acceptance criteria before an estimate.\n{clarification}{booking}\n\nThis is a discovery response, not a quote or commitment to availability.\n\nOmar"


def process(db, lead_id, trigger="intake"):
    lead = locked_lead(db, lead_id)
    if lead.processed:
        return lead
    run = make_run(db, lead, "intake", trigger)
    lead.status = "PROCESSING"
    event(db, lead, "ai_extraction_attempted", {"provider": config.LLM_PROVIDER, "prompt_version": "extract-v1"})
    stage = "extraction"
    try:
        extraction = Extraction.model_validate(providers.extractor(config.LLM_PROVIDER).extract(lead).model_dump())
        # Deterministically enforce unknown budget/deadline/context even if a provider omits them.
        missing = list(dict.fromkeys(extraction.missing_information + providers.MockExtractor().extract(lead).missing_information))
        stage = "qualification"
        lead.requirements = extraction.model_dump()
        lead.missing, lead.urgency = missing, extraction.urgency
        qualify(lead, settings(db))
        event(db, lead, "ai_extraction_completed", {"provider": config.LLM_PROVIDER, "prompt_version": "extract-v1"})
        event(db, lead, "qualification_calculated", {"score": lead.score, "category": lead.category})
        stage = "crm_sync"
        sync_crm(db, lead, trigger)
        stage = "response_draft"
        message = db.scalar(select(Message).where(Message.lead_id == lead.id, Message.kind == "initial"))
        if not message:
            message = Message(lead_id=lead.id, subject=f"Your {lead.service} enquiry", content=draft_content(lead, settings(db)), provider="template")
            db.add(message)
            db.flush()
            event(db, lead, "response_generated", {"message_id": message.id, "prompt_version": message.prompt_version})
        lead.processed = True
        finish(run)
        resolve_previous(db, run)
        rules = settings(db)
        stage = "notification"
        if rules["notifications_enabled"] and lead.category == "high":
            notification = make_run(db, lead, "notification", trigger)
            try:
                providers.slack_notify(lead.id, lead.score, lead.correlation_id)
                finish(notification)
                resolve_previous(db, notification)
            except Exception:
                log_exception(logger, "slack notification failed", lead_id=lead.id, run_id=notification.id)
                finish(notification, "Notification failed. Check Slack configuration.", "notification")
        stage = "delivery"
        if rules["safe_automation"] and lead.category == "high" and lead.consent and not lead.opted_out:
            message.approval, message.approved_by = "approved", "safe-automation"
            event(db, lead, "response_approved", {"message_id": message.id}, "safe-automation")
            db.commit()
            send(db, message.id, "safe-automation")
        else:
            stage = "persist"
            db.commit()
    except Exception:
        # The stack reaches the operator log; the stored cause stays operator-safe
        # and names the stage that actually failed rather than always blaming extraction.
        log_exception(logger, "lead processing failed", lead_id=lead_id, stage=stage, trigger=trigger, provider=config.LLM_PROVIDER)
        error, category = STAGE_FAILURES.get(stage, ("Processing failed at an unexpected step.", "unknown"))
        db.rollback()
        lead = locked_lead(db, lead_id)
        lead.status, lead.processed = "NEEDS_REVIEW", False
        lead.review_reasons = [f"{error} Retry or inspect the original enquiry."]
        run = make_run(db, lead, "intake", trigger)
        finish(run, error, category)
        event(db, lead, "ai_extraction_attempted", {"provider": config.LLM_PROVIDER, "prompt_version": "extract-v1"})
        event(db, lead, "processing_failed" if stage != "extraction" else "ai_extraction_failed", {"error": error, "stage": stage})
        db.commit()
    return lead


def stop_reason(lead):
    if lead.opted_out or not lead.consent:
        return "opted_out"
    if lead.replied:
        return "replied"
    if lead.paused:
        return "paused"
    if lead.status in ["BOOKED", "WON", "LOST", "DISQUALIFIED"]:
        return lead.status.lower()
    return None


def cancel_followups(db, lead):
    reason = stop_reason(lead)
    if reason:
        for followup in db.scalars(select(FollowUp).where(FollowUp.lead_id == lead.id, FollowUp.state.in_(["scheduled", "pending_approval"]))):
            followup.state, followup.stop_reason = "cancelled", reason
            event(db, lead, "followup_cancelled", {"position": followup.position, "reason": reason})
        for msg in db.scalars(select(Message).where(Message.lead_id == lead.id, Message.kind != "initial", Message.state != "sent")):
            msg.approval = "rejected"


def send(db, message_id, actor="admin"):
    ref = db.get(Message, message_id)
    if not ref:
        raise HTTPException(404, "Message not found")
    lead = locked_lead(db, ref.lead_id)
    msg = db.scalar(select(Message).where(Message.id == message_id).with_for_update().execution_options(populate_existing=True))
    if msg.state == "sent":
        return msg
    if msg.state in ["unknown", "sending"]:
        raise HTTPException(409, "Delivery may have occurred. Reconcile with the provider before retrying.")
    if msg.approval != "approved":
        raise HTTPException(409, "Human approval is required before sending")
    if stop_reason(lead):
        raise HTTPException(409, "Delivery blocked: " + stop_reason(lead))
    run = make_run(db, lead, "email_delivery", actor)
    run.sanitized_input = {"lead_id": lead.id, "message_id": msg.id}
    try:
        if "\n\nStop project follow-ups: " not in msg.content:
            from itsdangerous import URLSafeTimedSerializer

            token = URLSafeTimedSerializer(config.SESSION_SECRET, salt="opt-out").dumps(lead.id)
            msg.content += f"\n\nStop project follow-ups: {config.PUBLIC_ORIGIN}/api/public/opt-out?token={token}"
        if config.EMAIL_PROVIDER == "mock":
            provider_id = "mock-" + msg.id
            db.add(Delivery(message_id=msg.id, provider_id=provider_id))
            db.flush()
        elif config.EMAIL_PROVIDER == "smtp":
            msg.state = "sending"
            db.commit()  # Durable send intent prevents blind retries after a crash.
            provider_id = providers.smtp_send(lead, msg)
        else:
            raise ValueError("Unknown email provider")
        msg.state, msg.error, msg.provider_id, msg.sent_at = "sent", None, provider_id, now()
        if msg.kind == "initial":
            lead.status = "CONTACTED"
            for position, days in enumerate(settings(db)["followup_days"], start=1):
                if not db.scalar(select(FollowUp).where(FollowUp.lead_id == lead.id, FollowUp.position == position)):
                    db.add(FollowUp(lead_id=lead.id, position=position, scheduled_at=now() + timedelta(days=days)))
                    event(db, lead, "followup_scheduled", {"position": position, "days": days})
        else:
            followup = db.scalar(select(FollowUp).where(FollowUp.lead_id == lead.id, FollowUp.position == int(msg.kind.split("_")[1])))
            followup.state, followup.error = "sent", None
        finish(run)
        resolve_previous(db, run)
        event(db, lead, "email_sent", {"message_id": msg.id, "provider": config.EMAIL_PROVIDER}, actor)
        db.commit()
    except Exception:
        log_exception(logger, "email delivery failed", lead_id=ref.lead_id, message_id=message_id, provider=config.EMAIL_PROVIDER, actor=actor)
        db.rollback()
        lead = locked_lead(db, ref.lead_id)
        msg = db.get(Message, message_id)
        msg.state = "unknown" if config.EMAIL_PROVIDER == "smtp" else "failed"
        msg.error = (
            "Delivery uncertain: reconcile with SMTP before retry." if msg.state == "unknown" else "Email delivery failed. Retry after checking configuration."
        )
        run = db.get(Run, run.id) or make_run(db, lead, "email_delivery", actor)
        run.sanitized_input = {"lead_id": lead.id, "message_id": msg.id}
        finish(run, msg.error, "email")
        event(db, lead, "email_failed", {"message_id": msg.id, "error": msg.error}, actor)
        db.commit()
    return msg


def due_followups(db, at=None):
    at = at or now()
    count = 0
    ids = db.scalars(select(FollowUp.id).where(FollowUp.scheduled_at <= at, FollowUp.state.in_(["scheduled", "pending_approval"]))).all()
    for followup_id in ids:
        try:
            count += prepare_followup(db, followup_id)
        except Exception:
            # One unprocessable row must not stop every later follow-up in the tick.
            log_exception(logger, "followup preparation failed", followup_id=followup_id)
            db.rollback()
    return count


def prepare_followup(db, followup_id):
    """Prepare one due follow-up. Returns 1 when a draft moved to pending approval."""
    ref = db.get(FollowUp, followup_id)
    lead = locked_lead(db, ref.lead_id)
    followup = db.scalar(select(FollowUp).where(FollowUp.id == followup_id).with_for_update().execution_options(populate_existing=True))
    prepared = 0
    if followup.state not in ["scheduled", "pending_approval"]:
        return 0
    if stop_reason(lead):
        cancel_followups(db, lead)
    elif followup.state == "scheduled":
        # Final follow-up is never prepared before the first is delivered.
        prior = db.scalar(select(FollowUp).where(FollowUp.lead_id == lead.id, FollowUp.position == followup.position - 1))
        if prior and prior.state != "sent":
            return 0
        run = make_run(db, lead, "followup", "scheduled_tick")
        followup.attempts += 1
        kind = f"followup_{followup.position}"
        if not db.scalar(select(Message).where(Message.lead_id == lead.id, Message.kind == kind)):
            db.add(Message(lead_id=lead.id, kind=kind, subject=f"Following up: {lead.service}", content=draft_content(lead, settings(db), True)))
            event(db, lead, "response_generated", {"type": kind})
        followup.state = "pending_approval"
        finish(run)
        prepared = 1
    db.commit()
    return prepared


def retry_run(db, run_id):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status != "failed" or run.retry_state == "resolved":
        raise HTTPException(409, "This run does not need a retry")
    lead = locked_lead(db, run.lead_id)
    event(db, lead, "manual_retry_requested", {"run_id": run.id, "workflow": run.workflow}, "admin")
    if run.workflow == "intake":
        db.commit()
        process(db, lead.id, "manual_retry")
    elif run.workflow == "crm_sync":
        sync_crm(db, lead, "manual_retry")
        db.commit()
    elif run.workflow == "email_delivery":
        msg_id = run.sanitized_input.get("message_id") or next(
            (
                e.detail.get("message_id")
                for e in reversed(db.scalars(select(Event).where(Event.lead_id == lead.id, Event.kind == "email_failed").order_by(Event.created_at)).all())
            ),
            None,
        )
        db.commit()
        if not msg_id:
            raise HTTPException(409, "Inspect the message before retrying")
        send(db, msg_id, "manual_retry")
    elif run.workflow == "notification":
        new = make_run(db, lead, "notification", "manual_retry")
        try:
            providers.slack_notify(lead.id, lead.score, lead.correlation_id)
            finish(new)
            resolve_previous(db, new)
        except Exception:
            log_exception(logger, "slack notification retry failed", lead_id=lead.id, run_id=new.id)
            finish(new, "Notification failed. Check Slack configuration.", "notification")
        db.commit()
    return lead


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
