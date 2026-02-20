#!/bin/bash
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.
# ####################################################################################
#
# Run all persistent memory tests.
# Usage: ./run_scripts/run_memory_tests.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "============================================================"
echo "  Genesis Persistent Memory — Full Test Suite"
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

run_test "test_functions/test_storage_backend.py"       "Test Gate 1+2+5: StorageBackend + Tokenizer + Dual-Pathway"
run_test "test_functions/test_persistent_adapter.py"     "Test Gate 3+4+5: PersistentMemoryAdapter + Config + Dual-Pathway"
run_test "test_functions/test_shared_memory.py"          "Test Gate 6: Multi-Agent Shared Memory"
run_test "test_functions/test_compaction.py"              "Test Gate 7: Compaction Engine"
run_test "test_functions/test_monitoring_integration.py"  "Test Gate 9: Monitoring Integration"
run_test "test_functions/test_pg_integration.py"          "Test Gate 11: PostgreSQL Integration (optional)"

echo "============================================================"
if [ $FAIL -eq 0 ]; then
    echo "  All persistent memory tests passed!"
else
    echo "  Some tests FAILED — see above."
    exit 1
fi
echo "============================================================"
