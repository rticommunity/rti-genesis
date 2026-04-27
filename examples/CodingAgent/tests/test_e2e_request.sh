#!/usr/bin/env bash
# End-to-end test: start agent, send RPC request, verify response.
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

echo "=== E2E request test ==="

# Start agent in background
echo "Starting CodingGenesisAgent..."
python "$AGENT_DIR/coding_genesis_agent.py" --backend claude --timeout 120 \
    > "$LOG_DIR/e2e_agent.log" 2>&1 &
AGENT_PID=$!
echo "Agent PID: $AGENT_PID"

cleanup() {
    echo "Cleaning up agent (PID $AGENT_PID)..."
    kill -TERM "$AGENT_PID" 2>/dev/null || true
    sleep 2
    kill -9 "$AGENT_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Wait for DDS discovery
echo "Waiting 10s for DDS discovery..."
sleep 10

# Verify agent is still running
if ! kill -0 "$AGENT_PID" 2>/dev/null; then
    echo "FAIL: Agent died during startup"
    cat "$LOG_DIR/e2e_agent.log"
    exit 1
fi

# Run E2E client
echo "Running E2E client..."
python "$SCRIPT_DIR/e2e_client.py"
E2E_EXIT=$?

echo "=== E2E request test complete (exit: $E2E_EXIT) ==="
exit $E2E_EXIT
