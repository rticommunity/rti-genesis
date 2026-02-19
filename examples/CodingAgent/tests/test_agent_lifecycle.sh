#!/usr/bin/env bash
# DDS lifecycle test: start agent, verify alive, send SIGTERM, verify clean exit.
# Requires DDS environment (source venv/bin/activate && source .env).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(cd "$AGENT_DIR/../.." && pwd)"

# Activate environment
if [ -f "$ROOT_DIR/venv/bin/activate" ]; then
    source "$ROOT_DIR/venv/bin/activate"
fi
if [ -f "$ROOT_DIR/.env" ]; then
    source "$ROOT_DIR/.env"
fi
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/lifecycle_test.log"

echo "=== Agent lifecycle test ==="
echo "Starting CodingGenesisAgent in background..."

python "$AGENT_DIR/coding_genesis_agent.py" --backend claude --timeout 30 \
    > "$LOG_FILE" 2>&1 &
AGENT_PID=$!

echo "Agent PID: $AGENT_PID"

# Wait for agent to initialize (DDS discovery takes a few seconds)
echo "Waiting 8s for DDS discovery..."
sleep 8

# Verify process is alive
if kill -0 "$AGENT_PID" 2>/dev/null; then
    echo "PASS: Agent process is alive"
else
    echo "FAIL: Agent process died during startup"
    cat "$LOG_FILE"
    exit 1
fi

# Send SIGTERM for clean shutdown
echo "Sending SIGTERM..."
kill -TERM "$AGENT_PID" 2>/dev/null || true

# Wait for clean exit (up to 10s)
WAIT_COUNT=0
while kill -0 "$AGENT_PID" 2>/dev/null && [ $WAIT_COUNT -lt 10 ]; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

if kill -0 "$AGENT_PID" 2>/dev/null; then
    echo "FAIL: Agent did not exit within 10s, force killing"
    kill -9 "$AGENT_PID" 2>/dev/null || true
    exit 1
else
    wait "$AGENT_PID" 2>/dev/null || true
    echo "PASS: Agent exited cleanly"
fi

echo "=== Agent lifecycle test complete ==="
