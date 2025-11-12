# Phase 4 Implementation Status

## Completed Steps

### ✅ Phase 1: Abstract Methods Added to GenesisAgent
- Added `_call_llm()` abstract method
- Added `_format_messages()` abstract method
- Added `_extract_tool_calls()` abstract method
- Added `_extract_text_response()` abstract method

### ✅ Phase 2: Orchestration Added to GenesisAgent
- Added `_orchestrate_tool_request()` method (150 lines of provider-agnostic logic)
- Added enhanced `_route_tool_call()` method  for clean tool routing

### ✅ Phase 3: Monitoring Wrapper Added to MonitoredAgent
- Added `_orchestrate_tool_request()` wrapper with monitoring events
- Wraps parent orchestration with `_publish_llm_call_start/complete()`

### ✅ Phase 4a: Abstract Methods Implemented in OpenAIGenesisAgent
- Implemented `_call_llm()` - OpenAI API call
- Implemented `_format_messages()` - OpenAI message format
- Implemented `_extract_tool_calls()` - Parse OpenAI tool calls
- Implemented `_extract_text_response()` - Extract text from response

### ⏸️ Phase 4b: PENDING - Simplify process_request()

The 600-line `process_request()` method needs to be replaced with a ~60 line simplified version.

## What Needs to Change in process_request()

**Current:** 600 lines with all orchestration logic inline
**Target:** ~60 lines that delegates to inherited orchestration

### The Simplified Version Should Be:

```python
async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
    """OpenAI-specific request processing using inherited orchestration"""
    user_message = request.get("message", "")
    logger.debug(f"===== TRACING: Processing request: {user_message} =====")
    
    try:
        # Enhanced tracing
        if self.enable_tracing:
            self._trace_discovery_status("BEFORE PROCESSING")
        
        # Ensure internal tools are discovered
        await self._ensure_internal_tools_discovered()
        
        # Check what tools are available
        available_functions = self._get_available_functions()
        agent_tools = self._get_available_agent_tools()
        
        # Select system prompt
        if not available_functions and not agent_tools:
            system_prompt = self.general_system_prompt
        else:
            system_prompt = self.function_based_system_prompt
        
        if self.enable_tracing:
            self._trace_discovery_status("AFTER DISCOVERY")
        
        # Get tools in OpenAI format
        tools = self._get_all_tool_schemas_for_openai()
        
        if not tools:
            # Simple conversation (no tools available)
            logger.debug("===== TRACING: No tools available, using simple conversation =====")
            
            messages = self._format_messages(user_message, system_prompt, self.memory.retrieve(k=100))
            response = await self._call_llm(messages)
            text = self._extract_text_response(response)
            
            self.memory.store(user_message, metadata={"role": "user"})
            self.memory.store(text, metadata={"role": "assistant"})
            return {"message": text, "status": 0}
        
        # Tool-based conversation (orchestrated by parent class)
        logger.debug(f"===== TRACING: Using tool-based orchestration with {len(tools)} tools =====")
        
        result = await self._orchestrate_tool_request(
            user_message=user_message,
            tools=tools,
            system_prompt=system_prompt,
            tool_choice=self.openai_tool_choice
        )
        
        if self.enable_tracing:
            self._trace_discovery_status("AFTER PROCESSING")
        
        return result
            
    except Exception as e:
        logger.error(f"===== TRACING: Error processing request: {str(e)} =======")
        logger.error(traceback.format_exc())
        return {"message": f"Error: {str(e)}", "status": 1}
```

## Status

**You are currently in ASK MODE**

To complete Phase 4b (replacing the 600-line method), you need to switch to AGENT MODE so I can make the large file edit.

The infrastructure is 95% complete:
- ✅ Base class has orchestration
- ✅ Monitoring wrapper exists
- ✅ Abstract methods implemented
- ⏸️ Just need to simplify process_request() (requires agent mode for large edit)

## Testing After Completion

After the edit is made:
```bash
cd tests/active
./run_interface_agent_service_test.sh
```

Should see identical behavior but with 80% less code in OpenAIGenesisAgent!

