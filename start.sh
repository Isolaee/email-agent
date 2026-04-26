#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Email Agent ==="

# Start backend
cd "$SCRIPT_DIR/backend"
if [ ! -d ".venv" ]; then
  echo "Creating Python venv..."
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

echo "Starting FastAPI on :8000 ..."
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start frontend dev server
cd "$SCRIPT_DIR/frontend"
if [ ! -d "node_modules" ]; then
  echo "Installing frontend deps..."
  npm install
fi

echo "Starting React dev server on :5173 ..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173  (accessible on LAN)"
echo ""
echo "Press Ctrl+C to stop both."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
