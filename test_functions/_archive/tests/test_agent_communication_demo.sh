#!/bin/bash

# Agent-to-Agent Communication Demo Script
# This script demonstrates working agent-to-agent communication by running
# two agents in separate processes using shell commands.

echo "🚀 Starting Agent-to-Agent Communication Demo"
echo "============================================"

# Change to the correct directory
cd "$(dirname "$0")/.."

# Clean up any background processes on exit
cleanup() {
    echo ""
    echo "🧹 Cleaning up background processes..."
    if [ ! -z "$AGENT_B_PID" ]; then
        echo "Stopping Agent B (PID: $AGENT_B_PID)..."
        kill $AGENT_B_PID 2>/dev/null
        wait $AGENT_B_PID 2>/dev/null
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start Agent B in the background using shell
echo "1️⃣ Starting Agent B (Responder) in background..."
echo "   Command: python test_functions/test_working_communication.py b"

# Start Agent B and capture its PID
python test_functions/test_working_communication.py b > /tmp/agent_b.log 2>&1 &
AGENT_B_PID=$!
echo "   Agent B started with PID: $AGENT_B_PID"

echo "   Agent B PID: $AGENT_B_PID"
echo "   Agent B log: /tmp/agent_b.log"

# Wait for Agent B to initialize
echo "⏳ Waiting 8 seconds for Agent B to initialize..."
sleep 8

# Check if Agent B is still running
if ! kill -0 $AGENT_B_PID 2>/dev/null; then
    echo "❌ Agent B failed to start. Check /tmp/agent_b.log for errors."
    echo "Agent B log contents:"
    cat /tmp/agent_b.log
    exit 1
else
    echo "✅ Agent B process is running (PID: $AGENT_B_PID)"
    # Show current log size
    if [ -f /tmp/agent_b.log ]; then
        LOG_SIZE=$(wc -l < /tmp/agent_b.log)
        echo "   Agent B log has $LOG_SIZE lines so far"
    else
        echo "   Agent B log file not created yet"
    fi
fi

echo "✅ Agent B is running and ready"

# Show Agent B's startup log
echo ""
echo "📋 Agent B Startup Log:"
echo "======================"
head -20 /tmp/agent_b.log

# Start Agent A in a separate shell process
echo ""
echo "2️⃣ Starting Agent A (Requester) to communicate with Agent B..."
echo "=============================================================="
echo "   Command: python test_functions/test_working_communication.py a"

# Run Agent A in foreground to see the communication
timeout 30s python test_functions/test_working_communication.py a

AGENT_A_EXIT_CODE=$?

# Show Agent B's full log output
echo ""
echo "3️⃣ Agent B Full Log Output:"
echo "=========================="
cat /tmp/agent_b.log

# Clean up Agent B
echo ""
echo "🧹 Stopping Agent B..."
if kill -0 $AGENT_B_PID 2>/dev/null; then
    kill $AGENT_B_PID 2>/dev/null
    echo "Waiting for Agent B to shutdown..."
    wait $AGENT_B_PID 2>/dev/null
    echo "Agent B stopped"
else
    echo "Agent B already stopped"
fi

# Report results
echo ""
echo "📊 Demo Results:"
echo "==============="
if [ $AGENT_A_EXIT_CODE -eq 0 ]; then
    echo "✅ Agent A completed successfully"
else
    echo "❌ Agent A exited with code: $AGENT_A_EXIT_CODE"
fi

echo "✅ Demo completed!" 