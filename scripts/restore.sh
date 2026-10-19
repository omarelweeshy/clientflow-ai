#!/bin/sh
# Restore a backup produced by scripts/backup.sh, or verify one without touching
# the running stack.
#
#   sh scripts/restore.sh <backup-directory> --verify   restore into a throwaway
#                                                       container and report counts
#   sh scripts/restore.sh <backup-directory> --apply    overwrite the live database
#
# --verify is the one to run regularly. It proves the dump actually loads, which
# is the only thing that makes a backup worth having.

set -eu

DIR=${1:?Usage: restore.sh <backup-directory> [--verify|--apply]}
MODE=${2:---verify}
PROJECT=${COMPOSE_PROJECT_NAME:-clientflow-ai}
DUMP="$DIR/clientflow.dump"

[ -f "$DUMP" ] || { echo "No clientflow.dump in $DIR"; exit 1; }

case "$MODE" in
--verify)
    NAME="clientflow-restore-check-$$"
    echo "Starting a throwaway PostgreSQL to replay the dump into"
    docker run -d --name "$NAME" \
        -e POSTGRES_USER=clientflow -e POSTGRES_PASSWORD=verify-only \
        -e POSTGRES_DB=clientflow postgres:17-alpine >/dev/null
    # shellcheck disable=SC2064
    trap "docker rm -f $NAME >/dev/null 2>&1 || true" EXIT INT TERM

    i=0
    while [ "$i" -lt 30 ]; do
        docker exec "$NAME" pg_isready -U clientflow -d clientflow >/dev/null 2>&1 && break
        i=$((i + 1))
        sleep 2
    done

    docker exec -i "$NAME" pg_restore -U clientflow -d clientflow --clean --if-exists < "$DUMP"
    echo "Restored. Row counts:"
    docker exec "$NAME" psql -U clientflow -d clientflow -t -c \
        "SELECT 'leads=' || (SELECT count(*) FROM leads)
             || ' messages=' || (SELECT count(*) FROM messages)
             || ' runs=' || (SELECT count(*) FROM runs)
             || ' audit=' || (SELECT count(*) FROM audit_entries)
             || ' schema=' || (SELECT version_num FROM alembic_version);"
    echo "Verification passed: the dump loads and the expected tables are present."
    ;;
--apply)
    printf 'This overwrites the live database in %s-db-1. Type the project name to confirm: ' "$PROJECT"
    read -r answer
    [ "$answer" = "$PROJECT" ] || { echo "Not confirmed, nothing changed."; exit 1; }
    echo "Stopping the services that write to the database"
    docker stop "${PROJECT}-api-1" "${PROJECT}-n8n-1" >/dev/null 2>&1 || true
    docker exec -i "${PROJECT}-db-1" pg_restore -U clientflow -d clientflow --clean --if-exists < "$DUMP"
    docker start "${PROJECT}-api-1" "${PROJECT}-n8n-1" >/dev/null 2>&1 || true
    echo "Restored. Check the dashboard and docker logs ${PROJECT}-api-1."
    ;;
*)
    echo "Unknown mode $MODE. Use --verify or --apply."
    exit 1
    ;;
esac
