# Monitoring Consolidation Bug Fix

## The Problem

After consolidating monitoring topics from separate `GenesisGraphNode`/`GenesisGraphEdge` topics to the unified `GraphTopology` topic, the monitoring viewer stopped seeing SERVICE and FUNCTION nodes. Only AGENT nodes (like PersonalAssistant) were visible.

### Symptoms
- `start_topology.sh --services 20` would start 20 calculator services
- Services would correctly publish via DDS (confirmed with `rtiddsspy`)
- But the monitoring viewer (`server.py`) would show ZERO nodes
- The viewer's log showed: `node_add id=... nodes=1` (only seeing PersonalAssistant)

## Root Cause

**`graph_state.py` was not updated when we consolidated monitoring topics.**

When `GraphMonitor.publish_node()` publishes to the unified `GraphTopology` topic (lines 214-229 of `graph_monitoring.py`), it puts node metadata in **top-level fields**:

```python
topology["element_id"] = component_id
topology["kind"] = 0  # NODE
topology["component_name"] = self._derive_node_name(...)  # ← TOP LEVEL
topology["component_type"] = node_type_str                # ← TOP LEVEL
topology["state"] = state_str                             # ← TOP LEVEL
topology["metadata"] = json.dumps(node_payload)           # ← capabilities in here
```

But `GraphSubscriber._setup_v2_topology_reader()` in `graph_state.py` (lines 283-290) was trying to read these fields from the **`metadata` JSON**:

```python
# WRONG - reading from metadata JSON
node_type = metadata.get("node_type", "UNKNOWN")        # ❌
node_name = metadata.get("node_name", node_id)          # ❌  
node_state = metadata.get("node_state", "UNKNOWN")      # ❌
```

This caused all nodes to have:
- `node_type = "UNKNOWN"`
- `node_name = node_id` (fallback)
- `node_state = "UNKNOWN"`

The viewer's internal graph logic may have been filtering out or mishandling nodes with UNKNOWN types.

## The Fix

Changed `graph_state.py` lines 283-290 to read from the **correct top-level DDS fields**:

```python
# CORRECT - reading from top-level DDS sample fields
node_type = str(data["component_type"]) if data["component_type"] is not None else "UNKNOWN"
node_name = str(data["component_name"]) if data["component_name"] is not None else node_id
node_state = str(data["state"]) if data["state"] is not None else "UNKNOWN"
caps = metadata.get("capabilities", {})  # capabilities ARE in metadata
```

## Files Modified

1. **`genesis_lib/graph_state.py`** (lines 283-290):
   - Fixed `GraphSubscriber._setup_v2_topology_reader()` to read `component_type`, `component_name`, and `state` from top-level DDS fields instead of from the metadata JSON

2. **`genesis_lib/monitored_agent.py`** (lines 378-413):
   - Added explicit logging to `_initialize_function_client()` and `_on_function_discovered()` for debugging
   - (These changes were for debugging and can be kept or removed)

## Testing

### Before Fix
```bash
$ python tests/helpers/monitor_graph_cli.py
Total nodes seen: 1
  - PersonalAssistant (type=AGENT_PRIMARY, ...)
```

### After Fix
```bash
$ ./start_topology.sh --agents 2 --services 3
$ python tests/helpers/monitor_graph_cli.py

Total Nodes: 17
Total Edges: 36

NODES BY TYPE:
   AGENT_PRIMARY        :   2
   FUNCTION             :  12
   SERVICE              :   3

EDGES BY TYPE:
   FUNCTION_CONNECTION            :  24
   SERVICE_TO_FUNCTION            :  12
```

## Monitoring CLI Tool

Created `/Users/jason/Documents/Genesis_rc1/Genesis_LIB/tests/helpers/monitor_graph_cli.py`:
- Real-time graph monitoring tool
- Shows nodes, edges, and topology changes
- Useful for debugging DDS discovery issues
- Based on the same `GraphService` used by `server.py`

### Usage
```bash
python tests/helpers/monitor_graph_cli.py --domain 0 --interval 2 --verbose
```

## Lessons Learned

1. **When refactoring data models, grep for ALL consumers of that data**
   - We updated writers (`graph_monitoring.py`) but not readers (`graph_state.py`)

2. **DDS sample structure != metadata JSON structure**
   - Top-level DDS fields are accessed via `data["field_name"]`
   - Metadata JSON is in `data["metadata"]` as a stringified JSON blob

3. **Create simple CLI test tools for complex systems**
   - `monitor_graph_cli.py` made the bug immediately obvious
   - Much faster than debugging through the web UI

## Related Documentation

- `MONITORING_CONSOLIDATION_VALIDATION.md` - Original consolidation plan
- `MONITORING_CONTENT_FILTERING.md` - Topic filtering strategy
- `V2_MONITORING_USAGE.md` - Unified monitoring API usage

## Verification

To verify the fix is working:

```bash
# Terminal 1: Start monitoring CLI
cd Genesis_LIB
python tests/helpers/monitor_graph_cli.py

# Terminal 2: Start some services and agents
./feature_development/interface_abstraction/start_topology.sh \
  --agents 2 --services 3 --interfaces 0 -t 60

# Watch Terminal 1 - should see all nodes and edges appear
```

Expected output:
- 2 AGENT_PRIMARY nodes
- 3 SERVICE nodes  
- 12 FUNCTION nodes (3 services × 4 functions)
- 12 SERVICE_TO_FUNCTION edges
- 24 FUNCTION_CONNECTION edges (2 agents × 12 functions)

Total: **17 nodes, 36 edges**



