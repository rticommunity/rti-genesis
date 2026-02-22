#!/usr/bin/env bash
# Launch PersistentMemoryAgent + Telegram bot interface.
#
# Usage:
#   bash run_telegram.sh
#   bash run_telegram.sh --config config/telegram_config.json
#   bash run_telegram.sh --verbose
#
# The agent runs in the background; the bot runs in the foreground.
# Press Ctrl+C to stop.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"

agent_pid=""
BOT_ARGS=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        *)
            BOT_ARGS+=("$1")
            shift
            ;;
    esac
done

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

# ── Check for Telegram Bot Token ─────────────────────────────────
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  TELEGRAM BOT SETUP (one-time)"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "  1. Open Telegram and search for @BotFather"
    echo "  2. Send /newbot and follow the prompts to create a bot"
    echo "  3. Copy the bot token (looks like: 123456:ABC-DEF...)"
    echo "  4. Add to your .env file:"
    echo "     echo 'TELEGRAM_BOT_TOKEN=your-token-here' >> $ROOT_DIR/.env"
    echo "  5. Re-run this script"
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    exit 1
fi

echo "═══════════════════════════════════════════════════════════"
echo "  Genesis Telegram Bot Interface"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ── Start agent in background ────────────────────────────────────
echo "Starting PersistentMemoryAgent in the background..."
python3 -u "$ROOT_DIR/examples/PersistentMemory/persistent_memory_agent.py" \
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

# ── Start Telegram bot in foreground ─────────────────────────────
echo ""
echo "Starting Telegram bot..."
echo "Press Ctrl+C to stop."
echo ""
python3 "$SCRIPT_DIR/telegram_interface.py" ${BOT_ARGS[@]+"${BOT_ARGS[@]}"}

echo "Bot exited. Cleanup via EXIT trap."
