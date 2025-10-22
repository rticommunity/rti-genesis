# Critical Monitoring Fix - Function Discovery Topology Publishing

## The Problem

When running a large network (20 services, 80 functions), the monitoring UI only showed 1 node (the PersonalAssistant agent) instead of the expected topology with services, functions, and connections.

### Root Cause

During the refactoring to make DDS the single source of truth for function discovery, we broke the bridge between:
1. **Discovery Layer** (DDS → FunctionRegistry)
2. **Monitoring Layer** (Graph topology for visualization)

**What Happened:**
- `FunctionRegistry.handle_advertisement()` correctly updated `discovered_functions{}` when DDS advertisements arrived ✅
- BUT `publish_discovered_functions()` was NEVER CALLED ❌
- Result: Functions were discovered but NEVER published to graph topology
- Monitoring UI showed only agents, no functions/services/connections

### Why This Matters

In a distributed system monitoring/management UI, you need to see:
- What services are running
- What functions each service provides
- Which agents can call which functions
- Network topology and dependencies
- DDS RPC connection paths

Without graph topology publishing:
- ❌ No function nodes visible
- ❌ No AGENT→FUNCTION edges
- ❌ No SERVICE→FUNCTION edges
- ❌ No connection topology
- ❌ Impossible to debug or manage large networks

## The Fix

### 1. Added Discovery Callback Registration

In `MonitoredAgent._initialize_function_client()`:
```python
# Register callback to publish graph topology when functions are discovered
if hasattr(self.app, 'function_registry') and self.app.function_registry:
    self.app.function_registry.add_discovery_callback(self._on_function_discovered)
```

### 2. Created Bridge Method

New `MonitoredAgent._on_function_discovered()` method:
- Invoked by FunctionRegistry when DDS advertisement arrives
- Converts single function to list format
- Calls `publish_discovered_functions()` to publish graph topology

### 3. Documented Critical Role

Added comprehensive documentation to `publish_discovered_functions()` explaining:
- Why it's critical for network monitoring
- What topology events it publishes
- The complete call chain from DDS to visualization
- What breaks without it

## The Complete Flow (Fixed)

```
Service starts
    ↓
Service advertises functions via DDS
    ↓
DDS delivers to GenesisAdvertisementListener.on_data_available()
    ↓
FunctionRegistry.handle_advertisement()
    ├─ Updates discovered_functions{} (source of truth)
    ├─ Sets _discovery_event
    └─ Calls discovery_callbacks
        ↓
        MonitoredAgent._on_function_discovered()  ← NEW CALLBACK
        ↓
        MonitoredAgent.publish_discovered_functions()
        ↓
        GraphMonitor publishes:
        ├─ Function nodes (with metadata)
        ├─ AGENT→FUNCTION edges
        ├─ REQUESTER→PROVIDER edges
        └─ EXPLICIT_CONNECTION edges
        ↓
        GraphSubscriber receives topology events
        ↓
        Monitoring UI shows complete network topology ✅
```

## What Gets Published

For each discovered function:
1. **Function Node**: Component with metadata (name, description, schema, provider_id)
2. **AGENT→FUNCTION Edge**: Shows which agents can call this function
3. **REQUESTER→PROVIDER Edges**: DDS RPC connection topology
4. **EXPLICIT_CONNECTION Edges**: Direct connections
5. **Updated Agent State**: READY with discovered function count

## Testing

Run the full topology test:
```bash
feature_development/interface_abstraction/start_topology.sh \
  --agents 10 --services 20 --interfaces 1 -t 180 --force
```

Expected results:
- ~20 SERVICE nodes
- ~80 FUNCTION nodes
- ~10 AGENT nodes  
- Multiple INTERFACE nodes
- SERVICE→FUNCTION edges
- AGENT→FUNCTION edges
- INTERFACE→AGENT edges

## Files Modified

1. **monitored_agent.py**:
   - `_initialize_function_client()`: Register discovery callback
   - `_on_function_discovered()`: New bridge method
   - `publish_discovered_functions()`: Added comprehensive documentation

## Architecture Principle

**DDS is the source of truth for discovery, but monitoring requires explicit topology publishing.**

- Discovery: Passive DDS listeners update internal state
- Monitoring: Active publishing of topology events for visualization
- Bridge: Discovery callbacks trigger monitoring publications

This separation allows:
- Clean discovery logic (DDS-focused)
- Flexible monitoring (can be disabled/customized)
- Independent evolution of both concerns

## Related Issues

This same pattern may need to be applied to:
- Agent discovery (agent-to-agent topology)
- Interface discovery (interface-to-agent topology)
- Service lifecycle events (service startup/shutdown)

Check that all discovery systems have corresponding monitoring callbacks.

