#!/usr/bin/env bash

# Test DDS durability for the Interface by starting it first, waiting,
# then launching rtiddsspy as a late joiner.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

INTERFACE_SCRIPT="$ROOT_DIR/run_scripts/helpers/interface_keepalive.py"
IFACE_LOG="$LOG_DIR/interface_durable_test.log"
SPY_LOG="$LOG_DIR/rtiddsspy_interface_durable_test.log"

IFACE_PID=""
SPY_PID=""

cleanup() {
  echo "[cleanup] stopping processes..."
  if [[ -n "${SPY_PID}" ]]; then kill ${SPY_PID} 2>/dev/null || true; wait ${SPY_PID} 2>/dev/null || true; fi
  if [[ -n "${IFACE_PID}" ]]; then kill ${IFACE_PID} 2>/dev/null || true; wait ${IFACE_PID} 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

# Pre-create logs so tail works
: > "$IFACE_LOG"; : > "$SPY_LOG"

PY="python3"; command -v python3 >/dev/null 2>&1 || PY="python"

echo "[start] launching interface..."
PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}" "$PY" "$INTERFACE_SCRIPT" > "$IFACE_LOG" 2>&1 &
IFACE_PID=$!
echo "[start] interface PID=$IFACE_PID (log: $IFACE_LOG)"

echo "[wait] sleeping 10s before starting rtiddsspy (late joiner)..."
sleep 10

if [[ -z "${NDDSHOME:-}" ]]; then echo "ERROR: NDDSHOME not set" >&2; exit 1; fi

TIMEOUT_TOOL=""; command -v timeout >/dev/null 2>&1 && TIMEOUT_TOOL="timeout 10s" || true
if [[ -z "$TIMEOUT_TOOL" ]] && command -v gtimeout >/dev/null 2>&1; then TIMEOUT_TOOL="gtimeout 10s"; fi

echo "[start] launching rtiddsspy (-printSample -useFirstPublicationQos)..."
if [[ -n "$TIMEOUT_TOOL" ]]; then
  bash -c "$TIMEOUT_TOOL \"$NDDSHOME/bin/rtiddsspy\" -printSample -useFirstPublicationQos" > "$SPY_LOG" 2>&1 &
  SPY_PID=$!
else
  "$NDDSHOME/bin/rtiddsspy" -printSample -useFirstPublicationQos > "$SPY_LOG" 2>&1 &
  SPY_PID=$!
  ( sleep 10; kill ${SPY_PID} 2>/dev/null || true ) &
fi
echo "[start] spy PID=$SPY_PID (log: $SPY_LOG)"

echo "[wait] sleeping 10s of overlap..."
sleep 10

echo "[stop] stopping processes and printing log tails..."
cleanup

echo "==== rtiddsspy (tail 200) ===="
tail -n 200 "$SPY_LOG" || true
echo "==== interface (tail 200) ===="
tail -n 200 "$IFACE_LOG" || true

echo "[done] logs are in $LOG_DIR"

