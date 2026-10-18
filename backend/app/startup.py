"""Configuration checks that run before the application serves traffic.

Misconfiguration used to surface late and quietly: an empty SESSION_SECRET
became a 503 the first time someone signed in, an empty ADMIN_PASSWORD_HASH
just made every password wrong, and a missing SMTP host became a KeyError that
the delivery path swallowed. Every problem is collected and reported at once,
so an operator fixes one list rather than one error per restart.
"""

import ipaddress
import os
from urllib.parse import urlsplit

PROVIDERS = {
    "LLM_PROVIDER": {"mock": [], "ollama": ["OLLAMA_URL", "OLLAMA_MODEL"]},
    "CRM_PROVIDER": {"internal": [], "hubspot": ["HUBSPOT_TOKEN"]},
    "EMAIL_PROVIDER": {"mock": [], "smtp": ["SMTP_HOST", "SMTP_FROM"]},
}


class ConfigurationError(RuntimeError):
    pass


def problems(env):
    found = []
    for name, minimum in [("SESSION_SECRET", 32), ("AUTOMATION_SECRET", 32)]:
        if len(env.get(name, "")) < minimum:
            found.append(f"{name} must be at least {minimum} characters")

    stored = env.get("ADMIN_PASSWORD_HASH", "")
    parts = stored.split("$")
    if len(parts) == 3 and (stored.startswith(("'", '"')) or stored.endswith(("'", '"'))):
        # configure.py single-quotes the value so Compose's .env parser keeps the
        # dollar signs. If the quotes survive into the process, every password
        # comparison fails and nothing says why.
        found.append("ADMIN_PASSWORD_HASH still has surrounding quotes; the value reaching the process must be unquoted")
    elif len(parts) != 3 or parts[0] != "pbkdf2_sha256" or not parts[1] or not parts[2]:
        found.append("ADMIN_PASSWORD_HASH is not a pbkdf2_sha256$salt$digest value; run scripts/configure.py")

    origin = env.get("PUBLIC_ORIGIN", "")
    parsed = urlsplit(origin)
    if parsed.scheme not in ["http", "https"] or not parsed.netloc:
        found.append("PUBLIC_ORIGIN must be an http or https origin")
    elif parsed.scheme == "https" and env.get("COOKIE_SECURE", "").lower() != "true":
        found.append("COOKIE_SECURE must be true when PUBLIC_ORIGIN is https, or the session cookie is sent over plain HTTP")

    if env.get("ORCHESTRATION_MODE", "app") not in ["app", "n8n"]:
        found.append("ORCHESTRATION_MODE must be app or n8n")

    for name, allowed in PROVIDERS.items():
        selected = env.get(name, "")
        if selected not in allowed:
            found.append(f"{name} must be one of {', '.join(sorted(allowed))}")
            continue
        for required in allowed[selected]:
            if not env.get(required, ""):
                found.append(f"{required} is required when {name} is {selected}")

    for entry in [x.strip() for x in env.get("TRUSTED_PROXY_CIDRS", "").split(",") if x.strip()]:
        try:
            ipaddress.ip_network(entry, strict=False)
        except ValueError:
            found.append(f"TRUSTED_PROXY_CIDRS contains an invalid network: {entry}")

    if not env.get("DATABASE_URL", ""):
        found.append("DATABASE_URL is required")

    return found


def check(env=None):
    """Raise with every problem listed, or return cleanly."""
    found = problems(env if env is not None else os.environ)
    if found:
        raise ConfigurationError("Refusing to start with invalid configuration:\n- " + "\n- ".join(found))
