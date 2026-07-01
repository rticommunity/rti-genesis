# Agent-as-Tool Pattern

Genesis allows agents to call other agents the same way they call functions — via LLM tool calls routed over DDS. This page documents the implemented architecture.

---

## Overview

When `enable_agent_communication=True` is passed to an agent, it:

1. Discovers other agents on the network via the `AgentCapability` DDS topic
2. Converts each discovered agent into an OpenAI-compatible tool schema
3. Includes those schemas in every LLM call alongside function tools and internal `@genesis_tool` methods
4. Routes any LLM tool calls targeting agents via DDS `AgentAgentRequest` / `AgentAgentReply`

The LLM sees a unified tool list — it does not know or care whether a tool is a local method, a remote function, or another agent.

---

## Tool Types in a Single LLM Call

```
_get_all_tool_schemas_for_openai()
    ├── function tools        (@genesis_function services discovered via FunctionRegistry)
    ├── agent tools           (discovered agents → converted to tool schemas)
    └── internal tools        (@genesis_tool methods on this agent class)
```

All three are combined into one list and sent in a single LLM call. No pre-classification step.

---

## Key Methods (`openai_genesis_agent.py`)

### `_ensure_agents_discovered()`
Called before each LLM invocation. Reads `discovered_agents` from `AgentCommunicationMixin`, skips self, and builds `self.agent_cache` — a mapping from capability-based tool names to agent metadata.

```python
async def _ensure_agents_discovered(self):
    for agent_id, agent_info in discovered_agents.items():
        if agent_id == self.app.agent_id:
            continue
        tool_names = self._generate_capability_based_tool_names(agent_info, ...)
        for tool_name, tool_description in tool_names.items():
            self.agent_cache[tool_name] = {
                "agent_id": agent_id,
                "agent_name": agent_info.get('name'),
                "capabilities": agent_info.get('capabilities', []),
                ...
            }
```

### `_convert_agents_to_tools()`
Converts `self.agent_cache` into OpenAI tool schemas. All agents use the same universal schema — a single `message` string parameter:

```python
tool_schema = {
    "type": "function",
    "function": {
        "name": tool_name,           # e.g. "get_weather_info"
        "description": "Specialised agent for weather, meteorology. Send natural language queries.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Natural language query"}
            },
            "required": ["message"]
        }
    }
}
```

Tool names are derived from agent capabilities, not agent names (e.g. `get_weather_info` not `WeatherAgent`).

### `_handle_agent_tool_call(tool_call)`
When the LLM calls an agent tool, this routes it via DDS:

```python
async def _handle_agent_tool_call(self, tool_call):
    tool_name = tool_call.function.name
    agent_info = self.agent_cache[tool_name]
    args = json.loads(tool_call.function.arguments)

    response = await self.send_agent_request(
        target_agent_id=agent_info["agent_id"],
        message=args["message"],
        conversation_id=self.current_conversation_id,
        timeout_seconds=15.0
    )
    return response['message']
```

---

## Discovery Infrastructure (`agent_communication.py`)

`AgentCommunicationMixin` provides:

| Method | What it does |
|--------|-------------|
| `_initialize_agent_rpc_types()` | Loads `AgentAgentRequest` / `AgentAgentReply` from `datamodel.xml` |
| `_setup_agent_discovery()` | Creates durable `AgentCapability` reader (TRANSIENT_LOCAL + RELIABLE) |
| `_setup_agent_capability_publishing()` | Publishes this agent's `AgentCapability` |
| `_setup_agent_rpc_service()` | Creates `rti.rpc.Replier` for unique per-agent endpoint |
| `send_agent_request()` | Sends `AgentAgentRequest`, waits for `AgentAgentReply` |
| `get_agents_by_capability()` | Filters discovered agents by capability string |
| `find_agents_by_specialization()` | Filters by specialization domain |

Each agent gets a unique RPC endpoint named `AgentService_{agent_id}`, so multiple agents of the same type can coexist without conflict.

---

## Classification

Agent routing uses **pure LLM-based semantic classification** — no rule-based or keyword matching. The LLM receives all agent tools in the unified tool list and decides which to call based on the tool name and description. This was an explicit design decision after rule-based routing caused misclassification bugs.

---

## Full Flow

```
Interface
    │ send_request({"message": "What's the weather in Denver?"})
    ▼
PersonalAssistant (OpenAIGenesisAgent, enable_agent_communication=True)
    │ _ensure_agents_discovered()   → builds agent_cache
    │ _ensure_functions_discovered() → function_cache
    │ _get_all_tool_schemas_for_openai() → [functions] + [agents] + [internal]
    │
    ▼ single LLM call with unified tool list
LLM
    │ chooses: get_weather_info(message="Denver weather")
    ▼
_handle_agent_tool_call()
    │ send_agent_request(target=WeatherAgent, message="Denver weather")
    │ DDS: AgentAgentRequest → AgentAgentReply
    ▼
WeatherAgent
    │ calls OpenWeatherMap API
    │ returns "Current weather in Denver: clear sky, 18°C"
    ▼
PersonalAssistant
    │ feeds result back to LLM → final response
    ▼
Interface ← "The weather in Denver is currently clear sky at 18°C."
```

---

## Enabling It

```python
agent = OpenAIGenesisAgent(
    model_name="gpt-4o",
    agent_name="MyAgent",
    enable_agent_communication=True
)
```

No other configuration needed. Agents join and leave the network dynamically; the tool list updates on each LLM call.

---

## Related

- [Function Discovery](function-discovery.md) — how `@genesis_function` services are discovered (same DDS pattern)
- [Agent Hierarchy](agent-hierarchy.md) — abstract methods to implement for a new provider
- [Reference: Function Call Flow](../reference/function-call-flow.md) — end-to-end sequence diagram

---

*(c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.*

*RTI grants Licensee a license to use, modify, compile, and create derivative works of the Software. Licensee has the right to distribute object form only for use with RTI products. The Software is provided "as is", with no warranty of any type, including any warranty for fitness for any purpose. RTI is under no obligation to maintain or support the Software. RTI shall not be liable for any incidental or consequential damages arising out of the use or inability to use the software.*
