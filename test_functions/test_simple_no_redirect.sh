#!/bin/bash

# Test script without output redirection to debug the hang issue
echo "=== Testing Agent Startup Without Output Redirection ==="

# Clean up any existing DDS processes
echo "Cleaning up existing DDS processes..."
pkill -f "rtiddsspy" || true
pkill -f "test_monitored_agent" || true
pkill -f "python.*agent" || true
sleep 2

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

echo "Starting Agent B in background (no output redirection)..."
python "$SCRIPT_DIR/test_monitored_agent_b.py" &
AGENT_B_PID=$!
pids+=("$AGENT_B_PID")

echo "Agent B PID: $AGENT_B_PID"
echo "Waiting 3 seconds for Agent B to initialize..."
sleep 3

echo "Starting Agent A in background (no output redirection)..."
python "$SCRIPT_DIR/test_monitored_agent_a.py" &
AGENT_A_PID=$!
pids+=("$AGENT_A_PID")

echo "Agent A PID: $AGENT_A_PID"
echo "Waiting 10 seconds for agents to discover each other..."
sleep 10

echo "Stopping agents..."
kill $AGENT_A_PID 2>/dev/null || true
kill $AGENT_B_PID 2>/dev/null || true

echo "Test complete." 