# MCP vs. A2A — Protocol Comparison

Two open standards have emerged in 2025 as the foundation for agent interoperability. They are complementary, not competing — each solves a different half of the connectivity problem in multi-agent AI systems.

---

## Origins

| | MCP | A2A |
|---|---|---|
| **Full name** | Model Context Protocol | Agent2Agent Protocol |
| **Created by** | Anthropic | Google |
| **Announced** | November 2024 | April 2025 (Google Cloud Next) |
| **Current version** | — | v1.0.0 (March 12, 2026) |
| **Governance** | Anthropic (open specification) | Agentic AI Foundation (AAIF), Linux Foundation — co-founded by OpenAI, Anthropic, Google, Microsoft, AWS, Block (Dec 2025) |
| **Key merger** | — | IBM's Agent Communication Protocol (ACP) merged into A2A (August 2025) |
| **Launch partners** | Claude, Cursor, Zed, and early MCP server ecosystem | 50+ partners: Microsoft, SAP, Salesforce, Atlassian, ServiceNow, Workday, PayPal, and others |
| **Ecosystem size** | 97M+ monthly SDK downloads, 5,800+ public servers (Feb 2026) | 150+ organizations in production (Apr 2026) |
| **Spec / repo** | https://modelcontextprotocol.io | https://a2a-protocol.org · https://github.com/a2aproject/A2A |

---

## The Problem Each Solves

### MCP — "How does an LLM access tools and data?"

Before MCP, every LLM application had to build its own custom integrations: one connector for GitHub, another for Slack, another for a database, etc. Each was bespoke and non-reusable.

MCP standardizes the interface between an **LLM host** (Claude, GPT, an agent runtime) and **external tools, data sources, and services**. A tool or data source that speaks MCP can be used by any MCP-compatible LLM host without custom glue code.

```
LLM Host (Claude, GPT, agent)
        ↕  MCP
Tool / Data Server (filesystem, GitHub, database, API)
```

### A2A — "How do agents talk to other agents?"

As organizations build multiple agents — each specialized, each potentially built with a different framework or by a different team — they need a way for agents to delegate work to each other without bespoke integrations.

A2A standardizes the interface between **one agent and another agent**, regardless of what framework they were built with or who built them.

```
Agent A (LangChain, internal)
        ↕  A2A
Agent B (CrewAI, external vendor)
```

---

## Core Concepts

### MCP

| Concept | Description |
|---------|-------------|
| **Host** | The LLM application that initiates connections (e.g., Claude Desktop, an agent runtime) |
| **Client** | Component inside the host that manages one MCP server connection |
| **Server** | Lightweight process exposing tools, resources, and prompts |
| **Tools** | Callable functions the LLM can invoke (e.g., `read_file`, `search_web`) |
| **Resources** | Data the LLM can read (e.g., file contents, database records) |
| **Prompts** | Reusable prompt templates the server can provide |
| **Transport** | stdio (local), SSE (legacy HTTP), Streamable HTTP (current standard) |

### A2A

| Concept | Description |
|---------|-------------|
| **Agent Card** | Machine-readable JSON at `/.well-known/agent-card.json` — the "OpenAPI spec for agents"; declares skills, capabilities, auth requirements, and endpoint URL |
| **Skills** | Capabilities the agent exposes (`AgentSkill` objects) — each has `id`, `name`, `description`, `tags`, `examples`, and supported MIME `inputModes`/`outputModes` |
| **Task** | Stateful unit of work with a full lifecycle: SUBMITTED → WORKING → COMPLETED / FAILED / CANCELED / REJECTED, plus interrupted states INPUT_REQUIRED and AUTH_REQUIRED |
| **Message** | Single communication turn (role: user or agent), containing an array of Parts |
| **Part** | Smallest content unit: `text`, `raw` (binary), `url`, or `data` (JSON) |
| **Artifact** | Tangible output produced by a task (document, image, analysis result), also composed of Parts; supports streaming via `append`/`lastChunk` flags |
| **contextId** | Groups multiple related Tasks into a logical conversation thread |
| **Client** | Agent initiating a delegation request |
| **Server** | Agent receiving and executing the delegated task |
| **Transport** | JSON-RPC 2.0 over HTTPS; also gRPC/Protobuf and REST (all three bindings are functionally equivalent) |
| **Async / long-running** | Push notifications: agent POSTs state updates to a client-provided HTTPS webhook URL |

---

## How They Work

### MCP Flow

1. Host (LLM app) connects to one or more MCP servers at startup
2. Host discovers available tools/resources from each server
3. LLM receives tool schemas; decides which to call
4. Host executes tool call via MCP client → server
5. Result returned to LLM as tool output

```
Startup:  Host ──connect──► Server  (discover tools)
Runtime:  LLM decides to call tool
          Host ──tool call──► Server ──result──► LLM
```

### A2A Flow

1. Caller fetches Agent Card from `/.well-known/agent-card.json` (one-time discovery)
2. Caller sends a task message (`a2a_sendMessage` or `a2a_sendStreamingMessage`) to the agent's endpoint
3. Agent processes the task; may transition through SUBMITTED → WORKING → INPUT_REQUIRED (needs clarification) → WORKING → COMPLETED
4. For streaming: agent sends Server-Sent Events (`TaskStatusUpdateEvent`, `TaskArtifactUpdateEvent`)
5. For long-running tasks: agent POSTs updates to client's webhook URL (`PushNotificationConfig`)
6. Multi-turn: if state is INPUT_REQUIRED, client sends a new message in the same `contextId`
7. Result returned as structured Task with Artifacts

```
Discovery:  Caller ──GET /.well-known/agent-card.json──► Agent
Task:       Caller ──a2a_sendMessage──► Agent
Streaming:  Agent ──SSE events (status + artifacts)──► Caller
Async:      Agent ──POST webhook──► Caller (for long-running tasks)
Multi-turn: Caller ──new message (same contextId)──► Agent  (on INPUT_REQUIRED)
```

---

## Key Differences

| Dimension | MCP | A2A |
|-----------|-----|-----|
| **Who calls who** | LLM/host calls a tool server | Agent calls another agent |
| **What is exposed** | Tools, Resources (data), Prompts | Agent Skills (higher-level capabilities) |
| **Caller** | LLM host / agent runtime | Another agent (or orchestrator) |
| **Callee** | Tool/data server (usually stateless) | Full agent (stateful, may use LLM and MCP internally) |
| **Execution model** | Synchronous (request → immediate result) | Asynchronous task state machine; poll, stream, or webhook |
| **Discovery** | Configured endpoint (URL known in advance) | Dynamic via `/.well-known/agent-card.json` |
| **Granularity** | Fine-grained (individual tool functions) | Coarse-grained (agent-level skills) |
| **Auth** | Spec-agnostic (server-dependent) | OAuth2 / OIDC / mTLS / Bearer built into spec |
| **State** | Stateless per call | Stateful task with 8 lifecycle states including INPUT_REQUIRED and AUTH_REQUIRED |
| **Multi-turn** | Not built-in (handled at host level) | Native via `contextId` and `referenceTaskIds` |
| **Long-running tasks** | Not designed for it | Push notification webhooks (agent POSTs to client URL) |
| **Wire format** | JSON-RPC 2.0 | JSON-RPC 2.0 (also gRPC/Protobuf and REST) |
| **Streaming** | Token-by-token tool results | SSE `TaskStatusUpdateEvent` + `TaskArtifactUpdateEvent` |
| **Transport** | stdio, SSE, Streamable HTTP | HTTPS + SSE; gRPC; REST |
| **Extensions** | Not applicable | Governed extension system (data, profile, method, state-machine types) |
| **Ecosystem** | 97M+ monthly SDK downloads, 5,800+ servers | 150+ orgs in production; 13 frameworks with native support |

---

## Analogy

Think of building a software system with microservices:

- **MCP** is like a **function call or API endpoint** — you call a specific operation and get a result. The callee is a service, not an agent.
- **A2A** is like **delegating a project to a contractor** — you hand off a goal, the contractor figures out how to do it (possibly using their own tools), and reports back when done.

Or in human terms:
- **MCP**: "Look up this file for me." (tool use)
- **A2A**: "Handle the customer support case for this user." (agent delegation)

---

## Use Together, Not Instead

In a real multi-agent system you need both:

```
User
  ↓
Orchestrator Agent
  ├─── MCP ──► File system tool
  ├─── MCP ──► Web search tool
  ├─── MCP ──► Database tool
  ├─── A2A ──► Specialist Agent A (billing, uses its own MCP tools internally)
  └─── A2A ──► Specialist Agent B (compliance, uses its own MCP tools internally)
```

The orchestrator uses MCP to access raw tools and data directly. It uses A2A to delegate entire goals to specialized agents, which may themselves use MCP internally. The caller does not need to know how the specialist agent works — just what it can do (from the Agent Card).

---

## Ecosystem Support (as of 2025–2026)

### MCP Adoption
- Native support in: Claude (Anthropic), Cursor, VS Code (Copilot), Zed, Windsurf
- Server ecosystem: 1000+ community MCP servers (GitHub, Slack, Postgres, filesystem, web search, etc.)
- Framework support: LangChain, LlamaIndex, AutoGen, Semantic Kernel, NeMo Agent Toolkit, and most major agent frameworks
- GENESIS: **partial support** — any `GenesisAgent` can expose itself as an MCP server via `agent.enable_mcp(port=8000)`; MCP client consumption of external servers is not yet implemented in production code

### A2A Adoption
- Created by Google (Apr 2025); IBM's competing ACP standard **merged into A2A** in August 2025, consolidating the field
- Now governed by the **Agentic AI Foundation (AAIF)**, Linux Foundation, co-founded by OpenAI, Anthropic, Google, Microsoft, AWS, Block (Dec 2025)
- v1.0.0 released March 2026; 150+ organizations in production
- Native cloud platform support: Google Vertex AI, Microsoft Azure AI Foundry, AWS Bedrock AgentCore
- 13 frameworks with native support: Google ADK, LangGraph, CrewAI, Semantic Kernel, BeeAI, Agno, AG2, LiteLLM, Pydantic AI, Strands, and more
- Language SDKs: Python (`pip install a2a-sdk`), JavaScript, Go, Java, .NET
- GENESIS: **not supported** — inter-agent communication uses DDS RPC instead

---

## Relevance to GENESIS and NAT

| | GENESIS | NeMo Agent Toolkit (NAT) |
|---|---|---|
| **MCP client** | Not implemented — `MCPServiceBase` (planned bridge from MCP → DDS) exists in examples but the class is not yet in `genesis_lib` | `mcp_client` function group; auto-discovers and maps tools |
| **MCP server** | **Yes** — `agent.enable_mcp(port=8000)` exposes any `GenesisAgent` as a FastMCP server on streamable-HTTP; also `genesis_mcp/test_runner_server.py` for dev tooling | `nat mcp serve` / `nat fastmcp server run` |
| **A2A client** | Not supported | `a2a_client` function group; fetches Agent Card, maps skills to functions |
| **A2A server** | Not supported | `nat a2a serve`; auto-generates Agent Card from workflow |

GENESIS agents are reachable from the MCP ecosystem (Claude Code, Cursor, NAT, etc.) via `enable_mcp()`. The missing piece is the reverse direction: a GENESIS agent consuming an external MCP server's tools and re-advertising them over DDS. A2A is not on the roadmap; GENESIS handles inter-agent communication at the DDS layer, which provides stronger real-time guarantees but is not interoperable with the HTTP-based A2A ecosystem.

---

## Known A2A Limitations

- **No agent-to-client callbacks** — agents cannot invoke methods back on the caller; client-side method exposure is not in the spec yet
- **No dynamic skill querying** — `QuerySkill()` for runtime capability interrogation is planned but not yet implemented; skills are static in the Agent Card
- **Knowledge alignment is out of scope** — A2A solves *communication*, not *semantic consistency*. Two fully compliant agents may still disagree on what "approved vendor" or "revenue" means. A separate governed semantic layer is required for true interoperability at the data level.
- **Mid-task modality switching** — adding a new I/O modality (e.g., audio) mid-conversation is still experimental
- **Authorization formalization** — detailed authorization schemes within the Agent Card spec are still in progress

---

## Summary

| Question | Answer |
|----------|--------|
| What is MCP? | Standard for LLMs/agents to access external tools and data (Anthropic, Nov 2024) |
| What is A2A? | Standard for agents to delegate tasks to other agents (Google Apr 2025 → AAIF/Linux Foundation) |
| Are they competing? | No — they solve different layers of the same problem |
| Do I need both? | Yes, in most real multi-agent systems |
| Who created MCP? | Anthropic |
| Who created A2A? | Google; IBM's ACP merged in Aug 2025; now governed by Agentic AI Foundation (AAIF) |
| What merged into A2A? | IBM's Agent Communication Protocol (ACP) from the BeeAI project (Aug 2025) |
| Current A2A version? | v1.0.0 (March 2026) |
| Which frameworks support MCP? | Nearly all major frameworks |
| Which frameworks support A2A? | 13 frameworks natively; all major cloud platforms (Google, Azure, AWS) |
