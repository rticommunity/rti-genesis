# GraphInterface Example

A minimal example interface that embeds the reusable Genesis Graph Viewer blueprint and Socket.IO bridge.

## What it does
- Starts a Flask + Socket.IO app
- Runs `GraphService` to subscribe to DDS topology/monitoring
- Registers the viewer under `/genesis-graph`
- Serves a simple page with a right-pane visualization (using `/genesis-graph/static/reference.js`)

## Run
```bash
# From repo root
examples/GraphInterface/run_graph_interface.sh
# Then open http://localhost:5080/
```

Environment variables:
- `GENESIS_DOMAIN` (default 0)
- `GENESIS_GRAPH_BRIDGE_UPDATE_SUPPRESS_MS` (default 500)
- `GENESIS_GRAPH_BRIDGE_REMOVE_SUPPRESS_MS` (default 2000)
- `GENESIS_GRAPH_BRIDGE_BATCH_MS` (default 0; when > 0, emits batched `graph_batch`)

## Customize
- Replace `templates/index.html` with your interface layout; keep the right pane’s `<div id="graph">` for the viewer.
- For a richer 3D scene, adapt from `feature_development/interface_abstraction/viewer/templates/index.html`.

## Stop
Ctrl+C; the app closes and `GraphService` stops.
