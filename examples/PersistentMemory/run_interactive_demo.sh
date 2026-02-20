#!/usr/bin/env bash
# Launch PersistentMemoryAgent + interactive interface.
#
# Usage:
#   bash run_interactive_demo.sh                                      # SQLite (default)
#   bash run_interactive_demo.sh --config config/enterprise_memory.json  # PostgreSQL
#   bash run_interactive_demo.sh --model claude-sonnet-4-20250514       # Choose model
#
# The agent runs in the background; the interface runs in the foreground.
# Press Ctrl+C or type 'quit' to stop.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"

agent_pid=""

# ── Cleanup ──────────────────────────────────────────────────────
cleanup() {
    echo ""
    echo "Initiating shutdown..."

    if [ -n "$agent_pid" ]; then
        echo "Stopping PersistentMemoryAgent (PID: $agent_pid)..."
        if kill "$agent_pid" > /dev/null 2>&1; then
            wait "$agent_pid" 2>/dev/null
            echo "Agent stopped."
        else
            echo "Agent (PID: $agent_pid) already stopped."
        fi
    fi

    echo "Agent log: $LOG_DIR/agent.log"
    echo "Cleanup complete."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# ── Environment ──────────────────────────────────────────────────
if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
    source "$ROOT_DIR/.venv/bin/activate"
elif [ -f "$ROOT_DIR/venv/bin/activate" ]; then
    source "$ROOT_DIR/venv/bin/activate"
fi
if [ -f "$ROOT_DIR/.env" ]; then
    source "$ROOT_DIR/.env"
fi
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

mkdir -p "$LOG_DIR"

# ── Start agent in background ────────────────────────────────────
echo "Starting PersistentMemoryAgent in the background..."
python3 -u "$SCRIPT_DIR/persistent_memory_agent.py" "$@" \
    > "$LOG_DIR/agent.log" 2>&1 &
agent_pid=$!
echo "Agent PID: $agent_pid (log: $LOG_DIR/agent.log)"

# Wait for DDS discovery
echo "Waiting for DDS discovery (5s)..."
sleep 5

# Verify agent is still running
if ! kill -0 "$agent_pid" 2>/dev/null; then
    echo "ERROR: Agent exited during startup. Check $LOG_DIR/agent.log"
    cat "$LOG_DIR/agent.log"
    exit 1
fi

# ── Start interface in foreground ────────────────────────────────
echo "Starting PersistentMemoryInterface..."
echo "Type 'quit' or 'exit' to stop, or press Ctrl+C."
echo ""
python3 "$SCRIPT_DIR/memory_interface.py"

echo "Interface exited. Cleanup via EXIT trap."
