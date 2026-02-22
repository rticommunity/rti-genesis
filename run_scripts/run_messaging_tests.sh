#!/bin/bash
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.
# ####################################################################################
#
# Run all messaging interface tests (Telegram + Slack).
# Usage: ./run_scripts/run_messaging_tests.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "============================================================"
echo "  Genesis Messaging Interfaces — Full Test Suite"
echo "============================================================"
echo ""

FAIL=0

run_test() {
    local test_file="$1"
    local label="$2"
    echo "--- $label ---"
    if python "$test_file"; then
        echo ""
    else
        echo "  *** FAILED: $label ***"
        echo ""
        FAIL=1
    fi
}

run_test "examples/TelegramInterface/tests/test_telegram_interface.py"    "Telegram: Unit Tests"
run_test "examples/TelegramInterface/tests/test_telegram_acceptance.py"   "Telegram: GWT Acceptance Tests"
run_test "examples/SlackInterface/tests/test_slack_interface.py"          "Slack: Unit Tests"
run_test "examples/SlackInterface/tests/test_slack_acceptance.py"         "Slack: GWT Acceptance Tests"

echo "============================================================"
if [ $FAIL -eq 0 ]; then
    echo "  All messaging interface tests passed!"
else
    echo "  Some tests FAILED — see above."
    exit 1
fi
echo "============================================================"
