# New LLM Provider Implementation Guide

## Quick Start

To add a new LLM provider (Anthropic, Google, Llama, etc.) to Genesis, you only need to:

1. **Copy** `openai_genesis_agent.py` to `[provider]_genesis_agent.py`
2. **Implement** 7 abstract methods (~50-150 lines of code)
3. **Test** using existing test suite

That's it! You automatically get: discovery, routing, orchestration, monitoring, multi-turn, and memory.

## The 7 Required Methods

### 1. `async def _call_llm(messages, tools, tool_choice)` 
**What**: Call your provider's API  
**Example OpenAI**: `return self.client.chat.completions.create(...)`  
**Example Anthropic**: `return self.client.messages.create(...)`  

### 2. `def _format_messages(user_message, system_prompt, memory_items)`
**What**: Convert conversation to provider's message format  
**Example OpenAI**: `[{"role": "system|user|assistant", "content": "..."}]`  
**Example Anthropic**: Separate system parameter, only user/assistant in messages  

### 3. `def _extract_tool_calls(response)`
**What**: Parse tool calls from response  
**Return**: `[{"id": "...", "name": "...", "arguments": {...}}]` or `None`  
**OpenAI**: `response.choices[0].message.tool_calls`  
**Anthropic**: Filter `response.content` blocks by `type="tool_use"`  

### 4. `def _extract_text_response(response)`
**What**: Extract text from response  
**Return**: String  
**OpenAI**: `response.choices[0].message.content`  
**Anthropic**: Join text blocks from `response.content`  

### 5. `def _create_assistant_message(response)`
**What**: Create message dict for conversation history  
**Return**: Message dict in provider's format  
**Critical**: Include `tool_calls` if present (needed for multi-turn)  

### 6. `async def _get_tool_schemas()`
**What**: Return all tool schemas in provider's format  
**Pattern**: Delegate to aggregator method (e.g., `_get_all_tool_schemas_for_[provider]`)  

### 7. `def _get_tool_choice()`
**What**: Return tool choice setting  
**OpenAI**: `"auto"` | `"required"` | `"none"`  
**Anthropic**: `{"type": "auto"}` | `{"type": "any"}` | `{"type": "tool", "name": "..."}`  

## Provider-Specific Schema Generation

You'll also need to create schema conversion methods (called by #6 above):

### Functions → Provider Format
```python
def _get_function_schemas_for_[provider](self):
    """Convert discovered functions to provider's tool format"""
    available_functions = self._get_available_functions()  # From parent
    # Convert each to provider format and return list
```

### Agents → Provider Format  
```python
def _convert_agents_to_[provider]_tools(self):
    """Convert discovered agents to provider's tool format"""
    agent_schemas = self._get_agent_tool_schemas()  # From parent
    # Wrap in provider format and return list
```

### Internal Tools → Provider Format
```python
def _get_internal_tool_schemas_for_[provider](self):
    """Generate provider schemas for @genesis_tool methods"""
    schema_generator = get_schema_generator("[provider]")  # May need to create
    # Generate schema for each internal tool and return list
```

### Aggregator Method
```python
def _get_all_tool_schemas_for_[provider](self):
    """Combine all tool types"""
    return (
        self._get_function_schemas_for_[provider]() +
        self._convert_agents_to_[provider]_tools() +
        self._get_internal_tool_schemas_for_[provider]()
    )
```

## Tool Schema Format Examples

### OpenAI Format
```python
{
    "type": "function",
    "function": {
        "name": "add",
        "description": "Add two numbers",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "number", "description": "First number"},
                "y": {"type": "number", "description": "Second number"}
            },
            "required": ["x", "y"]
        }
    }
}
```

### Anthropic Format
```python
{
    "name": "add",
    "description": "Add two numbers",
    "input_schema": {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "First number"},
            "y": {"type": "number", "description": "Second number"}
        },
        "required": ["x", "y"]
    }
}
```

### Google Gemini Format
```python
{
    "name": "add",
    "description": "Add two numbers",
    "parameters": {
        "type_": "OBJECT",
        "properties": {
            "x": {"type_": "NUMBER", "description": "First number"},
            "y": {"type_": "NUMBER", "description": "Second number"}
        },
        "required": ["x", "y"]
    }
}
```

## What You Get for Free

By extending `MonitoredAgent`, you automatically get:

### From GenesisAgent
- ✅ `process_request()` - Main request processing
- ✅ `process_agent_request()` - Agent-to-agent wrapper
- ✅ `_orchestrate_tool_request()` - Multi-turn orchestration
- ✅ `_route_tool_call()` - Routes to functions/agents/internal tools
- ✅ `_call_function()` - Execute external functions via RPC
- ✅ `_call_agent()` - Call other agents
- ✅ `_call_internal_tool()` - Execute @genesis_tool methods
- ✅ `_ensure_internal_tools_discovered()` - Auto-discover internal tools
- ✅ `_get_available_functions()` - Get discovered functions
- ✅ `_get_available_agent_tools()` - Get discovered agents
- ✅ `_get_agent_tool_schemas()` - Universal agent schemas

### From MonitoredAgent
- ✅ State machine (DISCOVERING → READY → BUSY → READY/DEGRADED)
- ✅ Graph topology publishing (nodes and edges)
- ✅ Event publishing (chain start/complete, LLM calls)
- ✅ Error recovery and state management
- ✅ Agent communication protocol

### From GenesisApp (via MonitoredAgent)
- ✅ DDS participant and domain management
- ✅ RPC service registration
- ✅ Advertisement publishing
- ✅ Content filtering by tags
- ✅ Memory adapter integration
- ✅ Function registry sharing

## __init__ Pattern

```python
def __init__(self, model_name="[default-model]", ...):
    # Store config
    self.enable_tracing = enable_tracing
    self.model_config = {"model_name": model_name, ...}
    
    # Initialize parent (gets you everything!)
    super().__init__(
        agent_name=agent_name,
        base_service_name=base_service_name,
        agent_type="AGENT",  # or "SPECIALIZED_AGENT"
        ...
    )
    
    # Initialize provider client
    self.api_key = os.environ.get("[PROVIDER]_API_KEY")
    self.client = ProviderClient(api_key=self.api_key)
    
    # Set tool choice
    self.provider_tool_choice = os.getenv("GENESIS_TOOL_CHOICE", "auto")
    
    # Initialize helpers (optional)
    self.generic_client = GenericFunctionClient(
        function_registry=self.app.function_registry
    )
    
    # Set system prompts (optional, can use defaults)
    self.function_based_system_prompt = "..."
    self.general_system_prompt = "..."
```

## Testing Your Implementation

Use the existing test suite - just swap the agent class:

```python
# tests/test_my_provider.py
from genesis_lib.my_provider_genesis_agent import MyProviderGenesisAgent

async def test_basic():
    agent = MyProviderGenesisAgent(agent_name="TestAgent")
    response = await agent.process_request({"message": "What is 2+2?"})
    assert response["status"] == 0
    assert "4" in response["message"]
    await agent.close()

# Or run existing integration tests:
# cd tests/active
# export MY_PROVIDER_API_KEY=...
# ./run_interface_agent_service_test.sh  # Should just work!
```

## Common Pitfalls

### 1. Tool Messages Without tool_calls
**Problem**: OpenAI/compatible providers require tool messages to follow an assistant message with `tool_calls`  
**Solution**: Make sure `_create_assistant_message()` includes `tool_calls` if present

### 2. Wrong Message Roles
**Problem**: Provider rejects messages with incorrect roles  
**Solution**: Check provider docs - some use "assistant", others "model", etc.

### 3. Tool Schema Mismatch
**Problem**: LLM can't parse your tool schemas  
**Solution**: Follow provider's exact schema format (see examples above)

### 4. Forgot to Call super()
**Problem**: Agent doesn't appear in discovery or monitoring breaks  
**Solution**: Always call `super().__init__(...)` in `__init__` and `await super().close()` in `close()`

### 5. Arguments as JSON String
**Problem**: `_extract_tool_calls()` returns arguments as string instead of dict  
**Solution**: Parse JSON: `json.loads(tc.function.arguments)` (OpenAI does this)

## File Structure

```
genesis_lib/
├── genesis_agent.py            # GenesisAgent (base class)
├── monitored_agent.py          # MonitoredAgent (monitoring layer)
├── openai_genesis_agent.py     # OpenAI implementation (TEMPLATE)
├── anthropic_genesis_agent.py  # Your Anthropic implementation
├── gemini_genesis_agent.py     # Your Google implementation
└── schema_generators.py        # Schema generators (may need to extend)
```

## Schema Generator Integration

If your provider needs custom schema generation:

```python
# In schema_generators.py, add:
class MyProviderSchemaGenerator(SchemaGenerator):
    def generate_tool_schema(self, metadata: Dict) -> Dict:
        """Convert Genesis metadata to provider format"""
        return {
            "name": metadata["name"],
            "description": metadata["description"],
            # ... provider-specific format
        }

# Register it:
def get_schema_generator(provider: str) -> SchemaGenerator:
    generators = {
        "openai": OpenAISchemaGenerator,
        "anthropic": AnthropicSchemaGenerator,
        "myprovider": MyProviderSchemaGenerator,  # Add yours
    }
    return generators.get(provider, OpenAISchemaGenerator)()
```

## Environment Variables

Your implementation should respect:

- `[PROVIDER]_API_KEY` - Provider API key (required)
- `GENESIS_TOOL_CHOICE` - Tool choice setting (optional, default "auto")
- `GENESIS_DOMAIN_ID` - DDS domain ID (optional, default 0)
- `GENESIS_LOG_LEVEL` - Logging level (optional, default INFO)

## Documentation

The `openai_genesis_agent.py` file is HEAVILY documented with:
- Architecture overview
- What you inherit for free
- What you must implement
- Provider-specific examples for Anthropic, Google, etc.
- Implementation notes and pitfalls
- Multi-turn conversation flow
- Message format requirements

**Use it as your reference implementation!**

## Summary

Creating a new provider = **~50-150 lines of provider-specific code**

You get ~2000 lines of battle-tested infrastructure for free:
- Discovery (functions, agents, internal tools)
- Multi-turn orchestration
- Tool routing and execution
- Memory management
- Monitoring and observability
- Agent communication
- RPC infrastructure

This is the power of Genesis's architecture! 🚀




