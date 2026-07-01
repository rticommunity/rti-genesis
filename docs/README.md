# Genesis Documentation

Start at [README.md](../README.md) for installation and your first agent.

---

## Guides

Task-oriented how-tos for building with Genesis.

- [Creating an Agent](guides/creating-an-agent.md) — agents, interfaces, internal tools, agent-to-agent
- [Creating a Service](guides/creating-a-service.md) — expose functions via `@genesis_function`
- [Agent Capabilities](guides/capabilities.md) — configure what your agent advertises
- [Monitoring](guides/monitoring.md) — enable and use the unified monitoring system
- [Local Inference](guides/local-inference.md) — run agents with Ollama (no API costs)

---

## Reference

Stable lookup material.

- [DDS Topics](reference/topics.md) — all topics, QoS, and field definitions
- [Function RPC](reference/function-rpc.md) — detailed RPC protocol and flow
- [Function Call Flow](reference/function-call-flow.md) — agent-as-tool sequence diagram
- [DDS Configuration](reference/dds-configuration.md) — QoS tuning and macOS troubleshooting
- [Known Issues](reference/known-issues.md) — current known issues and workarounds
- [RTI RPC API](reference/rti-rpc-api.md) — RTI Connext RPC API reference
- [DDS GUID Identification](reference/dds-guid.md) — client and provider ID identification

---

## Architecture

Contributor-facing internals. Start here if you're extending Genesis.

- [Overview](architecture/overview.md) — component model, communication patterns, file layout
- [Agent Hierarchy](architecture/agent-hierarchy.md) — class hierarchy and abstract method contracts
- [Capability System](architecture/capability-system.md) — three-tier capability resolution
- [Function Discovery](architecture/function-discovery.md) — how `@genesis_function` services are discovered
- [Agent-as-Tool](architecture/agent-as-tool.md) — how agents are discovered and exposed as LLM tools
- [Monitoring System](architecture/monitoring-system.md) — GraphMonitor, GraphState, event types
- [Multi-Provider Architecture](architecture/multi-provider.md) — LLM provider abstraction design
- [Add a Provider](architecture/add-provider.md) — add a new LLM provider in ~150 lines
- [Code Explorer](architecture/explorer.md) — fast file/class navigation for contributors

---

## Examples

Each example has its own README:

- `examples/HelloWorld/` — minimal agent + service + interface
- `examples/MultiAgent/` — agent-as-tool with real APIs
- `examples/GraphInterface/` — chat + live network visualization
- `examples/StandaloneGraphViewer/` — pure network topology server
- `examples/PersistentMemory/` — agent with cross-session memory

---

## Testing

See [tests/README.md](../tests/README.md) for test setup and the full test suite documentation.

---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
