#!/bin/bash

# Monitored Agent Communication Test Script
# Tests agent-to-agent communication with monitoring events

echo "🚀 Starting Monitored Agent Communication Test"
echo "============================================="

# Change to the correct directory
cd "$(dirname "$0")/.."

# Clean up any background processes on exit
cleanup() {
    echo ""
    echo "🧹 Cleaning up background processes..."
    if [ ! -z "$AGENT_B_PID" ]; then
        echo "Stopping Monitored Agent B (PID: $AGENT_B_PID)..."
        kill $AGENT_B_PID 2>/dev/null
        wait $AGENT_B_PID 2>/dev/null
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start Monitored Agent B and capture its PID
echo "1. Starting Monitored Agent B (responder)..."
echo "   Command: python test_functions/test_monitored_agent_communication.py b"
python test_functions/test_monitored_agent_communication.py b > /tmp/monitored_agent_b.log 2>&1 &
AGENT_B_PID=$!
echo "   Monitored Agent B started with PID: $AGENT_B_PID"

# Wait for Agent B to initialize
echo "2. Waiting for Monitored Agent B to initialize..."
sleep 5

# Check if Agent B is still running
if ! kill -0 $AGENT_B_PID 2>/dev/null; then
    echo "❌ Monitored Agent B failed to start. Check /tmp/monitored_agent_b.log for errors."
    echo "Monitored Agent B log contents:"
    cat /tmp/monitored_agent_b.log
    exit 1
else
    echo "✅ Monitored Agent B process is running (PID: $AGENT_B_PID)"
    # Show current log size
    if [ -f /tmp/monitored_agent_b.log ]; then
        LOG_SIZE=$(wc -l < /tmp/monitored_agent_b.log)
        echo "   Monitored Agent B log has $LOG_SIZE lines so far"
    else
        echo "   Monitored Agent B log file not created yet"
    fi
fi

# Start Agent A (requester)
echo ""
echo "3. Starting Monitored Agent A (requester)..."
echo "   Command: python test_functions/test_monitored_agent_communication.py a"
echo ""

timeout 20s python test_functions/test_monitored_agent_communication.py a

AGENT_A_EXIT_CODE=$?

echo ""
echo "4. Test Results:"

if [ $AGENT_A_EXIT_CODE -eq 0 ]; then
    echo "✅ SUCCESS: Monitored agent communication test completed successfully!"
    echo "📊 Monitoring events should have been published during the interaction"
elif [ $AGENT_A_EXIT_CODE -eq 124 ]; then
    echo "⏰ TIMEOUT: Agent A timed out - this might be normal if the test completed"
else
    echo "❌ FAILURE: Agent A exited with code $AGENT_A_EXIT_CODE"
fi

echo ""
echo "5. Monitored Agent B Log Output:"
echo "================================"
if [ -f /tmp/monitored_agent_b.log ]; then
    cat /tmp/monitored_agent_b.log
else
    echo "No log file found for Monitored Agent B"
fi

# Clean up
cleanup 