#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/backend/.venv/bin/python}"
"$PYTHON" -m alembic -c "$ROOT/backend/alembic.ini" upgrade head
