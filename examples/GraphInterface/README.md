# GraphInterface Example

A complete demo showing how to build a web interface that combines:
- **Agent Discovery & Chat** - Connect to and interact with Genesis agents
- **Real-time Graph Visualization** - See your agent/service topology update live in 3D
- **Reusable Components** - Uses the Genesis Graph Viewer blueprint and Socket.IO bridge

## What You'll See

When you run this example, you'll get a split-screen web interface:
- **Left pane**: Agent discovery dropdown, connect button, and chat interface
- **Right pane**: 3D visualization of your Genesis network topology (agents, services, interfaces)

The interface lets you:
1. Discover available agents in your Genesis network
2. Connect to a specific agent (PersonalAssistant or WeatherExpert)
3. Chat with the agent and see responses
4. Watch the network graph update in real-time as components start/stop

## Prerequisites

- Genesis library installed (see root README.md)
- Python dependencies: `flask`, `flask-socketio`
- (For multi-agent demo) Example agents and services from this repo

## Quick Start: Server Only

Run just the GraphInterface server (no agents):

```bash
# From repo root
./examples/GraphInterface/run_graph_interface.sh

# Then open http://localhost:5080/
```

This starts the server and graph viewer, but you'll need to start agents separately if you want to chat with them.

## Full Demo: Multi-Agent

Run the complete demo with multiple agents and services:

```bash
# From repo root
./examples/GraphInterface/run_with_multiagent.sh

# Then open http://localhost:5080/
```

This launches:
- **GraphInterface server** (port 5080)
- **PersonalAssistant agent** - General purpose assistant with calculator access
- **WeatherExpert agent** - Weather information specialist
- **Calculator service** - Math computation service

**Note**: All services write logs to `examples/GraphInterface/logs/`

## How to Use the Interface

1. **Open** http://localhost:5080/ in your browser
2. **Wait 2-3 seconds** for agent discovery to complete
3. **Click "Refresh"** to populate the agents dropdown
4. **Select an agent** from the dropdown (e.g., "PersonalAssistant")
5. **Click "Connect"** to establish connection to that agent
6. **Type a message** in the chat input (e.g., "What is 15 + 27?")
7. **Press "Send"** and see the agent's response
8. **Watch the graph** on the right pane showing the network topology

## Example Interactions

**With PersonalAssistant:**
- "What is 42 * 18?"
- "Calculate 100 divided by 5"

**With WeatherExpert:**
- "What's the weather in Paris?"
- "Tell me about the weather in Tokyo"

## Architecture Overview

This example demonstrates the Genesis multi-component pattern:

```
Flask/SocketIO Web Server
    ├── MonitoredInterface (agent discovery & chat)
    ├── GraphService (DDS topology monitoring)
    └── register_graph_viewer (mounts reusable viewer at /genesis-graph)
```

**Key components:**
- `server.py` - Flask app with Socket.IO for bidirectional communication
- `MonitoredInterface` - Discovers and connects to Genesis agents
- `GraphService` - Subscribes to DDS monitoring topics for live topology
- `register_graph_viewer()` - Mounts the reusable graph viewer blueprint
- `index.html` - Simple UI with chat and embedded graph viewer

## Configuration

**Environment variables:**
- `GENESIS_DOMAIN` - DDS domain ID (default: 0)
- `PORT` - Server port (default: 5080)
- `GENESIS_GRAPH_BRIDGE_UPDATE_SUPPRESS_MS` - Update throttle (default: 500ms)
- `GENESIS_GRAPH_BRIDGE_REMOVE_SUPPRESS_MS` - Removal delay (default: 2000ms)
- `GENESIS_GRAPH_BRIDGE_BATCH_MS` - Batch mode threshold (default: 0)

**Command line args:**
```bash
python examples/GraphInterface/server.py -p 8080 --host 0.0.0.0
```

## Customization

**Replace the UI:**
- Edit `templates/index.html` for your custom interface
- Keep the `<div id="graph">` element for the 3D viewer
- The viewer supports extensive customization via the `orbital_viewer.js` API

**Use the reusable viewer in your own app:**
```python
from genesis_lib.graph_state import GraphService
from genesis_lib.web.graph_viewer import register_graph_viewer

graph = GraphService(domain_id=0)
graph.start()
register_graph_viewer(app, socketio, graph, url_prefix="/genesis-graph")
```

## Testing

**Test agent isolation** (verify each agent gets only its own messages):
```bash
# Start the multi-agent demo first
./examples/GraphInterface/run_with_multiagent.sh

# In another terminal:
cd Genesis_LIB
python examples/GraphInterface/test_unique_agents.py
```

This verifies that connecting to PersonalAssistant only sends messages to that agent, not to WeatherExpert.

## Logs

All component logs are written to `examples/GraphInterface/logs/`:
- `server.log` - GraphInterface server output
- `personal_assistant.log` - PersonalAssistant agent
- `weather_agent.log` - WeatherExpert agent
- `calculator_service.log` - Calculator service

## Stop

Press `Ctrl+C` to stop all services. The cleanup trap will terminate all background processes.

## Troubleshooting

**"No agents discovered"**
- Wait 3-5 seconds after starting agents for DDS discovery
- Click the "Refresh" button
- Check that agents are running: `ps aux | grep python | grep agent`
- Check logs in `examples/GraphInterface/logs/`

**"Failed to connect to agent"**
- Ensure you clicked "Refresh" before connecting
- Verify the agent is running and logged in its log file
- Check that all services are on the same `GENESIS_DOMAIN` (default: 0)

**"Graph not showing"**
- Wait a few seconds for topology data to arrive
- Check browser console (F12) for JavaScript errors
- Verify GraphService is running (check server logs)

**Port already in use**
```bash
./examples/GraphInterface/run_with_multiagent.sh -p 8080
```

## Learn More

- See `examples/MultiAgent/` for more complex multi-agent patterns
- See `genesis_lib/web/graph_viewer.py` for the reusable viewer implementation
- See `V2_MONITORING_USAGE.md` for details on the monitoring architecture
