#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="${1:?Usage: restore.sh DATABASE_DUMP (restore into an empty database)}"
test -f "$FILE"
docker compose --project-directory "$ROOT" -f "$ROOT/docker-compose.yml" exec -T postgres pg_restore --exit-on-error --no-owner -U creator -d creator_platform < "$FILE"
echo "Database restored. Restore the matching media backup separately before resuming writes."
