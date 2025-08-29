#!/bin/bash

# run_test_agent_with_functions.sh - A script to test TestAgent with calculator functions
# This script starts calculator services and tests the agent's ability to discover and use them

# Set strict error handling
set -e

# Configuration
TIMEOUT=60  # Timeout in seconds
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_DIR="$SCRIPT_DIR/../logs"
DEBUG=${DEBUG:-false}  # Set to true to show debug output
mkdir -p "$LOG_DIR"

# Get the project root directory
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
[ "$DEBUG" = "true" ] && echo "Project root: $PROJECT_ROOT"

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
    for pid in "${pids[@]}"; do
        if ps -p "$pid" > /dev/null; then
            kill "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null || true
        fi
    done
    pkill -f "python.*test_agent" || true
}

# Set up trap for cleanup on script termination
trap cleanup EXIT

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ ERROR: OPENAI_API_KEY environment variable is not set"
    echo "Please set your OpenAI API key before running this test"
    exit 1
fi

# Main execution
echo "Starting TestAgent with functions test..."
[ "$DEBUG" = "true" ] && echo "Logs will be saved to $LOG_DIR"

# Start multiple calculator services in the background
echo "Starting calculator services..."
for i in {1..3}; do
    python -m test_functions.calculator_service > "$LOG_DIR/calculator_service_$i.log" 2>&1 &
    CALC_PID=$!
    pids+=("$CALC_PID")
    echo "Started calculator service $i with PID $CALC_PID"
done

# Wait for services to start
echo "Waiting for services to start..."
sleep 10

# Function to run a single test
run_test() {
    local test_name=$1
    local question=$2
    local log_file="$LOG_DIR/test_agent_${test_name}.log"
    
    echo "=================================================="
    echo "Running test: $test_name"
    echo "Question: $question"
    echo "=================================================="
    
    # Run the Python script with timeout and capture output
    PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT timeout $TIMEOUT python "$PROJECT_ROOT/run_scripts/helpers/test_agent.py" "$question" > "$log_file" 2>&1
    exit_code=$?
    
    # Check exit status
    if [ $exit_code -eq 124 ]; then
        display_log_on_failure "$log_file" "timeout" "test_agent.py timed out after ${TIMEOUT}s"
        cleanup
        exit 1
    elif [ $exit_code -ne 0 ]; then
        display_log_on_failure "$log_file" "exit_code" "test_agent.py failed with exit code $exit_code"
        cleanup
        exit 1
    fi
    
    # Check for Python errors in the log
    if grep -q "ImportError\|NameError\|TypeError\|AttributeError\|RuntimeError\|SyntaxError\|IndentationError" "$log_file"; then
        display_log_on_failure "$log_file" "python_error" "test_agent.py encountered Python errors"
        cleanup
        exit 1
    fi
    
    # Extract and display the agent's response
    agent_response=$(grep "Agent response:" "$log_file" | sed 's/Agent response: //')
    if [ -z "$agent_response" ]; then
        display_log_on_failure "$log_file" "response_error" "test_agent.py did not produce a response"
        cleanup
        exit 1
    fi
    
    # Test-specific checks
    if [ "$test_name" = "function_test" ]; then
        # Check for RPC call in function test
        if ! grep -q "Calling function add via RPC" "$log_file"; then
            display_log_on_failure "$log_file" "rpc_error" "Did not see RPC call in function test"
            cleanup
            exit 1
        fi
        
        # Check for function result
        if ! grep -q "Function add returned: {'result': 535353}" "$log_file"; then
            display_log_on_failure "$log_file" "result_error" "Did not see expected function result"
            cleanup
            exit 1
        fi
        
        echo "✅ SUCCESS: Function test completed successfully"
        echo "🤖 Agent's Response:"
        echo "$agent_response"
        echo "📊 Function Call Confirmed:"
        grep "Calling function add via RPC" "$log_file"
        grep "Function add returned" "$log_file"
        echo "=================================================="
    else
        # For non-function test, ensure no RPC calls were made
        if grep -q "Calling function.*via RPC" "$log_file"; then
            display_log_on_failure "$log_file" "rpc_error" "Unexpected RPC call in non-function test"
            cleanup
            exit 1
        fi
        
        echo "✅ SUCCESS: Non-function test completed successfully"
        echo "🤖 Agent's Response:"
        echo "$agent_response"
        echo "📊 Confirmed: No function calls were made"
        echo "=================================================="
    fi
    
    return 0
}

# Run the function test
run_test "function_test" "Can you add 424242 and 111111?"

# Run the non-function test
run_test "non_function_test" "Tell me a joke"

[ "$DEBUG" = "true" ] && echo "Logs are available in $LOG_DIR"
echo "=================================================="

# Exit with success
exit 0 
