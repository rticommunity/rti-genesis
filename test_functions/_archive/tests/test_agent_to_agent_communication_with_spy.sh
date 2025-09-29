#!/bin/bash

# Test script for agent-to-agent communication with RTIDDSSPY monitoring
# This script starts two agents in separate processes and uses RTIDDSSPY to monitor
# DDS topics to see what advertisements are being published

echo "=== Testing Agent-to-Agent Communication with DDS Spy ==="

# Clean up any existing DDS processes that might cause resource conflicts
echo "Cleaning up existing DDS processes..."
pkill -f "rtiddsspy" || true
pkill -f "test_monitored_agent" || true
pkill -f "python.*agent" || true
sleep 2

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Log files
AGENT_A_LOG="$SCRIPT_DIR/agent_a_spy.log"
AGENT_B_LOG="$SCRIPT_DIR/agent_b_spy.log"
SPY_LOG="$SCRIPT_DIR/dds_spy.log"

# PIDs for cleanup
pids=()

# Cleanup function
cleanup() {
    echo "Cleaning up processes..."
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    # Extra cleanup for rtiddsspy
    pkill -f "rtiddsspy" || true
    echo "Cleanup complete."
}
trap cleanup EXIT

# Clean up any existing log files
rm -f "$AGENT_A_LOG" "$AGENT_B_LOG" "$SPY_LOG"

# Check for NDDSHOME
if [ -z "$NDDSHOME" ]; then
    echo "ERROR: NDDSHOME environment variable is not set."
    echo "Please set NDDSHOME to your RTI Connext DDS installation directory."
    exit 1
fi

# Verify rtiddsspy exists
if [ ! -f "$NDDSHOME/bin/rtiddsspy" ]; then
    echo "ERROR: rtiddsspy not found at $NDDSHOME/bin/rtiddsspy"
    echo "Please verify that NDDSHOME is set correctly and rtiddsspy exists in the bin directory."
    echo "Current NDDSHOME: $NDDSHOME"
    exit 1
fi

echo "Starting RTIDDSSPY to monitor DDS topics..."
# Monitor all relevant topics for agent communication
"$NDDSHOME/bin/rtiddsspy" -printSample \
    -topic 'RegistrationAnnouncement' \
    -topic 'AgentCapability' \
    -topic 'AgentAgentRequest' \
    -topic 'AgentAgentReply' \
    -topic 'MonitoringEvent' \
    -topic 'ComponentLifecycleEvent' \
    > "$SPY_LOG" 2>&1 &
SPY_PID=$!
pids+=("$SPY_PID")

echo "RTIDDSSPY started (PID: $SPY_PID), monitoring topics..."
sleep 2

echo "Starting Agent B (responder)..."
python "$SCRIPT_DIR/test_monitored_agent_b.py" > "$AGENT_B_LOG" 2>&1 &
AGENT_B_PID=$!
pids+=("$AGENT_B_PID")

echo "Waiting 3 seconds for Agent B to initialize..."
sleep 3

echo "Starting Agent A (requester)..."
python "$SCRIPT_DIR/test_monitored_agent_a.py" > "$AGENT_A_LOG" 2>&1 &
AGENT_A_PID=$!
pids+=("$AGENT_A_PID")

echo "Waiting 15 seconds for agents to discover each other and communicate..."
sleep 15

echo "Stopping agents..."
kill $AGENT_A_PID 2>/dev/null || true
kill $AGENT_B_PID 2>/dev/null || true

# Wait a moment for processes to clean up
sleep 2

echo "Stopping RTIDDSSPY..."
kill $SPY_PID 2>/dev/null || true
sleep 1

echo ""
echo "=== Agent A Log ==="
if [ -f "$AGENT_A_LOG" ]; then
    cat "$AGENT_A_LOG"
else
    echo "Agent A log not found"
fi

echo ""
echo "=== Agent B Log ==="
if [ -f "$AGENT_B_LOG" ]; then
    cat "$AGENT_B_LOG"
else
    echo "Agent B log not found"
fi

echo ""
echo "=== DDS Spy Log ==="
if [ -f "$SPY_LOG" ]; then
    cat "$SPY_LOG"
else
    echo "DDS Spy log not found"
fi

echo ""
echo "=== DDS Topic Analysis ==="

if [ -f "$SPY_LOG" ]; then
    echo "Topics with activity:"
    grep -E "(New writer for topic|SAMPLE for topic)" "$SPY_LOG" | sort -u || echo "No topic activity detected"
    
    echo ""
    echo "RegistrationAnnouncement samples:"
    grep -A 10 "SAMPLE for topic 'RegistrationAnnouncement'" "$SPY_LOG" || echo "No RegistrationAnnouncement samples"
    
    echo ""
    echo "AgentCapability samples:"
    grep -A 10 "SAMPLE for topic 'AgentCapability'" "$SPY_LOG" || echo "No AgentCapability samples"
    
    echo ""
    echo "AgentAgentRequest samples:"
    grep -A 10 "SAMPLE for topic 'AgentAgentRequest'" "$SPY_LOG" || echo "No AgentAgentRequest samples"
    
    echo ""
    echo "AgentAgentReply samples:"
    grep -A 10 "SAMPLE for topic 'AgentAgentReply'" "$SPY_LOG" || echo "No AgentAgentReply samples"
else
    echo "No spy log available for analysis"
fi

echo ""
echo "=== Verifying Communication ==="

# Check if agents discovered each other
if grep -q "Agent A discovered.*test_monitored_agent_b" "$AGENT_A_LOG" 2>/dev/null; then
    echo "✓ Agent A discovered Agent B"
else
    echo "✗ Agent A did not discover Agent B"
fi

if grep -q "Agent B discovered" "$AGENT_B_LOG" 2>/dev/null; then
    echo "✓ Agent B discovered other agents"
else
    echo "✗ Agent B did not discover other agents"
fi

# Check if communication worked
if grep -q "Direct communication successful" "$AGENT_A_LOG" 2>/dev/null; then
    echo "✓ Direct agent-to-agent communication successful"
else
    echo "✗ Direct agent-to-agent communication failed"
fi

if grep -q "Agent B received agent request" "$AGENT_B_LOG" 2>/dev/null; then
    echo "✓ Agent B received request from Agent A"
else
    echo "✗ Agent B did not receive request from Agent A"
fi

echo "=== Test Complete ===" 