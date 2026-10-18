import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./clientflow.db")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
AUTOMATION_SECRET = os.getenv("AUTOMATION_SECRET", "")
PUBLIC_ORIGIN = os.getenv("PUBLIC_ORIGIN", "http://localhost:3010").rstrip("/")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
ORCHESTRATION_MODE = os.getenv("ORCHESTRATION_MODE", "app")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")
CRM_PROVIDER = os.getenv("CRM_PROVIDER", "internal")
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "mock")
# Per-IP rate limiting is only sound when a trusted reverse proxy supplies the
# client address. List the proxy networks allowed to assert it; empty means
# trust nothing and fall back to the socket peer.
TRUSTED_PROXY_CIDRS = [x.strip() for x in os.getenv("TRUSTED_PROXY_CIDRS", "").split(",") if x.strip()]
CLIENT_IP_HEADER = os.getenv("CLIENT_IP_HEADER", "x-forwarded-for").lower()
