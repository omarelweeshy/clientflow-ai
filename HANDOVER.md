# ClientFlow AI: Project Guide and Agent Handover

**Purpose:** Give a new maintainer or coding agent enough context to understand, run, verify, and safely extend this repository.

**Last workspace inspection:** 2026-10-19. **Checkout:** `main`, commit `b664d36e956b5ccea2a7177de6bcbcc589326ea9` (2026-10-12). **Git status at inspection:** clean before this guide was added. **Docker Desktop:** unavailable during this inspection, so the local services could not be queried or smoke-tested now.

This file is a map and handover, not a replacement for the detailed source documents. Prefer code and the linked documents when they disagree with this summary.

## What this project is

ClientFlow AI is an independent portfolio project for a solo freelancer or small team handling prospective client enquiries. It demonstrates a complete, inspectable lead workflow: capture an enquiry, extract structured requirements, apply explicit qualification rules, create an internal CRM opportunity, prepare a response, require human approval, deliver through a mock outbox or optional email adapter, and manage separately approved follow-ups and stop conditions.

The intended engineering story is operational automation with durable state and human control. The AI extractor does not set the score, decide consent, approve a message, or perform actions. The public Vercel site is a portfolio simulation with fictional data; the local Docker application is the full backend-backed demo. These are different editions.

This is independent portfolio work, not commissioned client work. It is a single-organization MVP, not a hardened, multi-tenant SaaS product.

## Current state and what is verified

- Git remote: `https://github.com/omarelweeshy/clientflow-ai.git`; default work is on `main`.
- The repository is connected to a Vercel project. The intended public URL is [clientflow-ai-eight.vercel.app](https://clientflow-ai-eight.vercel.app).
- The latest recorded anonymous production browser smoke and three-job GitHub Actions pass are dated 2026-10-12. See [deployment notes](docs/VERCEL.md) and [verification evidence](docs/VERIFICATION.md). This inspection did not make a fresh network request to GitHub or Vercel, so recheck current remote status before making present-tense availability claims.
- The Docker stack could not be inspected because the Docker Desktop Linux engine pipe was absent. Do not assume the services are running just because a browser tab or old log showed localhost previously.
- The most recent release evidence records 35 PostgreSQL backend tests, 9 frontend unit tests, lint, type checking, production builds, and public-demo browser smoke as passed at that time. It is historical evidence, not a test run for this checkout on 2026-10-19.
- Optional Ollama, HubSpot, SMTP, and Slack adapters exist, but their live external behavior has not been verified. Mock email writes to the app's outbox; it does not send internet email. See the integration matrix in [verification evidence](docs/VERIFICATION.md).

## Two editions: keep their boundaries clear

### Public portfolio demo (Vercel)

The public build uses `NEXT_PUBLIC_DEMO_MODE=true` at build time. It runs in the browser using fictional sample records and browser `localStorage`. It allows visitors to simulate intake, editing, approval, delivery, retries, replies, follow-up scheduling, and cancellation. It has no login and makes no requests from the UI to the app API. API proxy routes reject requests in demo mode. No PostgreSQL database, local enquiries, n8n instance, or provider secrets are deployed with it.

Browser state is not encrypted and is scoped to a browser profile on that origin. Treat it as disposable fictional demo data. Do not add production credentials, database URLs, or backend endpoints to Vercel's public demo configuration.

Deployment root is `frontend`; framework is Next.js; Node version 24; build command is `npm run build`. `NEXT_PUBLIC_DEMO_MODE=true` must be present during the build. The GitHub repository is connected to Vercel, so pushing to its production branch can trigger a production deployment. Confirm the target and Vercel status before relying on it.

### Full local Docker application

Compose runs PostgreSQL 17, FastAPI, Next.js, and n8n. The frontend talks to FastAPI through a same-origin proxy; PostgreSQL is the durable source of truth; n8n orchestrates scheduled work. The default app mode processes incoming intake in FastAPI. n8n runs scheduled operations and is available at port 5678. The default provider modes are mock/deterministic unless `.env` was explicitly changed.

Ports bind to loopback by default: web `3010`, API `8010`, n8n `5678`; PostgreSQL is internal to the Compose network. Named volumes preserve PostgreSQL and n8n state. `docker compose down` preserves volumes; do not use `down -v` unless the user explicitly wants to erase local data and has confirmed the target.

## Architecture and critical behavior

```text
Browser
  -> Next.js UI and same-origin API proxy
  -> FastAPI (validation, auth, business state, approval, audit)
       -> PostgreSQL (durable source of truth)
       -> extraction: deterministic mock or optional Ollama
       -> internal CRM, optional HubSpot contact adapter
       -> mock outbox or optional SMTP
       -> optional Slack webhook
n8n -> protected FastAPI automation endpoints (separate shared secret)
```

Important invariants to preserve:

1. Preserve the submitted enquiry. Extraction is schema-validated and must not silently replace original facts.
2. Deterministic code owns qualification, consent, eligibility, approval, and sequence-stop decisions. Model output is suggestions and structured extraction only.
3. Repeated intake and delivery requests must remain idempotent. Database uniqueness constraints and PostgreSQL row locks protect concurrent operations; do not replace these guarantees with only frontend checks.
4. An approval applies to a specific saved draft revision. Editing invalidates its approval. Every follow-up needs a separate approval.
5. Recheck opt-out and all sequence-stop conditions when delivering. Replies, booking, opt-out, won/lost outcomes, and pause should stop future follow-ups.
6. SMTP timeout/crash can leave delivery uncertain. Preserve the reconciliation guard and never blindly resend uncertain email.
7. Provider details and raw secrets must not leak into API errors, logs, public demo data, screenshots, or Git.

## Run locally

Prerequisites: Docker Desktop using Linux containers, Docker Compose, and Python 3.12 or newer for first-time configuration. Clone the repository, then from its root run:

```powershell
python scripts/configure.py
docker compose up -d --build
```

The documented one-command path performs setup, starts services, seeds fictional fixtures, and imports/publishes the five n8n schedules:

```powershell
.\scripts\start-demo.ps1
```

The script preserves an existing `.env`. Generated configuration and the administrator password are local-only: read the password from `local-secrets/admin-password.txt`. Never paste its value into issues, agent prompts, or this document.

Useful local pages:

- Dashboard/login: <http://localhost:3010/login>
- Public intake: <http://localhost:3010/intake>
- FastAPI docs: <http://localhost:8010/docs>
- n8n editor: <http://localhost:5678>

The n8n editor may require creating its local owner account on first use. It is a trusted administrator surface with environment access; keep it on loopback and do not expose it publicly.

Useful diagnostics:

```powershell
docker compose ps
docker compose logs --tail 100 api
docker compose logs --tail 100 web
docker compose logs --tail 100 n8n
docker compose exec api alembic current
docker compose exec api python -m app.seed
```

If ports are occupied, change `WEB_PORT`, `API_PORT`, and the matching `PUBLIC_ORIGIN` in `.env`. Internal service URLs should continue using the Compose names, such as `http://api:8000`.

For exact workflow import/publish and manual execution instructions, see [n8n operations](docs/N8N.md). `ORCHESTRATION_MODE=n8n` changes intake processing to n8n; the default is `app`. Change it only when intentionally validating that mode.

## Verification commands

Use the repository's [verification report](docs/VERIFICATION.md) for the evidence ledger and known limits. Key checks from a clean checkout:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
python scripts/check_exports.py
python scripts/scan_secrets.py
cd frontend
npm ci --no-audit --no-fund
npm run lint
npm run typecheck
npm test
npm run build
cd ..
```

Backend tests should run from `backend` and must target a disposable database whose name contains `test`; never point tests at the local demo database. CI provisions a separate PostgreSQL `clientflow_test`. The public production browser smoke requires a built server and Playwright browser; see [Vercel preview and smoke steps](docs/VERCEL.md). The standard CI workflow runs backend/PostgreSQL, frontend, and public-demo jobs on pushes and pull requests.

Before commit, inspect `git status`, `git diff --check`, and `git diff`. Check that `.env`, `local-secrets/`, volumes, generated outputs, and real personal/client data are not staged.

## Repository map

| Path | Purpose |
|---|---|
| `frontend/` | Next.js app, components, API proxy, browser-only demo implementation and tests |
| `backend/app/` | FastAPI routes, services, models, auth, integrations and business workflow |
| `backend/alembic/` | Database schema migrations |
| `backend/tests/` | Backend tests, including PostgreSQL-backed concurrency and workflow checks |
| `n8n/` | Five credential-free exported workflows mounted read-only into local n8n |
| `scripts/` | Setup/startup, exports/secret hygiene checks, fixtures and browser smoke scripts |
| `examples/` | Fictional API payloads for exercising intake |
| `docs/` | Reviewer guide, case study, API/data model, architecture decision, plan, demo, security, n8n, Vercel, verification and screenshots |
| `.github/workflows/ci.yml` | Three-job CI for backend, standard frontend, and public demo browser smoke |
| `.github/dependabot.yml` | Automated dependency update configuration |
| `compose.yaml` | Local four-service application stack and persistent volumes |

## Existing documentation

- [README](README.md): project overview, setup, architecture, workflow and roadmap.
- [Reviewer guide](docs/REVIEWER_GUIDE.md): concise portfolio walkthrough.
- [Case study](docs/CASE_STUDY.md): product and engineering rationale.
- [API and data model](docs/API.md): endpoint and persistence details.
- [Architecture decision](docs/ADR-001.md): state ownership and orchestration decision.
- [Security model](docs/SECURITY.md): threat model, controls and limitations.
- [n8n operations](docs/N8N.md): import, execution and scheduling.
- [Vercel notes](docs/VERCEL.md): public demo config, behavior, local preview and smoke testing.
- [Verification report](docs/VERIFICATION.md): historical test evidence, integration status and untested areas.
- [Roadmap](docs/PLAN.md): planned scope; check current code and issues before treating it as current priority.

## Security and deployment limits

Local application auth is single-administrator and local-demo oriented. The project does not yet provide multi-user roles, MFA, session revocation, a durable leased worker queue, full ingress abuse protection, backups/restore drills, data retention/deletion controls, production monitoring, or a formal security assessment. Live provider delivery, inbound replies, booking webhooks, and external-provider contract behavior remain unverified. Do not call the system production-ready or claim real emails/AI/provider updates were exercised.

Before any real public enquiry collection, plan and verify TLS and secure cookies, authentication/session controls, ingress rate limiting, reliable workers and retry/reconciliation, data lifecycle and privacy controls, backups/restore, monitoring/alerts, provider contracts, and n8n isolation. The Vercel public demo is not a backend deployment and cannot collect leads into the local system.

## Handover for the next agent

Start here before editing:

1. Read this guide, then inspect `git status --short`, `git log -5 --oneline`, remotes, and relevant `AGENTS.md` files. Preserve the user's existing work and do not assume this document's inspection date is still current.
2. Read the smallest relevant source and the corresponding linked document. Treat code, tests, and current runtime as authoritative over stale narrative docs.
3. Establish which edition is in scope: public browser simulation, local Docker application, or both. Keep the public demo isolated from local backend state and secrets.
4. For behavior changes, identify the database invariants, approval/consent boundaries, and tests before editing. Keep mock-vs-live claims explicit.
5. Run focused tests first, then the matching CI checks. Backend tests require a disposable `*_test` database. Do not test against a personal or demo database.
6. Inspect the final diff and secret hygiene. Report exact checks run, their results, and what remains unverified. Recheck GitHub/Vercel live state before claiming a deployment succeeded.

The immediate known limitation at this handover's creation is environmental: Docker Desktop was not reachable from this workspace. If the next task needs the local stack, start Docker Desktop and verify `docker compose ps` before proceeding. No project code change was made to the services as part of this documentation handover.

## License

The repository is MIT licensed. See [LICENSE](LICENSE).
