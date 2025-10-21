# Tracing Methods Refactoring

## Issue
The tracing methods `_trace_openai_call()` and `_trace_openai_response()` were located in `OpenAIGenesisAgent`, but their functionality is provider-agnostic and would be useful for debugging any LLM provider (Anthropic, Google, etc.).

## Problem
```python
# BEFORE: In OpenAIGenesisAgent (WRONG)
def _trace_openai_call(self, ...):
    """Enhanced tracing: OpenAI API call details"""
    # This logic works for ANY LLM provider!
    logger.debug(f"🚀 TRACE: === CALLING OPENAI API: {context} ===")
    ...

def _trace_openai_response(self, response):
    """Enhanced tracing: OpenAI response analysis"""
    # Accesses OpenAI-specific response format
    if hasattr(response, 'choices') and response.choices:
        message = response.choices[0].message
        ...
```

These methods:
1. Were OpenAI-specific in **name only**
2. Were **not even being called** (dead code after refactoring)
3. Would be **useful for all LLM providers** for debugging

## Solution

### 1. Moved to `GenesisAgent` with Provider-Agnostic Implementation

**File:** `genesis_lib/agent.py`

```python
def _trace_llm_call(self, context: str, tools: List[Dict], user_message: str, 
                    tool_responses: Optional[List[Dict]] = None):
    """
    Enhanced tracing: LLM API call details.
    Provider-agnostic tracing for debugging LLM interactions.
    """
    if not getattr(self, 'enable_tracing', False):
        return
        
    logger.debug(f"🚀 TRACE: === CALLING LLM: {context} ===")
    logger.debug(f"🚀 TRACE: User message: {user_message}")
    
    if tools:
        logger.debug(f"🚀 TRACE: Tools provided: {len(tools)} tools")
        for i, tool in enumerate(tools):
            # Handle different tool schema formats (OpenAI, Anthropic, etc.)
            tool_name = (tool.get('function', {}).get('name') or 
                       tool.get('name', 'Unknown'))
            logger.debug(f"🚀 TRACE: Tool {i+1}: {tool_name}")
    else:
        logger.debug(f"🚀 TRACE: NO TOOLS PROVIDED TO LLM")
    
    if tool_responses:
        logger.debug(f"🚀 TRACE: Tool responses included: {len(tool_responses)} responses")

def _trace_llm_response(self, response: Any, provider_name: str = "LLM"):
    """
    Enhanced tracing: LLM response analysis.
    Provider-agnostic tracing for debugging LLM responses.
    """
    if not getattr(self, 'enable_tracing', False):
        return
        
    logger.debug(f"🎯 TRACE: === {provider_name} RESPONSE RECEIVED ===")
    
    # Try to extract text using the provider's abstract method
    try:
        text = self._extract_text_response(response)
        if text:
            logger.debug(f"🎯 TRACE: Response content length: {len(text)} characters")
            logger.debug(f"🎯 TRACE: Response content preview: {text[:100]}...")
    except Exception:
        logger.debug(f"🎯 TRACE: Could not extract text content")
    
    # Try to extract tool calls using the provider's abstract method
    try:
        tool_calls = self._extract_tool_calls(response)
        if tool_calls:
            logger.debug(f"🎯 TRACE: *** TOOL CALLS DETECTED: {len(tool_calls)} ***")
            for i, tool_call in enumerate(tool_calls):
                logger.debug(f"🎯 TRACE: Tool call {i+1}: {tool_call['name']}")
        else:
            logger.debug(f"🎯 TRACE: *** NO TOOL CALLS - DIRECT RESPONSE ***")
    except Exception:
        logger.debug(f"🎯 TRACE: Could not extract tool calls")
```

### 2. Integrated into Orchestration

The tracing methods are now automatically called in `_orchestrate_tool_request()`:

```python
async def _orchestrate_tool_request(self, user_message: str, tools: List[Dict],
                                    system_prompt: str, tool_choice: str = "auto"):
    # Format messages
    messages = self._format_messages(user_message, system_prompt, memory_items)
    
    # Trace call if enabled
    if getattr(self, 'enable_tracing', False):
        self._trace_llm_call("initial orchestration", tools, user_message)
    
    # Call LLM
    response = await self._call_llm(messages, tools, tool_choice)
    
    # Trace response if enabled
    if getattr(self, 'enable_tracing', False):
        provider_name = self.__class__.__name__.replace("GenesisAgent", "")
        self._trace_llm_response(response, provider_name or "LLM")
    
    # Multi-turn loop also traces each iteration
    ...
```

### 3. Removed from OpenAIGenesisAgent

The old OpenAI-specific methods were deleted since:
1. They weren't being used (dead code)
2. The functionality is now in the base class
3. All providers inherit the same tracing

## Benefits

### 1. Reusability Across Providers
All LLM providers automatically get tracing:

```python
class AnthropicGenesisAgent(MonitoredAgent):
    def __init__(self, enable_tracing=True, ...):
        super().__init__(...)
        self.enable_tracing = enable_tracing  # Automatically uses _trace_llm_call/response!
```

### 2. Provider-Agnostic
- Handles different tool schema formats (OpenAI's nested `function`, Anthropic's flat `name`)
- Uses abstract methods (`_extract_text_response`, `_extract_tool_calls`) to work with any provider
- Gracefully handles extraction failures

### 3. Consistent Debugging
Same tracing format across all providers:
```
🚀 TRACE: === CALLING LLM: initial orchestration ===
🚀 TRACE: Tools provided: 4 tools
🎯 TRACE: === OpenAI RESPONSE RECEIVED ===
🎯 TRACE: *** TOOL CALLS DETECTED: 1 ***
```

### 4. Opt-In via `enable_tracing`
Tracing only activates when `enable_tracing=True`:

```python
# Enable tracing for debugging
agent = OpenAIGenesisAgent(enable_tracing=True)

# Disable for production (default)
agent = OpenAIGenesisAgent(enable_tracing=False)
```

## Test Results

✅ **All tests passing:**
```
./run_interface_agent_service_test.sh: SUCCESS
- Agent discovery: ✅
- Function discovery: ✅
- Tool execution: ✅
- Multi-turn orchestration: ✅
```

## Files Modified

1. **`genesis_lib/agent.py`**
   - Added `_trace_llm_call()` (~35 lines)
   - Added `_trace_llm_response()` (~35 lines)
   - Integrated tracing into `_orchestrate_tool_request()`

2. **`genesis_lib/openai_genesis_agent.py`**
   - Removed `_trace_openai_call()` (dead code)
   - Removed `_trace_openai_response()` (dead code)
   - Net reduction: ~45 lines

## Architecture Impact

```
GenesisAgent
  ├─ Orchestration: _orchestrate_tool_request()
  ├─ Tool routing: _route_tool_call()
  ├─ Tracing: _trace_llm_call()         ← NEW!
  ├─ Tracing: _trace_llm_response()     ← NEW!
  └─ Abstract methods for providers

MonitoredAgent
  ├─ Monitoring wrapper
  └─ Discovery tracing: _trace_discovery_status()

OpenAIGenesisAgent
  ├─ Provider implementations
  └─ (tracing removed - now inherited)  ← CLEANED UP!
```

## Usage Example

```python
# Create agent with tracing enabled
agent = OpenAIGenesisAgent(
    model_name="gpt-4o",
    enable_tracing=True  # Enable detailed LLM call/response tracing
)

# Process request - will automatically log:
# 🚀 TRACE: === CALLING LLM: initial orchestration ===
# 🎯 TRACE: === OpenAI RESPONSE RECEIVED ===
await agent.process_request({"message": "What is 2+2?"})
```

---

**Date:** October 20, 2025  
**Related:** REFACTORING_COMPLETE_PHASE4.md, AGENT_SCHEMA_REFACTORING.md

