import hashlib
import hmac
import ipaddress
import logging
import secrets
from datetime import timedelta
from fastapi import HTTPException, Request
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from . import config
from .db import SessionLocal
from .models import RateBucket, now
from .observability import get_logger, log

logger = get_logger("clientflow.security")


def trusted_networks():
    networks = []
    for entry in config.TRUSTED_PROXY_CIDRS:
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            log(logger, logging.WARNING, "ignoring malformed trusted proxy CIDR", entry=entry)
    return networks


def client_ip(request: Request):
    """Return (address, trusted).

    `trusted` is True only when a configured proxy network supplied the address.
    Behind an ingress that does not set the client-IP header, every request
    shares one socket peer, so an address keyed bucket would be global. Callers
    must not apply a strict per-client limit on an untrusted address.
    """
    peer = request.client.host if request.client else ""
    networks = trusted_networks()
    if not networks:
        return peer, False
    try:
        if not any(ipaddress.ip_address(peer) in network for network in networks):
            return peer, False
    except ValueError:
        return peer, False
    forwarded = request.headers.get(config.CLIENT_IP_HEADER, "")
    if not forwarded:
        return peer, False
    # Right-most entry is the one appended by the single trusted hop. Anything
    # further left was supplied by the caller and is not evidence.
    candidate = forwarded.split(",")[-1].strip()
    try:
        return str(ipaddress.ip_address(candidate)), True
    except ValueError:
        log(logger, logging.WARNING, "trusted proxy supplied an unparseable client address")
        return peer, False


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


def limit_client(request, action, per_client, backstop, window):
    """Rate limit one action.

    A strict bucket is applied per client address when that address can be
    trusted. A generous global backstop always applies, so a deployment without
    a trusted proxy still has a ceiling without one caller being able to lock
    everyone else out.
    """
    address, trusted = client_ip(request)
    if trusted:
        rate_limit(f"{action}:ip:{address}", per_client, window)
    rate_limit(f"{action}:all", backstop, window)


def prune_buckets(db, at=None):
    """Delete long-expired buckets so the table does not grow without bound."""
    cutoff = (at or now()) - timedelta(days=1)
    return db.execute(delete(RateBucket).where(RateBucket.expires_at <= cutoff)).rowcount


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
        # No row matched: either the bucket does not exist yet, or it is at its
        # limit. Do not decide by looking for the row. Concurrent first requests
        # race here, and the losers would find the bucket the winner just
        # inserted and reject a request whose count is still 1. Attempt the
        # insert and let the unique constraint settle the race instead.
        try:
            db.add(RateBucket(key=key, hits=1, expires_at=instant + timedelta(seconds=window)))
            db.commit()
            return
        except IntegrityError:
            db.rollback()
        result = db.execute(update(RateBucket).where(RateBucket.key == key, RateBucket.hits < limit).values(hits=RateBucket.hits + 1))
        db.commit()
        if not result.rowcount:
            # The bucket exists and the retried increment still matched nothing,
            # so it is genuinely at its limit.
            raise HTTPException(429, "Too many requests. Try again later.", headers={"Retry-After": str(window)}) from None
