# RTI GENESIS

**Open-source distributed AI agent framework that brings industrial-grade reliability to multi-agent systems — powered by RTI Connext DDS.**

GENESIS enables teams to build, deploy, and connect AI agents across distributed machines with zero-configuration discovery, guaranteed message delivery, and sub-millisecond latency. It is the only AI agent framework built on the same middleware used in surgical robots, flight control systems, and autonomous vehicles.

---

[GitHub](#) · [Documentation](#) · [RTI Community](#)

---

## See GENESIS in Action

| Example | What it demonstrates |
|---------|---------------------|
| **Hello World** | Minimal agent + service + CLI interface; function calling over DDS in under 50 lines |
| **Multi-Agent** | Agent-as-Tool pattern: WeatherAgent automatically discovers and delegates to an OpenWeatherMap service |
| **GraphInterface** | Live web-based topology visualization of a running multi-agent network |
| **CodingAgent** | Agent that writes and executes Python code as a tool |
| **PersistentMemory** | Context preservation across sessions |
| **Slack / Telegram Interface** | Drop-in messaging interfaces for existing agent networks |

```bash
# Run the multi-agent demo in under 5 minutes
git clone https://github.com/rticommunity/rti-genesis
cd rti-genesis && ./setup.sh
cd examples/MultiAgent && ./run_interactive_demo.sh
```

---

## How It Works

### Zero-Configuration Agent Discovery

GENESIS replaces service registries, configuration files, and port lists with **RTI Connext DDS automatic discovery**. Every agent and service publishes its capabilities to a durable DDS topic the moment it starts. Any component joining the network — on the same machine, across a LAN, or across a WAN — immediately receives the full catalog of available agents and functions. No coordinator. No broker. No restart required.

```
Agent A starts  →  publishes Advertisement(kind=AGENT) to DDS
Agent B starts  →  reads Advertisement, auto-discovers Agent A
Agent B's LLM   →  sees Agent A as a callable tool — no config needed
```

This makes GENESIS uniquely suited for **dynamic topologies**: drone fleets, edge devices, mobile platforms, and any environment where components join and leave unpredictably.

---

### Agent-as-Tool: Natural Language Delegation

The central innovation in GENESIS is the **Agent-as-Tool pattern**. Every discovered agent is automatically converted into an OpenAI-compatible tool schema and injected into the primary agent's LLM call — alongside local tools and service functions — in a single unified toolset.

The LLM decides which agent or function to call using natural language. Routing happens transparently over DDS RPC. No separate orchestration stage. No manual wiring.

```
User query
    ↓
Primary Agent (single LLM call)
    ├── @genesis_tool methods       (local)
    ├── @genesis_function services  (RPC over DDS)
    └── Discovered remote agents    (Agent-as-Tool over DDS RPC)
```

This eliminates the need for hand-written orchestration logic in the common multi-agent case.

---

### Simplify Development

GENESIS uses two decorators to eliminate boilerplate. JSON schemas, DDS advertisements, and tool registrations are all generated automatically from Python type hints and docstrings.

**Expose a function as a network-callable tool:**
```python
from genesis_lib.enhanced_service_base import EnhancedServiceBase
from genesis_lib.decorators import genesis_function

class WeatherService(EnhancedServiceBase):
    @genesis_function()
    async def get_forecast(self, city: str, days: int) -> dict:
        """Return a weather forecast for the given city."""
        ...
```

**Add a tool directly to an agent:**
```python
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
from genesis_lib.decorators import genesis_tool

class AnalysisAgent(OpenAIGenesisAgent):
    @genesis_tool(description="Analyze a dataset and return key statistics")
    async def analyze(self, data: str) -> dict:
        ...
```

Both decorators auto-generate the full JSON Schema, advertise the capability over DDS, and make it immediately available to any other agent on the network.

**Adding a new LLM provider** requires implementing 7 abstract methods (~150 lines). Currently shipped: OpenAI, Anthropic (Claude), Ollama (local inference).

---

### Industrial-Grade Reliability

GENESIS is built on **RTI Connext DDS** — the OMG-standard middleware (ISO/IEC 19506) deployed in FDA-cleared medical devices, NATO systems, and autonomous vehicle platforms. This gives every GENESIS deployment capabilities that HTTP-based agent frameworks cannot match:

| Capability | GENESIS (DDS) | HTTP-based frameworks |
|------------|--------------|----------------------|
| **Delivery guarantee** | Configurable: best-effort or reliable, per topic | Retry logic only |
| **Late-joiner catch-up** | TRANSIENT_LOCAL durability — new agents see full history immediately | Must re-request or miss data |
| **Liveliness detection** | Heartbeat-based; dead agents detected automatically | Timeout-based polling |
| **Transport** | UDP, TCP, shared memory (sub-ms on same host) | HTTP/TCP only |
| **Broker** | None — true peer-to-peer | Central broker or service mesh |
| **Network topology** | LAN, WAN, air-gapped, cross-cloud | Internet/HTTPS required |

For **safety-critical deployments**, DDS Security (planned) adds certificate-based authentication, encrypted transport, and fine-grained access control lists at the topic and participant level.

---

### Complete Execution Visibility

Every component in a GENESIS network publishes lifecycle and chain events to DDS monitoring topics. No instrumentation code required in application logic.

**What is tracked automatically:**
- Node state transitions: `DISCOVERING → READY → BUSY → DEGRADED → OFFLINE`
- Edge events: discovery, connection established, request sent, response received
- Chain overlays: a single user query correlated across every hop (Interface → Agent → Agent → Service) via `chain_id` and `call_id`

**Visualization tools:**
- **GraphInterface** (`examples/GraphInterface/`): live web-based graph of the running network — nodes, edges, state colors, and chain traces update in real time
- **`genesis_monitor_extended.py`**: curses terminal UI with color-coded event filtering
- **`rtiddsspy`**: RTI DDS Spy for raw traffic inspection at the wire level

```
User query "What is the weather in Rome?"
    chain_id: abc123
    ├── Interface → PrimaryAgent       [call_id: 1]
    ├── PrimaryAgent → WeatherAgent    [call_id: 2]  ← agent-as-tool
    └── WeatherAgent → WeatherService  [call_id: 3]  ← function RPC
    All three hops visible in GraphInterface under chain abc123
```

---

### Security and Deployment

| Layer | Capability |
|-------|-----------|
| **Transport** | DDS Security plugin (planned): cert-based auth, AES-encrypted UDP/TCP, fine-grained ACLs per topic |
| **Network isolation** | DDS domain IDs partition networks without any firewall rules |
| **Agent identity** | DDS participant GUIDs uniquely identify every component |
| **Air-gapped deployment** | No internet dependency; runs fully on-premise or on disconnected edge hardware |
| **MCP interoperability** | `agent.enable_mcp(port=8000)` exposes any GENESIS agent as a FastMCP server — callable from Claude Code, Cursor, NAT, or any MCP client |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      User / Interface                    │
│          GenesisInterface / MonitoredInterface           │
└────────────────────────┬────────────────────────────────┘
                         │  DDS RPC (InterfaceAgentRequest)
┌────────────────────────▼────────────────────────────────┐
│                    Primary Agent                         │
│              OpenAIGenesisAgent / LocalGenesisAgent      │
│                                                          │
│  Single LLM call with unified toolset:                   │
│  ┌─────────────┬──────────────────┬──────────────────┐  │
│  │ @genesis_   │  Discovered      │  Discovered      │  │
│  │ tool methods│  service funcs   │  remote agents   │  │
│  └─────────────┴──────────────────┴──────────────────┘  │
└──────┬──────────────────┬──────────────────┬────────────┘
       │ direct call      │ DDS RPC          │ DDS RPC
       │                  │ (FunctionRequest) │ (AgentAgentRequest)
┌──────▼──────┐   ┌───────▼───────┐  ┌───────▼──────────┐
│  Internal   │   │   Service     │  │  Specialist      │
│  Tool       │   │   (function   │  │  Agent           │
│  (@genesis_ │   │    server)    │  │  (own LLM +      │
│   tool)     │   │               │  │   tools + DDS)   │
└─────────────┘   └───────────────┘  └──────────────────┘

All components publish to:
  rti/connext/genesis/Advertisement          (durable — discovery)
  rti/connext/genesis/monitoring/Event       (volatile — lifecycle)
  rti/connext/genesis/monitoring/GraphTopology (durable — visualization)
```

---

## Target Use Cases

### Defense and Aerospace
GENESIS originated as a U.S. Air Force SBIR contract (FA8730-25-P-B001). DDS is DoD-familiar middleware deployed across NATO programs and defense systems. Air-gapped operation, DDS Security, and deterministic QoS align with defense requirements.

### Robotics and Autonomous Systems
Sub-millisecond DDS transport and peer-to-peer topology make GENESIS suitable for robot fleet coordination, UAV swarm management, and autonomous vehicle systems where HTTP latency is unacceptable.

### Industrial Control and Edge AI
DDS QoS guarantees (reliable delivery, liveliness, durability) bring the same reliability model used in power grid control and process automation to LLM-driven agent networks.

### Simulation and Digital Twin Integration
The original SBIR use case: connecting LLM agents to DDS-based simulation environments (Simulink, RTI Connext-based systems). GENESIS agents can interact with and control simulation state over the same DDS fabric.

### Enterprise AI Pipelines
Chain agents and services across machines and cloud regions. Combine GENESIS transport with NVIDIA NeMo Customizer (fine-tuning) and NIM (optimized inference) via the `enable_mcp()` bridge — no changes to GENESIS transport code required.

---

## Requirements

| | |
|---|---|
| **Python** | 3.10 |
| **Middleware** | RTI Connext DDS 7.7.0+ (free 60-day eval, Connext Express, or University Program) |
| **LLM** | OpenAI API key, Anthropic API key, or local Ollama install |
| **OS** | macOS, Linux, Windows |

```bash
# Install
git clone https://github.com/rticommunity/rti-genesis
cd rti-genesis && ./setup.sh
source venv/bin/activate && source .env

# Verify
python -c "import rti.connextdds as dds; print('RTI Connext DDS available')"
```

---

*RTI GENESIS — (c) 2025 Real-Time Innovations, Inc. All rights reserved.*
*Originated from U.S. Air Force SBIR Phase I contract AF242-0002. Authors: Gianpiero Napoli, Paul Pazandak, Dr. Jason Upchurch.*
