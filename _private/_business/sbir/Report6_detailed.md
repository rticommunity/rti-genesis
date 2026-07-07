# Report 6 — Detailed Technical Addendum (M7)

This is a standalone deep‑dive for Milestone/Sprint 7. Note on sequencing: by agreement with the TPOC, we executed M7 before M6 to unblock integrations and demos. The core outcome is the elimination of the centralized “service registry” process in favor of a fully distributed capability integrated into the genesis_lib, powered by DDS advertisements and RPC.

Placeholders for images (to be populated):
- Registry‑Free Architecture Diagram — PLACEHOLDER: `docs/images/m7_architecture.png`
- Live Graph Topology (service/function overlays) — PLACEHOLDER: `docs/images/m7_graph_view.png`

---

## 7.1 Objectives and Rationale
- Remove single points of failure and bottlenecks created by a brokered registry process.
- Enable real‑time composition: services can appear/disappear; agents adapt instantly.
- Provide a uniform tool surface to LLMs that merges internal agent tools and discovered distributed functions.
- Preserve traceability: every discovery, selection, and call is visible in monitoring/graph overlays.

---

## 7.2 Components and Responsibilities
- Service (Genesis RPC Service):
  - Auto‑discovers local `@genesis_tool` functions at startup.
  - Publishes `FunctionCapability` advertisements on DDS; re‑advertises on a refresh interval or lifecycle events.
  - Handles `FunctionRequest` and returns `FunctionReply` with JSON payloads and error codes.
- Agent (OpenAIGenesisAgent / MonitoredAgent):
  - Subscribes to `FunctionCapability` and maintains a discovery cache (with TTL and priority).
  - Builds a unified tool list for the LLM (internal tools + discovered functions).
  - On tool selection, routes to the correct service via DDS RPC and returns the result.
- Graph/Monitoring:
  - Visualizes service→function edges from advertisements and agent→service edges from discoveries/requests.
  - Emits `ChainEvent` for every tool call with timing, status, and error details.
- DDS Infrastructure:
  - Provides RELIABLE | TRANSIENT_LOCAL durability for discovery topics to support late joiners.

---

## 7.3 Capability Advertisement Schema

Fields published on `FunctionCapability` (canonical subset):
- `function_id` (UUID) — unique per service instance and function.
- `service_name` (string) — logical service endpoint name.
- `provider_id` (string) — instance tag for the service; used for routing.
- `name` (string) — function/tool name (LLM‑friendly).
- `description` (string) — concise description for schema/tooltips.
- `parameter_schema` (JSON) — JSON Schema for arguments.
- `version` (semver) — function version for compatibility.
- `priority` (int) — selection tie‑breaker (higher wins) when duplicates exist.
- `advertised_at` (ns since epoch) — publication timestamp.
- `ttl_ms` (int) — advisory time‑to‑live for cache entries.

Notes:
- Services re‑advertise on interval `ttl_ms/2` or on lifecycle events (start/stop).
- Agents drop expired capabilities and prefer the most recent advertisement by `(priority, advertised_at)`.

---

## 7.4 Discovery Cache and Selection Logic
- Cache keyed by `(name, service_name, provider_id)` with version tracking.
- When multiple providers advertise the same function, the agent chooses by:
  1) Highest `priority`
  2) Most recent `advertised_at`
  3) Locality hint (optional; e.g., same host/partition)
- Agents can filter by tags (e.g., domain partition, specialization) for scoped toolsets.

---

## 7.5 Invocation Path and Error Model
- `FunctionRequest` includes `{request_id, function_id, args_json, conversation_id?, timeout_ms?}`.
- `FunctionReply` returns `{request_id, status, result_json?, error_code?, error_message?}`.
- Status codes: `OK | ERROR | TIMEOUT | RETRYABLE`.
- Idempotency: Duplicate `request_id` within a short window returns the original reply.
- Streaming (future): chunked replies via `ChainEvent` segments for long‑running tasks.

---

## 7.6 Monitoring and Graph Integration
- Discovery events create edges: `Service → Function` (advertise) and `Agent → Service` (discover).
- Tool invocations emit `ChainEvent` with micro‑timings: `t_discovery`, `t_queue`, `t_exec`, `t_total`.
- Late joiners reconstruct topology via durable discovery events and recent ChainEvents.

---

## 7.7 Performance Snapshot (Observed)
- Discovery latency: typical < 100 ms for same‑host publisher/subscriber.
- Function call overhead (DDS RPC path, excluding tool execution): < 50 ms.
- End‑to‑end tool use (LLM + RPC + service execution): < 2.7 s for math; weather queries depend on external API latency but remain within demo bounds.

---

## 7.8 Failure Modes and Mitigations
- Lost advertisements → mitigated by periodic re‑advertise; TTL expiration removes stale entries.
- Duplicate/Conflicting ads → resolved by `(priority, advertised_at)` rule.
- Service crash during invocation → agent observes timeout and returns `RETRYABLE` or `ERROR` with ChainEvent diagnostics.
- Schema drift → JSON Schema validation at the service boundary; error returns include schema mismatch details.

---

## 7.9 Security Roadmap (Stage Ahead of M6)
- DDS Security governance/permissions with signed participants.
- Capability signing or mTLS‑style trust for advertisement authenticity.
- Access control lists per partition/domain; requestor identity tagging in `FunctionRequest`.

---

## 7.10 Quantitative Metrics (Registry Workstream)
- Timeline: 2025‑04‑06 → 2025‑08‑20
- Commits: 30 | Files changed: 57
- Additions/Deletions: +6,043 / −1,907
- High‑churn files: `openai_genesis_agent.py`, `enhanced_service_base.py`, `function_discovery.py`, `rpc_service.py`, `rpc_client.py`, `config/datamodel.xml`.

---

## 7.11 Reproduction Guide
1) Start Graph Interface for live topology.
2) Launch a service exposing `@genesis_tool` functions (e.g., CalculatorService) — it auto‑advertises capabilities.
3) Launch an agent (e.g., PersonalAssistant) — it discovers functions and merges them into its tool list.
4) Ask the agent to perform an operation; observe `Agent → Service → Function` path, reply, and ChainEvents in the viewer.

Environment variables (common):
- `GENESIS_DOMAIN` (default 0)
- `GENESIS_GRAPH_BRIDGE_UPDATE_SUPPRESS_MS` (default 500)
- `GENESIS_GRAPH_BRIDGE_REMOVE_SUPPRESS_MS` (default 2000)

---

## 7.12 Image Placeholders
- Architecture: PLACEHOLDER — add `docs/images/m7_architecture.png`.
- Graph Viewer: PLACEHOLDER — add `docs/images/m7_graph_view.png`.

---

## 7.13 Code Samples — Using @genesis_tool

These samples show how to expose local agent methods as tools with automatic schema generation and LLM injection. Agents decorated with `@genesis_tool` require no manual JSON schema work; GENESIS derives parameter and return schemas from type hints and docstrings.

Minimal agent exposing two tools
```python
#!/usr/bin/env python3
import asyncio
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
from genesis_lib.decorators import genesis_tool

class MyOpsAgent(OpenAIGenesisAgent):
    @genesis_tool(description="Add two integers and return the sum")
    async def add(self, a: int, b: int) -> int:
        """Add two numbers.

        Args:
            a: First integer
            b: Second integer
        """
        return a + b

    @genesis_tool(operation_type="TEXT", description="Count occurrences of a letter in text")
    async def count_letter(self, text: str, letter: str) -> int:
        """Count the number of times letter appears in text.

        Args:
            text: Body of text to scan
            letter: Single character to count
        """
        return sum(1 for c in text if c == letter)

if __name__ == "__main__":
    asyncio.run(MyOpsAgent().run())
```

Notes
- The `@genesis_tool` decorator creates OpenAI/Anthropic‑compatible tool schemas from type hints; these are injected into the LLM call automatically by `OpenAIGenesisAgent`.
- The agent’s Genesis RPC service auto‑starts when an asyncio loop is present; `run()` is idempotent.

Service‑side note
- Distributed services typically use `@genesis_function` (not `@genesis_tool`) on methods inside classes derived from `EnhancedServiceBase`. Those are auto‑advertised via `FunctionCapability` and invoked via DDS RPC. Use `@genesis_tool` for agent‑local tools.

---

## 7.14 Scaling Experiment — 2 Interfaces, 12 Agents, 20 Services (4 functions each)

Goal
- Validate distributed registry behavior and monitoring/graph coherence under moderate churn and scale.

Topology under test
- Interfaces: 2
- Agents: 12 (1 primary assistant + 11 specialized or general)
- Services: 20 (each advertises 4 functions) → 80 distributed functions
- Expected node count (approximate): 2 (interfaces) + 12 (agents) + 20 (services) + 80 (functions) = 114 nodes
- Expected discovery events: 80 function capabilities observed by each agent → up to 960 capability observations (before dedup/refresh)

Methodology
- Launch Graph Interface for live visualization and monitoring.
- Start 20 identical service instances exposing four math/text functions each (e.g., add, subtract, multiply, letter_count) using `EnhancedServiceBase` + `@genesis_function`.
- Start 12 agents (mix of general/specialized) that subscribe to `FunctionCapability` and expose a few `@genesis_tool` methods locally.
- Start a second interface to simulate concurrent operator sessions.
- Drive 200 randomized tool calls across the agent pool: 75% routed to distributed services, 25% to local agent tools.
- Capture metrics: discovery completion time per agent, RPC success rate, average end‑to‑end latency (tool selection → reply), graph node/edge counts, CPU/memory snapshot per process class.

Pass criteria / target thresholds
- Discovery completion: < 2 s after last service starts (per agent) for the full 80 functions.
- RPC success rate: ≥ 99% across 200 randomized calls; no dropped replies.
- End‑to‑end latency (excluding external APIs): median < 600 ms; p95 < 1.2 s.
- Graph integrity: node/edge counts match expectations within ±5%; no stale edges after teardown.

Expected observations (deterministic counts)
- Capability fan‑out: 80 `FunctionCapability` ads × 12 agents ≈ 960 observations.
- Graph edges (steady‑state):
  - 20 `Service → Function` edges × 4 each = 80
  - Up to 12 `Agent → Service` edges per agent to frequently used services (depends on routing);
    exact count varies with call patterns and viewer batch/remove suppression.

Reproduction sketch (shell)
```bash
# 1) Graph Interface
examples/GraphInterface/run_graph_interface.sh &

# 2) Start 20 services (example service with four functions)
for i in $(seq 1 20); do
  python examples/MultiAgent/calculator_service.py --instance "$i" &
done

# 3) Start 12 agents (one primary + 11 helpers)
python examples/MultiAgent/personal_assistant.py &
for i in $(seq 1 11); do
  python examples/MultiAgent/generic_agent.py --instance "$i" &
done

# 4) Second interface
examples/GraphInterface/run_graph_interface.sh --port 5081 &

# 5) Drive randomized calls (pseudo)
python tools/drive_random_calls.py --agents 12 --services 20 --calls 200
```

Result capture (to be filled when executed)
- Discovery completion (mean/p95): [TBD] / [TBD]
- RPC success rate: [TBD]
- Median / p95 E2E latency: [TBD] / [TBD]
- Max resident memory (agent/service/interface): [TBD]
- Final graph node/edge counts: [TBD]

---

## 7.15 GraphInterface Example — Demonstration of Distributed Capabilities

Purpose
- Provide a minimal, scriptable demonstration of the distributed registry and live monitoring/graphing capabilities. This example embeds the reusable graph viewer, exposes a simple web UI for agent chat, and bridges DDS monitoring to Socket.IO updates for the browser.

Location
- Path: `examples/GraphInterface/`
- Entrypoint: `examples/GraphInterface/server.py`

What it starts
- `GraphService` subscriber that ingests topology/monitoring events from DDS.
- Reusable Graph Viewer mounted under `/genesis-graph` with static assets.
- `MonitoredInterface` that advertises an interface node and discovers agents, enabling chat/tool interactions from the browser.

HTTP routes
- `GET /` — simple UI shell (left: chat/agent controls; right: graph viewer pane).
- `GET /api/health` — health probe with UTC timestamp JSON.
- Graph viewer assets are served under `/genesis-graph/*`.

Socket.IO events (browser ↔ server)
- `connect` — initializes a single `MonitoredInterface` instance; triggers agent refresh.
- `refresh_agents` — enumerates discovered agents from the interface and emits `agents` list.
- `connect_to_agent {agent_name}` — binds the interface to the chosen agent service and emits `agent_connected` on success.
- `send_message {message}` — sends a chat payload to the connected agent; emits `agent_response` with results, or `error`.

Environment variables
- `GENESIS_DOMAIN` (default 0)
- `GENESIS_GRAPH_BRIDGE_UPDATE_SUPPRESS_MS` (default 500) — coalesce rapid updates for smoother rendering.
- `GENESIS_GRAPH_BRIDGE_REMOVE_SUPPRESS_MS` (default 2000) — delay removal batches to avoid flicker during churn.
- `GENESIS_GRAPH_BRIDGE_BATCH_MS` (default 0) — when > 0, emits `graph_batch` messages instead of individual events.

Run
```bash
# From repo root
examples/GraphInterface/run_graph_interface.sh
# or directly
python examples/GraphInterface/server.py --port 5080
```

Demonstrated capabilities (ties to M7 work)
- Distributed registry: as services start, they publish `FunctionCapability`; the UI discovers agents/services and the viewer draws `Service → Function` and `Agent → Service` edges in real time.
- Tool unification: when connected to an agent, the browser chat triggers LLM tool selection; calls route automatically via DDS RPC to the correct service.
- Monitoring and traceability: each call emits `ChainEvent` and viewer overlays the call path; late joiners reconstruct the graph via durable events.

Scaling notes
- Multiple interface instances can be run (e.g., `--port 5081`) to simulate concurrent operator sessions; the graph still represents the unified DDS domain.
- Bridge suppress/batch settings should be tuned for higher churn (see env vars above).

Image placeholder
- UI screenshot: PLACEHOLDER — add `docs/images/m7_graph_interface_ui.png`.
