#!/bin/bash
# test_monitoring_complete.sh - Comprehensive monitoring coverage test
# Verifies ALL monitoring features: nodes, edges (agent→agent, agent→service, service→function), and chain events

set -e

TIMEOUT=90
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_DIR="$SCRIPT_DIR/../logs"
DEBUG=${DEBUG:-false}
mkdir -p "$LOG_DIR"

PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
[ "$DEBUG" = "true" ] && echo "Project root: $PROJECT_ROOT"

cd "$SCRIPT_DIR"

# Array to store PIDs
declare -a pids=()

cleanup() {
    [ "$DEBUG" = "true" ] && echo "Cleaning up monitoring test processes..."
    for pid in "${pids[@]}"; do
        if ps -p "$pid" > /dev/null 2>&1; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
    # PARALLEL-SAFE: Only kill processes tracked by PID, no broad pkill
    # The pkill commands below are REMOVED to prevent killing other parallel tests
}

trap cleanup EXIT

echo "=================================================="
echo "Running comprehensive monitoring coverage test..."
echo "=================================================="

# Start the comprehensive monitoring test FIRST (it needs to start before agents to catch all events)
MONITOR_SCRIPT="$PROJECT_ROOT/tests/monitoring/test_complete_monitoring_coverage.py"
echo "Starting monitoring verifier from: $MONITOR_SCRIPT"
PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT timeout $TIMEOUT python "$MONITOR_SCRIPT" > "$LOG_DIR/test_complete_monitoring.log" 2>&1 &
MONITOR_PID=$!
pids+=("$MONITOR_PID")
echo "Started monitoring verifier with PID $MONITOR_PID"

# Give monitor 3 seconds to start and begin listening
sleep 3

# Start 2 agents for agent→agent edge verification
echo "Starting PersonalAssistant agent..."
PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT timeout $((TIMEOUT-5)) python "$PROJECT_ROOT/examples/MultiAgent/agents/personal_assistant.py" > "$LOG_DIR/personal_assistant_complete.log" 2>&1 &
PA_PID=$!
pids+=("$PA_PID")
echo "Started PersonalAssistant with PID $PA_PID"

echo "Starting WeatherAgent..."
PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT timeout $((TIMEOUT-5)) python "$PROJECT_ROOT/examples/MultiAgent/agents/weather_agent.py" > "$LOG_DIR/weather_agent_complete.log" 2>&1 &
WA_PID=$!
pids+=("$WA_PID")
echo "Started WeatherAgent with PID $WA_PID"

# Start 1 service for agent→service edge verification
echo "Starting Calculator service..."
PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT timeout $((TIMEOUT-5)) python -m test_functions.calculator_service > "$LOG_DIR/calculator_service_complete.log" 2>&1 &
CALC_PID=$!
pids+=("$CALC_PID")
echo "Started Calculator service with PID $CALC_PID"

# Wait for the monitoring test to complete (it runs for 60s)
echo "Waiting for monitoring verifier to complete..."
wait $MONITOR_PID || true
EXIT_CODE=$?

# Check the exit code
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Comprehensive monitoring test PASSED!"
    exit 0
else
    if [ $EXIT_CODE -eq 124 ]; then
        echo "❌ Monitoring test timed out after ${TIMEOUT}s"
    else
        echo "❌ Monitoring test FAILED with exit code $EXIT_CODE"
    fi
    
    echo "=================================================="
    echo "Monitoring Test Log (last 50 lines):"
    echo "=================================================="
    tail -n 50 "$LOG_DIR/test_complete_monitoring.log" | sed 's/^/  /'
    echo "=================================================="
    echo "Full log available at: $LOG_DIR/test_complete_monitoring.log"
    echo "=================================================="
    
    exit 1
fi

