"""Standard-library local setup. Does not overwrite user configuration."""

import hashlib
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    raise SystemExit(".env already exists. Preserving it; edit it manually if needed.")
password = secrets.token_urlsafe(18)
salt = secrets.token_hex(16)
digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
db_password = secrets.token_hex(24)
text = (root / ".env.example").read_text()
text = text.replace("replace-with-a-random-password", db_password)
text = text.replace(
    "replace-with-at-least-32-random-characters", secrets.token_hex(32), 1
)
text = text.replace(
    "replace-with-at-least-32-random-characters", secrets.token_hex(32), 1
)
text = text.replace("replace-with-a-random-key", secrets.token_hex(32))
# Single quoting preserves literal dollar signs in Docker Compose's .env parser.
text = text.replace(
    "generate-with-scripts-configure.py", f"'pbkdf2_sha256${salt}${digest}'"
)
target.write_text(text)
private = root / "local-secrets"
private.mkdir(exist_ok=True)
(private / "admin-password.txt").write_text(password)
print("Created .env and local-secrets/admin-password.txt (both ignored).")
print("Run: docker compose up --build -d")
