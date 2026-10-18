"""Per-client rate limiting must not become one shared bucket behind a proxy."""

import uuid
from datetime import timedelta
import pytest
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


def test_expired_buckets_are_pruned(client):
    with SessionLocal() as db:
        db.add(RateBucket(key="stale", hits=1, expires_at=now() - timedelta(days=3)))
        db.add(RateBucket(key="fresh", hits=1, expires_at=now() + timedelta(hours=1)))
        db.commit()
        assert security.prune_buckets(db) == 1
        db.commit()
        remaining = set(db.scalars(select(RateBucket.key)).all())
    assert remaining == {"fresh"}
