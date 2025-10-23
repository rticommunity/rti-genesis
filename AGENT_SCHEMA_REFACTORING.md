# Agent Tool Schema Refactoring

## Issue
The universal agent tool schema generation was incorrectly placed in `OpenAIGenesisAgent` when it should be in `GenesisAgent` since it's provider-agnostic.

## Problem
```python
# BEFORE: In OpenAIGenesisAgent (WRONG)
def _convert_agents_to_tools(self):
    """Generate UNIVERSAL agent schemas in OpenAI format"""
    # This was doing TWO things:
    # 1. Creating universal agent schemas (provider-agnostic)
    # 2. Wrapping in OpenAI format (provider-specific)
```

The universal agent schema pattern (all agents accept a `message` parameter) should work for **any** LLM provider, not just OpenAI.

## Solution

### 1. Added `_get_agent_tool_schemas()` to GenesisAgent
**File:** `genesis_lib/genesis_agent.py`

```python
def _get_agent_tool_schemas(self) -> List[Dict[str, Any]]:
    """
    Get provider-agnostic tool schemas for discovered agents.
    
    This uses the UNIVERSAL AGENT SCHEMA pattern where all agents
    accept a 'message' parameter regardless of their internal implementation.
    
    Returns:
        List of agent tool schemas with 'name', 'description', and 'parameters'
    """
    agent_schemas = []
    
    available_agent_tools = self._get_available_agent_tools()
    for tool_name, agent_info in available_agent_tools.items():
        agent_name = agent_info.get('agent_name', 'Unknown Agent')
        capabilities = agent_info.get('capabilities', [])
        
        # Create capability-based description
        if capabilities:
            capability_desc = f"Specialized agent for {', '.join(capabilities[:3])}"
            if len(capabilities) > 3:
                capability_desc += f" and {len(capabilities)-3} more capabilities"
        else:
            capability_desc = f"General purpose agent ({agent_name})"
        
        # UNIVERSAL AGENT SCHEMA - provider-agnostic
        agent_schemas.append({
            "name": tool_name,
            "description": f"{capability_desc}. Send natural language queries and receive responses.",
            "parameters": {
                "message": {
                    "type": "string",
                    "description": "Natural language query or request to send to the agent"
                }
            },
            "required": ["message"]
        })
    
    return agent_schemas
```

### 2. Simplified `_convert_agents_to_tools()` in OpenAIGenesisAgent
**File:** `genesis_lib/openai_genesis_agent.py`

```python
def _convert_agents_to_tools(self):
    """
    Convert agent schemas to OpenAI tool format.
    
    Gets universal agent schemas from parent class and wraps them
    in OpenAI's tool format.
    """
    # Get universal agent schemas from parent (provider-agnostic)
    agent_schemas = self._get_agent_tool_schemas()
    
    # Wrap in OpenAI-specific format
    openai_tools = []
    for schema in agent_schemas:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": schema["name"],
                "description": schema["description"],
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": schema["parameters"]["message"]
                    },
                    "required": schema["required"]
                }
            }
        })
    
    return openai_tools
```

## Benefits

### 1. Clear Separation of Concerns
- **GenesisAgent**: Universal agent discovery and schema generation (provider-agnostic)
- **OpenAIGenesisAgent**: OpenAI-specific formatting only

### 2. Reusability
Other LLM providers can now easily use the same universal agent schemas:

```python
class AnthropicGenesisAgent(MonitoredAgent):
    def _convert_agents_to_tools(self):
        """Convert agent schemas to Anthropic tool format"""
        # Get universal schemas from parent
        agent_schemas = self._get_agent_tool_schemas()
        
        # Wrap in Anthropic format
        anthropic_tools = []
        for schema in agent_schemas:
            anthropic_tools.append({
                "name": schema["name"],
                "description": schema["description"],
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message": schema["parameters"]["message"]
                    },
                    "required": schema["required"]
                }
            })
        
        return anthropic_tools
```

### 3. Consistency
The universal agent schema pattern is now clearly defined in one place and inherited by all providers.

## Test Results

✅ **All tests passing:**
```
./run_triage_suite.sh:
- ✅ Stage 1: Memory recall
- ✅ Stage 2: Agent↔Agent communication
- ✅ Stage 3: Interface→Agent→Service
- ✅ Stage 4a: Monitoring graph-state invariants
- ✅ Stage 4a.2: Interface→Agent monitoring
```

## Files Modified

1. **`genesis_lib/genesis_agent.py`**
   - Added `_get_agent_tool_schemas()` method (~40 lines)
   - Generates provider-agnostic agent tool schemas

2. **`genesis_lib/openai_genesis_agent.py`**
   - Simplified `_convert_agents_to_tools()` method (50 → 30 lines)
   - Now just wraps universal schemas in OpenAI format

## Architecture Impact

This completes the multi-provider architecture refactoring:

```
GenesisAgent
  ├─ Discovery: _get_available_agent_tools()
  ├─ Universal Schemas: _get_agent_tool_schemas()  ← NEW!
  └─ Orchestration: _orchestrate_tool_request()

MonitoredAgent
  └─ Monitoring wrapper

OpenAIGenesisAgent
  ├─ Format wrapper: _convert_agents_to_tools()     ← SIMPLIFIED!
  └─ OpenAI API calls
```

---

**Date:** October 20, 2025  
**Related:** REFACTORING_COMPLETE_PHASE4.md, MULTI_PROVIDER_ARCHITECTURE.md

