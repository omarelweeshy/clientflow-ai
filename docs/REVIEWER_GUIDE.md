# Evaluate ClientFlow AI in five minutes

ClientFlow AI demonstrates the lifecycle of a freelance enquiry, including the operational work after generation: qualification, approval, delivery, duplicate protection, follow-ups and recovery. This is an independent portfolio project by Omar Ashraf, not commissioned client work.

## Start

Clone the repository, then run `scripts/start-demo.ps1` on Windows or `sh scripts/start-demo.sh` on Linux/macOS. Docker with Compose and Python 3.12+ are required. First startup downloads images and builds the frontend, so allow several minutes.

Open <http://localhost:3010/login>. Read the generated password in `local-secrets/admin-password.txt`. Each installation generates its own credentials. Nothing needs a paid account.

## Review the behavior

| Step | Action | Expected evidence |
|---|---|---|
| 1 | Inspect the overview and open Nadia's seeded enquiry | Preserved original requirements, qualification breakdown, CRM opportunity and event timeline |
| 2 | Edit a pending response and save it | Previous revision retained; approval resets |
| 3 | Approve, then send | One persistent mock delivery; two follow-up steps scheduled |
| 4 | Repeat the send if the action is available | No additional delivery |
| 5 | Enable **Reply received** | Remaining follow-ups cancelled; future delivery blocked |
| 6 | Submit fictional data through `/intake` | New lead appears with its draft and review reasons |
| 7 | Inspect Automation runs and retry an unresolved simulated failure | New run and resolution history, with original enquiry retained |

Scheduled n8n delivery can pick up an approved draft before you click Send. This is expected: approval is the human gate. The mock outbox records delivery without sending internet email. The fixtures include simulated failures; retries may already have resolved them on a reused installation.

## Inspect the engineering

- [Architecture decision](ADR-001.md): FastAPI owns business state; n8n orchestrates protected operations.
- [API and data model](API.md): persistent records, authentication boundaries and routes.
- [Tests](../backend/tests/test_workflow.py): deduplication, concurrency, revision approval, sequence stops and SMTP uncertainty.
- [n8n exports](../n8n/): five inspectable workflows without embedded credentials.
- [Verification report](VERIFICATION.md): observed local results and untested integrations.
- [Threat model](SECURITY.md): concrete controls and deployment gaps.

## What this proves

The local workflow, PostgreSQL persistence, human approval and recoverable mock integrations are exercised end to end. Mock extraction is deterministic and does not establish real-model accuracy. SMTP deliverability, Ollama quality, live HubSpot/Slack behavior, automated reply detection and production security are not established.

Stop with `docker compose down`. Named volumes keep your data. Never use real prospect details in screenshots or issue reports.
