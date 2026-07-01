# Genesis Architecture

A concise reference for contributors and advanced users. Covers component model, file layout, APIs, DDS types, and extension patterns.

---

## Core Components

| Component | Role | Base Class | File |
|-----------|------|-----------|------|
| **Interface** | Entry point — accepts user/app input, sends to agent via DDS RPC | `GenesisInterface` / `MonitoredInterface` | `interface.py`, `monitored_interface.py` |
| **Agent** | Orchestrator — integrates LLM, calls tools (functions, agents, internal methods) | `GenesisAgent` → `MonitoredAgent` → `OpenAIGenesisAgent` | `agent.py`, `monitored_agent.py`, `openai_genesis_agent.py` |
| **Service** | Function provider — exposes callable functions via DDS RPC | `EnhancedServiceBase` / `GenesisRPCService` | `enhanced_service_base.py`, `rpc_service.py` |
| **Discovery** | Advertises and discovers callable functions across the network | `FunctionRegistry` | `function_discovery.py` |
| **Agent↔Agent** | Routes requests to specialized agents via DDS RPC | `AgentCommunicationMixin` | `agent_communication.py` |
| **Monitoring** | Publishes real-time topology nodes/edges and chain events | `GraphMonitor`, `GraphState` | `graph_monitoring.py`, `graph_state.py` |

---

## Repository Layout

```
genesis_lib/
├── agent.py                    GenesisAgent — discovery, tool routing, orchestration
├── monitored_agent.py          MonitoredAgent — state machine, graph topology publishing
├── openai_genesis_agent.py     OpenAIGenesisAgent — OpenAI provider
├── anthropic_genesis_agent.py  AnthropicGenesisAgent — Anthropic provider
├── local_genesis_agent.py      LocalGenesisAgent — Ollama / local inference
├── interface.py                GenesisInterface — RPC client side of Interface↔Agent
├── monitored_interface.py      MonitoredInterface — adds node/edge events and chain overlay
├── rpc_service.py              GenesisRPCService — base service loop and reply handling
├── enhanced_service_base.py    EnhancedServiceBase — @genesis_function wiring + advertisement
├── rpc_client.py               GenesisRPCClient — sends FunctionRequest, correlates reply
├── function_discovery.py       FunctionRegistry — DDS-based discovery and caching
├── agent_communication.py      AgentCommunicationMixin — agent-as-tool routing
├── decorators.py               @genesis_function, @genesis_tool
├── graph_monitoring.py         GraphMonitor — topology and chain events
├── graph_state.py              GraphState — in-memory graph model
├── datamodel.py                Python IDL: FunctionRequest, FunctionReply, etc.
└── config/
    └── datamodel.xml           DDS type definitions, QoS profiles, topic configurations
```

---

## Communication Patterns

### Interface → Agent
- **Types**: `InterfaceAgentRequest` / `InterfaceAgentReply` (XML, string payloads + `conversation_id`)
- **Mechanism**: `rti.rpc.Requester` on interface, `rti.rpc.Replier` on agent
- **API**: `interface.connect_to_agent(service_name)` → `interface.send_request({...})`

### Agent → Service (function RPC)
- **Types**: `FunctionRequest` / `FunctionReply` (Python IDL, arguments/result are JSON strings)
- **Mechanism**: `GenesisRPCClient` ↔ `GenesisRPCService`
- **Targeting**: `FunctionCapability.service_name` tells callers which endpoint hosts a function

### Agent ↔ Agent (specialization delegation)
- **Types**: `AgentAgentRequest` / `AgentAgentReply` (XML)
- **Mechanism**: `AgentCommunicationMixin` manages discovery + dynamic RPC endpoints
- **Classification**: Pure LLM-based routing (no rule-based matching)

---

## Discovery and Advertisement

- Services advertise via `FunctionCapability` (name, description, JSON parameter schema, `provider_id`, `service_name`)
- Agents discover functions through `FunctionRegistry`, which caches metadata for targeting
- Agents advertise capabilities via `AgentCapability` for agent-as-tool conversion and routing
- All discovery is DDS-native — zero configuration, works across machines and networks

---

## DDS Topics

| Topic | Type | Purpose |
|-------|------|---------|
| `genesis_agent_registration_announce` | `GenesisRegistration` (XML) | Agent presence and registration |
| `FunctionCapability` | XML | Function discovery and metadata |
| `AgentCapability` | XML | Agent discovery and specializations |
| `InterfaceAgentRequest/Reply` | XML | Interface→Agent RPC |
| `AgentAgentRequest/Reply` | XML | Agent↔Agent RPC |
| `FunctionRequest/Reply` | Python IDL | Agent→Service function RPC |
| `GenesisGraphNode` / `GenesisGraphEdge` | XML | Real-time network topology |
| `ChainEvent` | XML | Multi-hop flow correlation |
| `MonitoringEvent` | XML | General lifecycle and monitoring |

Full schema: `genesis_lib/config/datamodel.xml`

---

## Monitoring and Graph

- `GraphMonitor` publishes durable nodes/edges representing components and their relationships
- State transitions (`DISCOVERING → READY → BUSY → READY`) are published per component
- `ChainEvent` overlays correlate classification → tool call → result across multiple hops
- The Graph Interface (`examples/GraphInterface/`) visualizes this in real time

---

## Extension Patterns

### Add a Service
Subclass `EnhancedServiceBase`, decorate functions with `@genesis_function`, call `_advertise_functions()`. Functions are discovered automatically.

```python
class MyService(EnhancedServiceBase):
    def __init__(self):
        super().__init__("MyService", capabilities=["my-capability"])
        self._advertise_functions()

    @genesis_function()
    async def my_function(self, x: float) -> dict:
        """Do something with x."""
        return {"result": x * 2}
```

### Add an Agent
Subclass `OpenAIGenesisAgent` (or another provider agent). Internal tools use `@genesis_tool`.

```python
class MyAgent(OpenAIGenesisAgent):
    def __init__(self):
        super().__init__(model_name="gpt-4o", agent_name="MyAgent")

    @genesis_tool(description="Process some data")
    async def process(self, data: str) -> dict:
        return {"processed": data.upper()}
```

### Add an Interface
Subclass `MonitoredInterface`, connect to an agent, send requests.

```python
interface = MonitoredInterface("MyInterface", "MyService")
await interface.connect_to_agent(service_name="MyAgent")
response = await interface.send_request({"message": "Hello"})
```

### Add a new LLM Provider
See [add-provider.md](add-provider.md) — about 7 abstract methods, ~150 lines.

---

## Further Reading

- [Agent Hierarchy](agent-hierarchy.md) — abstract method contracts for provider implementations
- [Capability System](capability-system.md) — three-tier capability resolution
- [Function Discovery](function-discovery.md) — discovery flow and agent-as-tool conversion
- [Monitoring System](monitoring-system.md) — GraphMonitor, GraphState, event types
- [Multi-Provider Architecture](multi-provider.md) — three-layer provider abstraction
- [Reference: DDS Topics](../reference/topics.md) — full topic and QoS reference
- [Reference: Function RPC](../reference/function-rpc.md) — detailed RPC protocol

---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
