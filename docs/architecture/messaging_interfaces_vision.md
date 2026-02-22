# Messaging Interfaces for Genesis: Technical Vision

*Thin transport adapters for Telegram, Slack, and future platforms — built on MonitoredInterface*

---

## 1. Problem Statement

Every new channel into the Genesis agent network reimplements the same lifecycle: discover agents via DDS, select one, establish a session, format requests, parse responses, and handle errors. The CLI does it. The web GUI does it. Any future Telegram bot or Slack app would do it again.

This creates three compounding problems:

1. **Duplication.** Each platform reimplements MonitoredInterface lifecycle management: discovery polling, connection establishment, request/response serialization, and session teardown.

2. **Inconsistency.** Without a shared pattern, each interface diverges on session identity, error handling, timeout behavior, and response formatting.

3. **Expense.** Adding a new platform requires understanding DDS internals, MonitoredInterface state machine semantics, and Genesis request/response formats before writing a single line of platform-specific code.

The solution is a **messaging gateway pattern** where each platform is reduced to a transport adapter — a thin shell that translates platform messages to and from the standard MonitoredInterface API. All agent logic, DDS communication, and monitoring stay in the existing Genesis infrastructure.

**Concrete goal:** Telegram and Slack interfaces with fewer than 500 lines of platform-specific code each, all agent interaction delegated to a single MonitoredInterface instance per gateway process.

---

## 2. Design Principles

**P1 — Transport is a thin shell.** The platform adapter handles three concerns: receiving platform messages, sending platform responses, and format translation. All agent logic flows through MonitoredInterface.

**P2 — One MonitoredInterface per gateway instance.** Each gateway process creates one MonitoredInterface, connects to one agent, routes all platform messages through it. One INTERFACE node in the Genesis graph.

**P3 — Explicit session mapping.** `(platform, channel_id, thread_id)` maps deterministically to a Genesis `conversation_id`. PersistentMemoryAdapter preserves history correctly across restarts.

**P4 — Platform-aware formatting.** Responses arrive as markdown, get converted to Telegram MarkdownV2 or Slack mrkdwn. Long responses are chunked at platform-specific limits.

**P5 — Monitoring is automatic.** MonitoredInterface provides ChainEvent tracking, graph topology, and state machine transitions with zero platform-specific monitoring code.

**P6 — Config over code.** JSON config with environment variable overrides for secrets. No hardcoded secrets.

**P7 — Security by default.** Allowlists, rate limiting, and input sanitization enabled by default.

---

## 3. Architecture Overview

### 3.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Genesis Agent Network                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ CodingAgent  │  │ PlanningAgent│  │ WeatherAgent │  ...     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         └──────────────────┼──────────────────┘                 │
│                            │ DDS Topics (GenesisRPCRequest/Reply)│
└────────────────────────────┼────────────────────────────────────┘
                             │
                    ┌────────▼───────────┐
                    │ MonitoredInterface  │
                    │ (agent discovery,   │
                    │  DDS RPC, ChainEvent│
                    │  tracking, state    │
                    │  machine)           │
                    └────────┬────────────┘
                             │ Python dict
                    ┌────────▼────────────┐
                    │ MessagingGateway     │
                    │ (session mapping,    │
                    │  auth, rate limiting,│
                    │  format bridging)    │
                    └────────┬────────────┘
              ┌──────────────┼──────────────┐
     ┌────────▼───────┐  ┌──▼──────────┐  ┌▼──────────────┐
     │ Telegram        │  │ Slack        │  │ Future         │
     │ python-telegram │  │ slack-bolt   │  │ (Discord,      │
     │ -bot            │  │              │  │  WhatsApp)     │
     └────────┬────────┘  └──┬──────────┘  └┬──────────────┘
         Users (mobile)    Users (desktop)   Users
```

### 3.2 Data Flow

```
User (Telegram/Slack)
    ↓ platform-native message
Platform Transport (python-telegram-bot / slack-bolt)
    ↓ SDK parses → handler callback
TelegramGenesisInterface / SlackGenesisInterface
    ↓ 1. Authenticate (allowlist/workspace)
    ↓ 2. Rate limit check
    ↓ 3. Map (platform, channel_id, thread_id) → conversation_id
    ↓ 4. Check slash commands (/agents, /status)
    ↓ 5. Build: {"message": "text", "conversation_id": "telegram-12345"}
MonitoredInterface.send_request(request_data)
    ↓ BUSY state → ChainEvent START → DDS RPC → ChainEvent COMPLETE → READY
Agent Response {"response": "..."}
    ↓ Convert markdown → platform format
    ↓ Chunk if exceeds platform limit
    ↓ Send via platform SDK
User receives formatted response
```

---

## 4. Transport Bridge Pattern

Each platform implements a class that extends MonitoredInterface and adds platform transport. Gateway logic (session mapping, auth, commands) lives inline in each class.

### 4.1 Data Classes

```python
@dataclass
class IncomingMessage:
    """Normalized message from any platform."""
    platform: str              # "telegram", "slack"
    channel_id: str            # Platform channel/chat identifier
    thread_id: Optional[str]   # Thread within channel (None = top-level)
    user_id: str               # Platform user identifier
    user_display_name: str     # Human-readable name
    text: str                  # Raw message text
    timestamp: float           # Unix timestamp
    is_command: bool = False
    command: Optional[str] = None
    command_args: List[str] = field(default_factory=list)

@dataclass
class OutgoingResponse:
    """Normalized response to send to a platform."""
    channel_id: str
    thread_id: Optional[str]
    text: str                  # Standard markdown
    chunks: List[str] = field(default_factory=list)
    parse_mode: Optional[str] = None
```

### 4.2 Platform Interface Pattern

```python
class TelegramGenesisInterface(MonitoredInterface):
    """Telegram transport for Genesis agent communication."""

    def __init__(self, config: dict):
        super().__init__(
            interface_name=config.get("interface_name", "TelegramInterface"),
            service_name=config["agent_service_name"],
        )
        self.bot = telegram.Bot(token=config["bot_token"])
        self.application = ApplicationBuilder().token(config["bot_token"]).build()
        self.allowed_chat_ids = config.get("allowed_chat_ids", None)
        self.rate_limiter = RateLimiter(config.get("rate_limits", {}))
        self._register_handlers()

    async def start(self) -> None:
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    async def stop(self) -> None:
        await self.application.updater.stop()
        await self.application.stop()
        await self.close()  # MonitoredInterface cleanup
```

### 4.3 Why Not a Separate Abstract Base Class

MonitoredInterface is already the base class. The shared logic (session mapping, formatting) is small utility functions, not a class hierarchy. Telegram uses long-polling; Slack uses WebSocket. Their lifecycles differ fundamentally. Two implementations are not a pattern — we extract common code when a third platform arrives.

---

## 5. Session Management

### 5.1 Conversation ID Mapping

```python
def compute_conversation_id(platform: str, channel_id: str,
                             thread_id: str = None) -> str:
    """Deterministic conversation ID from platform coordinates."""
    if thread_id:
        return f"{platform}-{channel_id}:{thread_id}"
    return f"{platform}-{channel_id}"
```

### 5.2 Platform Session Key Table

| Platform  | Session Key Components           | conversation_id Example            | Semantics                         |
|-----------|----------------------------------|------------------------------------|-----------------------------------|
| Telegram  | `chat_id`                        | `telegram-12345678`                | Per-chat (group or private)       |
| Telegram  | `chat_id` + `message_thread_id`  | `telegram-12345678:42`             | Forum topic thread                |
| Slack     | `channel`                        | `slack-C04ABCDEF`                  | Top-level channel conversation    |
| Slack     | `channel` + `thread_ts`          | `slack-C04ABCDEF:1678901234.567890`| Threaded conversation             |
| Discord   | `channel_id` + `thread_id`       | `discord-123:987`                  | Thread within channel             |
| WhatsApp  | `phone_number`                   | `whatsapp-15551234567`             | Per-phone conversation            |

### 5.3 Session State Storage

The gateway is **stateless** beyond the MonitoredInterface connection:

| State                    | Location             | Survives Restart? |
|--------------------------|----------------------|-------------------|
| Conversation history     | PersistentMemory DB  | Yes               |
| Agent connection         | MonitoredInterface   | No (rediscovery)  |
| Rate limit counters      | In-memory dict       | No (resets)       |
| Active conversation_ids  | Derived from message | Yes (deterministic)|

---

## 6. Platform Transport Model

| Feature                | Telegram                          | Slack                             | Discord (future)            | WhatsApp (future)          |
|------------------------|-----------------------------------|-----------------------------------|-----------------------------|----------------------------|
| **SDK**                | python-telegram-bot 21.x          | slack-bolt 1.x + slack-sdk 3.x   | discord.py 2.x              | whatsapp-cloud-api         |
| **Auth model**         | Bot token (BotFather)             | OAuth 2.0 (workspace install)     | Bot token (Dev Portal)      | Cloud API token            |
| **Message limit**      | 4096 chars                        | 40,000 chars                      | 2000 chars                  | 4096 chars                 |
| **Formatting**         | MarkdownV2 (18 escaped chars)     | mrkdwn (Slack-specific)           | Discord markdown            | Limited markdown           |
| **Rich UI**            | InlineKeyboardMarkup              | Block Kit (buttons, menus)        | Components (buttons)        | Interactive messages       |
| **Threading**          | reply_to_message_id, forum topics | thread_ts (native threads)        | Threads (auto-archive)      | No threading               |
| **Real-time**          | Long polling or webhooks          | Socket Mode (WebSocket)           | Gateway (WebSocket)         | Webhooks                   |
| **File upload**        | send_document (50MB)              | files_upload_v2 (1GB)             | send file (25MB)            | send_document (100MB)      |
| **Rate limits**        | 30 msg/s global, 1/s per chat     | Tier 2: ~20 req/min              | 50 req/s global             | 80 msg/s                   |
| **Typing indicator**   | send_chat_action("typing")        | N/A                               | trigger_typing_indicator()  | N/A                        |

```
Telegram Transport                         Slack Transport
┌────────────────────────────┐             ┌────────────────────────────┐
│ python-telegram-bot App    │             │ slack-bolt App             │
│  Updater (long-polling)    │             │  Socket Mode (WebSocket)   │
│  Handlers:                 │             │  Listeners:                │
│   /start  → _cmd_start    │             │   @app.message → _on_msg   │
│   /agents → _cmd_agents   │             │   @app.command → _cmd_*    │
│   text    → _on_message   │             │   @app.action  → _on_sel   │
│  Outbound: send_message   │             │  Outbound: chat_postMessage│
│  Keyboard: InlineKeyboard  │             │  Blocks: Block Kit JSON    │
└────────────────────────────┘             └────────────────────────────┘
```

---

## 7. MessagingGateway Core

Gateway logic lives inline in each platform class. The processing flow:

```python
async def _handle_message(self, platform_message):
    # 1. Normalize → IncomingMessage
    incoming = self._normalize(platform_message)

    # 2. Authenticate
    if not self._is_allowed(incoming):
        return  # Silent reject

    # 3. Rate limit
    if not self._rate_limiter.allow(incoming.user_id):
        await self._send_response(incoming.channel_id, "Rate limit exceeded.")
        return

    # 4. Command dispatch
    if incoming.is_command:
        await self._dispatch_command(incoming)
        return

    # 5. Build Genesis request
    conversation_id = compute_conversation_id(
        incoming.platform, incoming.channel_id, incoming.thread_id)
    request_data = {"message": incoming.text, "conversation_id": conversation_id}

    # 6. Send to agent via MonitoredInterface
    await self._send_typing_indicator(incoming.channel_id)
    response = await self.send_request(request_data, timeout_seconds=120.0)

    # 7. Format and send response
    if response and response.get("response"):
        await self._send_formatted_response(
            incoming.channel_id, response["response"], incoming.thread_id)
```

### 7.1 Command Set

| Command       | Description                                    |
|---------------|------------------------------------------------|
| `/start`      | Welcome message and bot initialization         |
| `/help`       | Show available commands                        |
| `/agents`     | List discovered agents (inline keyboard/blocks)|
| `/connect`    | Connect to a specific agent by name            |
| `/disconnect` | Disconnect from current agent                  |
| `/status`     | Show connection status and session info        |

### 7.2 Agent Auto-Connect

```
0 agents → Wait. Reply: "No agents available. Waiting..."
1 agent  → Auto-connect. Reply: "Connected to {name}"
N agents → If default_agent configured: auto-connect.
           Otherwise: wait for /connect or show selection UI.
```

---

## 8. Message Format Bridging

### 8.1 Telegram MarkdownV2

```python
TELEGRAM_ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!"

def markdown_to_telegram(text: str) -> str:
    """Convert standard markdown to Telegram MarkdownV2.
    1. Extract and preserve code blocks and inline code
    2. Convert **bold** → *bold*, *italic* → _italic_
    3. Escape all 18 special chars in non-code text
    4. Reassemble
    """
    segments = _split_code_segments(text)
    result = []
    for seg_type, content in segments:
        if seg_type in ("code_block", "inline_code"):
            result.append(content)
        else:
            converted = _convert_markdown_syntax(content)
            result.append(_escape_telegram_chars(converted))
    return "".join(result)
```

### 8.2 Slack mrkdwn

```python
def markdown_to_slack(text: str) -> str:
    """Convert standard markdown to Slack mrkdwn.
    - **bold** → *bold*  (single asterisks)
    - [text](url) → <url|text>  (angle bracket links)
    - ## Heading → *Heading*  (no heading support, use bold)
    - Code blocks pass through unchanged
    """
    segments = _split_code_segments(text)
    result = []
    for seg_type, content in segments:
        if seg_type in ("code_block", "inline_code"):
            result.append(content)
        else:
            content = re.sub(r"\*\*(.+?)\*\*", r"*\1*", content)
            content = re.sub(r"\[(.+?)\]\((.+?)\)", r"<\2|\1>", content)
            content = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", content, flags=re.M)
            result.append(content)
    return "".join(result)
```

### 8.3 Message Chunking

```python
def chunk_text(text: str, max_len: int) -> list:
    """Split at platform limit. Prefer paragraph breaks → newlines →
    sentence boundaries → spaces → hard cut. Never split inside code blocks."""
    if len(text) <= max_len:
        return [text]
    split_at = _find_split_point(text, max_len)
    return [text[:split_at].rstrip()] + chunk_text(text[split_at:].lstrip(), max_len)
```

| Platform  | Text Limit | Long Code Strategy                |
|-----------|-----------|-----------------------------------|
| Telegram  | 4,096     | Chunk at 4096; long code → file   |
| Slack     | 40,000    | Chunk at 40000; long code → snippet|
| Discord   | 2,000     | Chunk at 2000; long code → file   |

---

## 9. Multi-Agent Routing

### 9.1 Agent Discovery Display

`/agents` queries `self.available_agents` (from DDS discovery) and shows platform-native UI:

```
Telegram: InlineKeyboardMarkup          Slack: Block Kit
┌──────────────────────────┐            ┌──────────────────────────┐
│ Available Agents:        │            │ Available Genesis Agents │
│ ┌──────────────────────┐ │            │ ─────────────────────── │
│ │ CodingAgent          │ │            │ *CodingAgent*           │
│ │ [Connect]            │ │            │ Service: `CodingService`│
│ ├──────────────────────┤ │            │ [Connect]               │
│ │ PlanningAgent        │ │            │                         │
│ │ [Connect]            │ │            │ *PlanningAgent*         │
│ └──────────────────────┘ │            │ Service: `PlanService`  │
└──────────────────────────┘            │ [Connect]               │
                                        └──────────────────────────┘
```

### 9.2 Agent Selection Flow

```
User sends /agents → Gateway shows selection UI → User taps "Connect" →
Gateway calls self.connect_to_agent(service_name) → Confirm: "Connected to X" →
All messages route to X until /disconnect or /connect to another agent
```

---

## 10. Authentication and Security

### 10.1 Telegram: Chat ID Allowlist

```python
class TelegramAuth:
    def __init__(self, config: dict):
        self.allowed_chat_ids = config.get("allowed_chat_ids")  # None=open, []=locked
        self.admin_chat_ids = config.get("admin_chat_ids", [])

    def is_allowed(self, chat_id: int) -> bool:
        if self.allowed_chat_ids is None:
            return True
        return chat_id in self.allowed_chat_ids
```

| Configuration               | Behavior                      |
|-----------------------------|-------------------------------|
| `"allowed_chat_ids": null`  | Open bot — anyone can use it  |
| `"allowed_chat_ids": []`    | Locked — no one can use it    |
| `"allowed_chat_ids": [123]` | Private — only chat 123       |

### 10.2 Slack: Workspace OAuth + Channel Restrictions

```python
class SlackAuth:
    def __init__(self, config: dict):
        self.allowed_channels = config.get("allowed_channels")  # None=all
        self.allowed_users = config.get("allowed_users")        # None=all

    def is_allowed(self, channel: str, user: str) -> bool:
        if self.allowed_channels and channel not in self.allowed_channels:
            return False
        if self.allowed_users and user not in self.allowed_users:
            return False
        return True
```

### 10.3 Secret Management

```
NEVER in config file:  bot tokens, OAuth secrets, signing secrets
ALWAYS via env vars:   TELEGRAM_BOT_TOKEN, SLACK_BOT_TOKEN, SLACK_APP_TOKEN
Config file only:      allowed_chat_ids, rate_limits, agent_service_name
```

### 10.4 Input Sanitization

```python
def sanitize_input(text: str, max_length: int = 4096) -> str:
    """Truncate, strip null bytes, strip control chars, normalize Unicode."""
    text = text[:max_length].replace("\x00", "")
    text = "".join(c for c in text
                   if c in ("\n", "\t") or not unicodedata.category(c).startswith("C"))
    return unicodedata.normalize("NFC", text).strip()
```

---

## 11. Rate Limiting and Queuing

### 11.1 Platform API Limits

```
Telegram:  30 msg/s global, 1 msg/s per chat, 20 msg/min per group
           HTTP 429 with retry_after header
Slack:     Tier 2 (chat.postMessage): ~20 req/min
           HTTP 429 with Retry-After header
Genesis:   No explicit limit (DDS backpressure, agent processing time)
```

### 11.2 User-Facing Rate Limiter

```python
class RateLimiter:
    """Sliding window rate limiter."""
    def __init__(self, config: dict):
        self.max_requests = config.get("max_requests_per_minute", 10)
        self.window_seconds = config.get("window_seconds", 60)
        self._requests = defaultdict(list)

    def allow(self, user_id: str) -> bool:
        now = time.time()
        self._requests[user_id] = [
            ts for ts in self._requests[user_id] if ts > now - self.window_seconds]
        if len(self._requests[user_id]) >= self.max_requests:
            return False
        self._requests[user_id].append(now)
        return True
```

### 11.3 Outbound Queue

```python
class OutboundQueue:
    """Per-channel rate-limited queue. Telegram: 1.0s delay. Slack: 3.0s."""
    def __init__(self, min_delay: float = 1.0):
        self.min_delay = min_delay
        self._last_send = {}

    async def send(self, channel_id: str, send_fn, *args, **kwargs):
        wait = self.min_delay - (time.time() - self._last_send.get(channel_id, 0))
        if wait > 0:
            await asyncio.sleep(wait)
        await send_fn(*args, **kwargs)
        self._last_send[channel_id] = time.time()
```

---

## 12. Media Handling

### 12.1 Code Block Handling

```
Short code (< 200 lines, fits in message):
    Telegram: ```language\ncode\n```  (client-side highlighting)
    Slack:    ```code```  (server-side highlighting)

Long code (> 200 lines OR exceeds limit):
    Telegram: send_document() as .py/.js/.ts file
    Slack:    files_upload_v2() as snippet with highlighting
```

### 12.2 Rich Content by Platform

| Content Type  | Telegram                        | Slack                          |
|--------------|--------------------------------|--------------------------------|
| URL image    | `send_photo(url=...)`          | Auto-unfurl in mrkdwn         |
| Base64 image | `send_photo(photo=BytesIO())` | `files_upload_v2(content=...)` |
| Markdown table| Monospace pre-formatted        | mrkdwn table or code block    |
| JSON response | Code block with `json` hint    | Code block or snippet file    |

---

## 13. Monitoring Integration

### 13.1 Automatic Monitoring

Both `TelegramGenesisInterface` and `SlackGenesisInterface` inherit MonitoredInterface. All monitoring is automatic:

```
TelegramGenesisInterface(MonitoredInterface)
├─ __init__() publishes DISCOVERING → READY state
├─ send_request() publishes:
│   ├─ BUSY state (before DDS RPC)
│   ├─ INTERFACE_REQUEST_START ChainEvent
│   ├─ INTERFACE_REQUEST_COMPLETE ChainEvent
│   └─ READY state (after DDS RPC)
├─ Agent discovery publishes INTERFACE→AGENT edges
└─ close() publishes OFFLINE state

No monitoring code required in platform classes.
```

### 13.2 Graph Topology

```
┌───────────────────────────────────────────────┐
│            Genesis Network Graph               │
│                                               │
│  ┌──────────────┐      ┌──────────────┐      │
│  │ Telegram      │─────▶│ CodingAgent  │      │
│  │ (INTERFACE)   │ edge │ (AGENT)      │      │
│  │ state: READY  │      │ state: READY │      │
│  └──────────────┘      └──────────────┘      │
│  ┌──────────────┐      ┌──────────────┐      │
│  │ Slack         │─────▶│ PlanningAgent│      │
│  │ (INTERFACE)   │ edge │ (AGENT)      │      │
│  └──────────────┘      └──────────────┘      │
└───────────────────────────────────────────────┘
```

### 13.3 ChainEvent Correlation

All events share the same `chain_id` for end-to-end tracing:

```
INTERFACE_REQUEST_START  {chain_id: "abc", interface_id: "tg-guid", target_id: "agent-guid"}
  → AGENT_PROCESSING_START  {chain_id: "abc"}
    → FUNCTION_CALL_START/COMPLETE  {chain_id: "abc"}
  → AGENT_PROCESSING_COMPLETE  {chain_id: "abc"}
INTERFACE_REQUEST_COMPLETE  {chain_id: "abc"}
```

---

## 14. Configuration

### 14.1 Override Hierarchy

```
Priority 1 (highest): Environment variables (secrets)
Priority 2:           Config file values (operational settings)
Priority 3 (lowest):  Hardcoded defaults (non-secret fields)
```

### 14.2 Telegram Config

```json
{
    "interface_name": "TelegramGenesisBot",
    "agent_service_name": "CodingAgentService",
    "telegram": {
        "bot_token": "${TELEGRAM_BOT_TOKEN}",
        "polling_mode": true,
        "allowed_chat_ids": null,
        "admin_chat_ids": [],
        "send_typing_indicator": true
    },
    "rate_limits": { "max_requests_per_minute": 10, "window_seconds": 60 },
    "formatting": { "parse_mode": "MarkdownV2", "max_message_length": 4096 },
    "agent_timeout_seconds": 120,
    "auto_connect_single_agent": true
}
```

### 14.3 Slack Config

```json
{
    "interface_name": "SlackGenesisBot",
    "agent_service_name": "CodingAgentService",
    "slack": {
        "bot_token": "${SLACK_BOT_TOKEN}",
        "app_token": "${SLACK_APP_TOKEN}",
        "signing_secret": "${SLACK_SIGNING_SECRET}",
        "socket_mode": true,
        "allowed_channels": null,
        "respond_in_thread": true
    },
    "rate_limits": { "max_requests_per_minute": 10, "outbound_delay_seconds": 3.0 },
    "formatting": { "parse_mode": "mrkdwn", "max_message_length": 40000, "use_block_kit": true },
    "agent_timeout_seconds": 120,
    "auto_connect_single_agent": true
}
```

### 14.4 Environment Variable Reference

| Variable                | Required | Platform | Description                         |
|-------------------------|----------|----------|-------------------------------------|
| `TELEGRAM_BOT_TOKEN`   | Yes*     | Telegram | Bot token from BotFather            |
| `SLACK_BOT_TOKEN`      | Yes*     | Slack    | Bot OAuth token (xoxb-...)          |
| `SLACK_APP_TOKEN`      | Yes*     | Slack    | App-level token (xapp-...)          |
| `SLACK_SIGNING_SECRET` | Yes*     | Slack    | Request signing secret              |
| `GENESIS_DOMAIN_ID`    | No       | Both     | DDS domain ID (default: 0)          |

*Required only for the respective platform.

### 14.5 Config Loading

```python
def load_config(config_path: str) -> dict:
    """Load JSON config with ${VAR_NAME} interpolation from env vars."""
    with open(config_path) as f:
        config = json.load(f)
    def _interpolate(obj):
        if isinstance(obj, str):
            return re.sub(r"\$\{(\w+)\}",
                          lambda m: os.environ.get(m.group(1), m.group(0)), obj)
        elif isinstance(obj, dict):
            return {k: _interpolate(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_interpolate(v) for v in obj]
        return obj
    return _interpolate(config)
```

---

## 15. Implementation Roadmap

### Phase 1 — Telegram Interface

| Step | Deliverable                           | Description                                    |
|------|---------------------------------------|------------------------------------------------|
| 1.1  | `telegram_interface.py`               | TelegramGenesisInterface extending MonitoredInterface |
| 1.2  | `format_telegram.py`                  | MarkdownV2 conversion, chunking at 4096        |
| 1.3  | `config/telegram_config.example.json` | Example config with documented fields          |
| 1.4  | `tests/test_telegram_interface.py`    | Unit tests: session, auth, format, chunking    |
| 1.5  | `tests/test_telegram_acceptance.py`   | Integration tests with mocked DDS              |
| 1.6  | `run_telegram.sh`                     | Launch script (agent + telegram bot)            |

### Phase 2 — Slack Interface

| Step | Deliverable                        | Description                                    |
|------|------------------------------------|------------------------------------------------|
| 2.1  | `slack_interface.py`               | SlackGenesisInterface with thread_ts handling   |
| 2.2  | `format_slack.py`                  | mrkdwn conversion, Block Kit builder            |
| 2.3  | `config/slack_config.example.json` | Example config with documented fields          |
| 2.4  | `tests/test_slack_interface.py`    | Unit tests: session, auth, format, threads     |
| 2.5  | `tests/test_slack_acceptance.py`   | Integration tests with mocked DDS              |
| 2.6  | `run_slack.sh`                     | Launch script (agent + slack bot)               |

### Phase 3 — Future Platforms (Discord, WhatsApp)

Same pattern: extend MonitoredInterface, add transport handlers, format bridge, config. Extract shared utilities to `genesis_lib/messaging/` if three+ platforms share significant code.

```
Week 1              Week 2              Week 3              Future
─────────────────   ─────────────────   ─────────────────   ─────────
Phase 1: Telegram   Phase 2: Slack      Polish & docs       Phase 3
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌───────┐
│ Core + format   │ │ Core + format   │ │ README files    │ │Discord│
│ Config + auth   │ │ Block Kit UI    │ │ E2E testing     │ │Whats- │
│ Tests + launch  │ │ Tests + launch  │ │ Edge cases      │ │App    │
└─────────────────┘ └─────────────────┘ └─────────────────┘ └───────┘
```

---

## 16. File Structure

```
examples/
├── TelegramInterface/
│   ├── telegram_interface.py            # TelegramGenesisInterface class
│   ├── format_telegram.py              # markdown_to_telegram(), chunk_text()
│   ├── config/
│   │   └── telegram_config.example.json # Example config (no secrets)
│   ├── tests/
│   │   ├── test_telegram_interface.py   # Unit tests (mock everything)
│   │   └── test_telegram_acceptance.py  # GWT acceptance tests (mock DDS)
│   ├── run_telegram.sh                  # Launch: agent + telegram bot
│   ├── logs/                            # Runtime logs (gitignored)
│   └── README.md                        # Setup: BotFather, config, run

├── SlackInterface/
│   ├── slack_interface.py               # SlackGenesisInterface class
│   ├── format_slack.py                 # markdown_to_slack(), block_kit_builder()
│   ├── config/
│   │   └── slack_config.example.json    # Example config (no secrets)
│   ├── tests/
│   │   ├── test_slack_interface.py      # Unit tests (mock everything)
│   │   └── test_slack_acceptance.py     # GWT acceptance tests (mock DDS)
│   ├── run_slack.sh                     # Launch: agent + slack bot
│   ├── logs/                            # Runtime logs (gitignored)
│   └── README.md                        # Setup: Slack app, OAuth, config, run

genesis_lib/
    # No changes for Phase 1-2. Interfaces are examples that USE genesis_lib.
    # Extract to genesis_lib/messaging/ only if Phase 3 reveals shared code.
```

Platform SDKs are **not** added to Genesis core dependencies:

```
examples/TelegramInterface/requirements.txt:  python-telegram-bot>=21.0
examples/SlackInterface/requirements.txt:     slack-bolt>=1.18, slack-sdk>=3.26
```

---

## 17. Test Strategy

### 17.1 Three Levels

```
                      ╱╲
                     ╱E2E╲         Level 3: Manual. Real tokens, real platform.
                    ╱──────╲
                   ╱Integr. ╲      Level 2: Mock DDS. Full interface class,
                  ╱──────────╲     mocked MonitoredInterface. GWT acceptance.
                 ╱ Unit Tests ╲    Level 1: Mock everything. Pure functions:
                ╱══════════════╲   format, session, auth, rate limit, chunk.

All automated tests use Genesis check()/failures/sys.exit(1) pattern. No pytest.
```

### 17.2 Unit Test Example (Genesis Pattern)

```python
#!/usr/bin/env python3
"""Unit tests for Telegram interface — pure logic, no dependencies."""
import sys

failures = []
def check(name, condition):
    if condition: print(f"  PASS: {name}")
    else: print(f"  FAIL: {name}"); failures.append(name)

# Session mapping
print("\n=== Session Mapping ===")
from telegram_interface import compute_conversation_id
check("private chat", compute_conversation_id("telegram", "123") == "telegram-123")
check("forum thread", compute_conversation_id("telegram", "123", "42") == "telegram-123:42")
check("deterministic", compute_conversation_id("telegram", "99") == compute_conversation_id("telegram", "99"))

# Auth
print("\n=== Authentication ===")
from telegram_interface import TelegramAuth
check("open mode", TelegramAuth({"allowed_chat_ids": None}).is_allowed(999))
check("locked mode", not TelegramAuth({"allowed_chat_ids": []}).is_allowed(999))
check("allowlist hit", TelegramAuth({"allowed_chat_ids": [111]}).is_allowed(111))
check("allowlist miss", not TelegramAuth({"allowed_chat_ids": [111]}).is_allowed(222))

# Rate limiting
print("\n=== Rate Limiting ===")
from telegram_interface import RateLimiter
lim = RateLimiter({"max_requests_per_minute": 2, "window_seconds": 60})
check("first allowed", lim.allow("u1"))
check("second allowed", lim.allow("u1"))
check("third rejected", not lim.allow("u1"))

# Formatting
print("\n=== MarkdownV2 ===")
from format_telegram import markdown_to_telegram, chunk_text
check("code block preserved", "```python" in markdown_to_telegram("```python\nprint(1)\n```"))
check("chunking respects limit", all(len(c) <= 100 for c in chunk_text("x" * 500, 100)))

print(f"\n{'='*60}")
if failures: print(f"FAILED: {len(failures)}"); sys.exit(1)
else: print("ALL TESTS PASSED"); sys.exit(0)
```

### 17.3 Integration Test Example

```python
#!/usr/bin/env python3
"""Integration tests — mock DDS, mock Telegram SDK."""
import sys, asyncio
from unittest.mock import AsyncMock, MagicMock, patch

failures = []
def check(name, condition):
    if condition: print(f"  PASS: {name}")
    else: print(f"  FAIL: {name}"); failures.append(name)

async def test_message_flow():
    """GWT: Given connected interface, When user sends message, Then response sent back."""
    with patch("telegram_interface.MonitoredInterface.__init__", return_value=None), \
         patch("telegram_interface.MonitoredInterface.send_request") as mock_send:
        mock_send.return_value = {"response": "Hello from agent!"}
        interface = TelegramGenesisInterface.__new__(TelegramGenesisInterface)
        interface.bot = AsyncMock()
        interface.rate_limiter = RateLimiter({"max_requests_per_minute": 100})
        interface.auth = TelegramAuth({"allowed_chat_ids": None})
        update = MagicMock(); update.effective_chat.id = 12345
        update.message.text = "What is the weather?"
        await interface._handle_message(update, None)
        check("agent called", mock_send.call_count == 1)
        check("response sent", interface.bot.send_message.called)

asyncio.run(test_message_flow())

print(f"\n{'='*60}")
if failures: print(f"FAILED: {len(failures)}"); sys.exit(1)
else: print("ALL TESTS PASSED"); sys.exit(0)
```

### 17.4 E2E Checklist (Manual)

```
Telegram:                                  Slack:
[ ] /start → welcome                      [ ] DM → response
[ ] /agents → inline keyboard             [ ] @mention → response
[ ] Connect → confirmation                 [ ] /agents → Block Kit
[ ] Message → agent response               [ ] Connect → confirmation
[ ] Long response → correct chunking       [ ] Thread → separate conversation_id
[ ] Code blocks → monospace                [ ] Long code → file snippet
[ ] Unauthorized → silent reject           [ ] Unauthorized channel → silent reject
[ ] Rate limited → rate limit message      [ ] Rate limited → rate limit message
[ ] Restart → resume context               [ ] Restart → resume context
```

---

## 18. References

### Platform SDKs and APIs

- **python-telegram-bot.** https://docs.python-telegram-bot.org/
- **Telegram Bot API.** https://core.telegram.org/bots/api
- **Telegram MarkdownV2.** https://core.telegram.org/bots/api#markdownv2-style
- **Slack Bolt for Python.** https://slack.dev/bolt-python/
- **Slack mrkdwn reference.** https://api.slack.com/reference/surfaces/formatting
- **Slack Block Kit.** https://api.slack.com/block-kit
- **Slack Socket Mode.** https://api.slack.com/apis/connections/socket

### Genesis Internal References

- **MonitoredInterface.** `genesis_lib/monitored_interface.py`
- **GenesisInterface.** `genesis_lib/interface.py`
- **GraphMonitor.** `genesis_lib/graph_monitoring.py`
- **PersistentMemoryAdapter vision.** `docs/architecture/persistent_memory_vision.md`
- **ExampleInterface.** `examples/ExampleInterface/`
- **DDS data model.** `genesis_lib/config/datamodel.xml`
- **QoS profiles.** `genesis_lib/config/USER_QOS_PROFILES.xml`

---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
