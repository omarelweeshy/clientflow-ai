import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, JSON, Integer, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), index=True)
    phone: Mapped[str] = mapped_column(String(40), default="")
    company: Mapped[str] = mapped_column(String(160), default="")
    website: Mapped[str] = mapped_column(String(500), default="")
    source: Mapped[str] = mapped_column(String(50), default="portfolio")
    service: Mapped[str] = mapped_column(String(80))
    enquiry: Mapped[str] = mapped_column(Text)
    budget: Mapped[str] = mapped_column(String(40))
    deadline: Mapped[str] = mapped_column(String(40), default="")
    contact_method: Mapped[str] = mapped_column(String(20), default="email")
    country: Mapped[str] = mapped_column(String(80), default="")
    urgency: Mapped[str] = mapped_column(String(20), default="unspecified")
    consent: Mapped[bool] = mapped_column(Boolean, default=True)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    replied: Mapped[bool] = mapped_column(Boolean, default=False)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    owner: Mapped[str] = mapped_column(String(100), default="Omar")
    status: Mapped[str] = mapped_column(String(30), default="NEW", index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(30), default="manual review")
    requirements: Mapped[dict] = mapped_column(JSON, default=dict)
    scoring: Mapped[list] = mapped_column(JSON, default=list)
    missing: Mapped[list] = mapped_column(JSON, default=list)
    review_reasons: Mapped[list] = mapped_column(JSON, default=list)
    probable_duplicate: Mapped[str | None] = mapped_column(String(36), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    correlation_id: Mapped[str] = mapped_column(String(36))
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class IntakeKey(Base):
    __tablename__ = "intake_keys"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"))


class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    kind: Mapped[str] = mapped_column(String(80))
    actor: Mapped[str] = mapped_column(String(80), default="system")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("lead_id", "kind"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="initial")
    subject: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    approval: Mapped[str] = mapped_column(String(20), default="pending")
    approved_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="draft")
    provider_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider: Mapped[str] = mapped_column(String(30), default="template")
    prompt_version: Mapped[str] = mapped_column(String(30), default="response-v1")
    revisions: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    # Set when a send intent is made durable, so a process that dies mid-delivery
    # leaves a timestamp the reaper can age out instead of a message stuck forever.
    sending_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reconciled_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), unique=True)
    state: Mapped[str] = mapped_column(String(20), default="pending")
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)


class FollowUp(Base):
    __tablename__ = "followups"
    __table_args__ = (UniqueConstraint("lead_id", "position"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(30), default="scheduled")
    stop_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    workflow: Mapped[str] = mapped_column(String(60))
    trigger: Mapped[str] = mapped_column(String(30), default="intake")
    correlation_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), default="running")
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    sanitized_input: Mapped[dict] = mapped_column(JSON, default=dict)
    sanitized_output: Mapped[dict] = mapped_column(JSON, default=dict)
    error_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    retry_state: Mapped[str] = mapped_column(String(20), default="none")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Delivery(Base):
    __tablename__ = "deliveries"
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class AuditEntry(Base):
    """Append-only record of sensitive administrative actions.

    Replaces a single settings row that was rewritten in full on every change,
    which grew without bound and lost entries when two writers overlapped.
    """

    __tablename__ = "audit_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(80))
    actor: Mapped[str] = mapped_column(String(80), default="admin")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    hits: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
