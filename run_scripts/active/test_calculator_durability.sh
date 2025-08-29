#!/bin/bash

# Script to test calculator service durability with DDS tracing

# Initialize test status
TEST_FAILED=0

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Set up log directory
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# Define script and log file names
SERVICE_SCRIPT="$PROJECT_ROOT/test_functions/calculator_service.py"
SERVICE_LOG="$LOG_DIR/serviceside_service_durability.log"
REGISTRATION_SPY_LOG="$LOG_DIR/serviceside_rtiddsspy_durability.log"
SERVICE_SPY_LOG="$LOG_DIR/serviceside_rtiddsspy_durability.log"
AGENT_SCRIPT="$PROJECT_ROOT/run_scripts/helpers/math_test_agent.py"
AGENT_LOG="$LOG_DIR/serviceside_agent_durability.log"

# Function to check for and clean up DDS processes
check_and_cleanup_dds() {
    echo "🔍 TRACE: Checking for existing DDS processes..."
    
    # Start spy to check for DDS activity
    SPY_LOG="$LOG_DIR/dds_check.log"
    "$NDDSHOME/bin/rtiddsspy" -printSample -qosFile "$PROJECT_ROOT/spy_transient.xml" -qosProfile SpyLib::TransientReliable > "$SPY_LOG" 2>&1 &
    SPY_PID=$!
    
    # Wait a bit to see if any DDS activity is detected
    sleep 5
    
    # Check if spy detected any activity
    if grep -q "New writer\|New data" "$SPY_LOG"; then
        echo "⚠️ TRACE: Detected DDS activity. Attempting to clean up..."
        
        # Try to kill any DDS processes
        pkill -f "rtiddsspy" || true
        pkill -f "python.*genesis_lib" || true
        
        # Wait a bit and check again
        sleep 5
        
        # Start a new spy to verify cleanup
        rm -f "$SPY_LOG"
        "$NDDSHOME/bin/rtiddsspy" -printSample -qosFile "$PROJECT_ROOT/spy_transient.xml" -qosProfile SpyLib::TransientReliable > "$SPY_LOG" 2>&1 &
        SPY_PID=$!
        sleep 5
        
        # Check if DDS activity is still present
        if grep -q "New writer\|New data" "$SPY_LOG"; then
            echo "❌ ERROR: Failed to clean up DDS processes. Please manually check and kill any running DDS processes."
            kill $SPY_PID 2>/dev/null || true
            return 1
        fi
    fi
    
    # Clean up spy
    kill $SPY_PID 2>/dev/null || true
    echo "✅ TRACE: No DDS processes detected or successfully cleaned up"
    return 0
}

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

# Function to cleanup any existing processes
cleanup_existing_processes() {
    echo "🧹 TRACE: Cleaning up any existing processes..."
    # Kill any existing calculator services
    pkill -f "python3.*calculator_service.py" || true
    # Kill any existing agents
    pkill -f "python3.*math_test_agent.py" || true
    # Kill any existing DDS spies
    pkill -f "rtiddsspy.*spy_transient.xml.*SpyLib::TransientReliable" || true
    sleep 2  # Give processes time to clean up
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

# Clear existing log files and check for DDS processes
echo "🧹 TRACE: Cleaning up before test..."
check_and_cleanup_dds || { echo "Test aborted due to DDS process issues"; exit 1; }
rm -f "$SERVICE_LOG" "$REGISTRATION_SPY_LOG" "$SERVICE_SPY_LOG" "$AGENT_LOG"

echo "🔬 TRACE: Starting Test 1 - Service Registration Durability Test"
echo "=============================================="

# Start the calculator service first
echo "🚀 TRACE: Starting calculator service..."
PYTHONUNBUFFERED=1 stdbuf -o0 -e0 python3 -u "$SERVICE_SCRIPT" > "$SERVICE_LOG" 2>&1 &
SERVICE_PID=$!
echo "✅ TRACE: Calculator service started with PID: $SERVICE_PID"

# Wait for the service to initialize and announce itself
echo "⏳ TRACE: Waiting for service to initialize..."
sleep 5

# Now start RTI DDS Spy AFTER the service
echo "🚀 TRACE: Starting RTI DDS Spy to verify durability..."
"$NDDSHOME/bin/rtiddsspy" -printSample -qosFile "$PROJECT_ROOT/spy_transient.xml" -qosProfile SpyLib::TransientReliable > "$REGISTRATION_SPY_LOG" 2>&1 &
REGISTRATION_SPY_PID=$!
echo "✅ TRACE: RTI DDS Spy started with PID: $REGISTRATION_SPY_PID (Log: $REGISTRATION_SPY_LOG)"

# Wait for the spy to receive the durable announcement
echo "⏳ TRACE: Waiting for RTI DDS Spy to receive durable announcement..."
sleep 5

# Check Test 1 - Service Registration Durability
echo "🔍 TRACE: Running Test 1 checks..."

# Check service initialization
check_log "$SERVICE_LOG" "CalculatorService initializing" "Service initialization" true
check_log "$SERVICE_LOG" "CalculatorService initialized" "Service initialization complete" true

# Check registration announcement
check_log "$REGISTRATION_SPY_LOG" "New writer.*topic=\"FunctionCapability\"" "Function capability writer creation" true
check_log "$REGISTRATION_SPY_LOG" "New data.*topic=\"FunctionCapability\"" "Function capability announcement" true

# Clean up Test 1
echo "🧹 TRACE: Cleaning up Test 1..."
kill_process "$REGISTRATION_SPY_PID" "registration spy" true
kill_process "$SERVICE_PID" "calculator service" false

echo "🔬 TRACE: Starting Test 2 - Service Function Registration Test"
echo "=============================================="

# Start the agent first
echo "🚀 TRACE: Starting agent..."
PYTHONUNBUFFERED=1 stdbuf -o0 -e0 python3 -u "$AGENT_SCRIPT" > "$AGENT_LOG" 2>&1 &
AGENT_PID=$!
echo "✅ TRACE: Agent started with PID: $AGENT_PID"

# Wait for the agent to initialize
echo "⏳ TRACE: Waiting for agent to initialize..."
sleep 5

# Start RTI DDS Spy for function test
echo "🚀 TRACE: Starting RTI DDS Spy for function test..."
"$NDDSHOME/bin/rtiddsspy" -printSample -qosFile "$PROJECT_ROOT/spy_transient.xml" -qosProfile SpyLib::TransientReliable > "$SERVICE_SPY_LOG" 2>&1 &
SERVICE_SPY_PID=$!
echo "✅ TRACE: RTI DDS Spy started with PID: $SERVICE_SPY_PID (Log: $SERVICE_SPY_LOG)"

# Now start the calculator service AFTER the agent
echo "🚀 TRACE: Starting calculator service..."
PYTHONUNBUFFERED=1 stdbuf -o0 -e0 python3 -u "$SERVICE_SCRIPT" > "$SERVICE_LOG" 2>&1 &
SERVICE_PID=$!
echo "✅ TRACE: Calculator service started with PID: $SERVICE_PID"

# Wait for function registration
echo "⏳ TRACE: Waiting for function registration..."
sleep 10

# Check Test 2 - Service Function Registration
echo "🔍 TRACE: Running Test 2 checks..."

# Check agent logs
check_log "$AGENT_LOG" "✅ TRACE: Agent created, starting run..." "Agent initialization" true
check_log "$AGENT_LOG" "MathTestAgent listening for requests" "Agent listening state" true

# Check DDS Spy logs for function registration
check_log "$SERVICE_SPY_LOG" 'New data.*topic="FunctionCapability"' "Spy received durable FunctionCapability data" true
check_log "$SERVICE_SPY_LOG" "New writer.*topic=\"CalculatorServiceReply\".*type=\"FunctionReply\".*name=\"Replier\"" "Service reply writer" true
check_log "$SERVICE_SPY_LOG" "reason: .*Function 'add' available.*" "Function discovery" true

# Clean up Test 2
echo "🧹 TRACE: Cleaning up Test 2..."
kill_process "$SERVICE_SPY_PID" "service spy" true
kill_process "$SERVICE_PID" "calculator service" false
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
