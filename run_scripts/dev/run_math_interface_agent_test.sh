#!/bin/bash

# Script to run concurrent Interface <-> Agent RPC test with DDS tracing

# Exit immediately if a command exits with a non-zero status.
set -e

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

# Ensure we are in the run_scripts directory
cd "$SCRIPT_DIR"

# Set up log directory
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# Clear existing log files
echo "🧹 TRACE: Clearing existing log files..."
rm -f "$LOG_DIR/rtiddsspy_math.log"
rm -f "$LOG_DIR/math_test_agent.log"
rm -f "$LOG_DIR/math_test_interface_*.log"

# Define script and log file names
AGENT_SCRIPT="$PROJECT_ROOT/run_scripts/helpers/math_test_agent.py"
INTERFACE_SCRIPT="$PROJECT_ROOT/run_scripts/helpers/math_test_interface.py"
AGENT_LOG="$LOG_DIR/math_test_agent.log"
SPY_LOG="$LOG_DIR/rtiddsspy_math.log"

# Number of interfaces to run
NUM_INTERFACES=20

# Process IDs
AGENT_PID=""
declare -a INTERFACE_PIDS
SPY_PID=""

# Cleanup function to ensure processes are killed
cleanup() {
    echo "🧹 TRACE: Starting cleanup process..."
    if [ -n "$AGENT_PID" ]; then
        echo "🔫 TRACE: Stopping agent process $AGENT_PID..."
        kill $AGENT_PID 2>/dev/null || true
        wait $AGENT_PID 2>/dev/null || true
    fi
    for pid in "${INTERFACE_PIDS[@]}"; do
        if [ -n "$pid" ]; then
            echo "🔫 TRACE: Stopping interface process $pid..."
            kill $pid 2>/dev/null || true
            wait $pid 2>/dev/null || true
        fi
    done
    if [ -n "$SPY_PID" ]; then
        echo "🔫 TRACE: Stopping RTI DDS Spy process $SPY_PID..."
        kill $SPY_PID 2>/dev/null || true
        wait $SPY_PID 2>/dev/null || true
    fi
    echo "✅ TRACE: Cleanup completed successfully"
}

# Set trap for cleanup on exit
trap cleanup EXIT INT TERM

# Start RTI DDS Spy with print sample
echo "🚀 TRACE: Starting RTI DDS Spy..."
"$NDDSHOME/bin/rtiddsspy" -printSample > "$SPY_LOG" 2>&1 &
SPY_PID=$!
echo "✅ TRACE: RTI DDS Spy started with PID: $SPY_PID (Log: $SPY_LOG)"

# Wait a moment for the spy to initialize
echo "⏳ TRACE: Waiting for RTI DDS Spy to initialize..."
sleep 2

# Run the agent in the background
echo "🚀 TRACE: Starting Math Test Agent in background..."
PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH" python "$AGENT_SCRIPT" > "$AGENT_LOG" 2>&1 &
AGENT_PID=$!
echo "✅ TRACE: Agent started with PID: $AGENT_PID (Log: $AGENT_LOG)"

# Wait for the agent to initialize
echo "⏳ TRACE: Waiting 3 seconds for agent to initialize..."
sleep 3

# Run multiple interface instances with minimal delay
echo "🚀 TRACE: Starting $NUM_INTERFACES Math Test Interfaces..."
for i in $(seq 1 $NUM_INTERFACES); do
    INTERFACE_LOG="$LOG_DIR/math_test_interface_${i}.log"
    PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH" python "$INTERFACE_SCRIPT" > "$INTERFACE_LOG" 2>&1 &
    INTERFACE_PIDS[$i]=$!
    echo "✅ TRACE: Interface $i started with PID: ${INTERFACE_PIDS[$i]} (Log: $INTERFACE_LOG)"
    # Add a tiny delay to prevent exact simultaneous starts but ensure overlap
    sleep 0.1
done

# Wait for all interfaces to complete
echo "⏳ TRACE: Waiting for interfaces to complete..."
EXIT_CODE=0
for i in $(seq 1 $NUM_INTERFACES); do
    if wait ${INTERFACE_PIDS[$i]}; then
        echo "✅ TRACE: Interface $i completed successfully"
    else
        echo "❌ TRACE: Interface $i failed"
        EXIT_CODE=1
    fi
done

# Wait a moment to ensure all DDS messages are captured
echo "⏳ TRACE: Waiting for final DDS messages..."
sleep 2

# Display the logs
echo -e "\n📜 TRACE: Displaying RTI DDS Spy Log:"
echo "----------------------------------------"
cat "$SPY_LOG"
echo -e "\n📜 TRACE: Displaying Agent Log:"
echo "----------------------------------------"
cat "$AGENT_LOG"
echo -e "\n📜 TRACE: Displaying Interface Logs:"
for i in $(seq 1 $NUM_INTERFACES); do
    echo -e "\n📜 TRACE: Interface $i Log:"
    echo "----------------------------------------"
    cat "$LOG_DIR/math_test_interface_${i}.log"
done

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ TRACE: All interfaces completed successfully"
else
    echo "❌ TRACE: Some interfaces failed"
fi

exit $EXIT_CODE 
