#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

export PYTHONUNBUFFERED=1
export GENESIS_DOMAIN="${GENESIS_DOMAIN:-0}"

cd "$ROOT_DIR"
python examples/GraphInterface/server.py


