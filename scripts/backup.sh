#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:?Usage: backup.sh BACKUP_DIRECTORY (pause writes first)}"
umask 077
mkdir -p "$DEST"
FILE="$DEST/database_$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose --project-directory "$ROOT" -f "$ROOT/docker-compose.yml" exec -T postgres pg_dump -U creator -d creator_platform -Fc > "$FILE.partial"
mv "$FILE.partial" "$FILE"
docker compose --project-directory "$ROOT" -f "$ROOT/docker-compose.yml" cp backend:/app/backend/storage "$FILE.media"
echo "Database and media backup completed: $FILE"
