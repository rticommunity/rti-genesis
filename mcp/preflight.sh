#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "[preflight] Repo root: $ROOT_DIR"

# 1) venv python
if [ ! -x "$ROOT_DIR/venv/bin/python" ]; then
  echo "[preflight] ERROR: venv missing. Create it and install deps:"
  echo "  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && pip install -e ."
  exit 1
fi

PY_VER="$($ROOT_DIR/venv/bin/python - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
echo "[preflight] Python: $($ROOT_DIR/venv/bin/python --version)"
if [ "${PY_VER}" != "3.10" ]; then
  echo "[preflight] ERROR: Python 3.10 required, found ${PY_VER}"
  exit 1
fi

# 2) mcp package
if ! "$ROOT_DIR/venv/bin/python" - <<'PY'
import sys
try:
    try:
        from mcp.server.fastmcp import FastMCP  # noqa: F401
        impl = 'FastMCP'
    except Exception:
        from mcp.server import Server  # noqa: F401
        impl = 'Server'
except Exception as e:
    print(e)
    raise SystemExit(1)
print("OK")
PY
then
  echo "[preflight] ERROR: MCP SDK imports failed in venv. Install/upgrade with:"
  echo "  source venv/bin/activate && pip install -U mcp"
  exit 1
fi

# 3) DDS (advisory but recommended)
RESOLVED_SPY=""
if [ -n "${RTI_BIN_DIR:-}" ] && [ -x "$RTI_BIN_DIR/rtiddsspy" ]; then
  RESOLVED_SPY="$RTI_BIN_DIR/rtiddsspy"
elif [ -n "${NDDSHOME:-}" ] && [ -x "$NDDSHOME/bin/rtiddsspy" ]; then
  RESOLVED_SPY="$NDDSHOME/bin/rtiddsspy"
fi
echo "[preflight] NDDSHOME=${NDDSHOME:-unset}"
echo "[preflight] rtiddsspy=${RESOLVED_SPY:-missing}"
if [ -z "$RESOLVED_SPY" ]; then
  echo "[preflight] WARNING: rtiddsspy not found. DDS-dependent tools will fail."
fi

# 4) OPENAI (advisory)
echo "[preflight] OPENAI_API_KEY=${OPENAI_API_KEY:+SET}" 

echo "[preflight] OK"
exit 0
