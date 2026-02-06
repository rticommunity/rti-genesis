#!/bin/bash
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
#                                                                                    #
# RTI grants Licensee a license to use, modify, compile, and create derivative       #
# works of the Software. Licensee has the right to distribute object form only       #
# for use with RTI products. The Software is provided "as is", with no warranty      #
# of any type, including any warranty for fitness for any purpose. RTI is under no   #
# obligation to maintain or support the Software. RTI shall not be liable for any    #
# incidental or consequential damages arising out of the use or inability to use     #
# the software.                                                                      #
# ####################################################################################

# run_test_local_agent_with_functions.sh - A script to test TestLocalAgent with calculator functions
# This script starts calculator services and tests the local agent's ability to discover and use them
# Uses Ollama for local inference (no API key required)

# Set strict error handling
set -e

# Configuration
TIMEOUT=90  # Longer timeout for local model inference
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_DIR="$SCRIPT_DIR/../logs"
DEBUG=${DEBUG:-false}  # Set to true to show debug output
mkdir -p "$LOG_DIR"

# Get the project root directory
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
[ "$DEBUG" = "true" ] && echo "Project root: $PROJECT_ROOT"

# Get domain ID from environment (default to 0)
DOMAIN_ID="${GENESIS_DOMAIN_ID:-0}"
echo "Using DDS domain: $DOMAIN_ID"

# Set PYTHONPATH to include the project root
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

SPY_LOG="$LOG_DIR/spy_run_test_local_agent_with_functions.log"

# Initialize array to store PIDs
declare -a pids=()

# Function to display log content on failure
display_log_on_failure() {
    local log_file=$1
    local error_type=$2
    local error_message=$3
    
    echo "❌ ERROR: $error_message"
    echo "=================================================="
    echo "Log file contents ($log_file):"
    echo "=================================================="
    tail -n 20 "$log_file" | sed 's/^/  /'
    echo "=================================================="
    echo "Full log available at: $log_file"
    echo "=================================================="
}

# Function to cleanup processes
cleanup() {
    [ "$DEBUG" = "true" ] && echo "Cleaning up processes..."
    # Kill spy if running
    if [ -n "$SPY_PID" ] && kill -0 "$SPY_PID" 2>/dev/null; then
        kill "$SPY_PID" 2>/dev/null || true
    fi
    for pid in "${pids[@]}"; do
        if ps -p "$pid" > /dev/null; then
            kill "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null || true
        fi
    done
}

# Set up trap for cleanup on script termination
trap cleanup EXIT

# PRE-FLIGHT CHECKS FOR OLLAMA
echo "=================================================="
echo "Checking Ollama availability..."
echo "=================================================="

# Check if ollama command exists
if ! command -v ollama &> /dev/null; then
    echo "❌ ERROR: Ollama is not installed"
    echo "Install with: curl -fsSL https://ollama.com/install.sh | sh"
    exit 1
fi

# Check if Ollama server is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "❌ ERROR: Ollama server is not running"
    echo "Start with: ollama serve"
    echo "Or ensure Ollama is running in the background"
    exit 1
fi

# Check if required model is available
echo "Checking for nemotron-mini:latest model..."
if ! ollama list | grep -q "nemotron-mini"; then
    echo "⚠️  Warning: nemotron-mini:latest not found"
    echo "Attempting to pull the model (this may take a few minutes)..."
    if ! ollama pull nemotron-mini:latest; then
        echo "❌ ERROR: Failed to pull nemotron-mini:latest"
        echo "You may need to pull it manually: ollama pull nemotron-mini:latest"
        exit 1
    fi
    echo "✅ Model pulled successfully"
else
    echo "✅ Model nemotron-mini:latest is available"
fi

echo "✅ All Ollama pre-flight checks passed"
echo "=================================================="

# Start rtiddsspy to monitor DDS traffic
if [ -n "$NDDSHOME" ] && [ -f "$NDDSHOME/bin/rtiddsspy" ]; then
    RTIDDSSPY_PROFILEFILE="$PROJECT_ROOT/spy_transient.xml" "$NDDSHOME/bin/rtiddsspy" -domainId $DOMAIN_ID > "$SPY_LOG" 2>&1 &
    SPY_PID=$!
    [ "$DEBUG" = "true" ] && echo "Started rtiddsspy monitoring (PID: $SPY_PID, Log: $SPY_LOG)"
fi

# Main execution
echo "Starting TestLocalAgent with functions test..."
[ "$DEBUG" = "true" ] && echo "Logs will be saved to $LOG_DIR"

# Get domain argument if set
DOMAIN_ARG=""
if [ -n "${GENESIS_DOMAIN_ID:-}" ]; then
    DOMAIN_ARG="--domain ${GENESIS_DOMAIN_ID}"
    echo "Using domain ${GENESIS_DOMAIN_ID} for services"
fi

# Start calculator service in the background
echo "Starting calculator service..."
python -m test_functions.services.calculator_service $DOMAIN_ARG > "$LOG_DIR/calculator_service_local.log" 2>&1 &
CALC_PID=$!
pids+=("$CALC_PID")
echo "Started calculator service with PID $CALC_PID"

# Wait for services to start
echo "Waiting for services to start..."
sleep 10

# Function to run a single test
run_test() {
    local test_name=$1
    local question=$2
    local log_file="$LOG_DIR/test_local_agent_${test_name}.log"
    
    echo "=================================================="
    echo "Running test: $test_name"
    echo "Question: $question"
    echo "=================================================="
    
    # Run the Python script with timeout and capture output
    if timeout $TIMEOUT python "$SCRIPT_DIR/../helpers/test_local_agent.py" "$question" > "$log_file" 2>&1; then
        echo "✅ Test completed: $test_name"
        # Show last few lines of output
        tail -5 "$log_file" | sed 's/^/  /'
        return 0
    else
        display_log_on_failure "$log_file" "test_execution" "Test '$test_name' failed or timed out"
        return 1
    fi
}

# Run tests
TEST_PASSED=0

# Test 1: Basic arithmetic
if run_test "arithmetic" "What is 42 plus 24?"; then
    TEST_PASSED=$((TEST_PASSED + 1))
fi

# Test 2: Multiplication
if run_test "multiply" "Calculate 15 times 8"; then
    TEST_PASSED=$((TEST_PASSED + 1))
fi

# Test 3: Complex calculation
if run_test "complex" "What is 100 divided by 4 plus 10?"; then
    TEST_PASSED=$((TEST_PASSED + 1))
fi

echo "=================================================="
echo "Test Summary: $TEST_PASSED/3 tests passed"
echo "=================================================="

# Check DDS traffic
if [ -f "$SPY_LOG" ]; then
    if grep -q "Calculator" "$SPY_LOG"; then
        echo "✅ DDS RPC traffic detected"
    else
        echo "⚠️  Warning: No DDS RPC traffic detected in spy log"
    fi
fi

# Final result
if [ $TEST_PASSED -eq 3 ]; then
    echo "✅ LocalGenesisAgent test PASSED - All tests successful"
    exit 0
else
    echo "❌ LocalGenesisAgent test FAILED - $((3 - TEST_PASSED)) test(s) failed"
    exit 1
fi
