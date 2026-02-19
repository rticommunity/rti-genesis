#!/bin/bash
# ============================================================================
# Launch CodingAgent + Web Interface
#
# Usage:
#   ./run_web.sh [--backend claude|codex] [--port 5080] [--workspace DIR]
#
# This script:
#   1. Sources the virtual environment and .env
#   2. Starts the CodingGenesisAgent in the background
#   3. Waits for DDS discovery
#   4. Starts the web server in the foreground
#   5. Cleans up on exit (SIGINT/SIGTERM)
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Defaults
BACKEND="codex"
PORT=5080
WORKSPACE="$SCRIPT_DIR/workspace"
AGENT_NAME=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --backend)
            BACKEND="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --workspace)
            WORKSPACE="$2"
            shift 2
            ;;
        --agent-name)
            AGENT_NAME="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--backend claude|codex] [--port 5080] [--workspace DIR] [--agent-name NAME]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Set default agent name based on backend
if [ -z "$AGENT_NAME" ]; then
    AGENT_NAME="CodingAgent-${BACKEND}"
fi

# Source environment
if [ -f "$ROOT_DIR/venv/bin/activate" ]; then
    source "$ROOT_DIR/venv/bin/activate"
fi
if [ -f "$ROOT_DIR/.env" ]; then
    source "$ROOT_DIR/.env"
fi

# Ensure workspace exists
mkdir -p "$WORKSPACE"

# Trap to clean up background processes
AGENT_PID=""
cleanup() {
    echo ""
    echo "[run_web] Shutting down..."
    if [ -n "$AGENT_PID" ] && kill -0 "$AGENT_PID" 2>/dev/null; then
        echo "[run_web] Stopping agent (PID $AGENT_PID)..."
        kill "$AGENT_PID" 2>/dev/null
        wait "$AGENT_PID" 2>/dev/null || true
    fi
    echo "[run_web] Done."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo "============================================"
echo "  Genesis CodingAgent — Web Interface"
echo "============================================"
echo "  Backend:   $BACKEND"
echo "  Port:      $PORT"
echo "  Workspace: $WORKSPACE"
echo "  Agent:     $AGENT_NAME"
echo "============================================"
echo ""

# Start CodingGenesisAgent in background
echo "[run_web] Starting CodingGenesisAgent ($BACKEND)..."
python "$SCRIPT_DIR/coding_genesis_agent.py" \
    --backend "$BACKEND" \
    --working-dir "$WORKSPACE" \
    --agent-name "$AGENT_NAME" &
AGENT_PID=$!

# Wait for agent to initialize and DDS discovery
echo "[run_web] Waiting for agent to initialize..."
sleep 4

# Verify agent is running
if ! kill -0 "$AGENT_PID" 2>/dev/null; then
    echo "[run_web] ERROR: Agent process exited unexpectedly."
    exit 1
fi

echo "[run_web] Agent running (PID $AGENT_PID)."
echo ""

# Start web server in foreground
echo "[run_web] Starting web server on http://localhost:$PORT"
echo "[run_web] Press Ctrl+C to stop."
echo ""

python "$SCRIPT_DIR/web_server.py" \
    --port "$PORT" \
    --workspace "$WORKSPACE"
