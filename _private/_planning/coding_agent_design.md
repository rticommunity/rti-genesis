# CodingGenesisAgent — Unified Design Document

## Overview

A Genesis agent that delegates work to **Claude Code** or **OpenAI Codex** as subprocess backends, running on **subscription pricing** (not API billing). The agent extends `MonitoredAgent`, integrates with DDS discovery, and presents coding capabilities as genesis tools.

---

## 1. Confirmed Auth Solutions

### Claude Code (`claude -p`)

| Item | Value |
|------|-------|
| Command | `claude -p "prompt" --output-format stream-json` |
| Subscription auth | Cached from `claude login` |
| Env var that MUST be absent | `ANTHROPIC_API_KEY` |
| How to launch | `env -u ANTHROPIC_API_KEY claude -p ...` |
| Stream format | One JSON object per line |
| Session resume | `--session-id <id>` or `--resume` |
| Working dir | `--cwd <path>` |
| Verified | Yes — dashboard confirmed zero API billing |

### OpenAI Codex (`codex exec`)

| Item | Value |
|------|-------|
| Command | `codex exec -m gpt-5.3-codex "prompt" --json` |
| Subscription auth | Cached from `codex login` |
| Env var that MUST be absent | `OPENAI_API_KEY` / `CODEX_API_KEY` |
| How to launch | `env -u OPENAI_API_KEY -u CODEX_API_KEY codex exec -m gpt-5.3-codex ...` |
| Stream format | JSONL (thread/turn/item events on stdout; errors on stderr) |
| Session resume | `codex exec resume --last` or `resume <SESSION_ID>` |
| Working dir | Runs in CWD of the subprocess |
| Model note | Must specify `-m gpt-5.3-codex` explicitly; default `gpt-5.3-codex-spark` is Pro-interactive-only |
| Verified | Yes — exec returns clean JSONL; **billing dashboard check pending** |

### Direct API (Bonus — no harness)

| Item | Value |
|------|-------|
| Endpoint | `https://api.anthropic.com/v1/messages` |
| Auth header | `Authorization: Bearer <setup-token>` |
| Required header | `anthropic-beta: oauth-2025-04-20` |
| Setup token | Generated via `claude setup-token` (valid 1 year) |
| Verified | Yes — dashboard confirmed zero API billing |

---

## 2. Event Stream Formats

### Claude Code Stream JSON

Each line is a complete JSON object. Key event types:

```json
{"type": "system", "subtype": "init", "session_id": "abc-123", ...}
{"type": "assistant", "subtype": "text", "text": "I'll help you..."}
{"type": "assistant", "subtype": "tool_use", "tool": {"name": "Write", ...}}
{"type": "tool", "subtype": "result", "tool_use_id": "...", "content": "..."}
{"type": "result", "subtype": "success", "result": "Final answer text", ...}
```

**Key events for Genesis integration:**
- `type=system, subtype=init` → session started, extract `session_id`
- `type=assistant, subtype=text` → streaming text output
- `type=assistant, subtype=tool_use` → harness is using a tool (file edit, bash, etc.)
- `type=tool, subtype=result` → tool result
- `type=result` → final answer, task complete

### Codex JSONL Events (verified from actual output)

Each line is a JSON object with a `type` field. Errors go to **stderr** (safe to ignore).
Note: the field is `type`, NOT `event` — corrected from initial docs.

```json
{"type":"thread.started","thread_id":"019c7199-a895-74f2-a004-3b2efce37bc3"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"GENESIS_CODEX_TEST_OK"}}
{"type":"turn.completed","usage":{"input_tokens":11161,"cached_input_tokens":6912,"output_tokens":24}}
```

For tool-using tasks, additional events appear:

```json
{"type":"item.completed","item":{"id":"item_1","type":"tool_call","name":"shell","arguments":"{...}"}}
{"type":"item.completed","item":{"id":"item_2","type":"tool_output","output":"..."}}
```

**Key events for Genesis integration:**
- `type=thread.started` → session started, extract `thread_id`
- `type=item.completed` where `item.type=agent_message` → text output
- `type=item.completed` where `item.type=tool_call` → harness tool usage
- `type=item.completed` where `item.type=tool_output` → tool result
- `type=turn.completed` → task complete, includes `usage` stats

---

## 3. Unified Abstraction Layer

### Event Normalization

Both streams are normalized to a common `CodingEvent` type:

```python
@dataclass
class CodingEvent:
    kind: str          # "init" | "text" | "tool_start" | "tool_result" | "done" | "error"
    session_id: str    # session/thread ID
    text: str = ""     # text content (for "text" and "done")
    tool_name: str = ""  # tool name (for "tool_start" / "tool_result")
    tool_input: dict = field(default_factory=dict)
    tool_output: str = ""
    raw: dict = field(default_factory=dict)  # original event for debugging
```

### Backend Protocol

```python
class CodingBackend(ABC):
    """Abstract interface for a coding agent subprocess."""

    @abstractmethod
    def build_command(self, prompt: str, session_id: str | None, cwd: str | None) -> list[str]:
        """Return the subprocess argv."""

    @abstractmethod
    def build_env(self) -> dict[str, str]:
        """Return env dict with billing env vars removed."""

    @abstractmethod
    def parse_line(self, line: str) -> CodingEvent | None:
        """Parse one line of stdout into a CodingEvent (or None to skip)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier: 'claude' or 'codex'."""
```

### Concrete Backends

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
            return CodingEvent(kind="init", session_id=obj.get("session_id", ""))
        if t == "assistant" and s == "text":
            return CodingEvent(kind="text", session_id="", text=obj.get("text", ""))
        if t == "assistant" and s == "tool_use":
            tool = obj.get("tool", {})
            return CodingEvent(kind="tool_start", session_id="",
                             tool_name=tool.get("name", ""), tool_input=tool.get("input", {}))
        if t == "tool" and s == "result":
            return CodingEvent(kind="tool_result", session_id="",
                             tool_output=obj.get("content", ""))
        if t == "result":
            return CodingEvent(kind="done", session_id="", text=obj.get("result", ""))
        return None


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
            return CodingEvent(kind="init", session_id=obj.get("thread_id", ""))
        if t == "item.completed" and item_type == "agent_message":
            return CodingEvent(kind="text", session_id="", text=item.get("text", ""))
        if t == "item.completed" and item_type == "tool_call":
            return CodingEvent(kind="tool_start", session_id="",
                             tool_name=item.get("name", ""),
                             tool_input=json.loads(item.get("arguments", "{}")))
        if t == "item.completed" and item_type == "tool_output":
            return CodingEvent(kind="tool_result", session_id="",
                             tool_output=item.get("output", ""))
        if t == "turn.completed":
            return CodingEvent(kind="done", session_id="",
                             raw=obj.get("usage", {}))
        return None
```

---

## 4. CodingGenesisAgent Class

```python
class CodingGenesisAgent(MonitoredAgent):
    """
    Genesis agent backed by Claude Code or Codex as a subprocess.
    Uses subscription pricing — no API keys needed.
    """

    def __init__(
        self,
        backend: str = "claude",           # "claude" or "codex"
        agent_name: str = "CodingAgent",
        base_service_name: str = "CodingAgent",
        description: str = "Coding agent powered by Claude Code / Codex",
        working_dir: str | None = None,    # project directory for the harness
        timeout: float = 300.0,            # 5 min default
        domain_id: int = 0,
        enable_agent_communication: bool = True,
        **kwargs,
    ):
        super().__init__(
            agent_name=agent_name,
            base_service_name=base_service_name,
            agent_type="SPECIALIZED_AGENT",
            description=description,
            domain_id=domain_id,
            enable_agent_communication=enable_agent_communication,
            **kwargs,
        )

        # Select backend
        if backend == "claude":
            self._backend = ClaudeBackend()
        elif backend == "codex":
            self._backend = CodexBackend()
        else:
            raise ValueError(f"Unknown backend: {backend}")

        self._working_dir = working_dir
        self._timeout = timeout
        self._active_sessions: dict[str, str] = {}  # request_id -> session_id

        # Set capabilities for agent-as-tool discovery
        self.set_agent_capabilities(
            capabilities=["coding", "software-engineering", "code-review", "debugging"],
            specializations=[f"{backend}-code"],
        )

    async def _process_request(self, request: dict) -> dict:
        """Execute a coding task via the backend subprocess."""
        message = request.get("message", "")
        conversation_id = request.get("conversation_id")
        session_id = self._active_sessions.get(conversation_id) if conversation_id else None

        chain_id = str(uuid.uuid4())

        # Publish chain start to DDS monitoring
        self._publish_chain_event(chain_id, "CHAIN_START", message)

        try:
            result_text, new_session_id, events = await self._run_subprocess(
                prompt=message,
                session_id=session_id,
            )

            # Store session for future multi-turn
            if conversation_id and new_session_id:
                self._active_sessions[conversation_id] = new_session_id

            self._publish_chain_event(chain_id, "CHAIN_COMPLETE", result_text)

            return {
                "message": result_text,
                "status": 0,
                "session_id": new_session_id,
                "backend": self._backend.name,
                "events_count": len(events),
            }

        except asyncio.TimeoutError:
            self._publish_chain_event(chain_id, "CHAIN_ERROR", "Timeout")
            return {"message": "Error: coding task timed out", "status": 1}
        except Exception as e:
            self._publish_chain_event(chain_id, "CHAIN_ERROR", str(e))
            return {"message": f"Error: {e}", "status": 1}

    async def _run_subprocess(
        self, prompt: str, session_id: str | None = None
    ) -> tuple[str, str | None, list[CodingEvent]]:
        """Spawn backend subprocess, parse streaming events, return result."""
        cmd = self._backend.build_command(prompt, session_id, self._working_dir)
        env = self._backend.build_env()

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=self._working_dir,
        )

        events: list[CodingEvent] = []
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
                    except json.JSONDecodeError:
                        continue
                    if event is None:
                        continue

                    events.append(event)

                    if event.kind == "init" and event.session_id:
                        new_session_id = event.session_id
                    elif event.kind == "text":
                        result_text += event.text
                    elif event.kind == "tool_start":
                        # Publish tool usage to graph monitoring
                        self.graph.publish_edge(
                            source_id=self.app.agent_id,
                            target_id=f"{self._backend.name}:{event.tool_name}",
                            edge_type=EDGE_TYPE["SERVICE_TO_FUNCTION"],
                            attrs={"tool": event.tool_name, "backend": self._backend.name},
                        )
                    elif event.kind == "done":
                        if event.text:
                            result_text = event.text  # final answer overrides streaming text

        finally:
            if proc.returncode is None:
                proc.terminate()
                await proc.wait()

        return result_text, new_session_id, events

    def _publish_chain_event(self, chain_id: str, event_type: str, detail: str):
        """Publish chain events to DDS for monitoring."""
        try:
            self.graph.publish_edge(
                source_id=self.app.agent_id,
                target_id=f"chain:{chain_id}",
                edge_type=EDGE_TYPE.get("CAPABILITY_BASED_TOOL", 3),
                attrs={
                    "chain_id": chain_id,
                    "event": event_type,
                    "detail": detail[:500],
                    "backend": self._backend.name,
                },
            )
        except Exception:
            pass  # monitoring is best-effort
```

---

## 5. File Layout

```
genesis_lib/
├── coding_agent/
│   ├── __init__.py           # exports CodingGenesisAgent, CodingEvent
│   ├── events.py             # CodingEvent dataclass
│   ├── backend.py            # CodingBackend ABC
│   ├── claude_backend.py     # ClaudeBackend implementation
│   ├── codex_backend.py      # CodexBackend implementation
│   └── agent.py              # CodingGenesisAgent (MonitoredAgent subclass)
```

---

## 6. Usage Examples

### Basic Claude Code Agent

```python
from genesis_lib.coding_agent import CodingGenesisAgent

agent = CodingGenesisAgent(
    backend="claude",
    agent_name="ClaudeCoder",
    working_dir="/path/to/project",
)
# Agent is now discoverable on the Genesis network.
# Other agents can delegate coding tasks to it via DDS.
await agent.run()
```

### Basic Codex Agent

```python
agent = CodingGenesisAgent(
    backend="codex",
    agent_name="CodexCoder",
    working_dir="/path/to/project",
)
await agent.run()
```

### Multi-Agent Setup (Primary + Coding Specialist)

```python
# The primary agent discovers coding agents automatically
primary = OpenAIGenesisAgent(
    model_name="gpt-4o",
    agent_name="Orchestrator",
    enable_agent_communication=True,
)

# Specialized coding agent
coder = CodingGenesisAgent(
    backend="claude",
    agent_name="CodeSpecialist",
    working_dir="/path/to/project",
)

# Orchestrator automatically discovers CodeSpecialist
# and can delegate: "Write a Python script that..."
```

---

## 7. Testing Checklist

- [x] Claude Code `-p` subscription auth (confirmed zero API billing)
- [x] Direct API with setup token + Bearer + oauth-beta (confirmed)
- [x] Codex `codex exec -m gpt-5.3-codex --json` functional (billing check pending)
- [ ] Claude stream JSON event parsing (unit test)
- [ ] Codex JSONL event parsing (unit test)
- [ ] CodingGenesisAgent subprocess lifecycle (integration test)
- [ ] Multi-turn session resume (both backends)
- [ ] Agent-as-tool discovery (primary agent finds coding agent)
- [ ] Timeout handling
- [ ] Error propagation

---

## 8. Next Steps

1. **Test Codex subscription auth** — `env -u OPENAI_API_KEY -u CODEX_API_KEY codex exec --json "test"`, check billing
2. **Implement `genesis_lib/coding_agent/`** — the 6-file module described above
3. **Write event parser unit tests** — feed recorded JSON lines through each backend's `parse_line`
4. **Integration test** — run a real coding task, verify DDS monitoring events appear
5. **Example script** — `examples/CodingAgent/run_coding_agent.sh`
