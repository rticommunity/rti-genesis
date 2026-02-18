#!/usr/bin/env bash
# Run live backend tests (skips if CLI not installed)
set -euo pipefail
cd "$(dirname "$0")/.."
echo "=== Running live backend tests ==="
python tests/test_live_backend.py
echo "=== Live backend tests complete ==="
