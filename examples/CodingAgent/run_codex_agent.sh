#!/usr/bin/env bash
# Launch CodingGenesisAgent with Codex backend
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Activate venv and source .env
if [ -f "$ROOT_DIR/venv/bin/activate" ]; then
    source "$ROOT_DIR/venv/bin/activate"
fi
if [ -f "$ROOT_DIR/.env" ]; then
    source "$ROOT_DIR/.env"
fi

export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

exec python "$SCRIPT_DIR/coding_genesis_agent.py" --backend codex "$@"
