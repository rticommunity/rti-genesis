# Monitoring Chain Events Fix - Agent→Service→Function Tracking

## Issue

The monitoring visualization was only showing request/reply activations from **interfaces to agents**, but not from **agents to services** or **services to functions**. The graph showed the topology (nodes and edges) correctly, but the dynamic request/reply flow was incomplete.

## Root Cause

The `MonitoredAgent` class had helper methods for publishing chain events (`_publish_function_call_start`, `_publish_function_call_complete`), but these were never being called because:

1. **Base Agent Implementation**: The `GenesisAgent._call_function()` method (in `genesis_lib/genesis_agent.py`) directly calls functions via the `FunctionRequester` without any monitoring.

2. **No Override in MonitoredAgent**: The `MonitoredAgent` class didn't override `_call_function()`, so when agents called functions, the base implementation was used with no monitoring events published.

3. **Unused Helper Method**: There was an `execute_function_with_monitoring()` method in `MonitoredAgent`, but it was never called by the actual code paths.

## Solution

Added a `_call_function()` override in `MonitoredAgent` to intercept ALL function calls and add monitoring:

```python
async def _call_function(self, function_name: str, **kwargs) -> Any:
    """
    DECORATOR PATTERN - Monitoring Wrapper for Function Calls
    
    Overrides GenesisAgent._call_function() to add chain event monitoring.
    """
    # Generate IDs for distributed tracing
    chain_id = str(uuid.uuid4())
    call_id = str(uuid.uuid4())
    
    # Lookup function metadata (function_id, provider_id)
    available_functions = self._get_available_functions()
    function_metadata = available_functions.get(function_name, {})
    function_id = function_metadata.get('function_id', function_name)
    provider_id = function_metadata.get('provider_id', None)
    
    # Publish AGENT→FUNCTION and AGENT→SERVICE start events
    self._publish_function_call_start(
        chain_id=chain_id,
        call_id=call_id,
        function_name=function_name,
        function_id=function_id,
        target_provider_id=provider_id,
    )
    
    try:
        # Call parent implementation (actual RPC)
        result = await super()._call_function(function_name, **kwargs)
        
        # Publish completion events
        self._publish_function_call_complete(
            chain_id=chain_id,
            call_id=call_id,
            function_name=function_name,
            function_id=function_id,
            source_provider_id=provider_id,
        )
        
        return result
    except Exception as e:
        logger.error(f"Function call failed: {function_name} - {e}")
        raise
```

## What Gets Published

When an agent calls a function, the following chain events are now published:

### Start Events (via `_publish_function_call_start`):

1. **FUNCTION_CALL_START**: Agent → Function
   - `event_type`: "FUNCTION_CALL_START"
   - `source_id`: Agent ID
   - `target_id`: Function ID
   - Tracks the logical function call

2. **AGENT_TO_SERVICE_START**: Agent → Service (if provider known)
   - `event_type`: "AGENT_TO_SERVICE_START"
   - `source_id`: Agent ID
   - `target_id`: Service ID (provider_id)
   - Tracks the agent-service connection

### Complete Events (via `_publish_function_call_complete`):

1. **FUNCTION_CALL_COMPLETE**: Function → Agent
   - `event_type`: "FUNCTION_CALL_COMPLETE"
   - `source_id`: Function ID
   - `target_id`: Agent ID

2. **AGENT_TO_SERVICE_COMPLETE**: Service → Agent (if provider known)
   - `event_type`: "AGENT_TO_SERVICE_COMPLETE"
   - `source_id`: Service ID
   - `target_id`: Agent ID

## Complete Chain Event Flow

With this fix, the full request/reply chain is now visible:

```
Interface → Agent (INTERFACE_REQUEST_START)
  │
  ├─ Agent → Service (AGENT_TO_SERVICE_START)      ← NEW: Now published
  │  │
  │  ├─ Service executes function
  │  │  └─ Function → Result
  │  │
  │  └─ Service → Agent (AGENT_TO_SERVICE_COMPLETE) ← NEW: Now published
  │
Agent → Interface (INTERFACE_REQUEST_COMPLETE)
```

## Related Changes

### 1. Graph Edge Simplification

In the same update, we also simplified the graph topology visualization:

**Before**: Agents published edges to every individual function they discovered
- Example: 10 agents × 20 services × 4 functions = 800 agent→function edges

**After**: Agents publish edges only to services
- Example: 10 agents × 20 services = 200 agent→service edges
- Service→function edges are still published by services (20 services × 4 functions = 80 edges)
- Total: 280 edges instead of 880 edges (68% reduction)

This makes large topologies much cleaner to visualize while still showing the full path: Agent → Service → Function.

**Changed in**: `genesis_lib/monitored_agent.py`, `publish_discovered_functions()` method (lines 814-831)

### 2. Documentation Updates

Updated the docstring for `publish_discovered_functions()` to reflect the new edge publishing behavior:

```python
**What Gets Published to Graph**:
1. Function nodes (with metadata: name, description, schema, provider_id)
2. AGENT→SERVICE edges (this agent can call functions from this service)
   - Note: We publish agent->service edges instead of agent->function edges
   - This prevents edge explosion (10 agents × 20 services × 4 functions = 800 edges)
   - Service->function edges are already published by MonitoredService
3. REQUESTER→PROVIDER edges (DDS RPC connection topology)
4. EXPLICIT_CONNECTION edges (direct connections)
5. Final READY state for agent (with discovered function count)
```

## Testing

To verify the fix:

1. **Start a topology**:
   ```bash
   cd Genesis_LIB
   ./feature_development/interface_abstraction/start_topology.sh \
     --agents 2 --services 3 --interfaces 1 -t 180
   ```

2. **Start the monitoring server**:
   ```bash
   HOST=0.0.0.0 PORT=5000 python3 feature_development/interface_abstraction/viewer/server.py
   ```

3. **Open browser** to `http://localhost:5000`

4. **Send a request** via the interface that requires function calls

5. **Observe**:
   - Graph shows: Interface nodes, Agent nodes, Service nodes, Function nodes
   - Graph shows edges: Interface→Agent, Agent→Service, Service→Function
   - Activations show: Interface→Agent requests AND Agent→Service requests
   - Timeline shows the full chain: Interface → Agent → Service → Function → Service → Agent → Interface

## Files Modified

- `genesis_lib/monitored_agent.py`:
  - Added `_call_function()` override (lines 1194-1269)
  - Marked `execute_function_with_monitoring()` as deprecated (lines 1271-1304)
  - Simplified `publish_discovered_functions()` to publish agent→service edges (lines 814-831)
  - Updated docstring for `publish_discovered_functions()` (lines 740-748)

## Impact

✅ **Monitoring visualization now shows complete request/reply chains**
✅ **Operators can trace full execution flow from interface → agent → service → function**
✅ **Performance analysis can measure agent→service latency**
✅ **Debugging can identify which services are being called by which agents**
✅ **Graph topology is cleaner with 68% fewer edges in large topologies**

## Notes

- The chain events are published to the unified `Event` DDS topic with `kind=0` (CHAIN)
- Events are volatile (not durable) to avoid historical event buildup
- Each function call gets unique `chain_id` and `call_id` for distributed tracing
- The monitoring is automatic - all subclasses of `MonitoredAgent` (including `OpenAIGenesisAgent`, `AnthropicGenesisAgent`, etc.) get this for free

---

**Date**: October 21, 2025
**Author**: AI Assistant (via Cursor)
**Status**: ✅ Complete


