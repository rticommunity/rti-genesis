#!/bin/bash

# Script to run simple Interface <-> Agent RPC test with DDS tracing

# Initialize test status
TEST_FAILED=0

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Set up log directory
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# Define script and log file names
AGENT_SCRIPT="$PROJECT_ROOT/run_scripts/helpers/math_test_agent.py"
INTERFACE_SCRIPT="$PROJECT_ROOT/run_scripts/helpers/math_test_interface.py"
AGENT_LOG="$LOG_DIR/math_test_agent.log"
INTERFACE_LOG="$LOG_DIR/math_test_interface.log"
REGISTRATION_SPY_LOG="$LOG_DIR/rtiddsspy_registration.log"
INTERFACE_SPY_LOG="$LOG_DIR/rtiddsspy_interface.log"

# Function to kill a process and ensure it's dead
kill_process() {
    local pid=$1
    local name=$2
    local is_spy=$3

    if [ "$is_spy" = "true" ]; then
        echo "🔫 TRACE: Stopping $name process $pid..."
        pkill -f "rtiddsspy.*spy_transient.xml.*SpyLib::TransientReliable" || true
        sleep 1
    else
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "🔫 TRACE: Stopping $name process $pid..."
            kill -TERM "$pid" 2>/dev/null || true
            sleep 1
            if kill -0 "$pid" 2>/dev/null; then
                echo "⚠️ TRACE: Process $pid didn't respond to SIGTERM, using SIGKILL..."
                kill -KILL "$pid" 2>/dev/null || true
            fi
            wait "$pid" 2>/dev/null || true
        fi
    fi
}

# Function to check log contents
check_log() {
    local log_file=$1
    local pattern=$2
    local description=$3
    local required=$4

    if grep -q "$pattern" "$log_file"; then
        echo "✅ TRACE: $description - Found in logs"
        return 0
    else
        if [ "$required" = "true" ]; then
            echo "❌ TRACE: $description - NOT FOUND in logs"
            TEST_FAILED=1
            return 1
        else
            echo "⚠️ TRACE: $description - NOT FOUND in logs (not required)"
            return 0
        fi
    fi
}

# Clear existing log files
echo "🧹 TRACE: Clearing existing log files..."
rm -f "$AGENT_LOG" "$INTERFACE_LOG" "$REGISTRATION_SPY_LOG" "$INTERFACE_SPY_LOG"

echo "🔬 TRACE: Starting Test 1 - Registration Durability Test"
echo "=============================================="

# Start the agent first
echo "🚀 TRACE: Starting agent..."
PYTHONUNBUFFERED=1 python3 -u "$AGENT_SCRIPT" > "$AGENT_LOG" 2>&1 &
AGENT_PID=$!
echo "✅ TRACE: Agent started with PID: $AGENT_PID"

# Wait for the agent to initialize and announce itself
echo "⏳ TRACE: Waiting for agent to initialize..."
sleep 5

# Now start RTI DDS Spy AFTER the agent
echo "🚀 TRACE: Starting RTI DDS Spy to verify durability..."
"$NDDSHOME/bin/rtiddsspy" -printSample -qosFile "$PROJECT_ROOT/spy_transient.xml" -qosProfile SpyLib::TransientReliable > "$REGISTRATION_SPY_LOG" 2>&1 &
REGISTRATION_SPY_PID=$!
echo "✅ TRACE: RTI DDS Spy started with PID: $REGISTRATION_SPY_PID (Log: $REGISTRATION_SPY_LOG)"

# Wait for the spy to receive the durable announcement
echo "⏳ TRACE: Waiting for RTI DDS Spy to receive durable announcement..."
sleep 10

# Check Test 1 - Registration Durability
echo "🔍 TRACE: Running Test 1 checks..."

# Check agent initialization
check_log "$AGENT_LOG" "✅ TRACE: Agent created, starting run..." "Agent initialization" true
check_log "$AGENT_LOG" "MathTestAgent listening for requests" "Agent listening state" true

# Check registration announcement
check_log "$REGISTRATION_SPY_LOG" "New writer.*topic=\"GenesisRegistration\"" "Registration writer creation" true
check_log "$REGISTRATION_SPY_LOG" "New data.*topic=\"GenesisRegistration\".*type=\"genesis_agent_registration_announce\"" "Registration announcement" true

# Clean up Test 1
echo "🧹 TRACE: Cleaning up Test 1..."
kill_process "$REGISTRATION_SPY_PID" "registration spy" true
kill_process "$AGENT_PID" "agent" false

echo "🔬 TRACE: Starting Test 2 - Interface Test"
echo "=============================================="

# Start a new agent for the interface test
echo "🚀 TRACE: Starting new agent for interface test..."
PYTHONUNBUFFERED=1 python3 -u "$AGENT_SCRIPT" > "$AGENT_LOG" 2>&1 &
AGENT_PID=$!
echo "✅ TRACE: Agent started with PID: $AGENT_PID"

# Wait for the agent to initialize
echo "⏳ TRACE: Waiting for agent to initialize..."
sleep 5

# Start RTI DDS Spy for interface test
echo "🚀 TRACE: Starting RTI DDS Spy for interface test..."
"$NDDSHOME/bin/rtiddsspy" -printSample -qosFile "$PROJECT_ROOT/spy_transient.xml" -qosProfile SpyLib::TransientReliable > "$INTERFACE_SPY_LOG" 2>&1 &
INTERFACE_SPY_PID=$!
echo "✅ TRACE: RTI DDS Spy started with PID: $INTERFACE_SPY_PID (Log: $INTERFACE_SPY_LOG)"

# Start the interface
echo "🚀 TRACE: Starting interface..."
python3 "$INTERFACE_SCRIPT" > "$INTERFACE_LOG" 2>&1 &
INTERFACE_PID=$!
echo "✅ TRACE: Interface started with PID: $INTERFACE_PID"

# Wait for the interface test to complete
echo "⏳ TRACE: Waiting for interface test to complete..."
wait $INTERFACE_PID || true

# Check Test 2 - Interface Test
echo "🔍 TRACE: Running Test 2 checks..."

# Check agent logs
check_log "$AGENT_LOG" "✅ TRACE: Agent created, starting run..." "Agent initialization" true
check_log "$AGENT_LOG" "MathTestAgent listening for requests" "Agent listening state" true
check_log "$AGENT_LOG" "Received request:" "Request received" true
check_log "$AGENT_LOG" "Sent reply:" "Reply sent" true

# Check interface logs
check_log "$INTERFACE_LOG" "Monitored interface MathTestInterface initialized" "Interface initialization" true
check_log "$INTERFACE_LOG" "<MonitoredInterface Handler> Agent Discovered: MathTestAgent (MathTestService)" "Agent discovery callback" true
check_log "$INTERFACE_LOG" "🔎 TRACE: Available agents found: {.*'prefered_name': 'MathTestAgent'.*}" "Available agents logged" true
check_log "$INTERFACE_LOG" "✅ TRACE: Agent discovered. Selecting first available: MathTestAgent" "Agent selection" true
check_log "$INTERFACE_LOG" "🔗 TRACE: Attempting to connect to service: MathTestService" "Connection attempt" true
check_log "$INTERFACE_LOG" "✅ TRACE: Successfully connected to agent: MathTestAgent" "Connection success" true
check_log "$INTERFACE_LOG" "📤 TRACE: Sending math request:" "Request sent" true
check_log "$INTERFACE_LOG" "📥 TRACE: Received reply:" "Reply received" true
check_log "$INTERFACE_LOG" "✅ TRACE: Math test passed" "Math test verification" true
check_log "$INTERFACE_LOG" "🏁 TRACE: MathTestInterface ending with exit code: 0" "Clean exit" true

# Check DDS Spy logs
check_log "$INTERFACE_SPY_LOG" "New data.*topic=\"GenesisRegistration\".*type=\"genesis_agent_registration_announce\"" "Agent registration" true
check_log "$INTERFACE_LOG" "✨ TRACE: Agent DISCOVERED: MathTestAgent (MathTestService)" "Interface discovery" true
# Note: Spy may wrap long lines, so match topic only (relaxed criterion)
check_log "$INTERFACE_SPY_LOG" "topic=\"MathTestServiceRequest\"" "RPC request" true
check_log "$INTERFACE_SPY_LOG" "topic=\"MathTestServiceReply\"" "RPC reply" true

# Clean up Test 2
echo "🧹 TRACE: Cleaning up Test 2..."
kill_process "$INTERFACE_SPY_PID" "interface spy" true
kill_process "$INTERFACE_PID" "interface" false
kill_process "$AGENT_PID" "agent" false

# Final report
echo "=============================================="
echo "Test Results Summary:"
if [ $TEST_FAILED -eq 0 ]; then
    echo "✅ TRACE: All tests passed successfully"
    exit 0
else
    echo "❌ TRACE: One or more tests failed"
    exit 1
fi
