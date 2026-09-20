#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/backend/.venv/bin/python}"
"$PYTHON" "$ROOT/backend/start.py" &
backend_pid=$!
npm --prefix "$ROOT/frontend" run dev &
frontend_pid=$!
cleanup() { kill "$backend_pid" "$frontend_pid" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
wait -n "$backend_pid" "$frontend_pid"
