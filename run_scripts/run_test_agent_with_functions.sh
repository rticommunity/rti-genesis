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

# Set PYTHONPATH to include the project root
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

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

# Start Letter Counter Service
echo "Starting Letter Counter service..."
python -m test_functions.letter_counter_service > "$LOG_DIR/letter_counter_service.log" 2>&1 &
LC_PID=$!
pids+=("$LC_PID")
echo "Started Letter Counter service with PID $LC_PID"

# Start Text Processor Service
echo "Starting Text Processor service..."
python -m test_functions.text_processor_service > "$LOG_DIR/text_processor_service.log" 2>&1 &
TP_PID=$!
pids+=("$TP_PID")
echo "Started Text Processor service with PID $TP_PID"

# Quick check for Text Processor Service startup
sleep 2 # Give it a moment to crash if it's going to
if [ ! -s "$LOG_DIR/text_processor_service.log" ] && ! ps -p "$TP_PID" > /dev/null; then
    echo "❌ ERROR: Text Processor Service failed to start or died immediately. Log is empty and process $TP_PID is not running."
    # Attempt to capture any immediate stderr if the log redirection failed
    echo "Attempting to get stderr from a direct run (this might hang if the service starts successfully but doesn't exit):"
    # We won't run this by default, but it's a manual debug step one could uncomment
    # timeout 5 python -m test_functions.text_processor_service
    exit 1 # Exit early as a crucial service failed
fi

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
    PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT timeout $TIMEOUT python "$PROJECT_ROOT/run_scripts/test_agent.py" "$question" > "$log_file" 2>&1
    exit_code=$?
    sync # Ensure all output from test_agent.py is flushed to disk
    
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
            display_log_on_failure "$log_file" "rpc_error" "Did not see RPC call in function test (add)"
            cleanup
            exit 1
        fi
        
        # Check for function result
        if ! grep -q "Function add returned: {'result': 535353}" "$log_file"; then
            display_log_on_failure "$log_file" "result_error" "Did not see expected function result for add"
            cleanup
            exit 1
        fi
        
        echo "✅ SUCCESS: Function test (calculator) completed successfully"
        echo "🤖 Agent's Response:"
        echo "$agent_response"
        echo "📊 Function Call Confirmed:"
        grep "Calling function add via RPC" "$log_file"
        grep "Function add returned" "$log_file"
        echo "=================================================="
    elif [ "$test_name" = "letter_counter_test" ]; then
        # Check for RPC call to count_letter
        if ! grep -q "Calling function count_letter via RPC" "$log_file"; then
            display_log_on_failure "$log_file" "rpc_error" "Did not see RPC call in letter_counter_test (count_letter)"
            cleanup
            exit 1
        fi

        # Check for function result (e.g., "The letter 'l' appears 4 times")
        # We'll make this check more flexible, just looking for the presence of the result from the service
        if ! grep -q "GenesisRPCClient - INFO - Function count_letter returned:.*'result': 5" "$log_file"; then
            display_log_on_failure "$log_file" "result_error" "Did not see expected function result for count_letter (expected 5)"
            cleanup
            exit 1
        fi

        echo "✅ SUCCESS: Letter Counter test completed successfully"
        echo "🤖 Agent's Response:"
        echo "$agent_response"
        echo "📊 Function Call Confirmed:"
        grep "Calling function count_letter via RPC" "$log_file"
        grep "Function count_letter returned" "$log_file"
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

# Run the letter counter test
run_test "letter_counter_test" "How many times does the letter 'l' appear in 'hello silly world'?"

# Run the text processor test
# run_test "text_processor_test" "Count the words in the sentence: 'this is a test of the system'"

[ "$DEBUG" = "true" ] && echo "Logs are available in $LOG_DIR"
echo "=================================================="

# Exit with success
exit 0 