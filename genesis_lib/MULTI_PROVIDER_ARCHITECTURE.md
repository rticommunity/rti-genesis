# Multi-Provider LLM Architecture

## Overview

Genesis supports multiple LLM providers (OpenAI, Anthropic, Gemini, etc.) through a three-layer architecture that separates concerns:

1. **GenesisAgent**: Provider-agnostic discovery and routing
2. **MonitoredAgent**: Provider-agnostic monitoring and tracing
3. **ProviderAgent**: Provider-specific API calls and schemas

This document explains how to add support for new LLM providers.

## Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ GenesisAgent (agent.py)                                     │
│ - Provider-agnostic tool discovery                          │
│ - Function routing (_call_function, _call_agent, etc.)     │
│ - Internal tool discovery (@genesis_tool)                   │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ inherits
┌─────────────────────────────────────────────────────────────┐
│ MonitoredAgent (monitored_agent.py)                         │
│ - process_request() monitoring wrapper                      │
│ - Graph publishing (_publish_classification_node)           │
│ - Chain tracking (_publish_llm_call_start/complete)         │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ inherits
┌─────────────────────────────────────────────────────────────┐
│ OpenAIGenesisAgent (openai_genesis_agent.py)                │
│ - client.chat.completions.create() calls                    │
│ - OpenAI message format                                     │
│ - _get_all_tool_schemas_for_openai()                        │
└─────────────────────────────────────────────────────────────┘
```

## What Goes Where

### GenesisAgent (Base Class)

**Purpose**: Provider-agnostic functionality that ALL agents need

**Includes**:
- `_get_available_functions()` - Query function registry
- `_get_available_agent_tools()` - Query discovered agents
- `_ensure_internal_tools_discovered()` - Find @genesis_tool methods
- `_call_function()` - Execute function via RPC
- `_call_agent()` - Execute agent-to-agent call
- `_call_internal_tool()` - Execute @genesis_tool method

**Rules**:
- Returns Python dicts, NOT provider-specific formats
- No LLM API calls
- No monitoring/tracing code
- Usable by ANY LLM provider

### MonitoredAgent (Monitoring Layer)

**Purpose**: Add monitoring/tracing to any agent type

**Includes**:
- `_publish_llm_call_start(chain_id, call_id, model_identifier)`
- `_publish_llm_call_complete(chain_id, call_id, model_identifier)`
- `_publish_classification_result(chain_id, call_id, function_name, function_id)`
- `_publish_classification_node(func_name, func_desc, reason)`
- `_publish_agent_chain_event(chain_id, call_id, event_type, source_id, target_id)`
- `execute_function_with_monitoring()` - Wraps function calls with events

**Rules**:
- No LLM-specific code
- Only publishes monitoring events
- Wraps base class methods with tracing
- Reusable across all providers

### ProviderAgent (OpenAI, Anthropic, etc.)

**Purpose**: Provider-specific LLM integration

**Includes**:
- API client calls (e.g., `client.chat.completions.create()`)
- Message format conversion (provider's JSON format)
- Schema generation (e.g., `_get_all_tool_schemas_for_openai()`)
- Provider-specific parameters (e.g., `tool_choice`, `temperature`)

**Rules**:
- Only provider-specific code
- Uses inherited discovery/routing methods
- Uses inherited monitoring methods
- Minimal implementation

## Adding a New Provider

### Step 1: Create Schema Generator

Add to `schema_generators.py`:

```python
class AnthropicSchemaGenerator(SchemaGenerator):
    """Schema generator for Anthropic tool format."""
    
    def generate_tool_schema(self, tool_meta: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Genesis tool metadata to Anthropic format"""
        return {
            "name": tool_meta.get("function_name"),
            "description": tool_meta.get("description"),
            "input_schema": {
                "type": "object",
                "properties": tool_meta.get("parameters", {}),
                "required": tool_meta.get("required", [])
            }
        }
```

### Step 2: Create Provider Agent Class

Create `anthropic_genesis_agent.py`:

```python
#!/usr/bin/env python3
"""
Anthropic Genesis Agent - LLM Provider Implementation

Extends MonitoredAgent to provide Anthropic Claude integration.
Inherits all discovery, routing, and monitoring from base classes.
"""

import anthropic
from genesis_lib.monitored_agent import MonitoredAgent
from genesis_lib.schema_generators import get_schema_generator

class AnthropicGenesisAgent(MonitoredAgent):
    """Agent using Anthropic's Claude API with Genesis capabilities"""
    
    def __init__(self, model_name="claude-3-5-sonnet-20241022", **kwargs):
        super().__init__(
            agent_name=kwargs.get("agent_name", "AnthropicAgent"),
            base_service_name=kwargs.get("base_service_name", "AnthropicChat"),
            **kwargs
        )
        
        # Initialize Anthropic client
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model_name = model_name
    
    def _get_all_tool_schemas_for_anthropic(self):
        """Generate Anthropic tool schemas (functions + agents + internal tools)"""
        schema_generator = get_schema_generator("anthropic")
        
        # Get available tools (inherited from GenesisAgent)
        functions = self._get_available_functions()
        agents = self._get_available_agent_tools()
        internal_tools = getattr(self, 'internal_tools_cache', {})
        
        # Convert to Anthropic format
        tools = []
        
        # Add function tools
        for name, info in functions.items():
            tools.append({
                "name": name,
                "description": info["description"],
                "input_schema": info["schema"]
            })
        
        # Add agent tools (universal schema)
        for tool_name, agent_info in agents.items():
            tools.append({
                "name": tool_name,
                "description": agent_info.get("tool_description", "Agent tool"),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Query for the agent"}
                    },
                    "required": ["message"]
                }
            })
        
        # Add internal tools
        for tool_name, tool_info in internal_tools.items():
            schema = schema_generator.generate_tool_schema(tool_info["metadata"])
            tools.append(schema)
        
        return tools
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process request using Anthropic Claude API"""
        user_message = request.get("message", "")
        
        # Ensure discovery (inherited from GenesisAgent)
        await self._ensure_internal_tools_discovered()
        
        # Get tools in Anthropic format
        tools = self._get_all_tool_schemas_for_anthropic()
        
        # Monitoring: LLM call start (inherited from MonitoredAgent)
        chain_id = str(uuid.uuid4())
        call_id = str(uuid.uuid4())
        self._publish_llm_call_start(chain_id, call_id, f"anthropic.{self.model_name}")
        
        # Call Anthropic API
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=4096,
            messages=[{"role": "user", "content": user_message}],
            tools=tools if tools else None
        )
        
        # Monitoring: LLM call complete
        self._publish_llm_call_complete(chain_id, call_id, f"anthropic.{self.model_name}")
        
        # Handle tool calls if present
        if response.stop_reason == "tool_use":
            for content_block in response.content:
                if content_block.type == "tool_use":
                    tool_name = content_block.name
                    tool_args = content_block.input
                    
                    # Route tool call (inherited from GenesisAgent)
                    functions = self._get_available_functions()
                    agents = self._get_available_agent_tools()
                    
                    if tool_name in functions:
                        result = await self._call_function(tool_name, **tool_args)
                    elif tool_name in agents:
                        result = await self._call_agent(tool_name, **tool_args)
                    elif tool_name in getattr(self, 'internal_tools_cache', {}):
                        result = await self._call_internal_tool(tool_name, **tool_args)
                    else:
                        result = f"Tool not found: {tool_name}"
                    
                    # Send tool result back to Claude (continuation not shown)
                    # ... multi-turn conversation handling ...
        
        # Extract text response
        text_response = next(
            (block.text for block in response.content if hasattr(block, "text")),
            "No response"
        )
        
        return {"message": text_response, "status": 0}
```

### Step 3: Register Schema Generator

In `schema_generators.py`, add to the registry:

```python
_schema_generators = {
    "openai": OpenAISchemaGenerator(),
    "anthropic": AnthropicSchemaGenerator(),  # Add this
    "local": LocalLLMSchemaGenerator(),
    "auto": OpenAISchemaGenerator()
}
```

### Step 4: Export from __init__.py

```python
from .anthropic_genesis_agent import AnthropicGenesisAgent

__all__ = [
    'OpenAIGenesisAgent',
    'AnthropicGenesisAgent',  # Add this
    # ...
]
```

## Common Pitfalls to Avoid

### ❌ DON'T: Put Provider Code in Base Classes

```python
# BAD: In GenesisAgent
def _get_available_functions_for_openai(self):
    # Don't put OpenAI-specific code in base class!
```

### ✅ DO: Use Provider-Agnostic Base Methods

```python
# GOOD: In OpenAIGenesisAgent
def _get_all_tool_schemas_for_openai(self):
    functions = self._get_available_functions()  # Generic
    # Convert to OpenAI format here
```

### ❌ DON'T: Duplicate Monitoring Code

```python
# BAD: In AnthropicGenesisAgent
def process_request(self, request):
    # Publishing monitoring events directly
    self.graph.publish_node(...)  # NO!
```

### ✅ DO: Use Inherited Monitoring Methods

```python
# GOOD: In AnthropicGenesisAgent
def process_request(self, request):
    self._publish_llm_call_start(...)  # Inherited from MonitoredAgent
```

### ❌ DON'T: Reimplement Tool Routing

```python
# BAD: Custom routing in provider agent
if tool_name.startswith("agent_"):
    # Custom agent routing logic
```

### ✅ DO: Use Inherited Routing

```python
# GOOD: Use base class methods
if tool_name in self._get_available_agent_tools():
    result = await self._call_agent(tool_name, **args)
```

## Provider Comparison Table

| Feature | GenesisAgent | MonitoredAgent | OpenAI | Anthropic | Future |
|---------|--------------|----------------|--------|-----------|--------|
| Discovery | ✅ Implements | Uses parent | Uses inherited | Uses inherited | Uses inherited |
| Routing | ✅ Implements | Uses parent | Uses inherited | Uses inherited | Uses inherited |
| Monitoring | ❌ None | ✅ Implements | Uses inherited | Uses inherited | Uses inherited |
| API Calls | ❌ None | ❌ None | ✅ Implements | ✅ Implements | ✅ Implements |
| Schemas | ❌ Generic | ❌ Generic | ✅ OpenAI format | ✅ Anthropic format | ✅ Provider format |

## Testing New Providers

1. **Discovery Test**: Verify functions/agents are discovered
2. **Routing Test**: Verify tools are routed correctly
3. **Monitoring Test**: Verify events are published
4. **Integration Test**: End-to-end with real API

Example test:

```python
async def test_anthropic_agent():
    agent = AnthropicGenesisAgent(
        agent_name="TestAgent",
        model_name="claude-3-5-sonnet-20241022"
    )
    
    # Test discovery (should work via inheritance)
    functions = agent._get_available_functions()
    assert isinstance(functions, dict)
    
    # Test schema generation (provider-specific)
    schemas = agent._get_all_tool_schemas_for_anthropic()
    assert all("name" in s and "input_schema" in s for s in schemas)
    
    # Test process_request (full integration)
    response = await agent.process_request({"message": "Hello!"})
    assert response["status"] == 0
```

## Benefits of This Architecture

1. **Minimal Code per Provider**: ~200 lines instead of 650+
2. **Consistent Behavior**: All providers use same discovery/routing
3. **Easy Testing**: Inherited methods are already tested
4. **Clear Boundaries**: Each layer has one responsibility
5. **Future-Proof**: Add new providers without changing base classes

## Questions?

See the implementation in:
- `genesis_lib/agent.py` (GenesisAgent base)
- `genesis_lib/monitored_agent.py` (MonitoredAgent wrapper)
- `genesis_lib/openai_genesis_agent.py` (Reference implementation)
- `genesis_lib/schema_generators.py` (Schema converters)

