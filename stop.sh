#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.pids"

if [ ! -f "$PID_FILE" ]; then
  echo "Email Agent does not appear to be running (no .pids file)."
  exit 0
fi

read -r BACKEND_PID FRONTEND_PID < "$PID_FILE"
echo "Stopping Email Agent (pids: $BACKEND_PID $FRONTEND_PID)..."
kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
fuser -k 5173/tcp 2>/dev/null || true

# Wait for processes to exit
for pid in "$BACKEND_PID" "$FRONTEND_PID"; do
  for _ in $(seq 1 10); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.3
  done
  kill -9 "$pid" 2>/dev/null || true
done

rm -f "$PID_FILE"
echo "Stopped."
