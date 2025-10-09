# Monitoring Topic Content Filtering Guide

## Overview

The unified monitoring topics are designed with efficient content filtering in mind. Each topic has a `kind` discriminator field that allows subscribers to filter events at the DDS middleware level, reducing network traffic and CPU usage.

---

## GraphTopology Topic (Durable)

### Kind Field
```xml
<enum name="GraphElementKind">
  <enumerator name="NODE" value="0"/>
  <enumerator name="EDGE" value="1"/>
</enum>
```

### Content Filter Examples

#### Subscribe to NODES only:
```python
import rti.connextdds as dds

# Create base topic
topology_topic = dds.DynamicData.Topic(
    participant, "rti/connext/genesis/monitoring/GraphTopology", topology_type
)

# Create filtered topic for NODEs only
node_filter = dds.DynamicData.ContentFilteredTopic(
    topology_topic,
    "NodeFilter",
    dds.Filter("kind = %0", ["0"])  # NODE = 0
)

# Create reader with filtered topic
node_reader = dds.DynamicData.DataReader(
    subscriber=subscriber,
    cft=node_filter,
    qos=reader_qos
)
```

#### Subscribe to EDGES only:
```python
# Create filtered topic for EDGEs only
edge_filter = dds.DynamicData.ContentFilteredTopic(
    topology_topic,
    "EdgeFilter",
    dds.Filter("kind = %0", ["1"])  # EDGE = 1
)

edge_reader = dds.DynamicData.DataReader(
    subscriber=subscriber,
    cft=edge_filter,
    qos=reader_qos
)
```

---

## MonitoringEventUnified Topic (Volatile)

### Kind Field
```xml
<enum name="EventKind">
  <enumerator name="CHAIN" value="0"/>
  <enumerator name="LIFECYCLE" value="1"/>
  <enumerator name="GENERAL" value="2"/>
</enum>
```

### Content Filter Examples

#### Subscribe to CHAIN events only (for activity overlays):
```python
# Create base topic
event_topic = dds.DynamicData.Topic(
    participant, "rti/connext/genesis/monitoring/Event", event_type
)

# Create filtered topic for CHAIN events
chain_filter = dds.DynamicData.ContentFilteredTopic(
    event_topic,
    "ChainEventFilter",
    dds.Filter("kind = %0", ["0"])  # CHAIN = 0
)

chain_reader = dds.DynamicData.DataReader(
    subscriber=subscriber,
    cft=chain_filter,
    qos=reader_qos
)
```

#### Subscribe to LIFECYCLE events only (for node state changes):
```python
# Create filtered topic for LIFECYCLE events
lifecycle_filter = dds.DynamicData.ContentFilteredTopic(
    event_topic,
    "LifecycleEventFilter",
    dds.Filter("kind = %0", ["1"])  # LIFECYCLE = 1
)

lifecycle_reader = dds.DynamicData.DataReader(
    subscriber=subscriber,
    cft=lifecycle_filter,
    qos=reader_qos
)
```

#### Subscribe to GENERAL events only (for logging/monitoring):
```python
# Create filtered topic for GENERAL events
general_filter = dds.DynamicData.ContentFilteredTopic(
    event_topic,
    "GeneralEventFilter",
    dds.Filter("kind = %0", ["2"])  # GENERAL = 2
)

general_reader = dds.DynamicData.DataReader(
    subscriber=subscriber,
    cft=general_filter,
    qos=reader_qos
)
```

#### Subscribe to multiple kinds (CHAIN + LIFECYCLE):
```python
# Create filtered topic for CHAIN and LIFECYCLE events
multi_filter = dds.DynamicData.ContentFilteredTopic(
    event_topic,
    "ChainAndLifecycleFilter",
    dds.Filter("kind = %0 OR kind = %1", ["0", "1"])  # CHAIN OR LIFECYCLE
)

multi_reader = dds.DynamicData.DataReader(
    subscriber=subscriber,
    cft=multi_filter,
    qos=reader_qos
)
```

---

## Benefits of Content Filtering

1. **Reduced Network Traffic**: Middleware filters before sending over network
2. **Lower CPU Usage**: Application doesn't process unwanted events
3. **Better Performance**: Critical for high-frequency event streams
4. **Scalability**: Enables specialized subscribers without overhead

---

## Use Cases

### Graph Viewer (needs topology only):
- Filter: `GraphTopology` with `kind = 0` (NODE) OR `kind = 1` (EDGE)
- No need for volatile events

### Activity Overlay (needs chain events only):
- Filter: `MonitoringEventUnified` with `kind = 0` (CHAIN)
- Shows real-time execution flows

### Health Monitor (needs lifecycle events only):
- Filter: `MonitoringEventUnified` with `kind = 1` (LIFECYCLE)
- Tracks component state changes

### Debug Logger (needs all events):
- Subscribe to unfiltered `MonitoringEventUnified` topic
- Gets all event kinds

---

## Implementation Notes

### In Publishers
- Always set the `kind` field correctly when publishing
- Use the enum constants (not magic numbers):
  ```python
  event["kind"] = 0  # CHAIN
  event["kind"] = 1  # LIFECYCLE
  event["kind"] = 2  # GENERAL
  ```

### In Subscribers
- Use `ContentFilteredTopic` instead of application-level filtering
- Filter expression syntax: `"kind = %0"` with parameter array
- Each ContentFilteredTopic needs a unique name per participant

### Performance Tips
- Content filtering happens at middleware level before deserialization
- Dramatically reduces CPU/memory for high-frequency streams
- Essential for real-time monitoring in production systems

---

## Examples in Codebase

See implementations in:
- `genesis_lib/interface.py` - Agent discovery filtering
- `genesis_lib/agent_communication.py` - Agent advertisement filtering
- `genesis_lib/function_discovery.py` - Function advertisement filtering

All use `ContentFilteredTopic` for efficient discrimination.

---

**Last Updated**: October 2025  
**Status**: Implemented in Phase 1-2 of monitoring consolidation

