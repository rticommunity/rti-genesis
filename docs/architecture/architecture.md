# Genesis Architecture (Overview)

Purpose: a concise, high‑level view of how Genesis fits together. For deep, API‑level and file‑level details, see `docs/architecture/architecture_detailed.md`.

## Core Components
- Interfaces: Entry points that accept user/app inputs and communicate with agents via DDS RPC.
  - Base: `genesis_lib/interface.py` → `GenesisInterface`
  - Monitored: `genesis_lib/monitored_interface.py` → `MonitoredInterface`
- Agents: Orchestrators that call tools (functions, other agents, internal methods) and integrate LLMs.
  - Base: `genesis_lib/agent.py` → `GenesisAgent`
  - Monitored: `genesis_lib/monitored_agent.py` → `MonitoredAgent`
  - OpenAI agent: `genesis_lib/openai_genesis_agent.py` → `OpenAIGenesisAgent`
- Services (Function Providers): RPC services exposing callable functions.
  - Base RPC: `genesis_lib/rpc_service.py` → `GenesisRPCService`
  - Enhanced: `genesis_lib/enhanced_service_base.py` → `EnhancedServiceBase`
- Discovery & Registry: Advertise and discover callable functions across the network.
  - `genesis_lib/function_discovery.py` → `FunctionRegistry`
- Transport: RTI Connext DDS + RPC.
  - XML types: `genesis_lib/config/datamodel.xml`
  - Python IDL (Function RPC): `genesis_lib/datamodel.py`
- Monitoring & Graph: Durable node/edge and activity events for live topology and tracing.
  - `genesis_lib/graph_monitoring.py`, `genesis_lib/graph_state.py`

## Communication Patterns
- Interface → Agent (chat/task):
  - Types: `InterfaceAgentRequest`/`InterfaceAgentReply` (XML)
  - Mechanism: `rti.rpc.Requester` on interface, `rti.rpc.Replier` on agent.
- Agent → Service (function RPC):
  - Types: `FunctionRequest`/`FunctionReply` (Python IDL)
  - Mechanism: `GenesisRPCClient` ↔ `GenesisRPCService`
  - Target resolution: from discovered `FunctionCapability.service_name`.
- Agent ↔ Agent (specialization delegation):
  - Types: `AgentAgentRequest`/`AgentAgentReply` (XML)
  - Mechanism: `AgentCommunicationMixin` handles discovery + RPC endpoints.

See the end‑to‑end sequence in `docs/user-guides/function_call_flow.md` (Agent‑as‑Tool pattern).

## Discovery & Advertisement
- Services advertise functions via `FunctionCapability` with name, description, JSON parameter schema, provider_id, and `service_name`.
- Agents and tools discover functions through `FunctionRegistry` and cache metadata for targeting RPC endpoints.
- Agents can also advertise capabilities via `AgentCapability` for agent‑as‑tool conversion and routing.

## Monitoring & Topology
- Unified graph: nodes (`GenesisGraphNode`) and edges (`GenesisGraphEdge`) represent components and relationships.
- Chain overlays (`ChainEvent`) correlate multi‑hop flows (classification, tool calls, results).
- Monitored variants publish state transitions (DISCOVERING, READY, BUSY) for realtime UIs (see Graph Interface demo).

## Examples
- Graph Interface UI: `examples/GraphInterface/server.py`
- Multi‑Agent demos: `examples/MultiAgent/`
- Drone demo orchestrator: `examples/DroneGraphDemo/run_drone_graph_demo.sh`

## Further Reading
- Function flow (sequence): `docs/user-guides/function_call_flow.md`
- Function RPC deep dive: `docs/user-guides/genesis_function_rpc.md`
- Agent architecture: `docs/architecture/AGENT_ARCHITECTURE_QUICK_REFERENCE.md`
- DDS RPC reference (quick): `docs/reference/RTI_7.3_RPC.md`

---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
