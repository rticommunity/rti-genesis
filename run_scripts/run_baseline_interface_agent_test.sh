#!/bin/bash

# Script to run the baseline Interface <-> Agent RPC test with DDS tracing

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
INTERFACE_SCRIPT="$PROJECT_ROOT/run_scripts/baseline_test_interface.py"
AGENT_LOG="$LOG_DIR/baseline_test_agent.log"
INTERFACE_LOG="$LOG_DIR/baseline_test_interface.log"
SPY_LOG="$LOG_DIR/rtiddsspy.log"

# Process IDs
AGENT_PID=""
INTERFACE_PID=""
SPY_PID=""

# Cleanup function to ensure processes are killed
cleanup() {
    echo "🧹 TRACE: Cleaning up..."
    if [ -n "$AGENT_PID" ]; then
        echo "🔫 TRACE: Killing agent process $AGENT_PID..."
        kill $AGENT_PID 2>/dev/null || true
        wait $AGENT_PID 2>/dev/null || true
    fi
    if [ -n "$INTERFACE_PID" ]; then
        echo "🔫 TRACE: Killing interface process $INTERFACE_PID..."
        kill $INTERFACE_PID 2>/dev/null || true
        wait $INTERFACE_PID 2>/dev/null || true
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

# Run the agent in the background
echo "🚀 TRACE: Starting Baseline Test Agent in background..."
# Ensure PYTHONPATH includes the project root for imports
PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH" python "$AGENT_SCRIPT" > "$AGENT_LOG" 2>&1 &
AGENT_PID=$!
echo "✅ TRACE: Agent started with PID: $AGENT_PID (Log: $AGENT_LOG)"

# Wait for the agent to initialize and become discoverable
# Adjust sleep time if needed based on system performance / DDS discovery time
SLEEP_TIME=5
echo "⏳ TRACE: Waiting ${SLEEP_TIME} seconds for agent to initialize..."
sleep $SLEEP_TIME

# Run the interface script in the foreground
echo "🚀 TRACE: Starting Baseline Test Interface..."
# Ensure PYTHONPATH includes the project root for imports
PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH" python "$INTERFACE_SCRIPT" > "$INTERFACE_LOG" 2>&1
INTERFACE_EXIT_CODE=$?
echo "👋 TRACE: Interface finished with exit code $INTERFACE_EXIT_CODE (Log: $INTERFACE_LOG)"

# Wait a moment to ensure all DDS messages are captured
echo "⏳ TRACE: Waiting for final DDS messages..."
sleep 2

# Cleanup will run automatically via trap
echo "✅ TRACE: Test completed successfully."

# Display the logs
echo -e "\n📜 TRACE: Displaying RTI DDS Spy Log:"
echo "----------------------------------------"
cat "$SPY_LOG"
echo -e "\n📜 TRACE: Displaying Agent Log:"
echo "----------------------------------------"
cat "$AGENT_LOG"
echo -e "\n📜 TRACE: Displaying Interface Log:"
echo "----------------------------------------"
cat "$INTERFACE_LOG"

# Check if the interface script ran successfully
if [ $INTERFACE_EXIT_CODE -ne 0 ]; then
    echo "❌ TRACE: Test Failed: Interface script exited with error code $INTERFACE_EXIT_CODE."
    exit 1
fi

# Optional: Check interface log for expected output (adjust grep pattern if needed)
echo "🔍 TRACE: Checking interface log for expected output..."
if grep -q "✅ TRACE: Test completed successfully" "$INTERFACE_LOG"; then
    echo "✅ TRACE: Test Passed: Found success message in interface log."
else
    echo "❌ TRACE: Test Failed: Did not find success message in interface log."
    exit 1
fi

echo "✅ TRACE: Test completed successfully."
exit 0 