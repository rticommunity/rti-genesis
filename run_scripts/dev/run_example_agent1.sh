#!/bin/bash

# run_example_agent1.sh - A script to test the ExampleAgent1 implementation
# This script runs the example agent with proper error handling and logging

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

# Function to clean up processes
cleanup() {
    [ "$DEBUG" = "true" ] && echo "Cleaning up any remaining processes..."
    pkill -f "python.*example_agent1" || true
    [ "$DEBUG" = "true" ] && echo "Cleanup complete"
}

# Set up trap for cleanup on script termination
trap cleanup EXIT

# Main execution
echo "Starting ExampleAgent1 test..."
[ "$DEBUG" = "true" ] && echo "Logs will be saved to $LOG_DIR"

# Run the example agent with timeout
log_file="$LOG_DIR/example_agent1_test.log"
echo "=================================================="
echo "Running example_agent1.py with ${TIMEOUT}s timeout..."
[ "$DEBUG" = "true" ] && echo "Log file: $log_file"
echo "=================================================="

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ ERROR: OPENAI_API_KEY environment variable is not set"
    echo "Please set your OpenAI API key before running this test"
    exit 1
fi

# Run the Python script with timeout and capture output
PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT timeout $TIMEOUT python "$PROJECT_ROOT/example_agent1.py" > "$log_file" 2>&1
exit_code=$?

# Check exit status
if [ $exit_code -eq 124 ]; then
    display_log_on_failure "$log_file" "timeout" "example_agent1.py timed out after ${TIMEOUT}s"
    cleanup
    exit 1
elif [ $exit_code -ne 0 ]; then
    display_log_on_failure "$log_file" "exit_code" "example_agent1.py failed with exit code $exit_code"
    cleanup
    exit 1
fi

# Check for Python errors in the log
if grep -q "ImportError\|NameError\|TypeError\|AttributeError\|RuntimeError\|SyntaxError\|IndentationError" "$log_file"; then
    display_log_on_failure "$log_file" "python_error" "example_agent1.py encountered Python errors"
    cleanup
    exit 1
fi

# Check for unexpected error messages in the log, excluding expected ones
# First, create a temporary file with error messages
temp_errors=$(mktemp)
grep "^ERROR:\|^Error:\|^error:\|Traceback (most recent call last)\|Exception:" "$log_file" > "$temp_errors" || true

# Then check if there are any unexpected errors (excluding known ones)
if [ -s "$temp_errors" ] && ! grep -q "No functions discovered" "$temp_errors"; then
    display_log_on_failure "$log_file" "unexpected_error" "example_agent1.py encountered unexpected errors"
    rm "$temp_errors"
    cleanup
    exit 1
fi
rm "$temp_errors"

# Check for successful agent response
if ! grep -q "Agent response:" "$log_file"; then
    display_log_on_failure "$log_file" "response_error" "example_agent1.py did not produce a response"
    cleanup
    exit 1
fi

# Check that the agent handled the no-functions case gracefully
if grep -q "No functions discovered" "$log_file"; then
    echo "ℹ️ Note: No functions were discovered in the distributed system (this is expected)"
fi

echo "✅ SUCCESS: example_agent1.py completed successfully"
echo "=================================================="

# Extract and display the agent's response
agent_response=$(grep "Agent response:" "$log_file" | sed 's/Agent response: //')
if [ -n "$agent_response" ]; then
    echo "🤖 Agent's Response:"
    echo "$agent_response"
    echo "=================================================="
fi

[ "$DEBUG" = "true" ] && echo "Logs are available in $LOG_DIR"
echo "=================================================="

# Exit with success
exit 0 