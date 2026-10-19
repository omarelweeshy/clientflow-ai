"""Per-client rate limiting must not become one shared bucket behind a proxy."""

import uuid
from datetime import timedelta
import pytest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app import config, security
from app.main import app
from app.db import SessionLocal
from app.models import RateBucket, now
from test_workflow import payload


@pytest.fixture
def proxied():
    """A client whose socket peer is a routable address, as it is behind a proxy.

    The default TestClient peer is the literal string "testclient", which no
    trusted-network check can match.
    """
    with TestClient(app, client=("10.1.2.3", 44000)) as c:
        yield c


def submit_from(client, address, key=None):
    return client.post(
        "/public/intake",
        json=payload(email=f"{uuid.uuid4().hex[:8]}@example.com"),
        headers={"Idempotency-Key": key or str(uuid.uuid4()), "X-Forwarded-For": address},
    )


def test_untrusted_forwarded_address_is_ignored(client, monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", [])
    request = type("R", (), {"client": type("C", (), {"host": "10.1.2.3"})(), "headers": {"x-forwarded-for": "203.0.113.9"}})()
    address, trusted = security.client_ip(request)
    assert (address, trusted) == ("10.1.2.3", False)


def test_trusted_proxy_address_is_used(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", ["10.0.0.0/8"])
    request = type("R", (), {"client": type("C", (), {"host": "10.1.2.3"})(), "headers": {"x-forwarded-for": "198.51.100.4, 203.0.113.9"}})()
    # Right-most entry only: anything further left was supplied by the caller.
    assert security.client_ip(request) == ("203.0.113.9", True)


def test_malformed_forwarded_address_falls_back_to_the_peer(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", ["10.0.0.0/8"])
    request = type("R", (), {"client": type("C", (), {"host": "10.1.2.3"})(), "headers": {"x-forwarded-for": "not-an-address"}})()
    assert security.client_ip(request) == ("10.1.2.3", False)


def test_one_address_cannot_exhaust_the_login_limit_for_another(proxied, monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", ["0.0.0.0/0"])
    attacker = {"Origin": config.PUBLIC_ORIGIN, "X-Forwarded-For": "203.0.113.9"}
    for _ in range(10):
        proxied.post("/auth/login", json={"password": "wrong"}, headers=attacker)
    assert proxied.post("/auth/login", json={"password": "wrong"}, headers=attacker).status_code == 429
    # The administrator, on a different address, is not locked out.
    admin_headers = {"Origin": config.PUBLIC_ORIGIN, "X-Forwarded-For": "198.51.100.4"}
    assert proxied.post("/auth/login", json={"password": "test-password"}, headers=admin_headers).status_code == 200


def test_intake_limit_is_keyed_per_address(proxied, monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", ["0.0.0.0/0"])
    for index in range(60):
        assert submit_from(proxied, "203.0.113.9", f"flood-{index:03}").status_code == 201
    assert submit_from(proxied, "203.0.113.9", "flood-blocked").status_code == 429
    assert submit_from(proxied, "198.51.100.4", "other-address").status_code == 201


def test_global_backstop_applies_without_a_trusted_proxy(client, monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", [])
    # Backstop only; no per-address bucket is created when the address is untrusted.
    for _ in range(3):
        client.post("/auth/login", json={"password": "wrong"}, headers={"Origin": config.PUBLIC_ORIGIN})
    with SessionLocal() as db:
        assert db.scalar(select(func.count(RateBucket.key))) == 1


def test_concurrent_first_requests_are_not_spuriously_rejected():
    """Several callers racing to create the same bucket must all be admitted.

    The losing threads used to find the bucket the winning thread had just
    inserted and return 429 for a request whose count was still 1.
    """
    import uuid as _uuid

    for attempt in range(8):
        key = f"race-{_uuid.uuid4()}"
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(lambda _: _attempt(key, limit=100), range(8)))
        rejected = [x for x in outcomes if x == 429]
        assert not rejected, f"attempt {attempt}: {len(rejected)} of 8 rejected below the limit"
        with SessionLocal() as db:
            assert db.scalar(select(RateBucket.hits).where(RateBucket.key == _hashed(key))) == 8


def _hashed(key):
    import hashlib

    return hashlib.sha256(key.encode()).hexdigest()


def _attempt(key, limit=100):
    from fastapi import HTTPException

    try:
        security.rate_limit(key, limit, 3600)
        return 200
    except HTTPException as exc:
        return exc.status_code


def test_a_bucket_at_its_limit_still_rejects():
    key = f"ceiling-{uuid.uuid4()}"
    for _ in range(3):
        assert _attempt(key, limit=3) == 200
    assert _attempt(key, limit=3) == 429


def test_expired_buckets_are_pruned(client):
    with SessionLocal() as db:
        db.add(RateBucket(key="stale", hits=1, expires_at=now() - timedelta(days=3)))
        db.add(RateBucket(key="fresh", hits=1, expires_at=now() + timedelta(hours=1)))
        db.commit()
        assert security.prune_buckets(db) == 1
        db.commit()
        remaining = set(db.scalars(select(RateBucket.key)).all())
    assert remaining == {"fresh"}
