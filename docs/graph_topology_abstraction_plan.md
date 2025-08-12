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

## Target Architecture

Library-centric, DDS-bridged graph service that exposes a DDS‑free API to interfaces.

- Publishing (existing, kept):
  - Producers (interfaces, agents, services) publish node/edge events via `genesis_lib.graph_monitoring.GraphMonitor`.
  - Near-term: continue emitting `ComponentLifecycleEvent` for NODE_DISCOVERY/EDGE_DISCOVERY.
  - Mid-term: migrate to unified `GenesisGraphEvent`/`GenesisActivityEvent` from `docs/unified_monitoring_system_plan.md`.

- Graph state and subscription (new in library):
  - `GenesisNetworkGraph`: thread-safe NetworkX-backed store for nodes/edges with typed helpers and exports.
  - `GraphSubscriber`: encapsulates all DDS subscriptions and normalizes events into `GenesisNetworkGraph`.
  - `GraphService`: façade providing start/stop, snapshots, change subscription, and export helpers.

- UI bridges (library provided; no DDS in UI code):
  - Extend `genesis_lib/web/socketio_graph_bridge.py` to accept a `GraphService` and forward `node_update`/`edge_update` to Socket.IO.
  - Optional Flask blueprint or FastAPI router:
    - GET `/api/graph` → Cytoscape JSON
    - WS `/api/graph/stream` → change events

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
  - Migrate publishers and subscribers to `GenesisGraphEvent`/`GenesisActivityEvent` as documented in `docs/unified_monitoring_system_plan.md`.
  - Provide compatibility shims so older components continue functioning during rollout.

- Phase 5: Tests and CI
  - Add unit tests that consume `GraphService` (DDS mocked) to validate export formats and basic graph semantics.
  - Keep integration tests that validate real DDS events (existing `test_graph_connectivity_validation*.py`), but allow testing via `GraphService.to_networkx()`.

## Visual Validation of Graph Completeness

- Web UI (reference):
  - Render `GraphService.to_cytoscape()` with Cytoscape.js.
  - Live updates via Socket.IO. Provide color/shape by type, edge labels (function names), legends, and filters (e.g., orphan nodes, disconnected components).

- CLI/Artifacts:
  - A `graph_cli.py` tool that prints summaries (nodes by type, edges by type, connectivity checks) and writes DOT/PNG for CI.
  - Use NetworkX metrics for connectivity, reachability (e.g., interfaces→agents, agents→functions), orphan detection.

## Why NetworkX + Cytoscape.js

- NetworkX:
  - Dominant Python graph library; comprehensive algorithms; intuitive API; abundant examples.
  - Already used in repo tests, easing adoption and validation.
- Cytoscape.js:
  - Robust, interactive rendering with extensive layouts (cose, fcose, dagre, etc.) and examples.
  - Simple JSON contract and efficient live updates.
- Graphviz:
  - Ideal for static artifacts and documentation; easy DOT export.

## DDS Bridge Details (hidden from UIs)

- `GraphSubscriber` exclusively manages DDS:
  - Readers: now `ComponentLifecycleEvent` (TRANSIENT_LOCAL, RELIABLE); later: `GenesisGraph`.
  - On data: normalize to Python dicts, update `GenesisNetworkGraph`, emit `node_update`/`edge_update` callbacks.
- Export APIs and the Socket.IO bridge keep UIs DDS-free.

## Deliverables

- `genesis_lib/graph_state.py`: `GenesisNetworkGraph`, `GraphSubscriber`, `GraphService` with exports and event subscription.
- `genesis_lib/web/socketio_graph_bridge.py`: extend to accept a `GraphService` instance.
- Optional: `genesis_lib/web/graph_blueprint.py` (Flask) or `fastapi_graph_router.py`.
- Update example UI: `examples/linchpin_demo/interfaces/genesis_web_interface.py` to use `GraphService`.
- `tools/graph_cli.py`: summaries, DOT/PNG exports, and simple validations.

## Acceptance Criteria

- Interfaces render topology without importing `rti.connextdds`.
- Graph snapshot available via simple Python API and via HTTP JSON.
- Live updates stream to the UI via Socket.IO with no DDS in UI code.
- Existing graph connectivity tests validate snapshots from `GraphService.to_networkx()`.
- `rtiddsspy` shows correct durable graph events from publishers.

## Notes

- This plan aligns with `docs/unified_monitoring_system_plan.md`: publisher-first validation using RTI DDS Spy, followed by subscriber/graph building, then UI integration.
- The design provides a low-friction API surface that coding models and developers can easily adopt, with many examples available on the internet for NetworkX and Cytoscape.js.
