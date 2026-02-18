#!/usr/bin/env bash
# Launch CodingGenesisAgent (Claude backend) + interactive interface.
#
# Usage:
#   bash run_example.sh                                        # Claude backend (default)
#   bash run_example.sh --backend codex                        # Codex backend
#   bash run_example.sh --timeout 600                          # Custom agent timeout
#   bash run_example.sh --working-dir /path/to/project         # Custom workspace
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
        echo "Stopping CodingGenesisAgent (PID: $agent_pid)..."
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
if [ -f "$ROOT_DIR/venv/bin/activate" ]; then
    source "$ROOT_DIR/venv/bin/activate"
fi
if [ -f "$ROOT_DIR/.env" ]; then
    source "$ROOT_DIR/.env"
fi
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

mkdir -p "$LOG_DIR"

# ── Default workspace directory ──────────────────────────────────
# Claude Code needs a working directory with write permissions.
# Default to workspace/ unless --working-dir is passed explicitly.
WORKSPACE_DIR="$SCRIPT_DIR/workspace"
mkdir -p "$WORKSPACE_DIR"

# Check if --working-dir was already provided in args
HAS_WORKING_DIR=false
for arg in "$@"; do
    if [ "$arg" = "--working-dir" ]; then
        HAS_WORKING_DIR=true
        break
    fi
done

EXTRA_ARGS=()
if [ "$HAS_WORKING_DIR" = false ]; then
    EXTRA_ARGS=("--working-dir" "$WORKSPACE_DIR")
fi

# ── Start agent in background ────────────────────────────────────
echo "Starting CodingGenesisAgent in the background..."
python3 -u "$SCRIPT_DIR/coding_genesis_agent.py" "$@" "${EXTRA_ARGS[@]}" \
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
echo "Starting CodingGenesisInterface..."
echo "Type 'quit' or 'exit' to stop, or press Ctrl+C."
echo ""
python3 "$SCRIPT_DIR/coding_interface.py"

echo "Interface exited. Cleanup via EXIT trap."
