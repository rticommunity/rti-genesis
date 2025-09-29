#!/bin/bash

# Test script for sequential agent startup to test durable topics
echo "=== Testing Sequential Agent Startup ==="

# Clean up any existing DDS processes that might cause resource conflicts
echo "Cleaning up existing DDS processes..."
pkill -f "rtiddsspy" || true
pkill -f "test_monitored_agent" || true
pkill -f "python.*agent" || true
sleep 2

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Log files
AGENT_A_LOG="$SCRIPT_DIR/agent_a_seq.log"
AGENT_B_LOG="$SCRIPT_DIR/agent_b_seq.log"

# PIDs for cleanup
pids=()

# Cleanup function
cleanup() {
    echo "Cleaning up processes..."
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    echo "Cleanup complete."
}
trap cleanup EXIT

# Clean up any existing log files
rm -f "$AGENT_A_LOG" "$AGENT_B_LOG"

echo "Step 1: Starting Agent B and letting it fully initialize..."
python "$SCRIPT_DIR/test_monitored_agent_b.py" > "$AGENT_B_LOG" 2>&1 &
AGENT_B_PID=$!
pids+=("$AGENT_B_PID")

echo "Waiting 5 seconds for Agent B to fully initialize and publish its capability..."
sleep 5

echo "Step 2: Starting Agent A (should discover Agent B via durable topic)..."
python "$SCRIPT_DIR/test_monitored_agent_a.py" > "$AGENT_A_LOG" 2>&1 &
AGENT_A_PID=$!
pids+=("$AGENT_A_PID")

echo "Waiting 10 seconds for Agent A to discover Agent B and attempt communication..."
sleep 10

echo "Stopping agents..."
kill $AGENT_A_PID 2>/dev/null || true
kill $AGENT_B_PID 2>/dev/null || true

# Wait a moment for processes to clean up
sleep 2

echo ""
echo "=== Agent B Log (started first) ==="
if [ -f "$AGENT_B_LOG" ]; then
    tail -n 50 "$AGENT_B_LOG"
else
    echo "Agent B log not found"
fi

echo ""
echo "=== Agent A Log (started second) ==="
if [ -f "$AGENT_A_LOG" ]; then
    tail -n 50 "$AGENT_A_LOG"
else
    echo "Agent A log not found"
fi

echo ""
echo "=== Checking Discovery ==="

# Check if Agent A discovered Agent B
if grep -q "Agent A discovered.*test_monitored_agent_b" "$AGENT_A_LOG" 2>/dev/null; then
    echo "✓ Agent A discovered Agent B"
else
    echo "✗ Agent A did not discover Agent B"
fi

# Check if Agent B discovered Agent A
if grep -q "Discovered NEW agent.*TestMonitoredAgentA" "$AGENT_B_LOG" 2>/dev/null; then
    echo "✓ Agent B discovered Agent A"
else
    echo "✗ Agent B did not discover Agent A"
fi

# Check if communication worked
if grep -q "Direct communication successful" "$AGENT_A_LOG" 2>/dev/null; then
    echo "✓ Direct agent-to-agent communication successful"
else
    echo "✗ Direct agent-to-agent communication failed"
fi

echo "=== Test Complete ===" 