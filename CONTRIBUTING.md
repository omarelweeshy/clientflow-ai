# Contributing

Run the demo and read `docs/REVIEWER_GUIDE.md` before changing workflow behavior. Keep business rules in the backend and use the existing provider interfaces for integrations.

Backend verification:

```sh
python -m venv .venv
# Activate .venv using your shell, then:
python -m pip install -r backend/requirements.txt
ruff check backend scripts
python scripts/check_exports.py
python scripts/scan_secrets.py
cd backend
python -m pytest -q
```

The default test database is disposable SQLite. Set `DATABASE_URL` to a separate PostgreSQL database whose name contains `test` to exercise the row-lock concurrency check. Never use the demo database for tests.

Frontend verification:

```sh
cd frontend
npm ci --no-audit --no-fund
npm run lint
npm run typecheck
npm test
npm run build
```

For changes to approval, delivery or follow-ups, verify their stop conditions and idempotency. For UI changes, run `scripts/browser-smoke.cjs` against mock adapters and inspect desktop/mobile screenshots as described in `docs/VERIFICATION.md`.

Use fictional data in examples, fixtures, screenshots and issues. Do not commit environment files, passwords, tokens, provider logs or database exports. Describe the problem, resulting behavior and verification in pull requests; identify anything untested.
