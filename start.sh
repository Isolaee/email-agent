#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.pids"

if [ -f "$PID_FILE" ]; then
  echo "Email Agent appears to already be running. Run ./stop.sh first."
  exit 1
fi

echo "=== Email Agent ==="

# Start backend
cd "$SCRIPT_DIR/backend"
if [ ! -d ".venv" ]; then
  echo "Creating Python venv..."
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

fuser -k 8000/tcp 2>/dev/null || true
echo "Starting FastAPI on :8000 ..."
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "Waiting for backend to be ready..."
until curl -s http://localhost:8000/docs > /dev/null 2>&1; do sleep 0.2; done

# Start frontend dev server
cd "$SCRIPT_DIR/frontend"
if [ ! -d "node_modules" ]; then
  echo "Installing frontend deps..."
  npm install
fi

fuser -k 5173/tcp 2>/dev/null || true
echo "Starting React dev server on :5173 ..."
npm run dev &
FRONTEND_PID=$!

echo "$BACKEND_PID $FRONTEND_PID" > "$PID_FILE"

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop, or run ./stop.sh from another terminal."

cleanup() {
  echo ""
  echo "Stopping Email Agent..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  fuser -k 5173/tcp 2>/dev/null || true
  rm -f "$PID_FILE"
}
trap cleanup EXIT
wait
