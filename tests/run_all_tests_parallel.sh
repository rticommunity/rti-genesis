#!/bin/bash

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
# Copyright (c) 2025, RTI & Jason Upchurch

set -e

# Configuration
TIMEOUT=120  # Default timeout in seconds per test
DEBUG=${DEBUG:-false}

# Get the script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

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
    local timeout="$3"
    local test_basename=$(basename "$test_script")
    local log_file="$LOG_DIR/parallel_${test_basename%.*}_domain${domain_id}.log"
    
    echo "  ▶️  Launching: $test_basename (domain $domain_id, timeout ${timeout}s)"
    
    # Export domain for test to use
    export GENESIS_DOMAIN_ID=$domain_id
    
    # Launch test in background
    if [[ "$test_script" == *.py ]]; then
        (PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT timeout $timeout python "$test_script" > "$log_file" 2>&1; echo $? > "${log_file}.exit") &
    else
        (PYTHONPATH=$PYTHONPATH:$PROJECT_ROOT timeout $timeout bash "$test_script" > "$log_file" 2>&1; echo $? > "${log_file}.exit") &
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

echo ""
echo "⏳ Waiting for all tests to complete..."
echo "   (${#TEST_PIDS[@]} tests running in parallel)"

# Wait for all background jobs
for pid in "${TEST_PIDS[@]}"; do
    wait "$pid" || true
done

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
    exit_file="${log_file}.exit"
    
    if [ -f "$exit_file" ]; then
        exit_code=$(cat "$exit_file")
        rm -f "$exit_file"
    else
        exit_code=999  # Unknown/killed
    fi
    
    if [ "$exit_code" -eq 0 ]; then
        echo "  ✅ PASS: $test_name (domain $domain)"
        ((PASSED_TESTS++))
    else
        echo "  ❌ FAIL: $test_name (domain $domain, exit $exit_code)"
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

