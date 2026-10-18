import os
import uuid
from datetime import datetime
from fastapi import FastAPI, Depends, Request, Response, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from . import config, service, security
from .observability import RequestContext, configure_logging, get_logger, log, log_exception
from .db import get_db
from .models import Lead, Event, Message, FollowUp, Opportunity, Run, Setting, now
from .schemas import Intake, SettingsBody, STATUSES

configure_logging()
logger = get_logger("clientflow.api")

app = FastAPI(
    title="ClientFlow AI",
    version="1.0.0",
    description="Single-organization lead automation. Public intake, administrator and shared-secret automation boundaries.",
)

# Outermost middleware, so a correlation id is bound before anything else runs
# and every log line from a request carries it.
app.add_middleware(RequestContext)


@app.middleware("http")
async def guard(request, call_next):
    try:
        length = int(request.headers.get("content-length", "0") or "0")
    except ValueError:
        return JSONResponse({"detail": "Invalid content length"}, status_code=400)
    if length > 20000:
        return JSONResponse({"detail": "Payload too large"}, status_code=413)
    # Also enforce on streamed/chunked payloads.
    if request.method in ["POST", "PATCH", "PUT"]:
        chunks, total = [], 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > 20000:
                return JSONResponse({"detail": "Payload too large"}, status_code=413)
            chunks.append(chunk)
        request._body = b"".join(chunks)  # Starlette cached-body replay for downstream validation.
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Do not echo submitted input, credentials or Pydantic exception contexts.
    return JSONResponse({"detail": [{"field": ".".join(map(str, x["loc"])), "message": x["msg"]} for x in exc.errors()]}, status_code=422)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(max_length=300)


@app.post("/auth/login")
def login(body: Login, request: Request, response: Response):
    security.rate_limit("login:" + request.client.host, 10, 900)
    if request.headers.get("origin") != config.PUBLIC_ORIGIN:
        raise HTTPException(403, "Origin verification failed")
    if not security.check_password(body.password):
        raise HTTPException(401, "Invalid password")
    token = security.session_value()
    response.set_cookie("cf_session", token, httponly=True, secure=config.COOKIE_SECURE, samesite="strict", max_age=28800, path="/")
    return {"csrf": security.serializer().loads(token)["csrf"]}


@app.get("/auth/session")
def session(user=Depends(security.admin)):
    return {"actor": user["actor"], "csrf": user["csrf"]}


@app.post("/auth/logout")
def logout(response: Response, user=Depends(security.admin)):
    response.delete_cookie("cf_session", path="/")
    return {"ok": True}


@app.get("/public/config")
def public_config(db: Session = Depends(get_db)):
    return {
        "services": list(dict.fromkeys(service.settings(db)["supported_services"] + ["Other"])),
        "budgets": ["unspecified", "under-500", "500-2000", "2000-5000", "5000-plus"],
    }


@app.post("/public/intake", status_code=201)
def intake(body: Intake, request: Request, db: Session = Depends(get_db)):
    security.rate_limit("intake:" + request.client.host, 60, 3600)
    security.rate_limit("email:" + str(body.email).lower(), 10, 3600)
    if body.honeypot:
        raise HTTPException(422, "Submission could not be accepted")
    if body.service not in service.settings(db)["supported_services"] + ["Other"]:
        raise HTTPException(422, "Choose a configured service")
    if body.contact_method == "phone" and not body.phone:
        raise HTTPException(422, "Phone is required for phone contact")
    key = request.headers.get("idempotency-key", "")
    if not 8 <= len(key) <= 100:
        raise HTTPException(400, "Provide an Idempotency-Key between 8 and 100 characters")
    try:
        correlation = str(uuid.UUID(request.headers.get("x-correlation-id", str(uuid.uuid4()))))
    except ValueError:
        raise HTTPException(400, "Invalid correlation ID") from None
    try:
        lead, duplicate = service.ingest(db, body, key, correlation)
    except IntegrityError:
        db.rollback()
        lead, duplicate = service.ingest(db, body, key, correlation)
    if not duplicate and config.ORCHESTRATION_MODE == "app":
        service.process(db, lead.id)
    # Uniform receipt avoids exposing someone else's lead identifier or duplicate state.
    return {"received": True, "correlation_id": correlation, "message": "Your enquiry was received. We will review it and respond."}


def serialize(row):
    if row is None:
        return None
    result = {}
    for column in row.__table__.columns:
        if column.name in ["fingerprint", "payload_hash"]:
            continue
        value = getattr(row, column.name)
        result[column.name] = value.isoformat() if isinstance(value, datetime) else value
    return result


@app.get("/admin/leads", dependencies=[Depends(security.admin)])
def leads(db: Session = Depends(get_db)):
    rows = db.scalars(select(Lead).order_by(Lead.created_at.desc()).limit(1000)).all()
    return [serialize(lead) for lead in rows]


@app.get("/admin/leads/{lead_id}", dependencies=[Depends(security.admin)])
def detail(lead_id: str, db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return {
        "lead": serialize(lead),
        "events": [serialize(x) for x in db.scalars(select(Event).where(Event.lead_id == lead_id).order_by(Event.created_at))],
        "messages": [serialize(x) for x in db.scalars(select(Message).where(Message.lead_id == lead_id).order_by(Message.created_at))],
        "followups": [serialize(x) for x in db.scalars(select(FollowUp).where(FollowUp.lead_id == lead_id).order_by(FollowUp.position))],
        "crm": serialize(db.scalar(select(Opportunity).where(Opportunity.lead_id == lead_id))),
    }


@app.get("/admin/overview", dependencies=[Depends(security.admin)])
def overview(db: Session = Depends(get_db)):
    rows = db.scalars(select(Lead)).all()
    runs = db.scalars(select(Run)).all()
    completed = [r for r in runs if r.completed_at]
    durations = [(service.aware(r.completed_at) - service.aware(r.started_at)).total_seconds() for r in completed]
    return {
        "total": len(rows),
        "new": sum(x.status == "NEW" for x in rows),
        "qualified": sum(x.category == "high" for x in rows),
        "review": sum(x.status == "NEEDS_REVIEW" for x in rows),
        "bookings": sum(x.status == "BOOKED" for x in rows),
        "conversion": round(sum(x.status == "WON" for x in rows) / max(1, len(rows)) * 100, 1),
        "failed_runs": sum(x.status == "failed" and x.retry_state != "resolved" for x in runs),
        "average_processing_seconds": round(sum(durations) / max(1, len(durations)), 2),
        "estimated_ai_cost": 0 if config.LLM_PROVIDER == "mock" else None,
        "approval_pending": len(db.scalars(select(Message).where(Message.approval == "pending", Message.state != "sent")).all()),
    }


class LeadUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str | None = None
    replied: bool | None = None
    opted_out: bool | None = None
    paused: bool | None = None
    owner: str | None = Field(default=None, max_length=100)


@app.patch("/admin/leads/{lead_id}", dependencies=[Depends(security.admin)])
def update_lead(lead_id: str, body: LeadUpdate, db: Session = Depends(get_db)):
    lead = service.locked_lead(db, lead_id)
    if body.status and body.status not in STATUSES:
        raise HTTPException(422, "Unsupported pipeline status")
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(lead, key, value)
    service.event(db, lead, "booking_recorded" if body.status == "BOOKED" else "status_changed", updates, "admin")
    service.cancel_followups(db, lead)
    db.commit()
    return serialize(lead)


@app.post("/admin/leads/{lead_id}/retry", dependencies=[Depends(security.admin)])
def retry_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = service.locked_lead(db, lead_id)
    service.event(db, lead, "manual_retry_requested", {}, "admin")
    db.commit()
    service.process(db, lead_id, "manual_retry")
    return {"ok": True}


@app.get("/admin/messages", dependencies=[Depends(security.admin)])
def messages(db: Session = Depends(get_db)):
    return [
        {**serialize(msg), "lead": serialize(db.get(Lead, msg.lead_id))}
        for msg in db.scalars(select(Message).where(Message.approval == "pending", Message.state != "sent").order_by(Message.created_at))
    ]


class EditMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=10, max_length=8000)
    subject: str = Field(min_length=1, max_length=200, pattern=r"^[^\r\n]+$")


@app.patch("/admin/messages/{message_id}", dependencies=[Depends(security.admin)])
def edit_message(message_id: str, body: EditMessage, db: Session = Depends(get_db)):
    ref = db.get(Message, message_id)
    if not ref:
        raise HTTPException(404, "Message not found")
    lead = service.locked_lead(db, ref.lead_id)
    msg = db.scalar(select(Message).where(Message.id == message_id).with_for_update().execution_options(populate_existing=True))
    if msg.state in ["sent", "unknown", "sending"]:
        raise HTTPException(409, "Cannot edit a delivered or uncertain message")
    msg.revisions = msg.revisions + [{"content": msg.content, "subject": msg.subject, "at": now().isoformat(), "actor": "admin"}]
    msg.content, msg.subject = body.content, body.subject
    msg.approval, msg.approved_by = "pending", None
    service.event(db, lead, "response_edited", {"message_id": msg.id, "revision": len(msg.revisions)}, "admin")
    db.commit()
    return serialize(msg)


@app.post("/admin/messages/{message_id}/{action}", dependencies=[Depends(security.admin)])
def message_action(message_id: str, action: str, db: Session = Depends(get_db)):
    ref = db.get(Message, message_id)
    if not ref:
        raise HTTPException(404, "Message not found")
    lead = service.locked_lead(db, ref.lead_id)
    msg = db.scalar(select(Message).where(Message.id == message_id).with_for_update().execution_options(populate_existing=True))
    if action == "send":
        return serialize(service.send(db, msg.id))
    if action not in ["approve", "reject"]:
        raise HTTPException(404, "Unknown action")
    if msg.state in ["sent", "sending", "unknown"]:
        raise HTTPException(409, "Delivery is final or requires reconciliation")
    if action == "approve" and service.stop_reason(lead):
        raise HTTPException(409, "Lead is not eligible for delivery")
    msg.approval = "approved" if action == "approve" else "rejected"
    msg.approved_by = "admin" if action == "approve" else None
    service.event(db, lead, "response_approved" if action == "approve" else "response_rejected", {"message_id": msg.id}, "admin")
    db.commit()
    return serialize(msg)


@app.get("/admin/runs", dependencies=[Depends(security.admin)])
def runs(db: Session = Depends(get_db)):
    return [serialize(x) for x in db.scalars(select(Run).order_by(Run.started_at.desc()).limit(1000))]


@app.post("/admin/runs/{run_id}/retry", dependencies=[Depends(security.admin)])
def retry_run(run_id: str, db: Session = Depends(get_db)):
    service.retry_run(db, run_id)
    return {"ok": True}


@app.get("/admin/settings", dependencies=[Depends(security.admin)])
def get_settings(db: Session = Depends(get_db)):
    return {
        "rules": service.settings(db),
        "providers": {
            "llm": config.LLM_PROVIDER,
            "crm": config.CRM_PROVIDER,
            "email": config.EMAIL_PROVIDER,
            "slack_configured": bool(os.getenv("SLACK_WEBHOOK_URL")),
            "orchestration": config.ORCHESTRATION_MODE,
        },
        "demo_defaults": True,
    }


@app.put("/admin/settings", dependencies=[Depends(security.admin)])
def put_settings(body: SettingsBody, db: Session = Depends(get_db)):
    if body.medium_threshold >= body.high_threshold:
        raise HTTPException(422, "Medium threshold must be below high threshold")
    row = db.get(Setting, "business")
    value = body.model_dump()
    if row:
        row.value = value
    else:
        db.add(Setting(key="business", value=value))
    # Global sensitive-action audit is attached to a dedicated settings audit table via settings history.
    audit = db.get(Setting, "audit")
    entry = {"kind": "settings_changed", "actor": "admin", "at": now().isoformat(), "safe_automation": body.safe_automation}
    if audit:
        audit.value = {"events": audit.value["events"] + [entry]}
    else:
        db.add(Setting(key="audit", value={"events": [entry]}))
    db.commit()
    return {"ok": True}


@app.post("/admin/followups/tick", dependencies=[Depends(security.admin)])
def admin_tick(db: Session = Depends(get_db)):
    return {"prepared": service.due_followups(db)}


@app.get("/automation/pending", dependencies=[Depends(security.automation)])
def pending(db: Session = Depends(get_db)):
    return {
        "leads": [
            {"id": x.id, "correlation_id": x.correlation_id} for x in db.scalars(select(Lead).where(Lead.processed.is_(False), Lead.status == "NEW").limit(50))
        ]
    }


@app.post("/automation/leads/{lead_id}/process", dependencies=[Depends(security.automation)])
def automation_process(lead_id: str, db: Session = Depends(get_db)):
    lead = service.process(db, lead_id, "n8n")
    return {"lead_id": lead.id, "status": lead.status}


@app.post("/automation/crm/tick", dependencies=[Depends(security.automation)])
def crm_tick(db: Session = Depends(get_db)):
    count = 0
    for lead_id in db.scalars(select(Opportunity.lead_id).where(Opportunity.state == "pending").limit(50)).all():
        service.sync_crm(db, service.locked_lead(db, lead_id), "n8n")
        db.commit()
        count += 1
    return {"processed": count}


@app.post("/automation/email/tick", dependencies=[Depends(security.automation)])
def email_tick(db: Session = Depends(get_db)):
    ids = db.scalars(select(Message.id).where(Message.approval == "approved", Message.state == "draft").limit(50)).all()
    count, skipped = 0, 0
    for message_id in ids:
        try:
            msg = service.send(db, message_id, "n8n")
            count += msg.state == "sent"
        except HTTPException as exc:
            # Expected when a stop condition or a concurrent send wins the race.
            db.rollback()
            skipped += 1
            log(logger, 20, "email tick skipped a message", message_id=message_id, status_code=exc.status_code)
    return {"sent": count, "skipped": skipped}


@app.post("/automation/followups/tick", dependencies=[Depends(security.automation)])
def followup_tick(db: Session = Depends(get_db)):
    return {"prepared": service.due_followups(db)}


@app.get("/automation/failures", dependencies=[Depends(security.automation)])
def failures(db: Session = Depends(get_db)):
    return {"runs": [serialize(x) for x in db.scalars(select(Run).where(Run.status == "failed", Run.retry_state == "available").limit(50))]}


@app.post("/automation/failures/notify", dependencies=[Depends(security.automation)])
def notify_failures(db: Session = Depends(get_db)):
    if not service.settings(db)["notifications_enabled"]:
        return {"notified": 0, "reason": "notifications disabled"}
    count = 0
    for run in db.scalars(select(Run).where(Run.status == "failed", Run.retry_state == "available").limit(50)):
        from .providers import slack_notify

        try:
            slack_notify(run.lead_id, 0, run.correlation_id)
            run.retry_state = "notified"
            count += 1
        except Exception:
            log_exception(logger, "failure notification could not be delivered", run_id=run.id, lead_id=run.lead_id)
            continue
    db.commit()
    return {"notified": count}


@app.get("/public/opt-out")
def opt_out_page(token: str):
    # GET does not mutate consent, avoiding automated link-scanner opt-outs.
    from html import escape
    from fastapi.responses import HTMLResponse

    return HTMLResponse(
        f'<html lang="en"><meta name="viewport" content="width=device-width"><title>Stop ClientFlow messages</title><body><h1>Stop project follow-ups</h1><form method="post"><input type="hidden" name="token" value="{escape(token, quote=True)}"><button>Confirm opt-out</button></form></body></html>'
    )


@app.post("/public/opt-out")
async def opt_out(request: Request, db: Session = Depends(get_db)):
    from urllib.parse import parse_qs
    from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

    token = parse_qs((await request.body()).decode()).get("token", [""])[0]
    try:
        lead_id = URLSafeTimedSerializer(config.SESSION_SECRET, salt="opt-out").loads(token, max_age=31536000)
    except (BadSignature, SignatureExpired):
        raise HTTPException(400, "Invalid or expired opt-out link") from None
    lead = service.locked_lead(db, lead_id)
    lead.opted_out = True
    service.event(db, lead, "status_changed", {"opted_out": True}, "prospect")
    service.cancel_followups(db, lead)
    db.commit()
    return PlainTextResponse("You have opted out. No further project follow-ups will be sent.")
