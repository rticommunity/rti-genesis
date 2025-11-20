# Standalone Graph Viewer

A pure visualization server with **no chat interface** - just the 3D network topology graph.

## What This Is

This example shows the **simplest possible** Genesis graph viewer:
- Real-time 3D visualization of your Genesis network
- Agents, services, interfaces, and their connections
- Live updates as components start/stop
- **No agent interaction** - pure monitoring

## When to Use This

Use StandaloneGraphViewer when you:
- Want to **monitor** Genesis topology without interacting with agents
- Need a **dashboard** view on a separate monitor
- Are **debugging** service discovery or network issues
- Want the **lightest weight** visualization (no chat UI overhead)
- Are running a **large-scale deployment** and just need visibility

## When to Use GraphInterface Instead

Use `examples/GraphInterface/` when you need:
- Agent discovery and connection
- Chat interface to interact with agents
- Split-screen view (chat + visualization)

## Quick Start

```bash
# From repo root
./examples/StandaloneGraphViewer/run.sh

# Then open http://localhost:5000/
```

The server automatically redirects `/` to `/genesis-graph/reference` where the 3D viewer is.

## Start Some Components

The viewer monitors whatever is running in your Genesis network. Start some components to see them appear:

```bash
# In separate terminals:
python test_functions/services/calculator_service.py
python examples/MultiAgent/agents/personal_assistant.py
python examples/MultiAgent/agents/weather_agent.py
```

Watch them appear in the graph in real-time!

## Configuration

### Command Line Options

```bash
./examples/StandaloneGraphViewer/run.sh --port 8080 --domain 1
```

**Options:**
- `-p, --port PORT` - Server port (default: 5000)
- `--host HOST` - Bind address (default: 0.0.0.0)
- `--domain ID` - DDS domain ID (default: 0)

### Environment Variables

```bash
PORT=8080 GENESIS_DOMAIN=1 ./examples/StandaloneGraphViewer/run.sh
```

- `PORT` - Server port
- `HOST` - Bind address
- `GENESIS_DOMAIN` - DDS domain ID

## How It Works

This example uses the library's built-in `create_viewer_app()` function:

```python
from genesis_lib.web.graph_viewer import create_viewer_app

app, socketio, graph = create_viewer_app(domain_id=0)
socketio.run(app, host="0.0.0.0", port=5000)
```

That's it! The library provides:
- Flask app with all routes configured
- Socket.IO for real-time updates
- GraphService monitoring DDS topology
- 3D orbital viewer at `/genesis-graph/reference`

## What You'll See

- **Agents** - Shown as orbiting nodes with AI capabilities
- **Services** - Provider nodes offering functions
- **Interfaces** - Connection points to the network
- **Functions** - Smaller nodes showing available capabilities
- **Edges** - Connections showing relationships (who provides what, who calls who)

**Interactions:**
- Click and drag to rotate
- Scroll to zoom
- Click nodes to see details
- Watch live updates as components start/stop

## Running with Stress Test

Combine with the stress test to visualize large topologies:

```bash
# Terminal 1: Start the viewer
./examples/StandaloneGraphViewer/run.sh

# Terminal 2: Launch 10 agents and 20 services
./tests/stress/start_topology.sh -a 10 -s 20 -i 0 -t 300

# Open http://localhost:5000/ and watch the graph populate!
```

## Architecture

```
StandaloneGraphViewer
    └── Uses library's create_viewer_app()
            ├── GraphService (monitors DDS)
            ├── Flask app (serves HTTP)
            ├── Socket.IO (real-time updates)
            └── /genesis-graph/reference (3D viewer)
```

**Comparison:**

| Feature | StandaloneGraphViewer | GraphInterface |
|---------|----------------------|----------------|
| Graph visualization | ✅ | ✅ |
| Agent discovery | ❌ | ✅ |
| Chat interface | ❌ | ✅ |
| Code complexity | Minimal (20 lines) | Full app |
| Use case | Monitoring/Dashboard | Interactive demo |

## API Endpoints

The library automatically provides these endpoints:

- `GET /` - Root (redirects to viewer)
- `GET /genesis-graph/reference` - Full-page 3D viewer
- `GET /genesis-graph/api/graph` - JSON graph data (Cytoscape format)
- `GET /genesis-graph/static/orbital_viewer.js` - 3D visualization code
- **Socket.IO** `/` - Real-time graph update events

## Troubleshooting

**"No nodes showing"**
- Make sure you have agents/services running
- Check they're on the same `GENESIS_DOMAIN` (default: 0)
- Wait 2-3 seconds for DDS discovery

**"Connection refused"**
- Check the port isn't in use: `lsof -i :5000`
- Try a different port: `./run.sh --port 8080`

**"Graph not updating"**
- Check browser console (F12) for errors
- Verify Socket.IO is connected (should see connection in console)
- Refresh the page

## Learn More

- See `genesis_lib/web/graph_viewer.py` for the library implementation
- See `examples/GraphInterface/` for a full interface with chat
- See `tests/stress/start_topology.sh` for stress testing large topologies
- See `V2_MONITORING_USAGE.md` for monitoring architecture details

