#!/bin/bash

# Script to run RTI DDS Spy and Baseline Test Agent with combined logging

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

# Define script and log file names
AGENT_SCRIPT="$PROJECT_ROOT/run_scripts/baseline_test_agent.py"
AGENT_LOG="$LOG_DIR/baseline_test_agent_with_spy.log"
SPY_LOG="$LOG_DIR/rtiddsspy.log"

# Process IDs
AGENT_PID=""
SPY_PID=""

# Cleanup function to ensure processes are killed
cleanup() {
    echo "🧹 TRACE: Cleaning up..."
    if [ -n "$AGENT_PID" ]; then
        echo "🔫 TRACE: Killing agent process $AGENT_PID..."
        kill $AGENT_PID 2>/dev/null || true
        wait $AGENT_PID 2>/dev/null || true
    fi
    if [ -n "$SPY_PID" ]; then
        echo "🔫 TRACE: Killing RTI DDS Spy process $SPY_PID..."
        kill $SPY_PID 2>/dev/null || true
        wait $SPY_PID 2>/dev/null || true
    fi
    echo "✅ TRACE: Cleanup finished."
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

# Run the agent with output to both log and screen
echo "🚀 TRACE: Starting Baseline Test Agent..."
# Ensure PYTHONPATH includes the project root for imports
PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH" python "$AGENT_SCRIPT" > "$AGENT_LOG" 2>&1 &
AGENT_PID=$!
echo "✅ TRACE: Agent started with PID: $AGENT_PID (Log: $AGENT_LOG)"

# Wait for 15 seconds
echo "⏳ TRACE: Running for 15 seconds..."
sleep 15

# Cleanup will run automatically via trap
echo "✅ TRACE: Test completed successfully."

# Display the logs
echo -e "\n📜 TRACE: Displaying RTI DDS Spy Log:"
echo "----------------------------------------"
cat "$SPY_LOG"
echo -e "\n📜 TRACE: Displaying Agent Log:"
echo "----------------------------------------"
cat "$AGENT_LOG"

exit 0 