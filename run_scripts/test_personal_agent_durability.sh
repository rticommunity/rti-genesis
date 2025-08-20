#!/usr/bin/env bash

# Test DDS durability by simulating a late-joining spy.
# - Start the PersonalAssistant agent
# - Wait 10 seconds
# - Start rtiddsspy with -printSample -useFirstPublicationQos
#   with a timeout to avoid indefinite run (preferred) [[memory:3593300]]
# - Wait 10 seconds and stop

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

AGENT_SCRIPT="$ROOT_DIR/agents/personal_assistant.py"
AGENT_LOG="$LOG_DIR/personal_agent_durable_test.log"
SPY_LOG="$LOG_DIR/rtiddsspy_durable_test.log"

AGENT_PID=""
SPY_PID=""

cleanup() {
  echo "[cleanup] stopping processes..."
  if [[ -n "${SPY_PID}" ]]; then kill ${SPY_PID} 2>/dev/null || true; wait ${SPY_PID} 2>/dev/null || true; fi
  if [[ -n "${AGENT_PID}" ]]; then kill ${AGENT_PID} 2>/dev/null || true; wait ${AGENT_PID} 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

echo "[start] launching PersonalAssistant..."
# Pre-create logs so tail always succeeds even if processes exit early
: > "$AGENT_LOG"
: > "$SPY_LOG"

# Choose python interpreter
PYTHON_BIN="python3"
if ! command -v python3 >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then PYTHON_BIN="python"; else echo "ERROR: python interpreter not found" >&2; exit 1; fi
fi

PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}" "$PYTHON_BIN" "$AGENT_SCRIPT" > "$AGENT_LOG" 2>&1 &
AGENT_PID=$!
echo "[start] agent PID=$AGENT_PID (log: $AGENT_LOG)"

echo "[wait] sleeping 10s before starting rtiddsspy (late joiner)..."
sleep 10

if [[ -z "${NDDSHOME:-}" ]]; then
  echo "ERROR: NDDSHOME is not set. Please export NDDSHOME to your RTI Connext installation." >&2
  exit 1
fi

# Prefer a command-line timeout if available; otherwise, run in background and stop later.
TIMEOUT_TOOL=""
if command -v timeout >/dev/null 2>&1; then
  TIMEOUT_TOOL="timeout 10s"
elif command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_TOOL="gtimeout 10s"
fi

echo "[start] launching rtiddsspy (-printSample -useFirstPublicationQos)..."
if [[ -n "$TIMEOUT_TOOL" ]]; then
  # Runs with a command-line timeout as preferred [[memory:3593300]]
  bash -c "$TIMEOUT_TOOL \"$NDDSHOME/bin/rtiddsspy\" -printSample -useFirstPublicationQos" > "$SPY_LOG" 2>&1 &
  SPY_PID=$!
else
  # Fallback: run in background and stop manually after 10s
  "$NDDSHOME/bin/rtiddsspy" -printSample -useFirstPublicationQos > "$SPY_LOG" 2>&1 &
  SPY_PID=$!
  ( sleep 10; kill ${SPY_PID} 2>/dev/null || true ) &
fi
echo "[start] rtiddsspy PID=$SPY_PID (log: $SPY_LOG)"

echo "[wait] sleeping 10s of overlap..."
sleep 10

echo "[stop] stopping processes and printing log tails..."
cleanup

echo "==== rtiddsspy (tail 200) ===="
tail -n 200 "$SPY_LOG" || true
echo "==== agent (tail 200) ===="
tail -n 200 "$AGENT_LOG" || true

echo "[done] logs are in $LOG_DIR"


