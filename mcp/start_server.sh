#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Load .env if present for NDDSHOME/API keys
if [ -f "$ROOT_DIR/.env" ]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
fi

# Run preflight checks
if ! bash "$ROOT_DIR/mcp/preflight.sh"; then
  echo "[start_server] Preflight failed. Fix issues above and retry."
  exit 1
fi

echo "[start_server] Starting MCP server (genesis-runner) ..."
exec "$ROOT_DIR/venv/bin/python" -m genesis_mcp.test_runner_server
