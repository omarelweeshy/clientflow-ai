# Verification report

Verified locally on Windows with Docker Desktop Linux containers, 2026-10-09. This report distinguishes the working demo from external-provider and production claims.

## Implemented

- Next.js/TypeScript public intake, password sign-in, overview, searchable/filterable pipeline, detailed lead timeline, response editor and approval queue, automation ledger and settings.
- FastAPI validation, normalization, durable keys/fingerprints, exact and configurable probable matching, preserved original enquiries, schema-validated extraction, deterministic editable scoring and service catalogue, internal CRM, revisions, approval and guarded delivery.
- PostgreSQL storage with Alembic migration `0001`, unique constraints and row locks. SQLite developer/test fallback.
- Initial response plus two separately approved follow-ups, ordering and reply/booking/opt-out/won/lost/pause cancellation.
- Safe error records, recoverable AI/CRM/mock-email failures, SMTP uncertainty protection, audit events and correlation IDs.
- Mock extraction, persistent mock email outbox and internal CRM; optional Ollama, HubSpot contact, SMTP and Slack adapters; configurable HTTPS booking URL.
- Five imported n8n workflows and published schedules, Compose stack, repeatable fictional fixtures, sample payloads, diagrams, screenshots, threat model, MIT license and GitHub Actions configuration.

## Passed

| Check | Observed result |
|---|---|
| PostgreSQL backend suite | **35 passed** against separate `clientflow_test`; includes simultaneous intake/send requests, approval, edits, opt-out, all stop conditions, streaming body limits, SMTP uncertainty and editable services |
| SQLite backend suite | **34 passed, 1 skipped**; PostgreSQL row-lock concurrency deliberately skipped |
| Frontend unit tests | **3 passed** for composed pipeline filters and literal search |
| Backend lint | Ruff passed on backend and scripts |
| Frontend lint / type checking | ESLint and `tsc --noEmit` passed |
| Production build | Next.js 16.4.0 / React 19.3.0 production build passed inside Docker using `npm ci` |
| Backend dependency audit | `pip-audit -r backend/requirements.txt`: no known vulnerabilities after updating FastAPI/Starlette and pytest |
| Frontend production dependency audit | `npm audit --omit=dev --audit-level=high`: 0 reported vulnerabilities |
| Docker | PostgreSQL and API healthy; Next.js and n8n running; existing DocIntel stack preserved |
| Migration | `alembic current`: `0001 (head)` |
| Seed | 12 fictional scenario leads; repeat seed adds none; separate browser/n8n verification fixtures remain explicitly fictional |
| Credential hygiene | Candidate Git files and exports contain no generated local secrets; `.env` and `local-secrets/` ignored |
| n8n import | Five JSON exports imported by n8n 2.42.5 |
| n8n execution | All five manual workflows executed against the protected local API; unavailable-port error branch returned a safe failure and was retained with `status=error`; scheduled success records confirmed with completion timestamps |
| Non-empty n8n flow | Stored NEW fixture → process/score/opportunity/pending draft → explicit approval → mock email; repeat email execution produced exactly one delivery and two schedules |
| n8n follow-up | Due first follow-up created as pending approval; final step waited; reply cancelled both scheduled steps; repeated tick added no extra message |
| Browser, desktop | Headless Microsoft Edge, 1440×1000: login, overview, pipeline navigation, lead timeline, approval queue, failures, settings and public form |
| Browser, mobile | 390×844: public intake, overview, lead timeline, approval queue and failures; no document-level horizontal overflow |
| Browser actions | New enquiry through real form → dashboard → approval → mock send → reply checkbox → cancelled follow-ups |
| Browser runtime | No page errors in the completed smoke script |

Screenshots live in `docs/screenshots/`. Source for repeatable browser verification: `scripts/browser-smoke.cjs`. Dependency audit results describe the advisory databases at execution time; they are not a security guarantee.

## Failures encountered and corrected

- Docker access required the local execution permission boundary. Access was granted and all services were exercised.
- Ports 3000/8000 belonged to DocIntel. ClientFlow uses loopback ports **3010/8010** and did not stop that stack.
- Next.js's Windows compiler initially failed to resolve the sandboxed workspace path. Verification passed with the necessary execution access and inside Linux Docker.
- A Windows-generated optional-dependency lockfile failed Linux `npm ci`. Regenerated the lockfile in Linux; clean Docker installation/build passed.
- n8n CLI execution collided with the running editor's task broker on 5679. CLI tests use `N8N_RUNNERS_BROKER_PORT=5681`.
- Browser verification found a delayed controlled-checkbox update; flags now update immediately and settle to persisted API state. Ambiguous test selectors were corrected.
- Mobile headline spacing and small annotation text were corrected after screenshot inspection.
- n8n initially left sparse execution metadata when successful execution saving was disabled. Success records are now retained, and HTTP errors use an explicit Stop And Error branch for visible failure status.
- The initial backend dependency audit found advisories in the older Starlette and pytest packages. FastAPI 0.143.0, Starlette 1.7.0 and pytest 9.1.1 were installed and reverified; the final audit is clear.
- The in-app browser tool could not initialize its kernel assets. Headless Edge completed the browser verification instead.

No final automated check failed unexpectedly. The intentionally unavailable n8n HTTP target is expected to produce a failed workflow. Backend TestClient emits one upstream deprecation warning about future `httpx2` use; tests pass. n8n reports optional Python-runner and internal-runner deprecation notices; these HTTP workflows contain no Python nodes. Native phone/Safari testing, formal accessibility auditing and an extended multi-day scheduling soak were not performed.

## Live versus simulated integrations

| Adapter / integration | Status |
|---|---|
| PostgreSQL | Live local database, migrations, persistence and concurrency exercised |
| n8n | Live local import, execution, error branch and published schedules; no external n8n account used |
| Internal CRM | Real persisted internal opportunities, no external CRM account |
| Mock extraction | Deterministic simulation; not real semantic model quality |
| Mock email | Real persistent outbox records; no internet email was sent |
| Ollama | Implemented, **not exercised live**; model availability, grounding and latency unverified |
| HubSpot | Implemented contact-upsert adapter, **not exercised live**; request failure/retry covered with provider stubs |
| SMTP | Implemented, **not exercised live**; timeout/uncertainty covered with a stub; deliverability unverified |
| Slack | Implemented, **not exercised live**; disabled by default; failure-notification workflow verified as a disabled no-op |
| Cal.com / booking | Configurable URL only; no live booking or OAuth integration; booking recorded manually |
| Inbound replies | Manually recorded; no mailbox integration |
| GitHub Actions | Workflow files provided; commands verified locally; no remote Actions run or public repository publication in this task |

## Security and production limits

Single administrator, stateless signed sessions without revocation/MFA, aggregate proxy rate limiting, synchronous intake processing and no durable worker lease/queue. SMTP's uncertain state requires external reconciliation. Reply/booking detection is manual. n8n editors are trusted and can access environment values. Formal security assessment, gateway hardening, TLS, backups/restore, privacy retention/deletion, provider contract tests and production monitoring remain necessary. See `SECURITY.md` for the complete threat model.

The application runs end to end **in local demo mode**. It is not claimed ready to receive production enquiries before those deployment and live-provider steps.

## GitHub preparation, 2026-10-09

- Re-ran the PostgreSQL suite: 35 passed, with the same upstream TestClient deprecation warning.
- Re-ran frontend lint, type checking and all three unit tests successfully.
- Executed the complete Windows startup script, including Docker production builds, readiness checks, repeatable seed, five workflow imports/publications and n8n restart.
- Re-ran the desktop/mobile browser workflow successfully. Public screenshots retain only earlier fictional fixtures; local user-entered data stays in the local database.
- Verified configuration generation in an empty temporary setup and refusal to overwrite an existing `.env`.
- Added portable clone instructions, a reviewer guide, engineering case study, contribution/security reporting guidance and dependency-update configuration.
- Verified staged files exclude local credentials, environment overrides, runtime volumes and generated TypeScript cache; known-token checks and `git diff --cached --check` pass.

## Exact run commands

```powershell
cd D:\Projects\clientflow-ai
.\scripts\start-demo.ps1
```

The script preserves an existing `.env`, starts/builds Compose, seeds only mock-mode fixtures, imports/publishes the five workflows and restarts n8n. On Linux/macOS: `sh scripts/start-demo.sh`.

Already configured stack:

```powershell
docker compose up -d
docker compose exec api alembic current
docker compose exec api python -m app.seed
Get-Content .\local-secrets\admin-password.txt
```

Open `http://localhost:3010/login`, `http://localhost:3010/intake`, `http://localhost:8010/docs` and `http://localhost:5678`.

Repeat browser smoke (requires fictional seed data and mock adapters):

```powershell
cd frontend
npm ci --no-audit --no-fund
npx playwright install chromium
cd ..
node scripts/browser-smoke.cjs
```

On this machine the browser checks used `$env:BROWSER_CHANNEL='msedge'` with preinstalled Edge. The smoke script adds a fictional prospect and performs mock delivery only. Do not run it against a real-provider environment.
