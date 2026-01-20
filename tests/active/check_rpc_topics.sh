#!/usr/bin/env bash
# Copyright (c) 2025, RTI & Jason Upchurch
set -euo pipefail

LOG_DIR="$(cd "$(dirname "$0")/../.." && pwd)/logs"

shopt -s nullglob
rc=0
for spy_log in "$LOG_DIR"/spy_*.log; do
  echo "=== Analyzing $spy_log ==="
  unified_req=$(grep -c "rti/connext/genesis/rpc/.*Request" "$spy_log" || true)
  unified_rep=$(grep -c "rti/connext/genesis/rpc/.*Reply" "$spy_log" || true)
  # Check for any legacy patterns (per-instance topics with GUIDs/UUIDs)
  legacy=$(grep -E "rti/connext/genesis/(CalculatorService|TextProcessorService|LetterCounterService)Request" "$spy_log" | grep -v "/rpc/" | wc -l || true)
  echo "unified_req=$unified_req unified_rep=$unified_rep legacy=$legacy"
  if [ "$legacy" -gt 0 ]; then
    echo "❌ FAIL: Legacy per-instance RPC topics detected"
    rc=1
  fi
  if [ "$unified_req" -eq 0 ] && [ "$unified_rep" -eq 0 ]; then
    echo "⚠️  WARNING: No unified RPC topics detected"
  else
    echo "✅ PASS: Unified RPC topics detected"
  fi
done
exit $rc


