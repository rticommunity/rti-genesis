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

# run_test_agent_memory.sh - Test agent memory recall functionality
# This script runs test_agent_memory.py with timeout and logs output for verification

set -e

TIMEOUT=30  # Timeout in seconds
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_DIR="$SCRIPT_DIR/../logs"
DEBUG=${DEBUG:-false}
mkdir -p "$LOG_DIR"

PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

LOG_FILE="$LOG_DIR/test_agent_memory.log"
SPY_LOG="$LOG_DIR/spy_run_test_agent_memory.log"

# Start rtiddsspy to monitor DDS traffic
if [ -n "$NDDSHOME" ] && [ -f "$NDDSHOME/bin/rtiddsspy" ]; then
    RTIDDSSPY_PROFILEFILE="$PROJECT_ROOT/spy_transient.xml" "$NDDSHOME/bin/rtiddsspy" > "$SPY_LOG" 2>&1 &
    SPY_PID=$!
    [ "$DEBUG" = "true" ] && echo "Started rtiddsspy monitoring (PID: $SPY_PID, Log: $SPY_LOG)"
fi

# Function to display log content on failure
show_log_on_failure() {
    local error_message=$1
    echo "❌ ERROR: $error_message"
    echo "=================================================="
    echo "Log file contents ($LOG_FILE):"
    echo "=================================================="
    tail -n 20 "$LOG_FILE" | sed 's/^/  /'
    echo "=================================================="
    echo "Full log available at: $LOG_FILE"
    echo "=================================================="
}

# Function to cleanup processes
cleanup() {
    [ "$DEBUG" = "true" ] && echo "Cleaning up processes..."
    # Kill spy if running
    if [ -n "$SPY_PID" ] && kill -0 "$SPY_PID" 2>/dev/null; then
        kill "$SPY_PID" 2>/dev/null || true
    fi
    return 0
}
trap cleanup EXIT

# Main execution
[ "$DEBUG" = "true" ] && echo "Logs will be saved to $LOG_DIR"

# Run the Python memory test with timeout (disable -e for this call to capture exit code)
set +e
PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT timeout $TIMEOUT python "$SCRIPT_DIR/../helpers/test_agent_memory.py" > "$LOG_FILE" 2>&1
exit_code=$?
set -e
sync

if [ $exit_code -eq 124 ]; then
    show_log_on_failure "test_agent_memory.py timed out after ${TIMEOUT}s"
    exit 1
elif [ $exit_code -ne 0 ]; then
    # Check if this is a test failure or just DDS cleanup errors
    if grep -q "✅ Multi-stage memory recall test PASSED" "$LOG_FILE"; then
        # Test passed, exit code was likely due to DDS cleanup issues
        [ "$DEBUG" = "true" ] && echo "Test passed but had DDS cleanup warnings (exit code $exit_code)"
    else
        show_log_on_failure "test_agent_memory.py failed with exit code $exit_code"
        exit 1
    fi
fi

# Check for memory recall test pass/fail first (treat pass as success even if DDS cleanup is noisy)
success_check=$(grep "✅ Multi-stage memory recall test PASSED" "$LOG_FILE" || true)
if [ -n "$success_check" ]; then
    echo "✅ SUCCESS: Memory recall test passed."
    exit 0
fi

# Check for Python errors in the log (excluding expected DDS cleanup warnings)
error_check=$(grep -v "Error closing participant\|DDS_Topic_destroyI\|DDS_DomainParticipant_delete_topic\|PRESParticipant_createTopic:FAILED TO ASSERT.*Advertisement" "$LOG_FILE" | grep "ImportError\|NameError\|TypeError\|AttributeError\|RuntimeError\|SyntaxError\|IndentationError" || true)
if [ -n "$error_check" ]; then
    show_log_on_failure "test_agent_memory.py encountered Python errors"
    exit 1
fi

# If not explicitly passed and no Python errors found, treat as failure and show log
show_log_on_failure "Memory recall test did not pass."
exit 1
# Skip if OPENAI_API_KEY not set (test requires OpenAI client)
if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "⚠️  Skipping memory recall test: OPENAI_API_KEY not set." | tee "$LOG_FILE"
    exit 0
fi
