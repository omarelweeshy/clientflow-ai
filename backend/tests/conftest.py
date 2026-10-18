import os
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///" + str(Path(tempfile.gettempdir()) / "clientflow-tests.db").replace("\\", "/"))
os.environ["SESSION_SECRET"] = "test-session-secret-do-not-use-in-production-1234"
os.environ["AUTOMATION_SECRET"] = "test-automation-secret-do-not-use-in-production-1234"
# Keep the structured log stream out of test output; caplog still captures records.
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app import config, security  # noqa: E402
from app.main import app  # noqa: E402
from app.db import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    # Run only against a disposable test database. Never production data.
    if "test" not in config.DATABASE_URL:
        raise RuntimeError("Tests require a database URL containing test")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", security.hash_password("test-password"))
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(config, "CRM_PROVIDER", "internal")
    monkeypatch.setattr(config, "EMAIL_PROVIDER", "mock")
    monkeypatch.setattr(config, "ORCHESTRATION_MODE", "app")
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin(client):
    result = client.post("/auth/login", json={"password": "test-password"}, headers={"Origin": config.PUBLIC_ORIGIN})
    assert result.status_code == 200
    client.headers.update({"Origin": config.PUBLIC_ORIGIN, "X-CSRF-Token": result.json()["csrf"]})
    return client
