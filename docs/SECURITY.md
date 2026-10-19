# Threat model and remaining production work

Assets: enquiry PII, original requirements, consent, administrator session, provider credentials, approved draft revisions and delivery state.

Trust boundaries: untrusted prospect → public form/proxy → FastAPI → PostgreSQL; administrator → authenticated dashboard; trusted n8n editor → shared-secret automation API; backend → external providers. Model output and enquiry text remain untrusted data.

| Threat | MVP control | Remaining limitation |
|---|---|---|
| Public administration access | Authentication dependency on every admin route | One admin identity; no MFA or individual accounts |
| CSRF | Strict same-site cookie, exact origin and random session token | Signed stateless sessions have no server revocation list |
| Duplicate redelivery | Persistent key/hash, unique fingerprint, opportunity/message/sequence constraints | Probable matches require human judgment; changed enquiries are separate opportunities |
| Concurrent actions | PostgreSQL lead/message row locks | SQLite fallback lacks equivalent concurrency semantics; production needs worker leases |
| Spam/abuse | Server validation, 20 KB body cap, 5,000-character enquiry, honeypot, DB rate buckets keyed per client address, plus a global backstop | Per-address limiting is **off by default**: it requires both an ingress that overwrites `X-Forwarded-For` and the operator opting in with `TRUST_UPSTREAM_FORWARDED_FOR=true`, plus `TRUSTED_PROXY_CIDRS` naming the proxy network. Without that only the backstop and per-email limits apply. No CAPTCHA |
| Prompt injection | No model tools or approvals, strict extraction schema, code-scored decisions | Schema cannot prove factual grounding of prose; review real-model output |
| Secret/log leakage | Environment-only credentials, safe exception messages, ID-only integration ledger | OS/Docker administrators and trusted n8n editors can read server environment |
| Unexpected outreach | Approval default, revision resets, eligibility rechecked, sequence stop policy | Explicit safe initial-response toggle can bypass approval for eligible leads |
| Unknown SMTP delivery | Durable sending intent; uncertain state blocks resend | No automated provider reconciliation UI; operator must verify receipt externally |
| Consent violation | Signed opt-out confirmation, send-time guard | Reply and booking are manually recorded; no inbound-mail/calendar hooks yet |
| SSRF | Enquiry websites are stored, never fetched; integration hosts come from trusted environment | Administrators must configure safe Ollama/Slack hosts |
| XSS | React escapes enquiry/model text; no raw HTML rendering; framing and content-type headers | CSP allows inline scripts for Next; nonce-based CSP is production work |
| Data loss | PostgreSQL named volume, migration tracking | No automated backups or restore drill; retention/deletion policy not implemented |

The local compose stack binds HTTP ports to `127.0.0.1` and leaves PostgreSQL internal. Set `COOKIE_SECURE=true`, HTTPS `PUBLIC_ORIGIN` and TLS ingress before deployment. Never reuse test credentials. Configuration generation stores the local demo password in an ignored file, not a public README. Set restrictive ACLs and move secrets to a secret manager for production.

External messages can be delivered at most once in the mock transaction. Exactly-once SMTP cannot be promised. A crash after external delivery but before database commit can leave an uncertain state; never blindly reset it to draft. HubSpot upserts contacts by normalized email and does not create remote deals. Slack notifications can be duplicated following a crash because the webhook does not support idempotency.

Production work: isolated asynchronous processing with leases and timeout/backoff policies; automated durable failure recovery; API pagination and large-volume analytics; dependency/security monitoring; per-user auth, MFA, revocation and session rotation; backups; retention and erasure; reliable opt-out/legal copy; email-domain authentication; provider reconciliation; verified live integrations and inbound events. This MVP has no independent penetration-test claim.

## Operational logs

Every request and every caught exception is written to stdout as one JSON
object, carrying a correlation and request identifier. Log context is filtered
by key, and values of known secret environment variables are replaced with
`[redacted]` in both messages and stack traces.

That filtering is not a guarantee. A stack trace can still contain text a
provider chose to put in an exception, including values this application never
configured. Treat the log stream as operator-confidential: it is a different
trust boundary from an API response, where provider errors are replaced with
fixed safe text.

## Configuration

The API refuses to start when configuration is invalid, reporting every problem
at once rather than failing later inside a request. Checks cover secret
lengths, the password-hash format, the public origin, a secure cookie whenever
that origin is https, the orchestration mode, the credentials each selected
provider requires, and the trusted proxy networks. See `app/startup.py`.

## Client addresses and rate limiting

A caller controls every header they send, `X-Forwarded-For` included. In the
default Compose stack Next.js is the edge: nothing in front of it rewrites that
header, so a value arriving there is the caller's claim, not evidence.

The proxy therefore forwards no client address unless
`TRUST_UPSTREAM_FORWARDED_FOR=true`, which is the operator asserting that a
sanitising ingress exists. With it false the API sees only the proxy's socket
peer, every request shares one address, and per-client limiting stays off. That
is weaker than per-address limiting but safe: the alternative is letting a
caller pick the bucket their requests are counted against, which defeats the
limit entirely rather than merely coarsening it.

On the API side a forwarded address is read only when the socket peer is inside
`TRUSTED_PROXY_CIDRS`, and only the right-most entry is used, since that is the
one a single trusted hop appends. Anything further left came from the caller.
