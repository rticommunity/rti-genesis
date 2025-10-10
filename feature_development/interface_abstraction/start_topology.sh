#!/usr/bin/env bash
# Start an arbitrary number of agents, services, and interfaces, track PIDs,
# and clean up on Ctrl-C or after a timeout. Avoids GNU timeout dependency.
set -Eeuo pipefail

# ----------------------------- Defaults ---------------------------------- #
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
AGENTS=${AGENTS:-1}
SERVICES=${SERVICES:-1}
INTERFACES=${INTERFACES:-1}
TIMEOUT_SEC=${TIMEOUT_SEC:-120}
LOGS_DIR=${LOGS_DIR:-"${ROOT_DIR}/feature_development/interface_abstraction/logs"}
ENABLE_SPY=${ENABLE_SPY:-1}   # 1=enable rtiddsspy logging if available
FORCE_RUN=${FORCE_RUN:-0}     # 1=ignore pre-existing DDS activity
PRECHECK_ENABLED=${PRECHECK_ENABLED:-1}  # 0=skip DDS precheck entirely
SPY_PRECHECK_SEC=${SPY_PRECHECK_SEC:-3}
SPY_KILL_GRACE_SEC=${SPY_KILL_GRACE_SEC:-2}
# Focus spy on a broader set of topics by default to capture end-to-end traffic
# Includes interface↔agent, agent↔agent, service RPC, monitoring, and graph topics
SPY_TOPIC_REGEX=${SPY_TOPIC_REGEX:-"(ComponentLifecycleEvent|MonitoringEvent|ChainEvent|OpenAIAgent(Request|Reply)|InterfaceAgent(Request|Reply)|AgentAgent(Request|Reply)|Function(Execution)?(Request|Reply)|.*CalculatorService.*|GenesisGraph(Node|Edge)|GenesisRegistration|AgentCapability|FunctionCapability)"}
SPY_ALL=${SPY_ALL:-1}   # 1=capture everything by default (no topic filtering)
SPY_STARTUP_WAIT_SEC=${SPY_STARTUP_WAIT_SEC:-5}

# Interface auto-question options
INTERFACE_QUESTIONS=()
ASK_DEFAULTS=${ASK_DEFAULTS:-0}  # 1=ask a couple of default questions automatically
INTERFACE_BETWEEN_Q_SEC=${INTERFACE_BETWEEN_Q_SEC:-3}

# Defaults for scripts (can be overridden via flags)
DEFAULT_AGENT_SCRIPT="${ROOT_DIR}/examples/MultiAgent/agents/personal_assistant.py"
DEFAULT_SERVICE_SCRIPT="${ROOT_DIR}/test_functions/services/calculator_service.py"
# Use SimpleGenesisInterfaceCLI by default so one interface can ask multiple questions
DEFAULT_INTERFACE_SCRIPT="${ROOT_DIR}/tests/helpers/simpleGenesisInterfaceCLI.py"

AGENT_CMD=("${PYTHON_BIN}" "${DEFAULT_AGENT_SCRIPT}")
SERVICE_CMD=("${PYTHON_BIN}" "${DEFAULT_SERVICE_SCRIPT}")
INTERFACE_CMD=("${PYTHON_BIN}" "${DEFAULT_INTERFACE_SCRIPT}")
# Allow additional heterogeneous agents (one instance per provided command)
EXTRA_AGENT_CMDS=()

# Ensure project is importable (fixes ModuleNotFoundError: genesis_lib)
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

# Enable V2 unified monitoring topics by default
# Using unified monitoring topics (GraphTopology, Event) by default

# --------------------------- Arg Parsing --------------------------------- #
usage() {
  cat <<EOF
Usage: $0 [options]

Options:
  -a, --agents N           Number of agent instances (default: ${AGENTS})
  -s, --services N         Number of service instances (default: ${SERVICES})
  -i, --interfaces N       Number of interface instances (default: ${INTERFACES})
  -t, --timeout SEC        Timeout in seconds before auto-shutdown (default: ${TIMEOUT_SEC})
  --agent-cmd CMD          Override agent command (quoted string)
  --service-cmd CMD        Override service command (quoted string)
  --interface-cmd CMD      Override interface command (quoted string)
  --logs-dir DIR           Directory for logs (default: ${LOGS_DIR})
  --no-precheck            Skip DDS precheck entirely (no rtiddsspy probe before start)
  --no-spy                 Disable rtiddsspy background logging
  --force                  Ignore pre-existing DDS activity and proceed (precheck still runs)
  --spy-topic REGEX        Topic regex for spy (not used by default; post-filter with grep recommended)
  --spy-all                Capture all topics (default behavior)
  --interface-question TXT Ask a question via the interface (repeatable)
  --ask-defaults           Ask two default questions (math + small talk)
  --extra-agent-cmd CMD    Start an additional agent with its own command (repeatable)
  -h, --help               Show this help and exit

Examples:
  $0 -a 1 -s 1 -i 1 -t 90
  $0 --agents 2 --services 1 --interfaces 1 \
     --agent-cmd "python3 examples/MultiAgent/agents/personal_assistant.py" \
     --service-cmd "python3 test_functions/calculator_service.py" \
     --interface-cmd "python3 run_scripts/simpleGenesisInterfaceStatic.py -v"
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -a|--agents) AGENTS="$2"; shift 2;;
      -s|--services) SERVICES="$2"; shift 2;;
      -i|--interfaces) INTERFACES="$2"; shift 2;;
      -t|--timeout) TIMEOUT_SEC="$2"; shift 2;;
      --agent-cmd) IFS=' ' read -r -a AGENT_CMD <<< "$2"; shift 2;;
      --service-cmd) IFS=' ' read -r -a SERVICE_CMD <<< "$2"; shift 2;;
      --interface-cmd) IFS=' ' read -r -a INTERFACE_CMD <<< "$2"; shift 2;;
      --logs-dir) LOGS_DIR="$2"; shift 2;;
      --no-precheck) PRECHECK_ENABLED=0; shift 1;;
      --no-spy) ENABLE_SPY=0; shift 1;;
      --force) FORCE_RUN=1; shift 1;;
      --spy-topic) SPY_TOPIC_REGEX="$2"; shift 2;;
      --spy-all) SPY_ALL=1; shift 1;;
      --interface-question) INTERFACE_QUESTIONS+=("$2"); shift 2;;
      --ask-defaults) ASK_DEFAULTS=1; shift 1;;
      --extra-agent-cmd) EXTRA_AGENT_CMDS+=("$2"); shift 2;;
      -h|--help) usage; exit 0;;
      *) echo "Unknown option: $1"; usage; exit 1;;
    esac
  done
}

# ---------------------------- Utilities ---------------------------------- #
mkdir -p "${LOGS_DIR}"
PIDS=()
PGIDS=()
TIMER_PID=""
SPY_PID=""
CANCELLED=0

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }

start_proc() {
  local kind="$1"; shift
  local idx="$1"; shift
  local -a cmd=("$@")
  local log_file="${LOGS_DIR}/${kind}_${idx}.log"

  # Prefer setsid if available to get a new process group per instance
  if command -v setsid >/dev/null 2>&1; then
    setsid "${cmd[@]}" >"${log_file}" 2>&1 &
  else
    "${cmd[@]}" >"${log_file}" 2>&1 &
  fi
  local pid=$!
  PIDS+=("${pid}")
  # Query process group id
  local pgid
  pgid=$(ps -o pgid= "${pid}" | tr -d ' ' || echo "${pid}")
  PGIDS+=("${pgid}")
  log "Started ${kind}#${idx} (PID=${pid}, PGID=${pgid}) → ${log_file}"
}

cleanup_children() {
  # First try TERM, then KILL if needed
  if [[ ${#PIDS[@]} -eq 0 ]]; then
    return
  fi
  log "Stopping ${#PIDS[@]} processes..."
  # Kill by process group to ensure all children die
  for pgid in "${PGIDS[@]}"; do
    if [[ -n "${pgid}" ]]; then
      kill -TERM -"${pgid}" 2>/dev/null || true
    fi
  done
  sleep 2
  for pgid in "${PGIDS[@]}"; do
    if [[ -n "${pgid}" ]]; then
      kill -KILL -"${pgid}" 2>/dev/null || true
    fi
  done
}

stop_spy() {
  if [[ -n "${SPY_PID}" ]]; then
    kill -INT "${SPY_PID}" 2>/dev/null || true
    # bounded wait for spy to exit
    local t=0
    while kill -0 "${SPY_PID}" 2>/dev/null && [[ $t -lt ${SPY_KILL_GRACE_SEC} ]]; do
      sleep 0.2
      t=$((t+1))
    done
    if kill -0 "${SPY_PID}" 2>/dev/null; then
      kill -TERM "${SPY_PID}" 2>/dev/null || true
      sleep 0.5
    fi
    if kill -0 "${SPY_PID}" 2>/dev/null; then
      kill -KILL "${SPY_PID}" 2>/dev/null || true
    fi
    SPY_PID=""
  fi
}

cleanup() {
  local ec=$?
  if [[ ${CANCELLED} -eq 0 ]]; then
    CANCELLED=1
  fi
  log "Cleanup triggered (exit code=${ec})"
  # Stop timer if running
  if [[ -n "${TIMER_PID}" ]]; then
    kill -TERM "${TIMER_PID}" 2>/dev/null || true
  fi
  stop_spy
  cleanup_children
  exit ${ec}
}

# Start one interface instance that sequentially asks all configured questions
start_interface_sequence() {
  local idx="$1"
  if [[ ${#INTERFACE_QUESTIONS[@]} -eq 0 ]]; then
    # Fallback: just start the interface as-is
    start_proc "interface" "${idx}" "${INTERFACE_CMD[@]}"
    return
  fi
  # If using the CLI, send all questions in a single run to keep one interface node
  if [[ "${INTERFACE_CMD[*]}" == *"simpleGenesisInterfaceCLI.py"* ]]; then
    # Always target the Personal Assistant to allow chaining; fall back to first if not found
    local aggregated=("${INTERFACE_CMD[@]}" -v --select-name "PersonalAssistant" --select-first --sleep-between "${INTERFACE_BETWEEN_Q_SEC}")
    for q in "${INTERFACE_QUESTIONS[@]}"; do
      aggregated+=( -m "$q" )
    done
    log "Interface#${idx} (CLI) sending ${#INTERFACE_QUESTIONS[@]} question(s) in one session."
    start_proc "interface" "${idx}" "${aggregated[@]}"
  else
    # Legacy static interface: run once per question (creates multiple interface nodes)
    local cmd_quoted
    cmd_quoted=$(printf '%q ' "${INTERFACE_CMD[@]}")
    local loop_script=""
    for q in "${INTERFACE_QUESTIONS[@]}"; do
      loop_script+="${cmd_quoted} --question $(printf '%q' "$q"); sleep ${INTERFACE_BETWEEN_Q_SEC}; "
    done
    log "Interface#${idx} will ask ${#INTERFACE_QUESTIONS[@]} question(s) (static mode)."
    start_proc "interface" "${idx}" bash -c "${loop_script}"
  fi
}

start_timer() {
  if [[ "${TIMEOUT_SEC}" -le 0 ]]; then
    return
  fi
  (
    sleep "${TIMEOUT_SEC}"
    log "Timeout ${TIMEOUT_SEC}s reached. Initiating shutdown..."
    # Trigger main trap path
    kill -INT $$ 2>/dev/null || true
  ) &
  TIMER_PID=$!
}

check_dds_activity() {
  if [[ -z "${NDDSHOME:-}" || ! -x "${NDDSHOME}/bin/rtiddsspy" ]]; then
    log "rtiddsspy not found (NDDSHOME/bin/rtiddsspy). Skipping DDS precheck."
    return
  fi
  local precheck_log="${LOGS_DIR}/dds_precheck.log"
  log "Checking for existing DDS traffic using rtiddsspy (${SPY_PRECHECK_SEC}s)..."
  # Build rtiddsspy command (avoid unsupported flags like -printTimestamp)
  local spy_cmd=("${NDDSHOME}/bin/rtiddsspy" -printSample -useFirstPublicationQos)
  # Prefer transient reliable QoS if file exists
  if [[ -f "${ROOT_DIR}/spy_transient.xml" ]]; then
    spy_cmd+=( -qosFile "${ROOT_DIR}/spy_transient.xml" -qosProfile SpyLib::TransientReliable )
  fi
  "${spy_cmd[@]}" >"${precheck_log}" 2>&1 &
  local tmp_pid=$!
  # Wait bounded time, then terminate
  sleep "${SPY_PRECHECK_SEC}"
  kill -INT "${tmp_pid}" 2>/dev/null || true
  # bounded wait for tmp_pid to exit
  local t=0
  while kill -0 "${tmp_pid}" 2>/dev/null && [[ $t -lt ${SPY_KILL_GRACE_SEC} ]]; do
    sleep 0.2
    t=$((t+1))
  done
  if kill -0 "${tmp_pid}" 2>/dev/null; then
    kill -TERM "${tmp_pid}" 2>/dev/null || true
    sleep 0.5
  fi
  if kill -0 "${tmp_pid}" 2>/dev/null; then
    kill -KILL "${tmp_pid}" 2>/dev/null || true
  fi

  # Determine if there is real DDS traffic (ignore header lines)
  if grep -Eq "New writer|New reader|New data|SAMPLE" "${precheck_log}"; then
    log "DDS activity detected before start. See: ${precheck_log}"
    if [[ ${FORCE_RUN} -eq 0 ]]; then
      log "Aborting. Re-run with --force if you intend to proceed despite existing DDS traffic."
      exit 2
    else
      log "--force specified. Proceeding despite pre-existing DDS traffic."
    fi
  else
    log "No DDS activity detected in precheck."
  fi
}

start_spy() {
  if [[ ${ENABLE_SPY} -eq 0 ]]; then
    return
  fi
  if [[ -z "${NDDSHOME:-}" || ! -x "${NDDSHOME}/bin/rtiddsspy" ]]; then
    log "rtiddsspy not found; live DDS spy logging disabled."
    return
  fi
  local spy_log="${LOGS_DIR}/rtiddsspy.log"
  log "Starting rtiddsspy background logger → ${spy_log} (no topic filter)"
  local spy_cmd=("${NDDSHOME}/bin/rtiddsspy" -printSample -useFirstPublicationQos)
  if [[ -f "${ROOT_DIR}/spy_transient.xml" ]]; then
    spy_cmd+=( -qosFile "${ROOT_DIR}/spy_transient.xml" -qosProfile SpyLib::TransientReliable )
  fi
  "${spy_cmd[@]}" >"${spy_log}" 2>&1 &
  SPY_PID=$!
}

# Ensure cleanup on signals and normal exit
trap cleanup INT TERM EXIT

# ---------------------------- Main --------------------------------------- #
parse_args "$@"

if [[ ${ASK_DEFAULTS} -eq 1 && ${#INTERFACE_QUESTIONS[@]} -eq 0 ]]; then
  # Provide defaults that exercise chaining (weather) and calculator RPC
  INTERFACE_QUESTIONS+=("What's the weather in Seattle today?")
  INTERFACE_QUESTIONS+=("What is 123 plus 456?")
  # Ensure WeatherExpert agent is started so the weather question is actually handled
  EXTRA_AGENT_CMDS+=("${PYTHON_BIN} ${ROOT_DIR}/examples/MultiAgent/agents/weather_agent.py")
fi

log "Root: ${ROOT_DIR}"
log "Logs: ${LOGS_DIR}"
log "Counts: agents=${AGENTS}, services=${SERVICES}, interfaces=${INTERFACES} (timeout=${TIMEOUT_SEC}s)"
log "Agent cmd: ${AGENT_CMD[*]}"
log "Service cmd: ${SERVICE_CMD[*]}"
log "Interface cmd: ${INTERFACE_CMD[*]}"
if [[ ${#INTERFACE_QUESTIONS[@]} -gt 0 ]]; then
  log "Interface questions (${#INTERFACE_QUESTIONS[@]}):"
  for q in "${INTERFACE_QUESTIONS[@]}"; do
    log "  - $q"
  done
fi
if [[ ${#EXTRA_AGENT_CMDS[@]} -gt 0 ]]; then
  log "Extra agents (${#EXTRA_AGENT_CMDS[@]}):"
  for c in "${EXTRA_AGENT_CMDS[@]}"; do
    log "  - $c"
  done
fi

# Precheck DDS traffic to avoid polluted graphs
if [[ ${PRECHECK_ENABLED} -eq 1 ]]; then
  check_dds_activity
else
  log "Skipping DDS precheck (--no-precheck)."
fi

# Start live DDS spy logger BEFORE launching components to capture initial samples
start_spy
if [[ -n "${SPY_PID}" ]]; then
  log "Waiting ${SPY_STARTUP_WAIT_SEC}s for rtiddsspy to initialize..."
  sleep "${SPY_STARTUP_WAIT_SEC}"
fi

# Start services first (providers), then agents, then interfaces
for ((i=1; i<=SERVICES; i++)); do
  start_proc "service" "${i}" "${SERVICE_CMD[@]}"
  sleep 0.2
done
for ((i=1; i<=AGENTS; i++)); do
  start_proc "agent" "${i}" "${AGENT_CMD[@]}"
  sleep 0.2
done
# Start one instance for each extra agent command
if [[ ${#EXTRA_AGENT_CMDS[@]} -gt 0 ]]; then
  extra_idx=1
  for cmd in "${EXTRA_AGENT_CMDS[@]}"; do
    log "Starting extra agent #${extra_idx}: ${cmd}"
    start_proc "agent_extra" "${extra_idx}" bash -c "${cmd}"
    extra_idx=$((extra_idx+1))
    sleep 0.2
  done
fi
for ((i=1; i<=INTERFACES; i++)); do
  # If questions are configured, run the interface for each question sequentially
  start_interface_sequence "${i}"
  sleep 0.2
done

start_timer
log "All processes started. Press Ctrl-C to stop."

# Keep running until interrupted or timeout
while true; do
  sleep 1
  :
done
