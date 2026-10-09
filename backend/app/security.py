import hashlib
import hmac
import secrets
from datetime import timedelta
from fastapi import HTTPException, Request
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from . import config
from .db import SessionLocal
from .models import RateBucket, now


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def check_password(password):
    try:
        _, salt, _ = config.ADMIN_PASSWORD_HASH.split("$")
        return hmac.compare_digest(hash_password(password, salt), config.ADMIN_PASSWORD_HASH)
    except ValueError:
        return False


def serializer():
    if len(config.SESSION_SECRET) < 32:
        raise HTTPException(503, "Configure a strong SESSION_SECRET")
    return URLSafeTimedSerializer(config.SESSION_SECRET, salt="clientflow-session-v1")


def session_value():
    return serializer().dumps({"actor": "admin", "csrf": secrets.token_urlsafe(32)})


def admin(request: Request):
    try:
        data = serializer().loads(request.cookies.get("cf_session", ""), max_age=28800)
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Sign in to continue") from None
    if request.method not in ["GET", "HEAD", "OPTIONS"]:
        if request.headers.get("origin") != config.PUBLIC_ORIGIN or not hmac.compare_digest(request.headers.get("x-csrf-token", ""), data["csrf"]):
            raise HTTPException(403, "CSRF verification failed")
    return data


def automation(request: Request):
    expected = config.AUTOMATION_SECRET
    if len(expected) < 32 or not hmac.compare_digest(request.headers.get("authorization", ""), f"Bearer {expected}"):
        raise HTTPException(401, "Invalid automation credential")


def rate_limit(key, limit, window=60):
    # Durable atomic UPDATE; no process-local counters. Keys are hashes, not raw IPs/emails.
    key = hashlib.sha256(key.encode()).hexdigest()
    with SessionLocal() as db:
        instant = now()
        db.execute(
            update(RateBucket).where(RateBucket.key == key, RateBucket.expires_at <= instant).values(hits=0, expires_at=instant + timedelta(seconds=window))
        )
        result = db.execute(update(RateBucket).where(RateBucket.key == key, RateBucket.hits < limit).values(hits=RateBucket.hits + 1))
        if result.rowcount:
            db.commit()
            return
        if db.get(RateBucket, key):
            raise HTTPException(429, "Too many requests. Try again later.", headers={"Retry-After": str(window)})
        try:
            db.add(RateBucket(key=key, hits=1, expires_at=instant + timedelta(seconds=window)))
            db.commit()
        except IntegrityError:
            db.rollback()
            result = db.execute(update(RateBucket).where(RateBucket.key == key, RateBucket.hits < limit).values(hits=RateBucket.hits + 1))
            db.commit()
            if not result.rowcount:
                raise HTTPException(429, "Too many requests. Try again later.") from None
