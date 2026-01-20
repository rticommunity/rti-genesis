#!/usr/bin/env bash
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


