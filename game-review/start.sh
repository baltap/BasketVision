#!/bin/bash
# Start the app on http://localhost:8000 (serves the built UI and the API). Everything stays on this computer.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${GAME_REVIEW_PYTHON:-/Users/peter/Data/Claude/BasketVision/basketball-poc/_work/venv/bin/python}"
if [ ! -d "$HERE/frontend/dist" ]; then
  echo "Building the UI first..."
  (cd "$HERE/frontend" && pnpm install --frozen-lockfile && pnpm build)
fi
if lsof -i :8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8000 is already in use, probably another copy of this app." >&2
  echo "Open http://localhost:8000 to use it, or stop it first: lsof -i :8000" >&2
  exit 1
fi
cd "$HERE/backend"
echo "Open http://localhost:8000"
exec "$PYTHON" -I -m uvicorn app:app --host 127.0.0.1 --port 8000
