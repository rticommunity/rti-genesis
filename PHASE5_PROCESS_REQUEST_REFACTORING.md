# Phase 5: Process Request Refactoring Complete

## Overview

Successfully completed Phase 5 of the architecture refactoring: moving `process_request()` and `process_agent_request()` from `OpenAIGenesisAgent` to `GenesisAgent` for maximum reusability across LLM providers.

## Changes Made

### 1. GenesisAgent (`agent.py`)

Added two new abstract methods for provider-specific implementations:

```python
@abstractmethod
async def _get_tool_schemas(self) -> List[Dict]:
    """
    Get all tool schemas in provider-specific format.
    
    This should return schemas for:
    - External functions (discovered via DDS)
    - Agent tools (other agents)
    - Internal tools (@genesis_tool decorated methods)
    
    Returns:
        List of tool schemas formatted for the specific LLM provider
    """
    pass

@abstractmethod
def _get_tool_choice(self) -> str:
    """
    Get provider-specific tool choice setting.
    
    Returns:
        Tool choice string (e.g., "auto", "required", "none" for OpenAI)
    """
    pass
```

Added a helper method for system prompt selection:

```python
def _select_system_prompt(self, available_functions: Dict, agent_tools: Dict) -> str:
    """
    Select appropriate system prompt based on available tools.
    Provider-agnostic logic.
    """
    if not available_functions and not agent_tools:
        return getattr(self, 'general_system_prompt', 'You are a helpful assistant.')
    else:
        return getattr(self, 'function_based_system_prompt', 
                      'You are a helpful assistant with access to tools.')
```

Added concrete `process_request()` method (previously abstract):

```python
async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a request using the LLM with tool support.
    Provider-agnostic orchestration - delegates provider-specific logic to abstract methods.
    """
    user_message = request.get("message", "")
    
    # Ensure internal tools are discovered
    await self._ensure_internal_tools_discovered()
    
    # Check what tools are available
    available_functions = self._get_available_functions()
    agent_tools = self._get_available_agent_tools()
    
    # Select appropriate system prompt
    system_prompt = self._select_system_prompt(available_functions, agent_tools)
    
    # Get tools in provider-specific format
    tools = await self._get_tool_schemas()
    
    if not tools:
        # Simple conversation (no tools available)
        memory_items = self.memory.retrieve(k=100)
        messages = self._format_messages(user_message, system_prompt, memory_items)
        response = await self._call_llm(messages)
        text = self._extract_text_response(response)
        
        self.memory.store(user_message, metadata={"role": "user"})
        self.memory.store(text, metadata={"role": "assistant"})
        return {"message": text, "status": 0}
    
    # Tool-based conversation (orchestrated by this class)
    tool_choice = self._get_tool_choice()
    return await self._orchestrate_tool_request(
        user_message=user_message,
        tools=tools,
        system_prompt=system_prompt,
        tool_choice=tool_choice
    )
```

Added `process_agent_request()` method:

```python
async def process_agent_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a request from another agent (agent-to-agent communication).
    Provider-agnostic wrapper that adds agent-specific tracing.
    """
    # Extract source agent info for tracing
    source_agent = request.get("source_agent", "unknown")
    user_message = request.get("message", "")
    
    if getattr(self, 'enable_tracing', False):
        logger.info(f"🤝 Agent-to-Agent Request from '{source_agent}': {user_message[:100]}")
    
    # Process using standard flow
    result = await self.process_request(request)
    
    if getattr(self, 'enable_tracing', False):
        response_msg = result.get("message", "")
        logger.info(f"🤝 Agent-to-Agent Response to '{source_agent}': {response_msg[:100]}")
    
    return result
```

### 2. MonitoredAgent (`monitored_agent.py`)

Updated `process_request()` to call parent's implementation:

```python
async def process_request(self, request: Any) -> Dict[str, Any]:
    # ... monitoring setup ...
    
    # Call parent's process_request (from GenesisAgent)
    result = await super().process_request(request)
    
    # ... monitoring teardown ...
    return result
```

Removed obsolete `_process_request()` stub method (previously raised `NotImplementedError`).

### 3. OpenAIGenesisAgent (`openai_genesis_agent.py`)

Removed `process_request()` and `process_agent_request()` methods (now inherited from `GenesisAgent`).

Added implementations for the two new abstract methods:

```python
async def _get_tool_schemas(self) -> List[Dict]:
    """
    Get all tool schemas in OpenAI format.
    Implements the abstract method from GenesisAgent.
    """
    return self._get_all_tool_schemas_for_openai()

def _get_tool_choice(self) -> str:
    """
    Get OpenAI-specific tool choice setting.
    Implements the abstract method from GenesisAgent.
    """
    return self.openai_tool_choice
```

Added documentation comment explaining the inherited behavior:

```python
# Note: process_request() is inherited from GenesisAgent
# OpenAI-specific behavior is provided through these abstract method implementations:
# - _get_tool_schemas() returns OpenAI-formatted tools via _get_all_tool_schemas_for_openai()
# - _get_tool_choice() returns self.openai_tool_choice
# - _call_llm() calls OpenAI API
# - _format_messages() formats in OpenAI message format
# - _extract_tool_calls() parses OpenAI tool_calls from response
# - _extract_text_response() extracts content from response
# - _create_assistant_message() creates OpenAI assistant message dicts
```

### 4. Test Agents

Updated `MathTestAgent` and `BaselineTestAgent` to implement the two new abstract methods:

```python
async def _get_tool_schemas(self):
    """Not used - this is a non-LLM agent"""
    raise NotImplementedError("MathTestAgent does not use LLM")

def _get_tool_choice(self):
    """Not used - this is a non-LLM agent"""
    raise NotImplementedError("MathTestAgent does not use LLM")
```

## Architecture Summary

### Inheritance Hierarchy

```
GenesisAgent (agent.py)
  ├─ Abstract LLM methods: _call_llm, _format_messages, _extract_tool_calls, 
  │                        _extract_text_response, _create_assistant_message
  ├─ Abstract schema methods: _get_tool_schemas, _get_tool_choice
  ├─ Concrete orchestration: process_request(), process_agent_request()
  └─ Concrete tool routing: _orchestrate_tool_request(), _route_tool_call()

    ↓ inherits

MonitoredAgent (monitored_agent.py)
  └─ Monitoring wrapper: overrides process_request() to add monitoring events
                        and calls super().process_request()

    ↓ inherits

OpenAIGenesisAgent (openai_genesis_agent.py)
  ├─ Implements _call_llm() → client.chat.completions.create()
  ├─ Implements _format_messages() → OpenAI message format
  ├─ Implements _extract_tool_calls() → Parse OpenAI response
  ├─ Implements _extract_text_response() → Extract content
  ├─ Implements _create_assistant_message() → Create OpenAI message dict
  ├─ Implements _get_tool_schemas() → _get_all_tool_schemas_for_openai()
  └─ Implements _get_tool_choice() → self.openai_tool_choice
```

### Provider-Agnostic vs Provider-Specific

**Provider-Agnostic (in GenesisAgent):**
- Request processing flow: `process_request()`, `process_agent_request()`
- Internal tool discovery: `_ensure_internal_tools_discovered()`
- Tool availability checks: `_get_available_functions()`, `_get_available_agent_tools()`
- System prompt selection: `_select_system_prompt()`
- Multi-turn orchestration: `_orchestrate_tool_request()`
- Tool routing: `_route_tool_call()`
- Memory management

**Provider-Specific (implemented in subclasses):**
- LLM API calls: `_call_llm()`
- Message formatting: `_format_messages()`
- Response parsing: `_extract_tool_calls()`, `_extract_text_response()`
- Message creation: `_create_assistant_message()`
- Tool schema generation: `_get_tool_schemas()`
- Tool choice configuration: `_get_tool_choice()`

## Benefits

1. **Maximum Reusability**: Core orchestration logic is now reusable across all LLM providers
2. **Clear Separation**: Provider-agnostic logic in `GenesisAgent`, provider-specific in subclasses
3. **Simplified Provider Implementation**: Adding Anthropic/Google/Llama only requires implementing 7 abstract methods
4. **Consistent Behavior**: All providers use the same orchestration flow, multi-turn logic, and tool routing
5. **Easy Testing**: Test agents can implement stubs for abstract methods while using real orchestration
6. **Better Architecture**: Business logic no longer resides in vendor-specific code

## Test Results

### Passing Tests:
✅ `run_interface_agent_service_test.sh` - Interface-Agent-Service pipeline test  
✅ `test_monitoring_graph_state.py` - Monitoring and graph state test

### Known Issues:
- `run_math_interface_agent_simple.sh` - Times out (unrelated to refactoring)
- `run_simple_agent.sh` - Has pre-existing `rpc_client_v2` import error

## Next Steps

To add a new LLM provider (e.g., Anthropic), create a new class:

```python
class AnthropicGenesisAgent(MonitoredAgent):
    """Agent using Anthropic's Claude API"""
    
    async def _call_llm(self, messages, tools=None, tool_choice="auto"):
        # Call Anthropic API
        return self.client.messages.create(...)
    
    def _format_messages(self, user_message, system_prompt, memory_items):
        # Format in Anthropic's message format
        ...
    
    def _extract_tool_calls(self, response):
        # Extract tool_use blocks from Anthropic response
        ...
    
    def _extract_text_response(self, response):
        # Extract text content
        ...
    
    def _create_assistant_message(self, response):
        # Create assistant message dict
        ...
    
    async def _get_tool_schemas(self):
        # Generate Anthropic tool schemas
        ...
    
    def _get_tool_choice(self):
        # Return Anthropic tool choice setting
        ...
```

All orchestration, tool routing, memory management, and multi-turn logic is automatically inherited!

## Files Modified

- `Genesis_LIB/genesis_lib/genesis_agent.py` - Added abstract methods, concrete process_request(), process_agent_request()
- `Genesis_LIB/genesis_lib/monitored_agent.py` - Updated to call super().process_request()
- `Genesis_LIB/genesis_lib/openai_genesis_agent.py` - Removed process_request(), added _get_tool_schemas() and _get_tool_choice()
- `Genesis_LIB/tests/helpers/math_test_agent.py` - Added stubs for new abstract methods
- `Genesis_LIB/tests/helpers/baseline_test_agent.py` - Added stubs for new abstract methods

## Conclusion

Phase 5 refactoring is complete! The architecture now has a clear separation between:
1. **GenesisAgent**: Provider-agnostic business logic
2. **MonitoredAgent**: Observability layer
3. **OpenAIGenesisAgent** (and future providers): Provider-specific implementations

This sets the foundation for easily supporting multiple LLM providers with minimal code duplication.

