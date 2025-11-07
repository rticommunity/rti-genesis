#!/bin/bash

# test_monitoring.sh - A script to test monitoring functionality
# This script starts the monitoring test and example agent with functions

# Set strict error handling
set -e

# Configuration
TIMEOUT=60  # Outer wrapper uses 60s; keep in sync with triage
MONITOR_TIMEOUT=$((TIMEOUT-10)) # Ensure our monitor exits before outer timeout
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_DIR="$SCRIPT_DIR/../logs"
DEBUG=${DEBUG:-false}  # Set to true to show debug output
mkdir -p "$LOG_DIR"

# Get the project root directory
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
[ "$DEBUG" = "true" ] && echo "Project root: $PROJECT_ROOT"
echo "Environment: PYTHON=$(command -v python), NDDSHOME=${NDDSHOME:-unset}"

# Change to tests directory
cd "$SCRIPT_DIR"
[ "$DEBUG" = "true" ] && echo "Changed to directory: $(pwd)"

# Initialize array to store PIDs
declare -a pids=()

# Function to display log content on failure
display_log_on_failure() {
    local log_file=$1
    local error_type=$2
    local error_message=$3
    
    echo "❌ ERROR: $error_message"
    echo "=================================================="
    echo "Log file contents ($log_file):"
    echo "=================================================="
    tail -n 20 "$log_file" | sed 's/^/  /'
    echo "=================================================="
    echo "Full log available at: $log_file"
    echo "=================================================="
}

# Function to cleanup processes
cleanup() {
    [ "$DEBUG" = "true" ] && echo "Cleaning up processes..."
    for pid in "${pids[@]}"; do
        if ps -p "$pid" > /dev/null; then
            kill "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null || true
        fi
    done
    # PARALLEL-SAFE: Only kill processes tracked by PID, no broad pkill
    # The pkill commands below are REMOVED to prevent killing other parallel tests
}

# Set up trap for cleanup on script termination
# Diagnostic tailer
tail_diagnostics() {
  echo "--- diagnostics: test_monitoring.log ---"; [ -f "$LOG_DIR/test_monitoring.log" ] && tail -n 80 "$LOG_DIR/test_monitoring.log" || echo "(missing)"; echo "--- end ---"
  echo "--- diagnostics: test_agent.log ---"; [ -f "$LOG_DIR/test_agent.log" ] && tail -n 80 "$LOG_DIR/test_agent.log" || echo "(missing)"; echo "--- end ---"
  for i in 1 2 3; do f="$LOG_DIR/calculator_service_${i}.log"; echo "--- diagnostics: ${f} ---"; [ -f "$f" ] && tail -n 80 "$f" || echo "(missing)"; echo "--- end ---"; done
  echo "--- diagnostics: rtiddsspy sweep ---"; [ -f "$SPY_LOG" ] && tail -n 80 "$SPY_LOG" || echo "(missing)"; echo "--- end ---"
}

on_timeout_term() {
  echo "❌ Monitoring wrapper received termination (likely outer timeout). Emitting diagnostics before exit."
  tail_diagnostics
  exit 124
}

trap cleanup EXIT
trap on_timeout_term SIGTERM SIGINT

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ ERROR: OPENAI_API_KEY environment variable is not set"
    echo "Please set your OpenAI API key before running this test"
    exit 1
fi

# Resolve and validate script paths
CALC_SCRIPT="$PROJECT_ROOT/test_functions/services/calculator_service.py"
MONITOR_HELPER="$PROJECT_ROOT/tests/helpers/test_monitoring.py"
AGENT_HELPER="$PROJECT_ROOT/tests/helpers/test_agent.py"

echo "Starting monitoring test..."
[ "$DEBUG" = "true" ] && echo "Logs will be saved to $LOG_DIR"
echo "Paths:"
echo "  CALC_SCRIPT = $CALC_SCRIPT"
echo "  MONITOR_HELPER = $MONITOR_HELPER"
echo "  AGENT_HELPER = $AGENT_HELPER"
for p in "$CALC_SCRIPT" "$MONITOR_HELPER" "$AGENT_HELPER"; do
  if [ ! -f "$p" ]; then
    echo "❌ ERROR: Expected path not found: $p"
    exit 2
  fi
done

# Start multiple calculator services in the background
echo "Starting calculator services..."
echo "Launching calculator service from: $CALC_SCRIPT"
for i in {1..3}; do
    PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT python "$CALC_SCRIPT" > "$LOG_DIR/calculator_service_$i.log" 2>&1 &
    CALC_PID=$!
    pids+=("$CALC_PID")
    echo "Started calculator service $i with PID $CALC_PID (log: $LOG_DIR/calculator_service_$i.log)"
done

# Wait for services to start
echo "Waiting for services to start..."
sleep 10

# Start the monitoring test in the background (with timeout)
echo "Starting monitoring test (timeout ${MONITOR_TIMEOUT}s) from: $MONITOR_HELPER"
PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT timeout $MONITOR_TIMEOUT python "$MONITOR_HELPER" > "$LOG_DIR/test_monitoring.log" 2>&1 &
MONITOR_PID=$!
pids+=("$MONITOR_PID")
echo "Started monitoring test with PID $MONITOR_PID"

# Wait a moment for the monitor to start
sleep 2

# Start example agent 1 with functions
echo "Starting test agent with functions from: $AGENT_HELPER"
PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT python "$AGENT_HELPER" "Can you add 424242 and 111111?" > "$LOG_DIR/test_agent.log" 2>&1 &
AGENT_PID=$!
pids+=("$AGENT_PID")
echo "Started test agent with PID $AGENT_PID"

# Optional DDS writer sweep to confirm components are alive
SPY_LOG="$LOG_DIR/rtiddsspy_monitoring_sweep.log"
if [ -z "${RTIDDSSPY_BIN:-}" ]; then
  if [ -n "${RTI_BIN_DIR:-}" ] && [ -x "${RTI_BIN_DIR}/rtiddsspy" ]; then
    RTIDDSSPY_BIN="${RTI_BIN_DIR}/rtiddsspy"
  elif [ -n "${NDDSHOME:-}" ] && [ -x "${NDDSHOME}/bin/rtiddsspy" ]; then
    RTIDDSSPY_BIN="${NDDSHOME}/bin/rtiddsspy"
  else
    RTIDDSSPY_BIN=""
  fi
fi

if [ -n "$RTIDDSSPY_BIN" ]; then
  echo "Running DDS writer sweep (advisory, -printSample only)..."
  rm -f "$SPY_LOG"
  TOPICS=(
    'Advertisement'
    'rti/connext/genesis/rpc/CalculatorServiceRequest' 'rti/connext/genesis/rpc/CalculatorServiceReply'
    'MonitoringEvent' 'ChainEvent'
  )
  # Prefer qos file if present
  QOS_ARGS=()
  if [ -f "$PROJECT_ROOT/spy_transient.xml" ]; then
    QOS_ARGS=( -qosFile "$PROJECT_ROOT/spy_transient.xml" -qosProfile SpyLib::TransientReliable )
  fi
  # Run in background (no -duration flag), stop after a short window
  "$RTIDDSSPY_BIN" -printSample "${QOS_ARGS[@]}" $(printf -- " -topic %q" "${TOPICS[@]}") > "$SPY_LOG" 2>&1 &
  SPY_PID=$!
  ( sleep 6; kill $SPY_PID 2>/dev/null || true ) &
  wait $SPY_PID 2>/dev/null || true
  if grep -E "New writer|SAMPLE for topic" "$SPY_LOG" >/dev/null 2>&1; then
    echo "DDS sweep: activity detected (see $SPY_LOG)."
  else
    echo "DDS sweep: no activity detected on target topics (see $SPY_LOG)."
  fi
else
  echo "DDS sweep skipped: rtiddsspy not found (NDDSHOME/RTI_BIN_DIR)."
fi

# Wait for the monitoring test to complete
echo "Waiting for monitoring test to complete..."
wait $MONITOR_PID || true
EXIT_CODE=$?

# Check the exit code
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Monitoring test completed successfully!"
else
    if [ $EXIT_CODE -eq 124 ]; then
        echo "❌ Monitoring test timed out after ${TIMEOUT}s (exit 124)"
    else
        echo "❌ Monitoring test failed with exit code $EXIT_CODE"
    fi
    # Tail primary and related logs for diagnostics
    display_log_on_failure "$LOG_DIR/test_monitoring.log" "test_failure" "Monitoring test failed or timed out"
    tail_diagnostics
    exit 1
fi

# Exit with success
exit 0 
