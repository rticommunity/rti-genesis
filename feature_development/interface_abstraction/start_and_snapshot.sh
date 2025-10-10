#!/usr/bin/env bash
# Start a small topology, wait, capture an internal graph snapshot, then stop.
# This script prefers the project venv if present and writes the snapshot to
# feature_development/interface_abstraction/logs/graph_snapshot.json

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# Base logs directory and a per-run subdirectory to avoid mixing with previous runs
BASE_LOGS_DIR="${ROOT_DIR}/feature_development/interface_abstraction/logs"
RUN_ID="run_$(date +%Y%m%d_%H%M%S)"
LOGS_DIR="${BASE_LOGS_DIR}/${RUN_ID}"
STARTER="${ROOT_DIR}/feature_development/interface_abstraction/start_topology.sh"
SNAPSHOT_PY="${ROOT_DIR}/feature_development/interface_abstraction/monitor_graph_snapshot.py"

# Defaults
AGENTS=${AGENTS:-1}
SERVICES=${SERVICES:-1}
INTERFACES=${INTERFACES:-1}
TOPO_TIMEOUT=${TOPO_TIMEOUT:-45}           # seconds the topology will run if not stopped sooner
SNAPSHOT_WAIT=${SNAPSHOT_WAIT:-8}          # seconds to wait before snapshot (allow topology to warm up)
SNAPSHOT_DURATION=${SNAPSHOT_DURATION:-6}  # seconds the snapshot listener runs
DOMAIN_ID=${DOMAIN_ID:-0}

# Prefer and activate project venv if available for consistent RTI env
if [[ -z "${VIRTUAL_ENV:-}" && -x "${ROOT_DIR}/run_scripts/venv/bin/activate" ]]; then
  # shellcheck disable=SC1090
  source "${ROOT_DIR}/run_scripts/venv/bin/activate"
fi

# Pick python from active venv if present, else fallback
PY_BIN="${PY_BIN:-${VIRTUAL_ENV:+${VIRTUAL_ENV}/bin/python}}"
PY_BIN="${PY_BIN:-python3}"

# Ensure logs dir and PYTHONPATH
mkdir -p "${LOGS_DIR}"
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

usage() {
  cat <<EOF
Usage: $0 [options] [--] [extra starter args]

Options:
  --agents N              Number of agent instances (default: ${AGENTS})
  --services N            Number of service instances (default: ${SERVICES})
  --interfaces N          Number of interface instances (default: ${INTERFACES})
  --topo-timeout SEC      Topology auto-shutdown timeout (default: ${TOPO_TIMEOUT})
  --snapshot-wait SEC     Seconds to wait before snapshot (default: ${SNAPSHOT_WAIT})
  --snapshot-duration SEC Seconds to listen for graph before writing (default: ${SNAPSHOT_DURATION})
  --domain N              DDS domain id for snapshot (default: ${DOMAIN_ID})
  -h, --help              Show this help

Notes:
  - Additional args after -- are passed through to start_topology.sh
  - Snapshot is written to: ${LOGS_DIR}/graph_snapshot.json
EOF
}

EXTRA_STARTER_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --agents) AGENTS="$2"; shift 2;;
    --services) SERVICES="$2"; shift 2;;
    --interfaces) INTERFACES="$2"; shift 2;;
    --topo-timeout) TOPO_TIMEOUT="$2"; shift 2;;
    --snapshot-wait) SNAPSHOT_WAIT="$2"; shift 2;;
    --snapshot-duration) SNAPSHOT_DURATION="$2"; shift 2;;
    --domain) DOMAIN_ID="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    --) shift; EXTRA_STARTER_ARGS=("$@"); break;;
    *) EXTRA_STARTER_ARGS+=("$1"); shift;;
  esac
done

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }

start_topology() {
  # We force a finite timeout in the starter so it exits on its own as a fallback
  TIMEOUT_SEC=${TOPO_TIMEOUT} \
  ENABLE_SPY=${ENABLE_SPY:-1} \
  SPY_ALL=${SPY_ALL:-1} \
  SPY_STARTUP_WAIT_SEC=${SPY_STARTUP_WAIT_SEC:-5} \
  PYTHON_BIN="${PY_BIN}" \
  "${STARTER}" \
    --agents "${AGENTS}" --services "${SERVICES}" --interfaces "${INTERFACES}" \
    --logs-dir "${LOGS_DIR}" \
    --force \
    "${EXTRA_STARTER_ARGS[@]}" &
  TOPO_PID=$!
  log "Started topology (PID=${TOPO_PID}); waiting ${SNAPSHOT_WAIT}s before snapshot..."
}

run_snapshot() {
  sleep "${SNAPSHOT_WAIT}"
  log "Running snapshot for ${SNAPSHOT_DURATION}s (domain=${DOMAIN_ID})..."
  SNAP_OUT="${LOGS_DIR}/graph_snapshot.json"
  ACTIVITY_OUT="${LOGS_DIR}/activities.json"
  "${PY_BIN}" "${SNAPSHOT_PY}" --domain "${DOMAIN_ID}" --duration "${SNAPSHOT_DURATION}" --pretty --out "${SNAP_OUT}" --activity-out "${ACTIVITY_OUT}" | sed 's/^/  /'
}

# Validate that GraphMonitor event IDs correspond to nodes/edges present in the snapshot
validate_events_vs_snapshot() {
  local snapshot_path="${SNAP_OUT:-${LOGS_DIR}/graph_snapshot.json}"
  local logs_dir="${LOGS_DIR}"
  local activity_path="${ACTIVITY_OUT:-${LOGS_DIR}/activities.json}"
  if [[ ! -f "${snapshot_path}" ]]; then
    log "Validation skipped: snapshot not found at ${snapshot_path}"
    return 0
  fi
  log "Validating GraphMonitor events against snapshot: ${snapshot_path}"
  "${PY_BIN}" - <<'PY' "${snapshot_path}" "${logs_dir}" "${activity_path}"
import json, re, sys, os, glob

snapshot_path = sys.argv[1]
logs_dir = sys.argv[2]
activity_path = sys.argv[3]

def safe_read(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return ''

with open(snapshot_path, 'r', encoding='utf-8') as f:
    snap = json.load(f)

nodes = snap.get('elements', {}).get('nodes', [])
edges = snap.get('elements', {}).get('edges', [])

snapshot_node_ids = {n.get('data', {}).get('id') for n in nodes if n.get('data') and n['data'].get('id')}
# Map function labels to ids for fallback resolution
function_label_to_id = {}
for n in nodes:
    d = n.get('data', {})
    if d.get('type') == 'FUNCTION':
        fid = d.get('id')
        label = d.get('label')
        if fid and label:
            function_label_to_id[str(label)] = fid
snapshot_edges = set()
service_to_function_edges = set()
for e in edges:
    d = e.get('data', {})
    src = d.get('source')
    tgt = d.get('target')
    typ = d.get('type')
    if src and tgt:
        snapshot_edges.add((src, tgt, typ))
        if typ == 'SERVICE_TO_FUNCTION':
            service_to_function_edges.add((src, tgt))

node_evt_re = re.compile(r"GraphMonitor: Published NODE\s+([0-9a-fA-F\-]+)\s+type=\d+\s+state=\d+")
edge_evt_re = re.compile(r"GraphMonitor: Published EDGE\s+([0-9a-fA-F\-]+)\s*->\s*([0-9a-fA-F\-]+)\s+type=([A-Z_]+)")

event_node_ids = set()
event_edges = []  # list of (src, dst, type, file, line_no)

log_files = sorted(glob.glob(os.path.join(logs_dir, '*.log')))
for lf in log_files:
    try:
        with open(lf, 'r', encoding='utf-8', errors='ignore') as f:
            for idx, line in enumerate(f, 1):
                if 'GraphMonitor: Published NODE' in line:
                    m = node_evt_re.search(line)
                    if m:
                        event_node_ids.add(m.group(1))
                elif 'GraphMonitor: Published EDGE' in line:
                    m = edge_evt_re.search(line)
                    if m:
                        src, dst, typ = m.group(1), m.group(2), m.group(3)
                        event_edges.append((src, dst, typ, lf, idx))
    except Exception:
        continue

errors = []
warnings = []

# Check that all event nodes exist in snapshot nodes
for nid in sorted(event_node_ids):
    if nid not in snapshot_node_ids:
        errors.append(f"Event NODE id not found in snapshot nodes: {nid}")

# Check edge endpoints exist; and whether the exact edge appears in snapshot
for src, dst, typ, lf, idx in event_edges:
    if src not in snapshot_node_ids:
        errors.append(f"Event EDGE src not found in snapshot nodes: {src} (from {lf}:{idx})")
    if dst not in snapshot_node_ids:
        errors.append(f"Event EDGE dst not found in snapshot nodes: {dst} (from {lf}:{idx})")
    if (src, dst, typ) not in snapshot_edges:
        warnings.append(f"Event EDGE not present in snapshot edges: {src}->{dst} type={typ} (from {lf}:{idx})")

# ---- Activity validation (ChainEvent) ----
activity_events = []
if activity_path and os.path.exists(activity_path):
    try:
        with open(activity_path, 'r', encoding='utf-8') as f:
            activity_events = json.load(f)
    except Exception:
        warnings.append(f"Unable to parse activities file: {activity_path}")

def resolve_function_node_id(act):
    fid = str(act.get('function_id') or '')
    if fid and fid in snapshot_node_ids:
        return fid, None  # resolved, no note
    # Try by label on target then source
    tid = str(act.get('target_id') or '')
    sid = str(act.get('source_id') or '')
    if tid in function_label_to_id:
        resolved = function_label_to_id[tid]
        note = None if (not fid or fid == resolved) else f"function_id_mismatch provided={fid} resolved={resolved}"
        return resolved, note
    if sid in function_label_to_id:
        resolved = function_label_to_id[sid]
        note = None if (not fid or fid == resolved) else f"function_id_mismatch provided={fid} resolved={resolved}"
        return resolved, note
    return '', None

for act in activity_events:
    ev = str(act.get('event_type') or '')
    sid = str(act.get('source_id') or '')
    tid = str(act.get('target_id') or '')
    if ev in ('FUNCTION_CALL_START', 'FUNCTION_CALL_COMPLETE', 'CLASSIFICATION_RESULT'):
        resolved_fn, note = resolve_function_node_id(act)
        if not resolved_fn:
            errors.append(f"Activity unresolved function mapping: event={ev} sid={sid} tid={tid} function_id={act.get('function_id','')}")
            continue
        if note:
            warnings.append(f"Activity function_id mismatch: {note} for event={ev}")
        # Check that some service advertises this function in snapshot
        has_svc_edge = any(t == resolved_fn for (_, t) in service_to_function_edges)
        if not has_svc_edge:
            warnings.append(f"Function node has no SERVICE_TO_FUNCTION edge in snapshot: function_id={resolved_fn} event={ev}")
    elif ev.startswith('INTERFACE_REQUEST_'):
        # If IDs look like UUID/GUID, ensure they exist as nodes
        if sid and not (sid in snapshot_node_ids or sid in function_label_to_id):
            warnings.append(f"Activity interface sid not present in snapshot nodes: {sid}")
        if tid and not (tid in snapshot_node_ids or tid in function_label_to_id):
            warnings.append(f"Activity interface tid not present in snapshot nodes: {tid}")

report_lines = []
report_lines.append(f"Snapshot nodes: {len(snapshot_node_ids)}; snapshot edges: {len(snapshot_edges)}")
report_lines.append(f"Event nodes: {len(event_node_ids)}; event edges: {len(event_edges)}")
report_lines.append(f"Errors: {len(errors)}; Warnings: {len(warnings)}")
if errors:
    report_lines.append("\nErrors:")
    report_lines.extend(errors)
if warnings:
    report_lines.append("\nWarnings:")
    report_lines.extend(warnings)

report = "\n".join(report_lines)
print(report)

# Also write to a file beside the snapshot
out_path = os.path.join(logs_dir, 'graph_validation_report.txt')
try:
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(report + "\n")
    print(f"Validation report written to: {out_path}")
except Exception:
    pass

sys.exit(1 if errors else 0)
PY
}

# Analyze rtiddsspy log for presence of expected DDS topics and sample counts
analyze_spy_log() {
  local spy_log="${LOGS_DIR}/rtiddsspy.log"
  if [[ ! -f "${spy_log}" ]]; then
    log "Spy log not found at ${spy_log}; skipping spy analysis"
    return 0
  fi
  log "Analyzing rtiddsspy log: ${spy_log}"
  "${PY_BIN}" - <<'PY' "${spy_log}" "${LOGS_DIR}"
import re, sys, os, json
spy_path = sys.argv[1]
out_dir = sys.argv[2]
text = ''
try:
    with open(spy_path, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
except Exception as e:
    print(f"Failed to read spy log: {e}")
    sys.exit(0)

topics = [
    'ChainEvent',
    'ComponentLifecycleEvent',
    'GenesisGraphNode',
    'GenesisGraphEdge',
    'FunctionCapability',
    'FunctionExecution',
    'OpenAIAgentRequest',
    'OpenAIAgentReply',
]

summary = {}
for t in topics:
    # Count occurrences of the topic name and SAMPLE lines mentioning it
    name_count = len(re.findall(rf"\b{re.escape(t)}\b", text))
    summary[t] = {"mentions": name_count}

report_lines = ["DDS Spy Topic Mentions:"]
for t in topics:
    report_lines.append(f"  - {t}: mentions={summary[t]['mentions']}")

# Simple expectations
warnings = []
if summary['ComponentLifecycleEvent']['mentions'] == 0:
    warnings.append('No ComponentLifecycleEvent seen in spy log')
if summary['GenesisGraphNode']['mentions'] == 0 and summary['GenesisGraphEdge']['mentions'] == 0:
    warnings.append('No GenesisGraphNode/Edge durable topics seen in spy log')
if summary['ChainEvent']['mentions'] == 0:
    warnings.append('No ChainEvent activity seen in spy log')

out = "\n".join(report_lines)
if warnings:
    out += "\nWarnings:\n" + "\n".join(f"  - {w}" for w in warnings)

# Heuristic: Look for agent->service activation in ChainEvent samples (source looks like GUID and target looks like GUID; may also include function_id field)
agent_to_service = 0
for m in re.finditer(r"ChainEvent.*source_id\s*:\s*([0-9A-Fa-f]{8,}).*target_id\s*:\s*([0-9A-Fa-f]{8,})", text, re.S):
    agent_to_service += 1
out += f"\nHeuristics: agent_to_service_edges_seen={agent_to_service}"

out_path = os.path.join(out_dir, 'spy_summary.txt')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(out + "\n")
print(out)
print(f"Spy summary written to: {out_path}")
PY
}

finish() {
  local ec=$?
  if [[ -n "${TOPO_PID:-}" ]] && kill -0 "${TOPO_PID}" 2>/dev/null; then
    log "Stopping topology PID=${TOPO_PID}..."
    kill -INT "${TOPO_PID}" 2>/dev/null || true
    sleep 1
    kill -TERM "${TOPO_PID}" 2>/dev/null || true
  fi
  log "Done (exit=${ec}). Snapshot at: ${LOGS_DIR}/graph_snapshot.json"
  exit ${ec}
}
trap finish INT TERM EXIT

log "Root: ${ROOT_DIR}"
log "Python: ${PY_BIN}"
log "Logs: ${LOGS_DIR}"

start_topology
run_snapshot

# Validate events against snapshot; this will cause a non-zero exit if hard mismatches are found
validate_events_vs_snapshot

# Analyze spy log for visibility of key DDS topics
analyze_spy_log

# Allow starter to wind down naturally; we rely on trap to stop it on script exit
sleep 1


