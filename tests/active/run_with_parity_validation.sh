#!/usr/bin/env bash
# Copyright (c) 2025, RTI & Jason Upchurch
# Wrapper script to run a test with monitoring parity validation
#
# Usage: ./run_with_parity_validation.sh <test_script> [validation_duration]
#
# Example:
#   ./run_with_parity_validation.sh run_simple_agent.sh 30
#   ./run_with_parity_validation.sh run_math_interface_agent_simple.sh 45

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GENESIS_LIB_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <test_script> [validation_duration]"
    echo ""
    echo "Example:"
    echo "  $0 run_simple_agent.sh 30"
    echo "  $0 run_math_interface_agent_simple.sh 45"
    exit 1
fi

TEST_SCRIPT="$1"
VALIDATION_DURATION="${2:-30}"

# Check if test script exists
if [ ! -f "$SCRIPT_DIR/$TEST_SCRIPT" ]; then
    echo "ERROR: Test script not found: $SCRIPT_DIR/$TEST_SCRIPT"
    exit 1
fi

echo "=========================================="
echo "Test with Monitoring Parity Validation"
echo "=========================================="
echo "Test Script: $TEST_SCRIPT"
echo "Validation Duration: ${VALIDATION_DURATION}s"
echo ""

# Start Python validator in background
echo "Starting Python data-level validator..."
cd "$GENESIS_LIB_DIR"
source .venv/bin/activate
python3 "$SCRIPT_DIR/validate_monitoring_parity.py" "$VALIDATION_DURATION" > "$GENESIS_LIB_DIR/logs/parity_validation.log" 2>&1 &
VALIDATOR_PID=$!

echo "Validator PID: $VALIDATOR_PID"
echo "Validator log: $GENESIS_LIB_DIR/logs/parity_validation.log"
echo ""

# Give validator time to set up subscriptions
sleep 3

# Run the test
echo "Running test: $TEST_SCRIPT"
echo ""
cd "$SCRIPT_DIR"
./"$TEST_SCRIPT"
TEST_EXIT_CODE=$?

echo ""
echo "Test completed with exit code: $TEST_EXIT_CODE"
echo ""

# Wait for validator to finish
echo "Waiting for validator to complete..."
wait "$VALIDATOR_PID" 2>/dev/null || true
VALIDATOR_EXIT_CODE=$?

echo ""
echo "=========================================="
echo "Results Summary"
echo "=========================================="
echo "Test Exit Code: $TEST_EXIT_CODE"
echo "Validator Exit Code: $VALIDATOR_EXIT_CODE"
echo ""

# Show validator results
if [ -f "$GENESIS_LIB_DIR/logs/parity_validation.log" ]; then
    echo "Validator Output:"
    echo "---"
    cat "$GENESIS_LIB_DIR/logs/parity_validation.log"
    echo "---"
fi

echo ""
if [ "$TEST_EXIT_CODE" -eq 0 ] && [ "$VALIDATOR_EXIT_CODE" -eq 0 ]; then
    echo "✅ SUCCESS - Test passed AND monitoring parity verified"
    exit 0
elif [ "$TEST_EXIT_CODE" -ne 0 ]; then
    echo "❌ FAIL - Test failed (exit code: $TEST_EXIT_CODE)"
    exit "$TEST_EXIT_CODE"
else
    echo "⚠️  MISMATCH - Test passed but parity validation failed"
    exit "$VALIDATOR_EXIT_CODE"
fi

