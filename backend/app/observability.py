"""Structured logging and request context.

Every log line is one JSON object on stdout so a container log collector can
parse it without a regex. Correlation and request identifiers travel in
context variables, which means service-layer code does not have to thread them
through every call signature.

Nothing here records enquiry text, names, email addresses, passwords, session
cookies or provider credentials. Log payloads carry identifiers and categories
only.
"""

import contextvars
import json
import logging
import os
import sys
import time
import uuid

correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")
request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

# Keys that must never reach a log line even if a caller passes them.
REDACTED = {"password", "token", "secret", "cookie", "authorization", "csrf", "enquiry", "email", "name", "phone", "content", "subject"}

# Environment variables whose values are scrubbed out of messages and stacks. A
# provider that echoes its own credential into an exception must not turn an
# operator log into a credential store.
SECRET_ENV = [
    "SESSION_SECRET",
    "AUTOMATION_SECRET",
    "ADMIN_PASSWORD_HASH",
    "POSTGRES_PASSWORD",
    "DATABASE_URL",
    "HUBSPOT_TOKEN",
    "SMTP_PASSWORD",
    "SMTP_USER",
    "SLACK_WEBHOOK_URL",
]


def secret_values():
    """Current secret values worth scrubbing, longest first so subsets do not win."""
    found = {os.getenv(name, "") for name in SECRET_ENV}
    return sorted((value for value in found if len(value) >= 8), key=len, reverse=True)


def scrub(text):
    for value in secret_values():
        if value in text:
            text = text.replace(value, "[redacted]")
    return text


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if correlation_id.get():
            payload["correlation_id"] = correlation_id.get()
        if request_id.get():
            payload["request_id"] = request_id.get()
        extra = getattr(record, "context", None)
        if extra:
            payload.update({k: v for k, v in extra.items() if k not in REDACTED})
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
            payload["stack"] = self.formatException(record.exc_info)
        return scrub(json.dumps(payload, default=str))


def configure_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    # Replace any handler installed by a previous call or by uvicorn's default config.
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)
    for name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        uv = logging.getLogger(name)
        uv.handlers = []
        uv.propagate = True


def get_logger(name):
    return logging.getLogger(name)


def log(logger, level, message, **context):
    logger.log(level, message, extra={"context": context})


def log_exception(logger, message, **context):
    """Record a caught exception with its stack, so `except Exception` is never silent."""
    logger.exception(message, extra={"context": context})


class RequestContext:
    """ASGI middleware binding a correlation and request id to each request."""

    def __init__(self, app):
        self.app = app
        self.logger = get_logger("clientflow.request")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        incoming = headers.get("x-correlation-id", "")
        try:
            correlation = str(uuid.UUID(incoming)) if incoming else str(uuid.uuid4())
        except ValueError:
            correlation = str(uuid.uuid4())
        correlation_token = correlation_id.set(correlation)
        request_token = request_id.set(str(uuid.uuid4()))
        started = time.monotonic()
        status_holder = {"status": 500}

        async def send_wrapper(event):
            if event["type"] == "http.response.start":
                status_holder["status"] = event["status"]
                event.setdefault("headers", [])
                event["headers"] = list(event["headers"]) + [(b"x-correlation-id", correlation.encode("latin-1"))]
            await send(event)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            log_exception(self.logger, "request failed", path=scope.get("path"), method=scope.get("method"))
            raise
        finally:
            log(
                self.logger,
                logging.INFO,
                "request completed",
                method=scope.get("method"),
                path=scope.get("path"),
                status=status_holder["status"],
                duration_ms=round((time.monotonic() - started) * 1000, 2),
            )
            correlation_id.reset(correlation_token)
            request_id.reset(request_token)
