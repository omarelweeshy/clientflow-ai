#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then python3 scripts/configure.py; fi
docker compose up --build -d --wait --wait-timeout 180
docker compose exec -T api python -m app.seed
docker compose exec -T n8n n8n import:workflow --separate --input=/workflows
for workflow_id in clientflow01 clientflow02 clientflow03 clientflow04 clientflow05; do
  docker compose exec -T n8n n8n publish:workflow --id="$workflow_id"
done
docker compose restart n8n
echo 'Demo ready: http://localhost:3010/login'
echo 'Read your generated password from local-secrets/admin-password.txt.'
