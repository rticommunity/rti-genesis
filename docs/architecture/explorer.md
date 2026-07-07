# Genesis LIB Explorer — Architecture, Flows, and DDS Map

Purpose: fast reference for contributors and agents to understand core class hierarchy, discovery, DDS topics, and request–reply paths without re-exploring the repo each time.

## Quick Repo Map (start points)
- Core library
  - `genesis_lib/genesis_app.py`
  - `genesis_lib/agent.py`
  - `genesis_lib/monitored_agent.py`
  - `genesis_lib/interface.py`
  - `genesis_lib/monitored_interface.py`
  - `genesis_lib/enhanced_service_base.py`
  - `genesis_lib/rpc_service.py`
  - `genesis_lib/rpc_client.py`
  - `genesis_lib/function_discovery.py`
  - `genesis_lib/agent_communication.py`
  - `genesis_lib/datamodel.py`
  - `genesis_lib/config/datamodel.xml`
- Examples
  - `examples/GraphInterface/server.py`
  - `examples/MultiAgent/README.md`
- Docs (deep dives)
  - `docs/user-guides/genesis_function_rpc.md`
  - `docs/user-guides/function_call_flow.md`
  - `docs/reference/RTI_7.3_RPC.md`
  - `docs/architecture/monitoring_system.md`

## Core Class Hierarchy (who extends whom)
- Interfaces
  - `GenesisInterface` → `MonitoredInterface`
- Agents
  - `GenesisAgent` → `MonitoredAgent` → concrete agents (e.g., `OpenAIGenesisAgent`)
- Services (function providers)
  - `GenesisRPCService` → `EnhancedServiceBase` → concrete services
- Discovery/Execution helpers
  - `FunctionRegistry` (advertises/discovers functions via DDS)
  - `GenesisRPCClient` (generic client for Function RPC)
  - `AgentCommunicationMixin` (agent-to-agent discovery + RPC, mixed into agents)

## Roles and Responsibilities
- `genesis_lib/genesis_app.py`: shared DDS setup for agents/interfaces; creates participant, registration topic/pubs/subs; constructs `FunctionRegistry`.
- `genesis_lib/agent.py`: agent base. Publishes registration, sets up Interface↔Agent RPC replier using `InterfaceAgentRequest/Reply` types. Optional agent↔agent via mixin.
- `genesis_lib/monitored_agent.py`: adds monitoring/graph events and convenience around calls.
- `genesis_lib/interface.py`: interface base. Monitors agent registration, creates RPC requester to a discovered agent’s service, and sends requests.
- `genesis_lib/monitored_interface.py`: adds monitoring and chain overlays to the interface.
- `genesis_lib/rpc_service.py`: base service with DDS `rti.rpc.Replier` using `FunctionRequest/Reply`. Registers functions and runs the request loop.
- `genesis_lib/enhanced_service_base.py`: service with auto function advertisement via `FunctionRegistry`, graph events, and wrappers.
- `genesis_lib/function_discovery.py`: advertises functions (as `FunctionCapability`) and discovers them; maintains in-memory catalog; contains execution Requester for function calls if needed.
- `genesis_lib/rpc_client.py`: generic RPC client using `rti.rpc.Requester` with `FunctionRequest/Reply` types.
- `genesis_lib/agent_communication.py`: agent capability advertisement and discovery; agent↔agent request–reply using `AgentAgentRequest/Reply`.

## DDS Types and Topics
- XML definitions: `genesis_lib/config/datamodel.xml`
  - Registration: `genesis_agent_registration_announce` on topic `GenesisRegistration`
  - Interface↔Agent RPC: `InterfaceAgentRequest`, `InterfaceAgentReply`
  - Agent↔Agent RPC: `AgentAgentRequest`, `AgentAgentReply`
  - Function advertisement: `FunctionCapability`
  - Monitoring/Graph: `MonitoringEvent`, `ChainEvent`, `GenesisGraphNode`, `GenesisGraphEdge`
- Python IDL structs (Function RPC): `genesis_lib/datamodel.py`
  - `Function`, `Tool`, `FunctionCall`, `FunctionRequest`, `FunctionReply`

QoS patterns (typical)
- Durability: `TRANSIENT_LOCAL` on discovery/monitoring topics
- Reliability: `RELIABLE`
- History: `KEEP_LAST` with depth (~256–500)
- Liveliness: `AUTOMATIC` (lease ~2s)

## Discovery and Advertisements
- Agent presence
  - Agents publish to `GenesisRegistration` (`genesis_agent_registration_announce`). Interfaces listen via `RegistrationListener` to detect arrivals/departures and capture `service_name`.
  - Agent capabilities are published on `AgentCapability` (rich metadata: capabilities, specializations, tags, model info). `AgentCommunicationMixin` reads/writes this.
- Function capabilities
  - Services (via `EnhancedServiceBase` → `FunctionRegistry`) publish `FunctionCapability` with: `name`, `description`, `parameter_schema` (JSON), `provider_id`, and crucially `service_name` (the RPC endpoint to target when calling this function).
  - Agents and generic clients subscribe to `FunctionCapability` to build a function catalog.

## Request–Reply Paths (who talks to whom)
- Interface → Agent (chat or high-level command)
  - Types: `InterfaceAgentRequest`/`InterfaceAgentReply` (XML dynamic data)
  - Mechanism: `rti.rpc.Requester` on interface, `rti.rpc.Replier` on agent; interface tracks discovery to pick a service name and then calls.
- Agent → Service (function call)
  - Types: Python IDL `FunctionRequest`/`FunctionReply`
  - Mechanism: `GenesisRPCClient`/`GenesisRPCService` or directly `rti.rpc.Requester/Replier` inside `EnhancedServiceBase`.
  - Target resolution: obtained from discovered `FunctionCapability.service_name`.
- Agent ↔ Agent (specialization delegation)
  - Types: `AgentAgentRequest`/`AgentAgentReply` (XML dynamic data)
  - Mechanism: `AgentCommunicationMixin` creates unique per-agent service names, handles discovery, and routes requests.

## Typical Call Flows
1) Interface → Primary Agent (LLM tools)
- Interface discovers an agent, binds to its service name, and sends `InterfaceAgentRequest`.
- Agent processes request and may select tools (functions or other agents) based on discovered catalogs.

2) Primary Agent → Function Service (via Function RPC)
- Uses discovered `FunctionCapability` to select function and target `service_name`.
- Builds `FunctionRequest(function.name, arguments=json.dumps(args))`; awaits `FunctionReply`.
- Service run loop (`GenesisRPCService.run`) parses JSON args, calls the implementation, and replies.

3) Primary Agent → Specialist Agent (Agent-as-Tool)
- Uses `AgentCapability` catalog; sends `AgentAgentRequest` to a unique agent service endpoint.
- Specialist may in turn call functions; context IDs can flow across hops.

Monitoring
- `GraphMonitor` publishes node/edge events for discovery, calls, and results.
- Optional `ChainEvent` overlays relate multi-hop chains.

## Mental Model: Where to Look for What
- Registration and DDS setup: `genesis_lib/genesis_app.py`
- Interface side binding + send: `genesis_lib/interface.py`, `genesis_lib/monitored_interface.py`
- Agent side receive + process: `genesis_lib/agent.py`, `genesis_lib/monitored_agent.py`
- Function service base mechanics: `genesis_lib/rpc_service.py`, `genesis_lib/enhanced_service_base.py`
- Function discovery and catalog: `genesis_lib/function_discovery.py`
- Agent-to-agent capability and RPC: `genesis_lib/agent_communication.py`
- Function call datatypes (Python IDL): `genesis_lib/datamodel.py`
- XML type catalog: `genesis_lib/config/datamodel.xml`

## How to Extend Safely
- New service
  - Subclass `EnhancedServiceBase`; add functions; call/run. Functions auto-advertise via `FunctionRegistry`.
- New interface
  - Subclass `MonitoredInterface`; use `connect_to_agent(service_name)` then `send_request({...})`.
- New agent
  - Subclass `MonitoredAgent`; optionally enable `AgentCommunicationMixin` for agent-as-tool flows.

## Quick rg Recipes (fast navigation)
- Classes of interest: `rg -n "class (Genesis|Monitored|Enhanced|FunctionRegistry|OpenAIGenesis)" genesis_lib`
- DDS topics in XML: `rg -n "<struct name=|<enum name=|Topic\(" genesis_lib/config/datamodel.xml genesis_lib -S`
- RPC usage sites: `rg -n "rti\.rpc\.(Requester|Replier)" genesis_lib`
- Function advertisement flow: `rg -n "FunctionCapability|register_function|advertise" genesis_lib`

## Test/Run Notes
- Full suite orchestrator: `run_scripts/run_all_tests.sh` (requires RTI Connext DDS 7.3+ and relevant API keys for LLM tests, e.g., `OPENAI_API_KEY`).
- Targeted examples: `examples/GraphInterface/server.py` and `examples/MultiAgent/*`.

## Deeper Reads (once, then skim as needed)
- `docs/user-guides/genesis_function_rpc.md` — complete Function RPC workflow and rationale.
- `docs/user-guides/function_call_flow.md` — sequence diagram for agent-as-tool.
- `docs/reference/RTI_7.3_RPC.md` — `rti.rpc` primitives reference.
- `docs/architecture/AGENT_ARCHITECTURE_QUICK_REFERENCE.md` — agent patterns and architecture.

---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
