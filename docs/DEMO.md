# Five-minute demo walkthrough

1. Start Compose and seed. Sign in with the generated local password. All names and failures are fictional, and external adapters are disabled.
2. Open overview. Inspect pending approval, recovery count, pipeline and activity derived from PostgreSQL.
3. Open Nadia's strong lead. Read the original enquiry, deterministic scoring and complete event timeline. AI context and generated suggestions are clearly separated.
4. Edit the response, save, approve, then send. Delivery is recorded in the mock outbox and two follow-ups are scheduled. A second send does not duplicate delivery.
5. Open public intake. Submit a new enquiry with partial requirements. Confirm receipt and its review reasons in the dashboard.
6. Find AI/CRM/email failure fixtures in Automation runs. Retry each; inspect the new successful run and resolution state. These are explicitly simulated failures, not claims of live-provider outages.
7. Open a contacted lead. Record reply, booking, opt-out or won/lost status. Future follow-ups become cancelled and delivery is blocked.
8. Import the n8n workflows. Execute manual triggers against the local API; switch to n8n orchestration for non-empty polling. Business decisions remain inspectable in PostgreSQL.

Scoring defaults are illustrative. Configure real service availability, budget policy and booking URL before accepting actual freelance enquiries. Real provider and production limitations are in the verification and security documents.
