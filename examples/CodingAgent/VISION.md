# CodingGenesisAgent: Technical Vision

**Distributed Coding Agents Powered by Claude Code & OpenAI Codex on Subscription Pricing**

---

## Problem Statement

Modern coding harnesses — Claude Code and OpenAI Codex — represent a step-function improvement over raw LLM API calls. They include sophisticated tooling: file editing, shell execution, search, multi-turn context, and agentic loops that dramatically outperform the model alone. However, they operate as isolated interactive terminal applications with no programmatic integration path into distributed systems.

Genesis enables distributed agent collaboration via DDS, but its existing `OpenAIGenesisAgent` calls the raw OpenAI API directly. This means:

1. **No access to harness tooling** — file editing, code search, shell execution, etc.
2. **API billing** — raw API calls cost 5-10x more than subscription pricing
3. **No distributed coding** — coding tasks can't be delegated across Genesis agent networks

We need Genesis agents that:
- Leverage the full Claude Code / Codex harness (tools, system prompts, agentic loops)
- Run on subscription pricing (not API billing)
- Integrate with Genesis discovery, monitoring, and agent-as-tool patterns
- Require zero changes to the genesis_lib core library

---

## Solution Architecture

### Thin Subprocess Bridge

Both Claude Code and Codex offer non-interactive pipe modes that stream structured JSON to stdout. We spawn them as subprocesses from a `MonitoredAgent` subclass, parse the event streams, and translate results back into Genesis RPC responses.

```
 Genesis Network (DDS)
        |
        v
 +-----------------------+
 | CodingGenesisAgent    |    extends MonitoredAgent
 |  (Python)             |    — no genesis_lib changes needed
 |                       |
 |  _process_request()   |
 |       |               |
 |       v               |
 |  CodingBackend.run()  |    ABC with two implementations
 |       |               |
 +-------|---------------+
         |
    asyncio.subprocess
         |
    +----v----+     +----v----+
    | claude  |     | codex   |
    |  -p     |     |  exec   |
    | (stdin/ |     | (stdin/ |
    |  stdout)|     |  stdout)|
    +---------+     +---------+
    Subscription    Subscription
    pricing         pricing
```

### Why This Works Without Library Changes

`MonitoredAgent` provides everything we need:

| Feature | MonitoredAgent API |
|---|---|
| DDS participant + topics | `self.app.participant`, `self.app.agent_id` |
| Request handling with state management | `process_request()` → READY/BUSY/READY |
| Abstract override point | `_process_request(request)` — we implement this |
| Graph monitoring | `self.graph.publish_node()`, `self.graph.publish_edge()` |
| Agent capability advertising | `self.set_agent_capabilities()` |
| Agent-to-agent communication | `enable_agent_communication=True` in constructor |
| Agent discovery (others find us) | Automatic via `publish_agent_capability()` |
| Lifecycle management | `close()` with OFFLINE state publishing |

The `CodingGenesisAgent` is a self-contained example that imports from `genesis_lib` like any other agent — `WeatherAgent`, `PersonalAssistant`, etc. No PRs required.

---

## Confirmed Auth: Subscription Pricing

### The Discovery

Both CLI tools prioritize API keys over subscription auth. When an API key environment variable is present, they bill to the API. The fix is to strip those env vars before launching the subprocess.

### Claude Code

**Verified** — zero API dashboard movement confirmed.

```bash
# This costs $$$:
ANTHROPIC_API_KEY=sk-... claude -p "hello"

# This uses subscription (free with Pro/Max):
env -u ANTHROPIC_API_KEY claude -p "hello"
```

**Mechanism**: `claude login` caches OAuth credentials. When `ANTHROPIC_API_KEY` is absent, Claude Code falls back to the cached OAuth session, which routes through subscription infrastructure.

**Reference**: GitHub issue [openai/codex#3040](https://github.com/anthropics/claude-code/issues/3040) — confirmed that `-p` mode wasn't using subscription when `ANTHROPIC_API_KEY` was present.

### OpenAI Codex

**Functional** — returns clean JSONL; billing dashboard check pending.

```bash
# This costs $$$:
OPENAI_API_KEY=sk-... codex exec "hello"

# This uses subscription:
env -u OPENAI_API_KEY -u CODEX_API_KEY codex exec -m gpt-5.3-codex "hello"
```

**Mechanism**: `codex login` caches ChatGPT OAuth credentials. Same pattern as Claude Code.

**Model note**: Must specify `-m gpt-5.3-codex` explicitly. The default `gpt-5.3-codex-spark` is restricted to Pro interactive mode and errors with "not supported when using Codex with a ChatGPT account."

### Direct API (Bonus — No Harness)

**Verified** — zero API dashboard movement confirmed.

For lightweight tasks that don't need harness tooling, Anthropic's API accepts setup tokens:

```bash
curl https://api.anthropic.com/v1/messages \
  -H "Authorization: Bearer $SETUP_TOKEN" \
  -H "anthropic-beta: oauth-2025-04-20" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-haiku-4-5-20251001","max_tokens":100,"messages":[...]}'
```

Setup tokens are generated via `claude setup-token` (valid 1 year, `sk-ant-oat01-` prefix). The `anthropic-beta: oauth-2025-04-20` header is **required** — without it, Bearer auth returns "OAuth authentication is currently not supported."

---

## Auth Strategy: Subscription-First with API Key Fallback

Most users will have both `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` in their environment (required by other Genesis agents like `OpenAIGenesisAgent`). The coding agent must handle this gracefully.

### Startup Auth Flow

```
Agent.__init__(backend="claude")
    │
    ├── 1. Check: is the CLI installed?
    │       No  → FATAL: "Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code"
    │       Yes ↓
    │
    ├── 2. Probe subscription auth:
    │       Run: env -u ANTHROPIC_API_KEY claude -p "ping" --output-format stream-json
    │       Parse stdout for a valid "result" event
    │       │
    │       ├── Success → mode = SUBSCRIPTION
    │       │   Log: "Using Claude Code on SUBSCRIPTION pricing (no API charges)"
    │       │
    │       └── Failure (exit code != 0, or auth error in stream) →
    │           │
    │           ├── 3. Check: is ANTHROPIC_API_KEY set?
    │           │       Yes → mode = API_KEY
    │           │       Print WARNING (colored):
    │           │       ┌──────────────────────────────────────────────────────────────┐
    │           │       │  ⚠  WARNING: No subscription auth found for Claude Code.    │
    │           │       │  Falling back to ANTHROPIC_API_KEY (API billing).            │
    │           │       │  This may cost 5-10x more than subscription pricing.         │
    │           │       │                                                              │
    │           │       │  To set up subscription auth:                                │
    │           │       │    1. Run: claude login                                      │
    │           │       │    2. Complete the OAuth flow in your browser                 │
    │           │       │    3. Restart this agent                                     │
    │           │       │                                                              │
    │           │       │  For long-lived/headless environments:                       │
    │           │       │    1. Run: claude setup-token                                │
    │           │       │    2. Export: CLAUDE_CODE_OAUTH_TOKEN=<token>                 │
    │           │       │    3. Restart this agent                                     │
    │           │       └──────────────────────────────────────────────────────────────┘
    │           │
    │           └── No API key either → FATAL:
    │               "No auth available. Run 'claude login' or set ANTHROPIC_API_KEY."
    │
    └── Store self._auth_mode = SUBSCRIPTION | API_KEY
```

Same flow for Codex with `codex login` / `OPENAI_API_KEY` / `CODEX_API_KEY`.

### build_env() Based on Auth Mode

```python
def build_env(self):
    env = os.environ.copy()
    if self._auth_mode == "subscription":
        # Strip API key so CLI uses cached OAuth
        env.pop("ANTHROPIC_API_KEY", None)
    # else: keep API key in env for API-billing fallback
    return env
```

### Why Probe at Startup

Running a one-shot probe (`"ping"`) during `__init__` takes ~2-3 seconds but gives us:
1. **Early failure** — don't wait until the first real request to discover auth is broken
2. **Clear messaging** — the user sees the warning immediately, not buried in task output
3. **Correct mode selection** — we know before any real work whether we're on subscription

### Setup Instructions (Printed on Fallback)

**Claude Code:**
```
claude login                          # Interactive OAuth (opens browser)
claude setup-token                    # Headless: generates 1-year Bearer token
export CLAUDE_CODE_OAUTH_TOKEN=<tok>  # For headless environments
```

**Codex:**
```
codex login                           # Interactive OAuth (opens browser)
# No headless token equivalent known yet — codex login caches credentials
```

---

## Event Stream Formats

### Claude Code (`--output-format stream-json`)

One JSON object per stdout line. Key types:

```
system/init       → session started, contains session_id
assistant/text    → streaming text from the model
assistant/tool_use→ harness using a tool (Write, Edit, Bash, Read, Glob, Grep, etc.)
tool/result       → tool execution result
result/success    → final answer, task complete
```

Claude Code's harness includes ~15 built-in tools: file read/write/edit, bash execution, glob/grep search, web fetch, notebook editing, and more. All tool invocations stream as events, giving full visibility into what the harness is doing.

### Codex (`--json`)

One JSON object per stdout line. Errors go to stderr (safe to ignore). Verified format:

```json
{"type":"thread.started","thread_id":"019c7199-..."}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"..."}}
{"type":"turn.completed","usage":{"input_tokens":11161,"cached_input_tokens":6912,"output_tokens":24}}
```

For tool-using tasks:

```json
{"type":"item.completed","item":{"id":"item_1","type":"tool_call","name":"shell","arguments":"{...}"}}
{"type":"item.completed","item":{"id":"item_2","type":"tool_output","output":"..."}}
```

**Note**: The top-level field is `type`, not `event`. Item data is nested under `item`. The `turn.completed` event includes token usage stats.

### Normalized Event Model

Both streams are normalized to a common type before reaching Genesis:

```python
@dataclass
class CodingEvent:
    kind: str          # "init" | "text" | "tool_start" | "tool_result" | "done" | "error"
    session_id: str    # from init event; empty otherwise
    text: str          # content for "text" and "done" events
    tool_name: str     # for "tool_start" / "tool_result"
    tool_input: dict   # arguments passed to the tool
    tool_output: str   # tool execution output
    raw: dict          # original JSON for debugging / forwarding
```

This normalization is the API boundary. Everything above it (the Genesis agent) is backend-agnostic.

---

## Class Design

### Backend Protocol

```python
class CodingBackend(ABC):
    """Subprocess bridge to a coding harness CLI."""

    @abstractmethod
    def build_command(self, prompt: str, session_id: str | None, cwd: str | None) -> list[str]:
        """Construct the subprocess argv."""

    @abstractmethod
    def build_env(self) -> dict[str, str]:
        """Return env dict with billing env vars stripped."""

    @abstractmethod
    def parse_line(self, line: str) -> CodingEvent | None:
        """Parse one stdout line into a normalized event (or None to skip)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier for monitoring: 'claude' or 'codex'."""
```

### ClaudeBackend

```python
class ClaudeBackend(CodingBackend):
    name = "claude"

    def build_command(self, prompt, session_id, cwd):
        cmd = ["claude", "-p", prompt, "--output-format", "stream-json"]
        if session_id:
            cmd += ["--session-id", session_id]
        if cwd:
            cmd += ["--cwd", cwd]
        return cmd

    def build_env(self):
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        return env

    def parse_line(self, line):
        obj = json.loads(line)
        t, s = obj.get("type"), obj.get("subtype")
        if t == "system" and s == "init":
            return CodingEvent("init", session_id=obj.get("session_id", ""))
        if t == "assistant" and s == "text":
            return CodingEvent("text", text=obj.get("text", ""))
        if t == "assistant" and s == "tool_use":
            tool = obj.get("tool", {})
            return CodingEvent("tool_start", tool_name=tool.get("name", ""),
                               tool_input=tool.get("input", {}))
        if t == "tool" and s == "result":
            return CodingEvent("tool_result", tool_output=obj.get("content", ""))
        if t == "result":
            return CodingEvent("done", text=obj.get("result", ""))
        return None
```

### CodexBackend

```python
class CodexBackend(CodingBackend):
    name = "codex"

    def __init__(self, model: str = "gpt-5.3-codex"):
        self._model = model

    def build_command(self, prompt, session_id, cwd):
        if session_id:
            return ["codex", "exec", "resume", session_id, "-m", self._model, "--json"]
        return ["codex", "exec", "-m", self._model, "--json", prompt]

    def build_env(self):
        env = os.environ.copy()
        env.pop("OPENAI_API_KEY", None)
        env.pop("CODEX_API_KEY", None)
        return env

    def parse_line(self, line):
        obj = json.loads(line)
        t = obj.get("type", "")
        item = obj.get("item", {})
        item_type = item.get("type", "")

        if t == "thread.started":
            return CodingEvent("init", session_id=obj.get("thread_id", ""))
        if t == "item.completed" and item_type == "agent_message":
            return CodingEvent("text", text=item.get("text", ""))
        if t == "item.completed" and item_type == "tool_call":
            return CodingEvent("tool_start", tool_name=item.get("name", ""),
                               tool_input=json.loads(item.get("arguments", "{}")))
        if t == "item.completed" and item_type == "tool_output":
            return CodingEvent("tool_result", tool_output=item.get("output", ""))
        if t == "turn.completed":
            return CodingEvent("done", raw=obj.get("usage", {}))
        return None
```

### CodingGenesisAgent

```python
class CodingGenesisAgent(MonitoredAgent):
    """
    Genesis agent that delegates work to Claude Code or Codex.
    Uses subscription pricing. No genesis_lib modifications required.
    """

    def __init__(self, backend="claude", agent_name="CodingAgent",
                 base_service_name="CodingAgent", working_dir=None,
                 timeout=300.0, domain_id=0,
                 enable_agent_communication=True, **kwargs):

        description = f"Coding agent powered by {backend} harness (subscription)"
        super().__init__(
            agent_name=agent_name,
            base_service_name=base_service_name,
            agent_type="SPECIALIZED_AGENT",
            description=description,
            domain_id=domain_id,
            enable_agent_communication=enable_agent_communication,
            **kwargs,
        )

        self._backend = ClaudeBackend() if backend == "claude" else CodexBackend()
        self._working_dir = working_dir
        self._timeout = timeout
        self._sessions = {}  # conversation_id -> session_id

        # Probe auth at startup: subscription-first, API key fallback
        self._auth_mode = self._probe_auth()
        self._backend.set_auth_mode(self._auth_mode)

        # Advertise coding capabilities for agent-as-tool discovery
        self.set_agent_capabilities(
            supported_tasks=["coding", "debugging", "code-review", "refactoring"],
            additional_capabilities={
                "specializations": [f"{backend}-code", "software-engineering"],
                "capabilities": ["code-generation", "file-editing", "shell-execution"],
                "classification_tags": ["code", "programming", "software", "debug", "refactor"],
                "model_info": {"backend": backend, "harness": True, "subscription": True},
            },
        )

    async def _process_request(self, request):
        """Execute a coding task via subprocess."""
        message = request.get("message", "")
        conv_id = request.get("conversation_id")
        session_id = self._sessions.get(conv_id) if conv_id else None

        cmd = self._backend.build_command(message, session_id, self._working_dir)
        env = self._backend.build_env()

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=self._working_dir,
        )

        events = []
        result_text = ""
        new_session_id = session_id

        try:
            async with asyncio.timeout(self._timeout):
                async for raw_line in proc.stdout:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        event = self._backend.parse_line(line)
                    except (json.JSONDecodeError, KeyError):
                        continue
                    if not event:
                        continue

                    events.append(event)

                    if event.kind == "init" and event.session_id:
                        new_session_id = event.session_id
                    elif event.kind == "text":
                        result_text += event.text
                    elif event.kind == "tool_start":
                        self.graph.publish_edge(
                            source_id=self.app.agent_id,
                            target_id=f"{self._backend.name}:{event.tool_name}",
                            edge_type=EDGE_TYPE["SERVICE_TO_FUNCTION"],
                            attrs={"tool": event.tool_name, "backend": self._backend.name},
                        )
                    elif event.kind == "done" and event.text:
                        result_text = event.text
        finally:
            if proc.returncode is None:
                proc.terminate()
                await proc.wait()

        if conv_id and new_session_id:
            self._sessions[conv_id] = new_session_id

        return {
            "message": result_text,
            "status": 0,
            "session_id": new_session_id,
            "backend": self._backend.name,
            "tool_calls": sum(1 for e in events if e.kind == "tool_start"),
        }
```

---

## File Layout

```
examples/CodingAgent/
    VISION.md                  # This document
    README.md                  # Quick-start usage guide
    coding_genesis_agent.py    # CodingGenesisAgent class
    backends/
        __init__.py
        events.py              # CodingEvent dataclass
        base.py                # CodingBackend ABC
        claude_backend.py      # Claude Code implementation
        codex_backend.py       # Codex implementation
    run_claude_agent.sh        # Launch script (Claude backend)
    run_codex_agent.sh         # Launch script (Codex backend)
    test_coding_agent.py       # Integration test
```

No files in `genesis_lib/` are created or modified.

---

## Integration with Existing Genesis Patterns

### Agent-as-Tool Discovery

When an `OpenAIGenesisAgent` (like `PersonalAssistant`) is running alongside a `CodingGenesisAgent`, the discovery flow is:

```
1. CodingGenesisAgent starts
2. publish_agent_capability() advertises:
   - specializations: ["claude-code", "software-engineering"]
   - capabilities: ["code-generation", "file-editing", "shell-execution"]
   - classification_tags: ["code", "programming", "software", ...]
3. PersonalAssistant's AgentCapabilityListener receives announcement
4. PersonalAssistant's _convert_agents_to_tools() generates tool schema:
   {
     "type": "function",
     "function": {
       "name": "get_claude_code_info",  # or "use_codingagent_service"
       "description": "Specialized agent for software-engineering",
       "parameters": {
         "type": "object",
         "properties": {
           "message": {"type": "string", "description": "Natural language query"}
         }
       }
     }
   }
5. User asks PersonalAssistant: "Refactor the auth module to use dependency injection"
6. LLM selects the coding agent tool
7. PersonalAssistant sends agent-to-agent request via DDS
8. CodingGenesisAgent spawns `claude -p "Refactor the auth module..."` subprocess
9. Claude Code does the work (reads files, edits code, runs tests)
10. Result returns through DDS to PersonalAssistant
11. PersonalAssistant synthesizes response for user
```

### Graph Monitoring

The coding agent publishes to the same DDS monitoring topics as any other agent:

- **Node events**: DISCOVERING → READY → BUSY → READY (or DEGRADED on error) → OFFLINE
- **Edge events**: `AGENT → backend:tool_name` for each tool the harness invokes
- All events visible in `GraphInterface` or any DDS monitoring subscriber

### Multi-Turn Sessions

Both backends support session resume:
- **Claude Code**: `--session-id <id>` on subsequent calls
- **Codex**: `codex exec resume <thread_id>`

The agent stores `conversation_id → session_id` mappings, so repeated requests within the same Genesis conversation maintain harness context (files read, edits made, etc.).

---

## Scenarios

### Scenario 1: Single Coding Agent

```
User → Interface → CodingGenesisAgent → claude -p → result
```

Simple delegation. The interface sends a coding request, the agent runs it through Claude Code, returns the result.

### Scenario 2: Orchestrator + Coding Specialist

```
User → Interface → PersonalAssistant ──agent-as-tool──→ CodingGenesisAgent → codex exec
                        │
                        └── Calculator Service → math functions
```

The PersonalAssistant handles general queries, delegates coding tasks to the CodingGenesisAgent, and calls Calculator for math. All discovered automatically via DDS.

### Scenario 3: Dual-Backend Coding

```
User → Interface → Orchestrator ──→ ClaudeCoder (Claude Code backend)
                                └──→ CodexCoder  (Codex backend)
```

Two coding agents with different backends. The orchestrator's LLM chooses which to delegate to based on the task. Both are discovered independently with different specialization tags.

### Scenario 4: Coding Agent + Function Services

```
CodingGenesisAgent → claude -p "analyze data in /tmp/data.csv"
                          │
    Claude Code internally uses Bash, Read, Write tools
    to process the file and return analysis
```

The harness's built-in tools handle file operations. The Genesis agent doesn't need to provide them — they come free with the harness.

---

## Risk Analysis

### What Could Require genesis_lib Changes

| Risk | Likelihood | Mitigation |
|---|---|---|
| `_process_request` needs async (currently sync signature in MonitoredAgent) | Medium | May need `async def _process_request` — check if `process_request` already awaits it |
| Streaming results (progressive updates during long tasks) | Low | Not needed for v1; can publish intermediate events to monitoring topics |
| Session state persistence across agent restarts | Low | Store to disk; pure example-level code |
| Timeout handling in `process_request` wrapper | Low | We handle timeouts in `_run_subprocess`; outer wrapper just sees the result |

**Key check needed**: Verify that `MonitoredAgent.process_request()` calls `await self._process_request(request)`. If so, our async implementation works directly. If it calls it synchronously, we'd need to wrap with `asyncio.run()` or propose a one-line library change.

From the code at `monitored_agent.py:244`:
```python
result = await self._process_request(request)
```

**Confirmed**: `_process_request` is awaited. Our async subprocess code works directly. No genesis_lib changes needed.

---

## Implementation Phases

### Phase 1: Core Agent (Claude Code backend)
- `CodingEvent` dataclass
- `CodingBackend` ABC + `ClaudeBackend`
- `CodingGenesisAgent` with subprocess management
- Basic integration test with `claude -p`
- Shell launch script

### Phase 2: Codex Backend
- `CodexBackend` implementation
- Verify subscription auth (billing dashboard check)
- Codex-specific launch script
- Event parser tests

### Phase 3: Multi-Agent Integration
- Test agent-as-tool discovery with `PersonalAssistant`
- Multi-turn session resume
- Graph monitoring visualization
- Example demo scripts

### Phase 4: Hardening
- Timeout handling and graceful subprocess termination
- Error propagation and retry logic
- Session cleanup on agent shutdown
- Comprehensive test suite

---

## Prerequisites

### Required
- Python 3.10+
- RTI Connext DDS 7.3.0+ (for genesis_lib)
- `claude` CLI installed and logged in (`claude login`)
- OR `codex` CLI installed and logged in (`codex login`)

### Environment
```bash
source venv/bin/activate && source .env

# Verify Claude Code subscription auth works:
env -u ANTHROPIC_API_KEY claude -p "echo test" --output-format stream-json

# Verify Codex subscription auth works:
env -u OPENAI_API_KEY -u CODEX_API_KEY codex exec -m gpt-5.3-codex --json "echo test"
```

**Critical**: `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` must NOT be in the subprocess environment. The agent's `build_env()` method handles this automatically.
