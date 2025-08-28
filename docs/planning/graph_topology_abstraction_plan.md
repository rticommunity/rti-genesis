# Genesis Graph Topology Abstraction Plan

This document proposes how to abstract graph construction and visualization into the Genesis library so that user interfaces do not directly depend on DDS APIs. The goal is to provide a simple, stable, and well-documented Python API for topology while retaining DDS as the source of truth.

## Goals

1. Decouple UIs from DDS for topology visualization and validation.
2. Centralize graph building in the library with an easy Python API and rich examples.
3. Keep DDS as the source of truth but hide it behind a graph service abstraction.
4. Support multiple export formats (JSON, DOT, Cytoscape) and real-time streaming.
5. Maintain backward compatibility during migration.

## Recommended Libraries

- NetworkX (Python): canonical in-process graph model, algorithms, metrics, and a large ecosystem. Already used in tests (e.g., `test_functions/test_graph_connectivity_validation*.py`).
- Cytoscape.js (Web): interactive, performant topology visualization with many layouts and examples. Ideal for reference UI.
- Graphviz (static optional): DOT export for quick CI artifacts and documentation images.
- Flask + Socket.IO: simple, robust web transport for snapshots and live updates.

## Target Architecture

Library-centric, DDS-bridged graph service that exposes a DDS‑free API to interfaces.

- Publishing (existing, kept):
  - Producers (interfaces, agents, services) publish node/edge events via `genesis_lib.graph_monitoring.GraphMonitor`.
  - Durable topology topics: `GenesisGraphNode`, `GenesisGraphEdge` (TRANSIENT_LOCAL, RELIABLE). These guarantee late joiners reconstruct topology.
  - For back-compat, `ComponentLifecycleEvent` is still emitted, but subscribers prefer the new durable topics.

- Graph state and subscription (new in library):
  - `GenesisNetworkGraph`: thread-safe in-memory store for nodes/edges with exports (NetworkX, Cytoscape JSON).
  - `GraphSubscriber`: encapsulates DDS readers (prefers `GenesisGraphNode/Edge`, falls back to `ComponentLifecycleEvent`) and normalizes to graph updates. Optional `ChainEvent` reader for activity overlay.
  - `GraphService`: façade providing start/stop, snapshots, and change subscriptions (`node_update`/`edge_update`, and `activity`).

- UI bridges (library provided; no DDS in UI code):
  - `genesis_lib/web/socketio_graph_bridge.py` forwards incremental updates to Socket.IO and emits a `graph_updated` signal only on creations (new node or new edge). Dataclass payloads are serialized to JSON.
  - Optional Flask blueprint or FastAPI router:
    - GET `/api/graph` → Cytoscape JSON snapshot
    - WS/Socket.IO `/api/graph/stream` → incremental change events

- Interfaces (consumers):
  - Replace direct DDS readers (e.g., in `examples/linchpin_demo/interfaces/genesis_web_interface.py`) with the library’s `GraphService` + Socket.IO bridge.
  - Interface code becomes DDS-version-agnostic.

## Proposed Library API

```python
# genesis_lib/graph_state.py

graph = GraphService(domain_id=0)
graph.start()  # creates DDS subscriber internally and maintains a NetworkX graph

snapshot = graph.get_snapshot()          # thread-safe copy or read-only view
cyto = graph.to_cytoscape()              # for web UIs
dot = graph.to_dot()                     # for Graphviz
G = graph.to_networkx()                  # for analysis/tests

def on_change(event, payload):           # event: "node_update" | "edge_update"
    pass
graph.subscribe(on_change)

# Activity overlay (ChainEvent)
def on_activity(activity):               # dict with source_id, target_id, chain_id, status, timestamp
    pass
graph.subscribe_activity(on_activity)
```

Socket.IO bridge:
```python
from genesis_lib.web.socketio_graph_bridge import attach_graph_to_socketio
attach_graph_to_socketio(graph, socketio)
```

## Migration Plan

- Phase 1: Publisher-first hardening (no subscriber changes yet)
  - Keep `GraphMonitor.publish_node/edge` as the single publishing API.
  - Validate shape and QoS using `rtiddsspy` (with a timeout) on `ComponentLifecycleEvent`.

- Phase 2: Library subscriber + graph state
  - Implement `GraphSubscriber`, `GenesisNetworkGraph`, and `GraphService` in `genesis_lib/graph_state.py`.
  - Implement export helpers: JSON, DOT, Cytoscape, NetworkX.
  - Extend `genesis_lib/web/socketio_graph_bridge.py` to accept a `GraphService`.
  - Optional: Flask blueprint or FastAPI router for `/api/graph` and `/api/graph/stream`.

- Phase 3: Replace DDS usage in Linchpin web UI
  - Edit `examples/linchpin_demo/interfaces/genesis_web_interface.py` to remove `rti.connextdds` readers.
  - Use `GraphService` for snapshots and live updates via Socket.IO bridge.

- Phase 4: Unified data model (optional follow-up)
  - Migrate publishers and subscribers to `GenesisGraphEvent`/`GenesisActivityEvent` as documented in `docs/planning/unified_monitoring_system_plan.md`.
  - Provide compatibility shims so older components continue functioning during rollout.

- Phase 5: Tests and CI
  - Add unit tests that consume `GraphService` (DDS mocked) to validate export formats and basic graph semantics.
  - Keep integration tests that validate real DDS events (existing `test_graph_connectivity_validation*.py`), but allow testing via `GraphService.to_networkx()`.

## Visual Validation of Graph Completeness

- Web UI (reference):
  - Render `GraphService.to_cytoscape()` with Cytoscape.js.
  - Live updates via Socket.IO. Provide color/shape by type, legends, and filters (e.g., orphan nodes, disconnected components).
  - Implemented Layered layout with four fixed bands:
    - Band 1: Interfaces (top)
    - Band 2: Agents (deterministic staggering + jitter for legibility)
    - Band 3: Services
    - Band 4: Functions (clustered directly beneath the owning service; functions sorted by label)
  - Other layouts available: Force (fcose/cose) and Radial. Force was evaluated but not used by default due to stability/viewport issues at scale.

- CLI/Artifacts:
  - A `graph_cli.py` tool that prints summaries (nodes by type, edges by type, connectivity checks) and writes DOT/PNG for CI.
  - Use NetworkX metrics for connectivity, reachability (e.g., interfaces→agents, agents→functions), orphan detection.

## Real-time Interaction Visualization (Activity Overlay)

- Source: `ChainEvent` (VOLATILE, RELIABLE). Optional mapping from selected `MonitoringEvent` types.
- Bridge behavior:
  - Forward each activity as `activity` payload over Socket.IO.
  - Add per-edge token bucket rate limiter (e.g., 60/s) and windowed aggregation for burst control.
  - Log drop/aggregate counts; keep UI responsive under load.
- Client overlay modes:
  - Pulse mode (default): brief glow/pulse on the traversed edge and a short node highlight (300–500 ms fade), no re-layout.
  - Heat mode: per-edge intensity (width/color) decays over 5–10 s; switch automatically when density is high.
  - Controls: density slider, mode toggle (Pulse/Heat), filters (operation/status), pin by `chain_id`.
- Performance:
  - Update only affected edges/nodes; avoid whole-graph redraws.
  - Cap concurrent animations; fall back to heat mode when FPS drops.
  - Evict stale `chain_id`s and maintain bounded client/server queues.

## DDS Bridge Details (hidden from UIs)

- `GraphSubscriber` exclusively manages DDS:
  - Readers: `GenesisGraphNode/Edge` (TRANSIENT_LOCAL, RELIABLE), fallback to `ComponentLifecycleEvent` for topology; `ChainEvent` for transient activity.
  - On data: normalize to Python dicts, update `GenesisNetworkGraph`, emit `node_update`/`edge_update` callbacks and activity events.
- `socketio_graph_bridge`:
  - Emits incremental `node_update`/`edge_update` to clients.
  - Emits `graph_updated` only for creations (first time a node_id or edge key `src->tgt:type` is observed).
  - Serializes dataclasses to JSON safely and logs every forwarded event and snapshot emission for diagnostics.

## Deliverables

- `genesis_lib/graph_state.py`: `GenesisNetworkGraph`, `GraphSubscriber`, `GraphService` with exports and event subscription (topology now, activity soon).
- `genesis_lib/web/socketio_graph_bridge.py`: forwards `node_update`/`edge_update`, creation-scoped `graph_updated`, and `activity` (with rate limiting to be added). Includes server-side tracing.
- Reference viewer (Flask + Cytoscape.js):
  - GET `/api/graph` for snapshots, Socket.IO for incremental updates.
  - Layered layout with four bands, agent staggering, and service-clustered functions.
  - Edge label toggle; layout selector (Force/Layered/Radial).

## Acceptance Criteria

- Interfaces render topology without importing `rti.connextdds`.
- Graph snapshot available via simple Python API and via HTTP JSON.
- Live updates stream to the UI via Socket.IO with no DDS in UI code.
- Layered layout maintains clear separation for large meshes (e.g., 3 interfaces, 10 agents, 20 services, 80 functions), with function clusters under services.
- `activity` overlay animates real-time interactions with density control and does not trigger topology re-layout.
- Existing graph connectivity tests validate snapshots from `GraphService.to_networkx()`.
- `rtiddsspy` shows correct durable graph events from publishers.

## Notes

- Force-directed layouts are visually appealing but can drift offscreen and introduce instability at scale; the layered preset provides deterministic, legible results and was chosen as default.
- Auto-refresh of the entire snapshot is avoided; incremental events drive updates and the bridge throttles `graph_updated` to creations only.
- The layered algorithm uses stable hashing for horizontal placement and a small per-band jitter (plus a stronger stagger for agents) to reduce overdraw while preserving tiers.
