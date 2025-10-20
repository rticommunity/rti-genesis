#!/usr/bin/env bash

# Genesis Fail-Fast Triage Test Suite
# -----------------------------------
# A new, optional runner that executes comprehensive tests first and,
# on failure, runs targeted subtests to isolate likely causes quickly.
#
# Keeps run_all_tests.sh intact. This script is safe to iterate on.
#
# Behavior:
# - Preflight: venv/.env, Python 3.10, locate rtiddsspy
# - DDS writer sweep: checks for writers on Genesis topics (excludes generic noise)
#   Note: this sweep logs warnings instead of aborting; it’s advisory.
# - Stages: memory -> agent_to_agent -> pipeline
# - On failure, triage subtests run in order to narrow down root cause
# - Stops at first definitive failure (fail-fast)
#
# Usage:
#   ./run_scripts/run_triage_suite.sh
#   DEBUG=true ./run_scripts/run_triage_suite.sh
#
set -euo pipefail

DEBUG=${DEBUG:-false}
TIMEOUT_DEFAULT=120

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

cd "$SCRIPT_DIR"

# Resolve script path across new structure (active/) with backward compatibility
resolve_path() {
  local rel="$1"
  if [ -e "$rel" ]; then echo "$rel"; return 0; fi
  if [ -e "active/$rel" ]; then echo "active/$rel"; return 0; fi
  echo "$rel"
}

log() { echo "$@"; }
dbg() { [ "$DEBUG" = "true" ] && echo "[DEBUG] $@" || true; }

# Activate venv and .env if present
if [ -z "${VIRTUAL_ENV:-}" ] && [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/venv/bin/activate"
fi
if [ -f "$PROJECT_ROOT/.env" ]; then
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
fi

# Python version check (3.10)
PY_MM=$(python - <<'EOF'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
EOF
)
if [ "${PY_MM%%.*}" != "3" ] || [ "${PY_MM#*.}" != "10" ]; then
  echo "Error: Python 3.10 is required. Current python is ${PY_MM}." >&2
  echo "Hint: run 'source venv/bin/activate' before invoking this script." >&2
  exit 2
fi

# Locate NDDSHOME and rtiddsspy
if [ -z "${NDDSHOME:-}" ]; then
  guess=$(ls -d /Applications/rti_connext_dds-* 2>/dev/null | sort -V | tail -n1)
  if [ -z "$guess" ]; then
    guess=$(ls -d "$HOME"/rti_connext_dds-* 2>/dev/null | sort -V | tail -n1)
  fi
  [ -n "$guess" ] && export NDDSHOME="$guess"
fi

# Using unified monitoring topics (GraphTopology, Event)

resolve_rtiddsspy() {
  if [ -n "${RTIDDSSPY_BIN:-}" ]; then
    echo "$RTIDDSSPY_BIN"; return 0
  fi
  if [ -n "${RTI_BIN_DIR:-}" ] && [ -x "${RTI_BIN_DIR}/rtiddsspy" ]; then
    echo "${RTI_BIN_DIR}/rtiddsspy"; return 0
  fi
  if [ -n "${NDDSHOME:-}" ] && [ -x "${NDDSHOME}/bin/rtiddsspy" ]; then
    echo "${NDDSHOME}/bin/rtiddsspy"; return 0
  fi
  return 1
}

RTIDDSSPY_BIN=$(resolve_rtiddsspy || true)
if [ -z "$RTIDDSSPY_BIN" ]; then
  echo "Warning: rtiddsspy not found. DDS writer sweep will be skipped." >&2
fi

# DDS writer sweep (advisory): look only at Genesis topics to reduce false-positives.
dds_writer_sweep() {
  [ -z "$RTIDDSSPY_BIN" ] && return 0
  local SWEEP_LOG="$LOG_DIR/triage_dds_sweep.log"
  rm -f "$SWEEP_LOG"
  # Topics most tests use; adjust as needed
  local topics=(
    'Advertisement'
    'rti/connext/genesis/rpc/CalculatorServiceRequest' 'rti/connext/genesis/rpc/CalculatorServiceReply'
    'InterfaceAgentRequest' 'InterfaceAgentReply'
    'MathTestServiceRequest' 'MathTestServiceReply'
  )
  dbg "Running DDS writer sweep on topics: ${topics[*]}"
  "$RTIDDSSPY_BIN" -printSample $(printf -- " -topic %q" "${topics[@]}") -duration 3 > "$SWEEP_LOG" 2>&1 || true
  if grep -E '(New writer for topic|SAMPLE for topic)' "$SWEEP_LOG" >/dev/null 2>&1; then
    echo "⚠️ DDS sweep: Activity detected on Genesis topics before tests start (see $SWEEP_LOG)." >&2
    echo "   Proceeding anyway (advisory sweep). If failures occur, re-run after cleanup." >&2
  else
    dbg "DDS sweep: No pre-existing activity on target topics."
  fi
}

# Generic runner with timeout and primary log
run_with_timeout() {
  local script_path=$1
  local timeout=${2:-$TIMEOUT_DEFAULT}
  local base=$(basename "$script_path")
  local log_file="$LOG_DIR/triage_${base%.*}.log"

  echo "=================================================="
  echo "Running $script_path with ${timeout}s timeout..."
  echo "Log: $log_file"
  echo "=================================================="

  if [[ "$script_path" == *.py ]]; then
    PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$PROJECT_ROOT" timeout "$timeout" python "$script_path" > "$log_file" 2>&1 || return $?
  else
    PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$PROJECT_ROOT" timeout "$timeout" bash "$script_path" > "$log_file" 2>&1 || return $?
  fi
}

show_tail() {
  local file=$1
  if [ -f "$file" ]; then
    echo "--- tail: $file ---"; tail -n 40 "$file"; echo "--- end ---"
  fi
}

triage_summary() {
  local summary_file="$LOG_DIR/triage_summary.txt"
  echo "$1" >> "$summary_file"
  echo "Triage summary updated: $summary_file"
}

fail_and_exit() {
  echo "❌ $1"
  shift
  for f in "$@"; do show_tail "$f"; done
  triage_summary "$1"
  exit 1
}

main() {
  echo "Starting Genesis triage suite..."
  echo "Python: $PY_MM | NDDSHOME=${NDDSHOME:-unset} | rtiddsspy=${RTIDDSSPY_BIN:-missing}"

  dds_writer_sweep || true

  # Stage 1: Memory
  if ! run_with_timeout "$(resolve_path run_test_agent_memory.sh)" 60; then
    MEM_LOG="$PROJECT_ROOT/logs/test_agent_memory.log"
    fail_and_exit "Stage: Memory recall failed" "${LOG_DIR}/triage_run_test_agent_memory.log" "$MEM_LOG" \
      "memory failure — run_math.sh will often confirm if RPC path is still healthy"
  fi
  echo "✅ Stage 1 passed: Memory recall"

  # Stage 2: Agent-to-Agent (comprehensive)
  if ! run_with_timeout "$(resolve_path test_agent_to_agent_communication.py)" 120; then
    echo "⚠️ Agent↔Agent failed — running targeted subtests..."
    # Subtest A: Interface→Agent→Service pipeline
    if run_with_timeout "$(resolve_path run_interface_agent_service_test.sh)" 75; then
      fail_and_exit "Agent↔Agent failed; pipeline passed (multi-agent/tooling issue likely)" \
        "${LOG_DIR}/triage_test_agent_to_agent_communication.log" \
        "agent-to-agent failed while pipeline passed — isolate @genesis_tool or discovery between agents"
    fi
    # Subtest B: Math simple (RPC + discovery)
    if run_with_timeout "$(resolve_path run_math_interface_agent_simple.sh)" 60; then
      fail_and_exit "Agent↔Agent and pipeline failed; math simple passed (RPC path OK, multi-stage flows failing)" \
        "${LOG_DIR}/triage_test_agent_to_agent_communication.log" \
        "rpc path healthy; focus on interface-agent coordination or topic filtering"
    fi
    # Subtest C: Math client (leanest RPC)
    if run_with_timeout "$(resolve_path run_math.sh)" 30; then
      fail_and_exit "High-level flows failed; basic RPC passed (likely discovery/registration sequencing)" \
        "${LOG_DIR}/triage_test_agent_to_agent_communication.log" \
        "consider timing/durability; check Advertisement durability"
    fi
    # If all subtests fail, declare broad DDS/RPC failure
    fail_and_exit "Agent↔Agent failed; all triage subtests failed (DDS/RPC baseline failing)" \
      "${LOG_DIR}/triage_test_agent_to_agent_communication.log" \
      "check DDS install/env (NDDSHOME, library paths); verify rtiddsspy and retry after cleanup"
  fi
  echo "✅ Stage 2 passed: Agent↔Agent"

  # Stage 3: Pipeline
  if ! run_with_timeout "$(resolve_path run_interface_agent_service_test.sh)" 75; then
    echo "⚠️ Pipeline failed — running targeted subtests..."
    if run_with_timeout "$(resolve_path run_math_interface_agent_simple.sh)" 60; then
      fail_and_exit "Pipeline failed; math simple passed (service RPC OK, interface/agent coupling issue)" \
        "${LOG_DIR}/triage_run_interface_agent_service_test.log" \
        "inspect interface logs, connection selection, and agent discovery callbacks"
    fi
    if run_with_timeout "$(resolve_path run_math.sh)" 30; then
      fail_and_exit "Pipeline failed; basic RPC passed (interface layer issue likely)" \
        "${LOG_DIR}/triage_run_interface_agent_service_test.log" \
        "focus on interface selection and expected log tokens"
    fi
    fail_and_exit "Pipeline and subtests failed (RPC baseline failing)" \
      "${LOG_DIR}/triage_run_interface_agent_service_test.log" \
      "verify calculator service and client basic path"
  fi
  echo "✅ Stage 3 passed: Interface→Agent→Service"

  # Stage 4: Monitoring (graph-state invariants + optional full monitoring test)
  echo "🔎 Stage 4: Monitoring coverage"

  # 4a) Graph-state invariants (no API keys required)
  if ! run_with_timeout "$(resolve_path test_monitoring_graph_state.py)" 75; then
    fail_and_exit "Monitoring graph-state invariants failed" \
      "${LOG_DIR}/triage_test_monitoring_graph_state.log" \
      "graph-state invariants failed — check node uniqueness, service→function edges, and BUSY→READY pairing"
  fi
  echo "✅ Stage 4a passed: Monitoring graph-state invariants"

  # 4a.2) Interface→Agent pipeline monitoring (edge + activity pairing)
  if ! run_with_timeout "$(resolve_path test_monitoring_interface_agent_pipeline.py)" 120; then
    fail_and_exit "Monitoring interface→agent pipeline failed" \
      "${LOG_DIR}/triage_test_monitoring_interface_agent_pipeline.log" \
      "interface→agent monitoring failed — verify INTERFACE_TO_AGENT edges and INTERFACE_REQUEST_START/COMPLETE activities"
  fi
  echo "✅ Stage 4a.2 passed: Interface→Agent monitoring"

  # 4b) Full monitoring test (requires OPENAI_API_KEY)
  if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "⚠️  Skipping full monitoring test: OPENAI_API_KEY not set."
    echo "    Set OPENAI_API_KEY to include full monitoring in triage."
  else
    if ! run_with_timeout "$(resolve_path test_monitoring.sh)" 90; then
      fail_and_exit "Full monitoring test failed" \
        "${LOG_DIR}/triage_test_monitoring.log" \
        "monitoring pipeline failure — check monitoring logs and agent/service logs"
    fi
  echo "✅ Stage 4b passed: Full monitoring"
  fi

  # 4c) Viewer contract (schema + back-compat gate)
  if ! run_with_timeout "$(resolve_path test_viewer_contract.py)" 30; then
    fail_and_exit "Viewer contract test failed" \
      "${LOG_DIR}/triage_test_viewer_contract.log" \
      "viewer topology contract failed — check schema mapping and required fields"
  fi
  echo "✅ Stage 4c passed: Viewer contract"

  echo "=================================================="
  echo "Triage suite completed."
  echo "For full coverage, run ./run_all_tests.sh"
  echo "Logs: $LOG_DIR"
  echo "=================================================="
}

main "$@"
