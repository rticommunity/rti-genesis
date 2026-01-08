# Genesis Architecture (Detailed)

This document complements the overview with file‑level pointers, APIs, and operational details.

## Repository Layout (key paths)
- Core library: `genesis_lib/`
  - App & Core: `genesis_lib/genesis_app.py`, `genesis_lib/datamodel.py`, `genesis_lib/config/datamodel.xml`
  - Interfaces: `genesis_lib/interface.py`, `genesis_lib/monitored_interface.py`
  - Agents: `genesis_lib/agent.py`, `genesis_lib/monitored_agent.py`, `genesis_lib/openai_genesis_agent.py`
  - Services: `genesis_lib/rpc_service.py`, `genesis_lib/enhanced_service_base.py`, `genesis_lib/rpc_client.py`
  - Discovery: `genesis_lib/function_discovery.py`
  - Agent‑to‑Agent: `genesis_lib/agent_communication.py`
  - Monitoring/Graph: `genesis_lib/graph_monitoring.py`, `genesis_lib/graph_state.py`
  - Utils: `genesis_lib/utils/`
- Examples: `examples/GraphInterface/`, `examples/MultiAgent/`, `examples/DroneGraphDemo/`
- Docs index: `docs/README.md`

## Core APIs (where to look)
- `GenesisInterface` (client side of Interface↔Agent RPC): `genesis_lib/interface.py`
  - Discovers agent registrations, connects (`connect_to_agent(service_name)`), sends requests (`send_request({...})`).
- `MonitoredInterface`: `genesis_lib/monitored_interface.py`
  - Adds node/edge events, optional chain overlay, reply listener for COMPLETE alignment.
- `GenesisAgent`: `genesis_lib/agent.py`
  - Publishes registration, implements RPC replier, processes interface requests, optional agent‑to‑agent setup.
- `MonitoredAgent`: `genesis_lib/monitored_agent.py`
  - Emits monitoring/chain events around classification, function calls, and results.
- `OpenAIGenesisAgent`: `genesis_lib/openai_genesis_agent.py`
  - Agent‑as‑Tool: builds unified toolset (functions + agents + @genesis_tool), performs a single LLM call, dispatches tool calls.
- `GenesisRPCService`/`EnhancedServiceBase`: `genesis_lib/rpc_service.py` / `genesis_lib/enhanced_service_base.py`
  - Base service loop (`receive_requests`, parse args, execute, reply), function wrappers, advertisement via `FunctionRegistry`.
- `GenesisRPCClient`: `genesis_lib/rpc_client.py`
  - Sends `FunctionRequest`, correlates and parses `FunctionReply`.
- `FunctionRegistry`: `genesis_lib/function_discovery.py`
  - Advertises function capability (`FunctionCapability`), listens for discovery, maintains cache and callbacks.
- `AgentCommunicationMixin`: `genesis_lib/agent_communication.py`
  - Agent capability advertisement/discovery, agent‑specific RPC endpoints, request routing.

## DDS Types & Topics
- XML (`genesis_lib/config/datamodel.xml`)
  - Registration: `genesis_agent_registration_announce` on `GenesisRegistration`.
  - Interface↔Agent RPC: `InterfaceAgentRequest`, `InterfaceAgentReply` (string payloads + conversation_id).
  - Agent↔Agent RPC: `AgentAgentRequest`, `AgentAgentReply`.
  - Capability Ads: `FunctionCapability`, `AgentCapability`.
  - Graph/Monitoring: `GenesisGraphNode`, `GenesisGraphEdge`, `MonitoringEvent`, `ChainEvent`, etc.
- Python IDL (`genesis_lib/datamodel.py`)
  - Function RPC: `Function`, `Tool`, `FunctionCall`, `FunctionRequest`, `FunctionReply` (arguments/result are JSON strings).

## Request–Reply Details
- Service naming: RPC endpoints are named via `service_name` when creating `Requester`/`Replier`.
- Function targeting: `FunctionCapability.service_name` tells callers which endpoint hosts a given function.
- Conversation context:
  - `conversation_id` exists for Interface↔Agent and Agent↔Agent (XML types).
  - Function RPC messages (Python IDL) don’t carry `conversation_id`; cross‑hop correlation uses chain/monitoring IDs.

## Monitoring/Graph
- Use `GraphMonitor` to publish durable nodes/edges for discovery, READY/BUSY state, function connections, and request/response overlays.
- Monitored classes publish both graph nodes and `ChainEvent` overlays to visualize multi‑hop flows (classification, tool calls, results).

## Development & Extension
- Add a new service: subclass `EnhancedServiceBase`, decorate/register functions, `run()` — functions auto‑advertise and become discoverable.
- Add an interface: subclass `MonitoredInterface`, use `connect_to_agent()` then `send_request()`.
- Add an agent: subclass `MonitoredAgent` (or `OpenAIGenesisAgent`), optionally enable `AgentCommunicationMixin` for agent‑as‑tool.
- Internal tools: decorate methods with `@genesis_tool`; schemas auto‑generated and included in toolset.

## Examples & Scripts
- Graph viewer server: `examples/GraphInterface/server.py` (mounts viewer at `/genesis-graph`).
- Multi‑Agent examples and scripts: `examples/MultiAgent/`.
- Drone demo launcher: `examples/DroneGraphDemo/run_drone_graph_demo.sh`.
- Test orchestration: `run_scripts/run_all_tests.sh`.

## Environment & Requirements
- Python 3.10; see `AGENTS.md` and `setup.sh` for quickstart.
- RTI Connext DDS 7.3+ installed and on PATH; set `GENESIS_DOMAIN` as needed.
- For OpenAI‑based agents: `OPENAI_API_KEY` must be set.

## Cross‑References
- Architecture overview: `docs/architecture/architecture.md`
- Function flow (sequence): `docs/user-guides/function_call_flow.md`
- Function RPC deep dive: `docs/user-guides/genesis_function_rpc.md`
- Agent architecture: `docs/architecture/AGENT_ARCHITECTURE_QUICK_REFERENCE.md`
- Graph/monitoring: `docs/architecture/monitoring_system.md`
