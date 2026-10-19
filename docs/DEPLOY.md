# Deploying the real stack

The [Vercel edition](VERCEL.md) is a browser simulation with no backend. This
document covers running the actual stack, which needs a host that can run
containers with persistent storage: FastAPI, PostgreSQL, n8n, Next.js and a
reverse proxy that terminates TLS.

**Status: written and locally exercised, not yet run on a live host.** The
Caddy configuration, compose override, and backup and restore scripts are in
the repository and the backup cycle has been verified against the local stack.
Nothing here has been executed on Oracle Cloud. Treat it as a plan to follow,
not a record of a completed deployment.

## Why not Vercel, Render or Fly

Vercel cannot run PostgreSQL, n8n or a long-lived worker. As of October 2026,
Fly.io has no free tier for new accounts, Railway gives $1 of monthly credit
after the first month, and Render's free PostgreSQL expires 30 days after
creation. Oracle Cloud's Always Free tier is the only one that runs this stack
persistently at no cost, though its ARM allowance was reduced in 2026 from
4 OCPU / 24 GB to **2 OCPU / 12 GB**, which is still far more than this needs.

Rough footprint: PostgreSQL ~200 MB, FastAPI ~150 MB, Next.js ~150 MB,
n8n ~400 MB. Under 1 GB in total.

## Prerequisites

- An Oracle Cloud account with an Always Free `VM.Standard.A1.Flex` instance.
  A1 capacity is frequently unavailable in popular regions; expect to retry.
- A domain name pointing an A record at the instance's public IP. Caddy obtains
  a certificate over HTTP, so port 80 must reach it. A bare IP will not work.
- The instance is ARM. All base images used here are multi-architecture, but
  the build has not been run on arm64, so budget time for a first build.

## Host preparation

```sh
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker "$USER" && newgrp docker
```

**Open the ports in two places.** This is the step people miss. Allowing 80 and
443 in the Oracle security list is not enough: Oracle's Ubuntu images also ship
`iptables` rules that reject everything else, so the traffic is dropped inside
the instance even when the cloud firewall allows it.

```sh
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

On an Oracle Linux image use `firewall-cmd --add-service=http --add-service=https --permanent` instead. Confirm from
outside the instance before continuing; a TLS certificate request that cannot
reach port 80 fails in a way that looks like a Caddy problem.

## Configure and start

```sh
git clone https://github.com/omarelweeshy/clientflow-ai.git
cd clientflow-ai
python3 scripts/configure.py
```

Then edit `.env` for a public deployment. These differ from the local demo:

| Setting | Value | Why |
|---|---|---|
| `PUBLIC_ORIGIN` | `https://your.domain` | The API rejects a login whose `Origin` does not match it exactly |
| `COOKIE_SECURE` | `true` | Required; startup refuses to run with an https origin and a non-secure cookie |
| `DOMAIN` | `your.domain` | Read by Caddy for the certificate |
| `TRUSTED_PROXY_CIDRS` | leave the default | Lets the API accept the address Caddy asserts |

Leave `LLM_PROVIDER`, `CRM_PROVIDER` and `EMAIL_PROVIDER` on their mock values
until a live provider has actually been tested. The startup check will refuse
to boot if a provider is selected without its credentials.

```sh
docker compose -f compose.yaml -f deploy/compose.prod.yaml up --build -d
docker compose exec -T api python -m app.seed   # fictional demo data, optional
```

The administrator password is in `local-secrets/admin-password.txt`.

## What the proxy chain does

Caddy is the only service on a public interface. The base compose file binds
api, web and n8n to `127.0.0.1`, which is not reachable from outside the host,
so those bindings are kept for debugging on the VM.

The security-critical line is in `deploy/Caddyfile`:

```
header_up X-Forwarded-For {remote_host}
```

Caddy's default is to *append* the peer address to whatever the caller sent, so
a caller supplying `X-Forwarded-For: 1.2.3.4` would produce
`1.2.3.4, <real peer>`. The Next.js proxy reads the left-most entry, so the
caller would be choosing the address their rate limit is counted against.
Setting the header replaces it, which is what makes this a sanitising ingress,
and that is the condition `TRUST_UPSTREAM_FORWARDED_FOR=true` asserts. See
[security model](SECURITY.md).

**n8n is not exposed.** Reach its editor through an SSH tunnel:

```sh
ssh -N -L 5678:127.0.0.1:5678 ubuntu@your.instance.ip
```

## Backups

```sh
sh scripts/backup.sh /var/backups/clientflow
sh scripts/restore.sh /var/backups/clientflow/<timestamp> --verify
```

`backup.sh` dumps the database and the n8n volume. `restore.sh --verify` replays
the dump into a throwaway container and prints row counts, without touching the
running stack. `--apply` overwrites the live database and asks for confirmation
first.

Run the verify step on a schedule, not just the backup. A backup that has never
been restored is an assumption.

```
15 3 * * *  cd /home/ubuntu/clientflow-ai && sh scripts/backup.sh /var/backups/clientflow
30 3 * * 0  cd /home/ubuntu/clientflow-ai && sh scripts/restore.sh "$(ls -d /var/backups/clientflow/*/ | tail -1)" --verify
```

The n8n archive is useless without the matching `N8N_ENCRYPTION_KEY` from
`.env`, which is deliberately not in the backup. Store that key separately, or
the workflow credentials cannot be decrypted.

## After deploying

Still open before this could be called production operated:

- No live email, CRM or model provider has been verified end to end.
- No metrics or alerting. Structured logs exist; nothing watches them.
- No load testing.
- `/admin/leads` returns up to 1000 rows without pagination.
- Log rotation for the container logs is not configured; Caddy's own access log
  rotates at 10 MiB.
