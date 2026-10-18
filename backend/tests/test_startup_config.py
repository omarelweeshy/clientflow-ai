"""The application must refuse to start misconfigured, and say everything that is wrong."""

import pytest
from app import providers, startup


def valid_env(**overrides):
    env = {
        "DATABASE_URL": "postgresql+psycopg://user:pw@db:5432/clientflow",
        "SESSION_SECRET": "x" * 32,
        "AUTOMATION_SECRET": "y" * 32,
        "ADMIN_PASSWORD_HASH": "pbkdf2_sha256$salt$digest",
        "PUBLIC_ORIGIN": "http://localhost:3010",
        "COOKIE_SECURE": "false",
        "ORCHESTRATION_MODE": "app",
        "LLM_PROVIDER": "mock",
        "CRM_PROVIDER": "internal",
        "EMAIL_PROVIDER": "mock",
        "TRUSTED_PROXY_CIDRS": "10.0.0.0/8",
    }
    env.update(overrides)
    return {k: v for k, v in env.items() if v is not None}


def test_a_valid_environment_has_no_problems():
    assert startup.problems(valid_env()) == []


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"SESSION_SECRET": "short"}, "SESSION_SECRET must be at least 32 characters"),
        ({"AUTOMATION_SECRET": ""}, "AUTOMATION_SECRET must be at least 32 characters"),
        ({"ADMIN_PASSWORD_HASH": ""}, "ADMIN_PASSWORD_HASH is not a pbkdf2_sha256$salt$digest value; run scripts/configure.py"),
        ({"ADMIN_PASSWORD_HASH": "plaintext"}, "ADMIN_PASSWORD_HASH is not a pbkdf2_sha256$salt$digest value; run scripts/configure.py"),
        ({"PUBLIC_ORIGIN": "not-a-url"}, "PUBLIC_ORIGIN must be an http or https origin"),
        ({"ORCHESTRATION_MODE": "sometimes"}, "ORCHESTRATION_MODE must be app or n8n"),
        ({"EMAIL_PROVIDER": "sendgrid"}, "EMAIL_PROVIDER must be one of mock, smtp"),
        ({"EMAIL_PROVIDER": "smtp"}, "SMTP_HOST is required when EMAIL_PROVIDER is smtp"),
        ({"CRM_PROVIDER": "hubspot"}, "HUBSPOT_TOKEN is required when CRM_PROVIDER is hubspot"),
        ({"LLM_PROVIDER": "ollama"}, "OLLAMA_URL is required when LLM_PROVIDER is ollama"),
        ({"TRUSTED_PROXY_CIDRS": "10.0.0.0/8,nonsense"}, "TRUSTED_PROXY_CIDRS contains an invalid network: nonsense"),
        ({"DATABASE_URL": ""}, "DATABASE_URL is required"),
    ],
)
def test_each_misconfiguration_is_reported(overrides, expected):
    assert expected in startup.problems(valid_env(**overrides))


def test_a_quoted_password_hash_is_rejected_with_its_own_message():
    found = startup.problems(valid_env(ADMIN_PASSWORD_HASH="'pbkdf2_sha256$salt$digest'"))
    assert found == ["ADMIN_PASSWORD_HASH still has surrounding quotes; the value reaching the process must be unquoted"]


def test_https_origin_requires_a_secure_cookie():
    found = startup.problems(valid_env(PUBLIC_ORIGIN="https://clientflow.example", COOKIE_SECURE="false"))
    assert any("COOKIE_SECURE must be true" in problem for problem in found)
    assert startup.problems(valid_env(PUBLIC_ORIGIN="https://clientflow.example", COOKIE_SECURE="true")) == []


def test_every_problem_is_reported_at_once():
    found = startup.problems(valid_env(SESSION_SECRET="", AUTOMATION_SECRET="", DATABASE_URL="", ORCHESTRATION_MODE="no"))
    assert len(found) == 4


def test_check_raises_with_the_whole_list():
    with pytest.raises(startup.ConfigurationError) as raised:
        startup.check(valid_env(SESSION_SECRET="", DATABASE_URL=""))
    message = str(raised.value)
    assert "SESSION_SECRET" in message and "DATABASE_URL" in message


def test_missing_provider_credentials_name_the_setting(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    with pytest.raises(RuntimeError, match="SMTP_HOST is not configured"):
        providers.required("SMTP_HOST")


def test_liveness_does_not_touch_the_database(client):
    """A dependency override is resolved per request, so this really proves it."""
    from app.db import get_db
    from app.main import app

    def refuse():
        raise AssertionError("liveness must not query the database")

    app.dependency_overrides[get_db] = refuse
    try:
        body = client.get("/health").json()
        assert body["status"] == "ok" and body["version"]
        # The same override makes readiness fail, which shows the override is live.
        with pytest.raises(AssertionError, match="must not query"):
            client.get("/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_readiness_reports_the_database(client):
    assert client.get("/health/ready").json() == {"status": "ready"}
