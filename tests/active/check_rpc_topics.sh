#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="$(cd "$(dirname "$0")/../.." && pwd)/logs"

shopt -s nullglob
rc=0
for spy_log in "$LOG_DIR"/spy_*.log; do
  echo "=== Analyzing $spy_log ==="
  unified_req=$(grep -c "rti/connext/genesis/rpc/CalculatorService.*Request" "$spy_log" || true)
  unified_rep=$(grep -c "rti/connext/genesis/rpc/CalculatorService.*Reply" "$spy_log" || true)
  legacy=$(grep -c "CalculatorService.*UUID.*Request" "$spy_log" || true)
  echo "unified_req=$unified_req unified_rep=$unified_rep legacy=$legacy"
  if [ "$legacy" -gt 0 ]; then
    echo "❌ FAIL: Legacy per-instance RPC topics detected"
    rc=1
  fi
done
exit $rc


