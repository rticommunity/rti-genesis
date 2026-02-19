#!/usr/bin/env bash
# Run backend parser unit tests
set -euo pipefail
cd "$(dirname "$0")/.."
echo "=== Running backend parser tests ==="
python tests/test_backends.py
echo "=== Backend parser tests complete ==="
