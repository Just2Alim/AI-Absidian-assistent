#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

if ! .venv/bin/python -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  .venv/bin/pip install -r backend/requirements.txt
fi

if [ ! -d "node_modules" ]; then
  npm install
fi

cleanup() {
  trap - INT TERM EXIT
  if [ -n "${BACKEND_PID:-}" ]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [ -n "${FRONTEND_PID:-}" ]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
}
trap cleanup INT TERM EXIT

.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8765 &
BACKEND_PID=$!

npm run dev &
FRONTEND_PID=$!

echo "Backend:  http://localhost:8765"
echo "Frontend: http://localhost:5173"
echo "Phone:    http://$(ipconfig getifaddr en0 2>/dev/null || echo '<mac-ip>'):5173"
echo "Press Ctrl+C to stop."

wait
