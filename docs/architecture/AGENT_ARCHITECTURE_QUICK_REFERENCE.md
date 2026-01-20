# Agent Architecture Quick Reference

## Abstract Methods Hierarchy

### GenesisAgent (Base Class)

**Abstract methods that MUST be implemented by concrete LLM providers:**

```python
# Core LLM interaction
async def _call_llm(messages, tools=None, tool_choice="auto") -> Any
def _format_messages(user_message, system_prompt, memory_items) -> List[Dict]
def _extract_tool_calls(response) -> Optional[List[Dict]]
def _extract_text_response(response) -> str
def _create_assistant_message(response) -> Dict

# Provider-specific tool configuration
async def _get_tool_schemas() -> List[Dict]
def _get_tool_choice() -> str
```

**Concrete methods (already implemented, inherited by all agents):**

```python
# Request processing
async def process_request(request) -> Dict[str, Any]
async def process_agent_request(request) -> Dict[str, Any]

# Tool orchestration
async def _orchestrate_tool_request(user_message, tools, system_prompt, tool_choice) -> Dict[str, Any]
async def _route_tool_call(tool_name, tool_args) -> Any

# Tool discovery and management
async def _ensure_internal_tools_discovered()
def _get_available_functions() -> Dict
def _get_available_agent_tools() -> Dict
def _get_agent_tool_schemas() -> List[Dict]

# Tool execution
async def _call_function(function_name, **kwargs)
async def _call_agent(agent_name, message, **kwargs)
async def _call_internal_tool(tool_name, **kwargs)

# Utilities
def _select_system_prompt(available_functions, agent_tools) -> str
def _trace_llm_call(context, tools, user_message, tool_responses=None)
def _trace_llm_response(response, provider_name="LLM")
```

### MonitoredAgent (Monitoring Layer)

**Overridden methods (adds monitoring):**

```python
async def process_request(request) -> Dict[str, Any]
    # Publishes BUSY/READY/DEGRADED states
    # Calls super().process_request(request)
```

**Additional monitoring methods:**

```python
def _publish_llm_call_start(chain_id, call_id, context)
def _publish_llm_call_complete(chain_id, call_id, context)
def _publish_classification_node(func_name, func_desc, reason)
```

### OpenAIGenesisAgent (OpenAI Implementation)

**Implements all abstract methods:**

```python
# LLM interaction (OpenAI-specific)
async def _call_llm(messages, tools=None, tool_choice="auto"):
    return self.client.chat.completions.create(
        model=self.model_config['model_name'],
        messages=messages,
        tools=tools,
        tool_choice=tool_choice
    )

def _format_messages(user_message, system_prompt, memory_items):
    # Returns OpenAI message format: [{"role": ..., "content": ...}, ...]
    
def _extract_tool_calls(response):
    # Parses response.choices[0].message.tool_calls
    
def _extract_text_response(response):
    # Returns response.choices[0].message.content
    
def _create_assistant_message(response):
    # Creates {"role": "assistant", "content": ..., "tool_calls": ...}

# Tool configuration (OpenAI-specific)
async def _get_tool_schemas():
    return self._get_all_tool_schemas_for_openai()
    
def _get_tool_choice():
    return self.openai_tool_choice  # "auto", "required", or "none"
```

**OpenAI-specific helper methods:**

```python
def _get_all_tool_schemas_for_openai() -> List[Dict]
def _get_function_schemas_for_openai(relevant_functions=None) -> List[Dict]
def _convert_agents_to_tools() -> List[Dict]
def _get_internal_tool_schemas_for_openai() -> List[Dict]
```

## Request Flow

### Interface → Agent Request Flow

```
1. Interface.send_broadcast_request({"message": "What is 2+2?"})
   ↓
2. MonitoredAgent.process_request(request)
   ├─ Publishes BUSY state
   ├─ Calls super().process_request(request)
   ↓
3. GenesisAgent.process_request(request)
   ├─ Discovers internal tools
   ├─ Gets available functions/agents
   ├─ Selects system prompt
   ├─ Calls _get_tool_schemas() [OpenAI implementation]
   ├─ If no tools: simple conversation
   │  ├─ Calls _format_messages() [OpenAI implementation]
   │  ├─ Calls _call_llm() [OpenAI implementation]
   │  └─ Calls _extract_text_response() [OpenAI implementation]
   ├─ If tools: calls _orchestrate_tool_request()
   ↓
4. GenesisAgent._orchestrate_tool_request(...)
   ├─ Formats messages with memory
   ├─ Calls _call_llm() with tools [OpenAI implementation]
   ├─ Calls _extract_tool_calls() [OpenAI implementation]
   ├─ If tool calls: executes via _route_tool_call()
   │  ├─ Calls external functions via RPC
   │  ├─ Calls other agents via agent-to-agent
   │  └─ Calls internal tools via direct method call
   ├─ Multi-turn loop until text response
   └─ Returns {"message": ..., "status": 0}
   ↓
5. MonitoredAgent.process_request() continues
   ├─ Publishes READY state
   └─ Returns result
```

### Agent → Agent Request Flow

```
1. Agent A calls Agent B via _call_agent("AgentB", message="Help me")
   ↓
2. GenesisAgent.process_agent_request(request)
   ├─ Logs agent-to-agent tracing
   ├─ Calls process_request(request)  [same flow as above]
   └─ Logs response tracing
```

## Adding a New LLM Provider

To add support for Anthropic Claude:

```python
from genesis_lib.monitored_agent import MonitoredAgent
import anthropic

class AnthropicGenesisAgent(MonitoredAgent):
    """Agent using Anthropic's Claude API"""
    
    def __init__(self, agent_name, **kwargs):
        super().__init__(agent_name=agent_name, **kwargs)
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model_name = "claude-3-5-sonnet-20241022"
        self.anthropic_tool_choice = {"type": "auto"}
    
    # Implement 7 abstract methods:
    
    async def _call_llm(self, messages, tools=None, tool_choice="auto"):
        kwargs = {"model": self.model_name, "messages": messages, "max_tokens": 4096}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        return self.client.messages.create(**kwargs)
    
    def _format_messages(self, user_message, system_prompt, memory_items):
        # Anthropic uses system parameter separately
        messages = []
        for entry in memory_items:
            role = entry.get("metadata", {}).get("role", "user")
            messages.append({"role": role, "content": str(entry["item"])})
        messages.append({"role": "user", "content": user_message})
        return messages
    
    def _extract_tool_calls(self, response):
        # Anthropic uses "tool_use" content blocks
        tool_calls = []
        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input
                })
        return tool_calls if tool_calls else None
    
    def _extract_text_response(self, response):
        # Extract text content blocks
        text_blocks = [b.text for b in response.content if b.type == "text"]
        return " ".join(text_blocks)
    
    def _create_assistant_message(self, response):
        # Anthropic returns content blocks directly
        return {"role": "assistant", "content": response.content}
    
    async def _get_tool_schemas(self):
        # Generate Anthropic tool schemas
        return self._get_all_tool_schemas_for_anthropic()
    
    def _get_tool_choice(self):
        return self.anthropic_tool_choice
    
    # Add helper method for Anthropic tool schema format
    def _get_all_tool_schemas_for_anthropic(self):
        # Convert Genesis schemas to Anthropic format
        # Anthropic format: {"name": "...", "description": "...", "input_schema": {...}}
        ...
```

That's it! All orchestration, tool routing, memory management, and multi-turn logic is inherited.

## Key Design Principles

1. **Single Responsibility**: Each class has one job
   - `GenesisAgent`: Core business logic
   - `MonitoredAgent`: Observability
   - `OpenAIGenesisAgent`: OpenAI-specific implementation

2. **Open/Closed Principle**: Open for extension (add new providers), closed for modification (no need to change base classes)

3. **Liskov Substitution**: Any `GenesisAgent` subclass can be used interchangeably

4. **Dependency Inversion**: `GenesisAgent` depends on abstractions (abstract methods), not concrete implementations

5. **Template Method Pattern**: `process_request()` is the template method that calls abstract methods at the right times

## Common Patterns

### Pattern 1: Tool-Free Conversation

```python
# In process_request():
if not tools:
    messages = self._format_messages(user_message, system_prompt, memory)
    response = await self._call_llm(messages)
    text = self._extract_text_response(response)
    return {"message": text, "status": 0}
```

### Pattern 2: Tool-Based Multi-Turn

```python
# In _orchestrate_tool_request():
response = await self._call_llm(messages, tools, tool_choice)
tool_calls = self._extract_tool_calls(response)

if tool_calls:
    for tool_call in tool_calls:
        result = await self._route_tool_call(tool_call['name'], tool_call['arguments'])
        # Add to conversation and continue...
```

### Pattern 3: Error Handling

```python
# MonitoredAgent wraps execution with error handling:
try:
    result = await super().process_request(request)
    self.graph.publish_node(..., state=STATE["READY"])
except Exception as e:
    self.graph.publish_node(..., state=STATE["DEGRADED"])
    raise
```

## Testing

### Unit Testing a Provider

```python
# Mock the LLM API
agent._call_llm = AsyncMock(return_value=mock_response)

# Test orchestration (inherited, should work)
result = await agent.process_request({"message": "test"})
assert result["status"] == 0

# Test provider-specific formatting
messages = agent._format_messages("hello", "system", [])
assert messages[0]["role"] == "system"  # Check provider format
```

### Integration Testing

```python
# Real LLM API with real tools
agent = OpenAIGenesisAgent(agent_name="TestAgent")
result = await agent.process_request({"message": "What is 2+2?"})
assert "4" in result["message"]
```


---
*Copyright (c) 2025, RTI & Jason Upchurch*
