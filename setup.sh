#!/usr/bin/env bash
set -euo pipefail

# Genesis-LIB setup wrapper - simplest possible local install
# - Creates .venv (Python 3.10) if missing
# - Activates it
# - pip installs the package locally
# - Verifies import and basic CLI

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

echo "==> Checking Python version (requires 3.10.x)"
PYV=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")
if [ "$PYV" != "3.10" ]; then
  echo "Warning: Detected Python $PYV. Prefer Python 3.10 for this project." >&2
fi

if [ ! -d .venv ]; then
  echo "==> Creating virtual environment (.venv)"
  python3.10 -m venv .venv
fi

echo "==> Activating virtual environment"
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Upgrading pip"
pip install --upgrade pip >/dev/null 2>&1 || true

echo "==> Installing genesis-lib locally"
pip install .

echo "==> Verifying import"
python -c "import genesis_lib; print('OK import ->', genesis_lib.__file__)"

echo "==> Checking NDDSHOME (optional for DDS-based tests)"
if [ -z "${NDDSHOME:-}" ]; then
  echo "Note: NDDSHOME not set. DDS-based tests and spy diagnostics may be skipped."
else
  if [ ! -x "$NDDSHOME/bin/rtiddsspy" ]; then
    echo "Warning: rtiddsspy not found at $NDDSHOME/bin/rtiddsspy" >&2
  else
    echo "rtiddsspy detected at $NDDSHOME/bin/rtiddsspy"
  fi
fi

echo "==> Quick CLI check (genesis-monitor --help)"
if command -v genesis-monitor >/dev/null 2>&1; then
  genesis-monitor --help | head -n 3 || true
else
  echo "CLI genesis-monitor not found in PATH (unexpected)" >&2
fi

echo "==> Done. To activate later:"
echo "    source $PROJECT_ROOT/.venv/bin/activate"
echo "==> To run tests (optional):"
echo "    cd $PROJECT_ROOT/tests && source venv/bin/activate && ./run_all_tests.sh"







