#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

export PYTHONUNBUFFERED=1
export GENESIS_DOMAIN="${GENESIS_DOMAIN:-0}"

# Args: -t <seconds> optional timeout, -p <port> server port (default 5080)
DURATION_SECONDS=""
SERVER_PORT="5080"
usage() {
  echo "Usage: $0 [-t seconds] [-p port]" >&2
}
while getopts ":t:p:h" opt; do
  case "$opt" in
    t) DURATION_SECONDS="$OPTARG" ;;
    p) SERVER_PORT="$OPTARG" ;;
    h) usage; exit 0 ;;
    \?) echo "Invalid option: -$OPTARG" >&2; usage; exit 1 ;;
    :) echo "Option -$OPTARG requires an argument." >&2; usage; exit 1 ;;
  esac
done

cd "$ROOT_DIR"

PIDS=()
cleanup() {
  echo "\n[cleanup] Stopping background processes..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup INT TERM EXIT

echo "[start] GraphInterface server (PORT=$SERVER_PORT)"
PORT="$SERVER_PORT" python examples/GraphInterface/server.py > "$LOG_DIR/server.log" 2>&1 &
PIDS+=("$!")

echo "[start] PersonalAssistant agent"
GENESIS_TRACE_AGENTS=1 python examples/MultiAgent/agents/personal_assistant.py > "$LOG_DIR/personal_assistant.log" 2>&1 &
PIDS+=("$!")

echo "[start] WeatherAgent"
GENESIS_TRACE_AGENTS=1 python examples/MultiAgent/agents/weather_agent.py > "$LOG_DIR/weather_agent.log" 2>&1 &
PIDS+=("$!")

echo "[start] CalculatorService"
python test_functions/calculator_service.py > "$LOG_DIR/calculator_service.log" 2>&1 &
PIDS+=("$!")

echo "\nOpen http://localhost:$SERVER_PORT/"
echo "Logs in $LOG_DIR"

if [[ -n "${DURATION_SECONDS}" ]]; then
  echo "Running for ${DURATION_SECONDS}s... (Ctrl+C to stop earlier)"
  sleep "${DURATION_SECONDS}" || true
else
  echo "Press Ctrl+C to stop. Waiting on server..."
  wait "${PIDS[0]}" || true
fi


