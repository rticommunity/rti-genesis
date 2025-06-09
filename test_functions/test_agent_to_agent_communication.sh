#!/bin/bash

# Test script for agent-to-agent communication
# This script starts two agents in separate processes to test communication

echo "=== Testing Agent-to-Agent Communication ==="

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Log files
AGENT_A_LOG="$SCRIPT_DIR/agent_a.log"
AGENT_B_LOG="$SCRIPT_DIR/agent_b.log"

# Clean up any existing log files
rm -f "$AGENT_A_LOG" "$AGENT_B_LOG"

echo "Starting Agent B (responder)..."
python "$SCRIPT_DIR/test_monitored_agent_b.py" > "$AGENT_B_LOG" 2>&1 &
AGENT_B_PID=$!

echo "Waiting 3 seconds for Agent B to initialize..."
sleep 3

echo "Starting Agent A (requester)..."
python "$SCRIPT_DIR/test_monitored_agent_a.py" > "$AGENT_A_LOG" 2>&1 &
AGENT_A_PID=$!

echo "Waiting 10 seconds for agents to discover each other and communicate..."
sleep 10

echo "=== Agent A Log ==="
cat "$AGENT_A_LOG"

echo ""
echo "=== Agent B Log ==="
cat "$AGENT_B_LOG"

echo ""
echo "Cleaning up processes..."
kill $AGENT_A_PID 2>/dev/null
kill $AGENT_B_PID 2>/dev/null

# Wait a moment for processes to clean up
sleep 2

echo "=== Verifying Communication ==="

# Check if agents discovered each other
if grep -q "Agent A discovered.*test_monitored_agent_b" "$AGENT_A_LOG"; then
    echo "✓ Agent A discovered Agent B"
else
    echo "✗ Agent A did not discover Agent B"
fi

if grep -q "Agent B discovered" "$AGENT_B_LOG"; then
    echo "✓ Agent B discovered other agents"
else
    echo "✗ Agent B did not discover other agents"
fi

# Check if communication worked
if grep -q "Direct communication successful" "$AGENT_A_LOG"; then
    echo "✓ Direct agent-to-agent communication successful"
else
    echo "✗ Direct agent-to-agent communication failed"
fi

if grep -q "Agent B received agent request" "$AGENT_B_LOG"; then
    echo "✓ Agent B received request from Agent A"
else
    echo "✗ Agent B did not receive request from Agent A"
fi

echo "=== Test Complete ===" 