#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

# Start 3 calculator services (legacy only)
echo "Starting 3 calculator services (legacy)" | tee "$LOG_DIR/parity.log"
USE_UNIFIED_RPC=false python3 "$ROOT_DIR/test_functions/services/calculator_service.py" >"$LOG_DIR/svc1_legacy.log" 2>&1 &
PID1=$!
USE_UNIFIED_RPC=false python3 "$ROOT_DIR/test_functions/services/calculator_service.py" >"$LOG_DIR/svc2_legacy.log" 2>&1 &
PID2=$!
USE_UNIFIED_RPC=false python3 "$ROOT_DIR/test_functions/services/calculator_service.py" >"$LOG_DIR/svc3_legacy.log" 2>&1 &
PID3=$!
sleep 2

echo "Running old path client calls" | tee -a "$LOG_DIR/parity.log"
USE_UNIFIED_RPC=false python3 - <<'PY'
import asyncio, os
from genesis_lib.rpc_client import GenesisRPCClient

async def main():
    c = GenesisRPCClient("CalculatorService", timeout=5)
    await c.wait_for_service(10)
    r1 = await c.call_function("add", x=5, y=3)
    r2 = await c.call_function("multiply", x=2, y=4)
    print(r1)
    print(r2)
    c.close()
asyncio.run(main())
PY
OLD_OUT=$?

kill $PID1 $PID2 $PID3 || true
sleep 1

# Start 3 calculator services (unified)
echo "Starting 3 calculator services (unified)" | tee -a "$LOG_DIR/parity.log"
USE_UNIFIED_RPC=true python3 "$ROOT_DIR/test_functions/services/calculator_service.py" >"$LOG_DIR/svc1_unified.log" 2>&1 &
PID1=$!
USE_UNIFIED_RPC=true python3 "$ROOT_DIR/test_functions/services/calculator_service.py" >"$LOG_DIR/svc2_unified.log" 2>&1 &
PID2=$!
USE_UNIFIED_RPC=true python3 "$ROOT_DIR/test_functions/services/calculator_service.py" >"$LOG_DIR/svc3_unified.log" 2>&1 &
PID3=$!
sleep 2

echo "Running new path client calls" | tee -a "$LOG_DIR/parity.log"
USE_UNIFIED_RPC=true python3 - <<'PY'
import asyncio, os
from genesis_lib.rpc_client_v2 import GenesisRPCClientV2

async def main():
    c = GenesisRPCClientV2("CalculatorService", timeout_seconds=5)
    r1 = await c.call("add", {"x": 5, "y": 3})
    r2 = await c.call("multiply", {"x": 2, "y": 4})
    print(r1)
    print(r2)
    c.close()
asyncio.run(main())
PY
NEW_OUT=$?

kill $PID1 $PID2 $PID3 || true

if [ "$OLD_OUT" -ne 0 ] || [ "$NEW_OUT" -ne 0 ]; then
  echo "❌ RPC parity script failed" | tee -a "$LOG_DIR/parity.log"
  exit 1
fi

echo "✅ RPC parity script executed basic checks" | tee -a "$LOG_DIR/parity.log"


