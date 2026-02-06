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

# Genesis Parallel Test Suite
# ===========================
#
# This script runs the complete Genesis test suite in PARALLEL with DDS domain isolation.
# Each test runs on its own DDS domain to prevent interference, drastically reducing
# total test time from ~10 minutes to ~2-3 minutes.
#
# Key features:
# - Domain isolation: Each test gets unique DDS domain (0-20)
# - Parallel execution: All tests launch simultaneously
# - Aggregated results: Collects and reports all test outcomes
# - Backward compatible: Uses same tests as run_all_tests.sh
#
# Prerequisites:
# - Python 3.10 or higher
# - RTI Connext DDS 7.3.0 or higher  
# - Required API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY) in environment
# - All dependencies installed via setup.sh
#
# Usage:
#   ./run_all_tests_parallel.sh
#
# Environment Variables:
#   NDDSHOME: Path to RTI Connext DDS installation
#   OPENAI_API_KEY: OpenAI API key for LLM tests
#   ANTHROPIC_API_KEY: Anthropic API key for Claude tests
#
# Exit Codes:
#   0: All tests passed successfully
#   1: One or more tests failed
#   2: Environment setup failed
#

set -e

# Configuration
TIMEOUT=120  # Default timeout in seconds per test
DEBUG=${DEBUG:-false}

# Get the script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

# Note: UDP-only transport is configured in USER_QOS_PROFILES.xml files
# in the working directories to avoid macOS shared memory exhaustion

cd "$SCRIPT_DIR"

# Resolve script path across new structure (active/) with backward compatibility
resolve_path() {
    local rel="$1"
    if [ -e "$rel" ]; then echo "$rel"; return 0; fi
    if [ -e "active/$rel" ]; then echo "active/$rel"; return 0; fi
    echo "$rel"
}

#########################################
# Environment activation and preflight  #
#########################################

# Require an active virtual environment
if [ -z "${VIRTUAL_ENV:-}" ]; then
    echo "Error: No virtual environment is active. Activate your project venv first:" >&2
    echo "  source .venv/bin/activate" >&2
    exit 2
fi

# Load project .env if present
if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
fi

# Ensure Python 3.10
PY_MM=$(python - <<'EOF'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
EOF
)
if [ "${PY_MM%%.*}" != "3" ] || [ "${PY_MM#*.}" != "10" ]; then
    echo "Error: Python 3.10 is required. Current python is ${PY_MM}." >&2
    exit 2
fi

# Require NDDSHOME
if [ -z "${NDDSHOME:-}" ]; then
    echo "Error: NDDSHOME is not set. Export NDDSHOME before running tests." >&2
    exit 2
fi

echo "ℹ️  Using unified monitoring topics (GraphTopology, Event)"
echo "ℹ️  Python: $PY_MM | NDDSHOME: $NDDSHOME"

# Set up log directory
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# Cleanup function
cleanup() {
    [ "$DEBUG" = "true" ] && echo "Cleaning up any remaining processes..."
    pkill -f "python.*calculator_service" || true
    pkill -f "python.*text_processor_service" || true
    pkill -f "python.*letter_counter_service" || true
    pkill -f "python.*simple_agent" || true
    pkill -f "python.*simple_client" || true
    pkill -f "python.*openai_chat_agent" || true
    pkill -f "python.*interface_cli" || true
    pkill -f "python.*test_agent" || true
    pkill -f "python.*personal_assistant" || true
    pkill -f "python.*weather_agent" || true
    [ "$DEBUG" = "true" ] && echo "Cleanup complete"
}

trap cleanup EXIT

#########################################
# Parallel test execution               #
#########################################

echo "🚀 Starting Genesis Parallel Test Suite..."
echo "📊 Tests will run in parallel with domain isolation"
START_TIME=$(date +%s)

# Arrays to track test execution
declare -a TEST_NAMES=()
declare -a TEST_PIDS=()
declare -a TEST_DOMAINS=()
declare -a TEST_LOG_FILES=()

# Function to launch a test in background with assigned domain
launch_test() {
    local test_script="$1"
    local domain_id="$2"
    local timeout_val="$3"
    local test_basename=$(basename "$test_script")
    local log_file="$LOG_DIR/parallel_${test_basename%.*}_domain${domain_id}.log"
    
    echo "  ▶️  Launching: $test_basename (domain $domain_id, timeout ${timeout_val}s)"
    
    # Launch test in background with GENESIS_DOMAIN_ID set in subshell environment
    if [[ "$test_script" == *.py ]]; then
        (
            export GENESIS_DOMAIN_ID=$domain_id
            export PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT
            timeout $timeout_val python "$test_script" > "$log_file" 2>&1
        ) &
    else
        (
            export GENESIS_DOMAIN_ID=$domain_id
            export PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT
            timeout $timeout_val bash "$test_script" > "$log_file" 2>&1
        ) &
    fi
    
    local pid=$!
    TEST_NAMES+=("$test_basename")
    TEST_PIDS+=("$pid")
    TEST_DOMAINS+=("$domain_id")
    TEST_LOG_FILES+=("$log_file")
}

# Launch all tests in parallel with unique domains
echo ""
echo "📋 Launching tests..."

# Core tests
launch_test "$(resolve_path run_test_agent_memory.sh)" 0 60
launch_test "$(resolve_path test_agent_to_agent_communication.py)" 1 120  
launch_test "$(resolve_path run_interface_agent_service_test.sh)" 2 120
launch_test "$(resolve_path run_math_interface_agent_simple.sh)" 3 60
launch_test "$(resolve_path run_math.sh)" 4 30
launch_test "$(resolve_path run_multi_math.sh)" 5 60
launch_test "$(resolve_path run_simple_agent.sh)" 6 60
launch_test "$(resolve_path run_simple_client.sh)" 7 60
launch_test "$(resolve_path test_calculator_durability.sh)" 8 60
launch_test "$(resolve_path start_services_and_cli.sh)" 10 90
launch_test "$(resolve_path test_genesis_framework.sh)" 11 120
launch_test "$(resolve_path test_mcp_agent.py)" 12 60
launch_test "$(resolve_path test_monitoring_complete.sh)" 13 90

# Triage-specific tests (additional coverage)
launch_test "$(resolve_path test_monitoring_graph_state.py)" 15 75
launch_test "$(resolve_path test_monitoring_interface_agent_pipeline.py)" 16 120
launch_test "$(resolve_path test_viewer_contract.py)" 17 30

# Conditional tests
if [ -n "${OPENAI_API_KEY:-}" ]; then
    launch_test "$(resolve_path run_test_agent_with_functions.sh)" 9 60
    launch_test "$(resolve_path test_monitoring.sh)" 14 90
else
    echo "  ⚠️  Skipping run_test_agent_with_functions.sh: OPENAI_API_KEY not set"
    echo "  ⚠️  Skipping test_monitoring.sh: OPENAI_API_KEY not set"
fi

# LocalGenesisAgent test (Ollama) - Domain 18
echo "  🤖 LocalGenesisAgent Test (Ollama)"
# Check if ollama is available
if command -v ollama &> /dev/null && curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    launch_test "$(resolve_path run_test_local_agent_with_functions.sh)" 18 90
else
    echo "  ⚠️  Skipping run_test_local_agent_with_functions.sh: Ollama not available (install from https://ollama.com)"
fi

echo ""
echo "⏳ Waiting for all tests to complete..."
echo "   (${#TEST_PIDS[@]} tests running in parallel)"
if [ "$DEBUG" = "true" ]; then
    echo "   DEBUG: PIDs: ${TEST_PIDS[*]}"
fi

# Wait for all test processes and capture their exit codes using temp file
EXITCODE_TMPDIR=$(mktemp -d)
declare -a TEST_EXIT_CODES=()

# Modified launch function to write exit codes to files
# (This requires updating launch_test, so we'll use polling instead)

# Poll for completion and capture exit codes via wait when each finishes
ALL_DONE=0
MAX_WAIT_SECONDS=300  # 5 minutes max
WAIT_START=$(date +%s)
declare -a CAPTURED_PIDS=()

while [ $ALL_DONE -eq 0 ]; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - WAIT_START))
    
    [ "$DEBUG" = "true" ] && echo "DEBUG: Wait loop iteration, elapsed=${ELAPSED}s, captured=${#CAPTURED_PIDS[@]}, total=${#TEST_PIDS[@]}"
    
    if [ $ELAPSED -gt $MAX_WAIT_SECONDS ]; then
        echo "⚠️  WARNING: Maximum wait time ($MAX_WAIT_SECONDS s) exceeded"
        break
    fi
    
    ALL_DONE=1
    for pid in "${TEST_PIDS[@]}"; do
        [ "$DEBUG" = "true" ] && echo "DEBUG: Checking PID $pid"
        # Skip if we already captured this PID
        if [[ " ${CAPTURED_PIDS[@]} " =~ " ${pid} " ]]; then
            continue
        fi
        
        # Check if process is still running
        if kill -0 "$pid" 2>/dev/null; then
            ALL_DONE=0
        else
            # Process finished - capture exit code and mark as captured
            wait "$pid" 2>/dev/null
            echo "$?" > "$EXITCODE_TMPDIR/$pid"
            CAPTURED_PIDS+=("$pid")
        fi
    done
    
    if [ $ALL_DONE -eq 0 ]; then
        sleep 1
    fi
done

# Build final exit code array in same order as TEST_PIDS
for pid in "${TEST_PIDS[@]}"; do
    if [ -f "$EXITCODE_TMPDIR/$pid" ]; then
        exit_code=$(cat "$EXITCODE_TMPDIR/$pid")
    else
        exit_code=999  # Unknown/timeout
    fi
    TEST_EXIT_CODES+=("$exit_code")
done

# Cleanup temp dir
rm -rf "$EXITCODE_TMPDIR"

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo "✅ All tests completed in ${ELAPSED}s"
echo ""

#########################################
# Aggregate and report results          #
#########################################

echo "=================================================="
echo "Test Results Summary"
echo "=================================================="

TOTAL_TESTS=${#TEST_NAMES[@]}
PASSED_TESTS=0
FAILED_TESTS=0
declare -a FAILED_TEST_NAMES=()

for i in "${!TEST_NAMES[@]}"; do
    test_name="${TEST_NAMES[$i]}"
    domain="${TEST_DOMAINS[$i]}"
    log_file="${TEST_LOG_FILES[$i]}"
    
    # Get exit code from the wait capture
    exit_code=${TEST_EXIT_CODES[$i]:-999}
    
    # Enhanced failure detection (matches run_all_tests.sh logic)
    failure_detected=0
    failure_reason=""
    
    # Check exit code
    if [ "$exit_code" -eq 124 ]; then
        failure_detected=1
        failure_reason="timeout"
    elif [ "$exit_code" -ne 0 ]; then
        failure_detected=1
        failure_reason="exit code $exit_code"
    fi
    
    # Check log file for test failures even if exit code is 0
    if [ -f "$log_file" ]; then
        # Check for explicit test failure markers
        if [ $failure_detected -eq 0 ] && grep -q "Some tests failed\|❌.*tests failed\|Test Results Summary:.*❌" "$log_file"; then
            failure_detected=1
            failure_reason="test failures in log"
        fi
        
        # Check for Python errors
        if [ $failure_detected -eq 0 ] && grep -q "ImportError\|NameError\|TypeError\|AttributeError\|RuntimeError\|SyntaxError\|IndentationError" "$log_file"; then
            failure_detected=1
            failure_reason="Python errors in log"
        fi
        
        # Check for unexpected termination (excluding normal cleanup kills)
        if [ $failure_detected -eq 0 ]; then
            temp_check=$(mktemp)
            grep -v "Killed: [0-9]\+\|TRACE.*Stopping\|TRACE.*Cleaning" "$log_file" > "$temp_check" 2>/dev/null || true
            if grep -q "Killed\|Segmentation fault\|Aborted\|core dumped" "$temp_check" 2>/dev/null; then
                failure_detected=1
                failure_reason="unexpected termination"
            fi
            rm -f "$temp_check"
        fi
    fi
    
    if [ $failure_detected -eq 0 ]; then
        echo "  ✅ PASS: $test_name (domain $domain)"
        ((PASSED_TESTS++))
    else
        echo "  ❌ FAIL: $test_name (domain $domain) - $failure_reason"
        echo "     Log: $log_file"
        FAILED_TEST_NAMES+=("$test_name")
        ((FAILED_TESTS++))
    fi
done

echo "=================================================="
echo "Total:  $TOTAL_TESTS tests"
echo "Passed: $PASSED_TESTS tests"
echo "Failed: $FAILED_TESTS tests"
echo "Time:   ${ELAPSED}s (parallel execution)"
echo "=================================================="

if [ "$FAILED_TESTS" -gt 0 ]; then
    echo ""
    echo "❌ FAILED TESTS:"
    for failed_test in "${FAILED_TEST_NAMES[@]}"; do
        echo "   - $failed_test"
    done
    echo ""
    echo "Review logs in: $LOG_DIR"
    exit 1
else
    echo ""
    echo "🎉 All tests PASSED!"
    exit 0
fi

