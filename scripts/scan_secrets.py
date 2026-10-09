"""Check candidate repository files against actual generated local secrets."""

from pathlib import Path
import subprocess
import re

root = Path(__file__).resolve().parents[1]
files = subprocess.check_output(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
    cwd=root,
    text=True,
).splitlines()
secrets = []
env = root / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        if line.startswith(
            (
                "SESSION_SECRET=",
                "AUTOMATION_SECRET=",
                "N8N_ENCRYPTION_KEY=",
                "POSTGRES_PASSWORD=",
                "ADMIN_PASSWORD_HASH=",
                "HUBSPOT_TOKEN=",
                "SMTP_PASSWORD=",
                "SLACK_WEBHOOK_URL=",
            )
        ):
            secrets.append(line.split("=", 1)[1].strip("'\""))
password_file = root / "local-secrets/admin-password.txt"
if password_file.exists():
    secrets.append(password_file.read_text().strip())
for name in set(files):
    parts = Path(name).parts
    if any(part in {"local-secrets", ".venv", ".venv312", "node_modules", ".next"} for part in parts):
        raise SystemExit(f"FAIL: private or generated path included: {name}")
    if (Path(name).name.startswith(".env") and Path(name).name != ".env.example") or Path(name).suffix in {".pem", ".key", ".db"}:
        raise SystemExit(f"FAIL: private configuration included: {name}")
    file = root / name
    if file.suffix.lower() in [".png", ".jpg", ".woff", ".woff2"]:
        continue
    if file.is_file():
        content = file.read_text(encoding="utf-8", errors="ignore")
        if any(secret and secret in content for secret in secrets):
            raise SystemExit(f"FAIL: generated secret present in {name}")
        patterns = [
            r"gh[pousr]_" + r"[A-Za-z0-9]{30,}",
            r"github_pat_" + r"[A-Za-z0-9_]{40,}",
            r"AKIA" + r"[A-Z0-9]{16}",
            r"-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            r"https://hooks\.slack\.com/services/" + r"[A-Za-z0-9/]{20,}",
        ]
        if any(re.search(pattern, content) for pattern in patterns):
            raise SystemExit(f"FAIL: credential-like value present in {name}")
assert ".env" not in files
assert not any(name.startswith("local-secrets/") for name in files)
print(
    f"PASS: {len(set(files))} candidate files pass known-token and generated-credential checks; private paths are excluded."
)
