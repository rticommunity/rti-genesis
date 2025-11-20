# GENESIS Monitoring System

Note (2025-08-28): The unified monitoring implementation centers on the GraphMonitor abstraction, which publishes durable nodes (GenesisGraphNode) and edges (GenesisGraphEdge) for discovery, state (DISCOVERING/READY/BUSY), and relationships (service→function, interface→agent). Activity overlays (ChainEvent) correlate multi-hop flows (classification, tool calls, results). See code in `genesis_lib/graph_monitoring.py`, `genesis_lib/graph_state.py`, and monitored variants: `genesis_lib/monitored_agent.py`, `genesis_lib/monitored_interface.py`, `genesis_lib/enhanced_service_base.py`.

## Overview
The GENESIS monitoring system provides visibility into distributed system events using DDS. It captures function discovery, calls, results, and status events across all services through three main components:
- `FunctionRegistry` (`genesis_lib/function_discovery.py`): Handles function registration and event publishing
- `EnhancedServiceBase` (`genesis_lib/enhanced_service_base.py`): Provides standardized monitoring interface
- `ExtendedMonitoringApp` (`genesis_monitor_extended.py`): Terminal-based monitoring visualization

## Event Types
Defined in `datamodel.xml:121-128`:
```xml
<enum name="EventType">
    <enumerator name="FUNCTION_DISCOVERY"/>  <!-- Function availability events -->
    <enumerator name="FUNCTION_CALL"/>      <!-- Function invocation events -->
    <enumerator name="FUNCTION_RESULT"/>    <!-- Function return value events -->
    <enumerator name="FUNCTION_STATUS"/>    <!-- Error and status events -->
    <enumerator name="FUNCTION_DISCOVERY_V2"/> <!-- Enhanced discovery (future use) -->
</enum>
```

## Entity Types
Defined in `datamodel.xml:130-135`:
```xml
<enum name="EntityType">
    <enumerator name="FUNCTION"/>
    <enumerator name="AGENT"/>
    <enumerator name="SPECIALIZED_AGENT"/>
    <enumerator name="INTERFACE"/>
</enum>
```

## Event Structure
Defined in `datamodel.xml:137-147`:
```xml
<struct name="MonitoringEvent">
    <member name="event_id" type="string" key="true" stringMaxLength="128"/>
    <member name="timestamp" type="int64"/>
    <member name="event_type" type="nonBasic" nonBasicTypeName="EventType"/>
    <member name="entity_type" type="nonBasic" nonBasicTypeName="EntityType"/>
    <member name="entity_id" type="string" stringMaxLength="128"/>
    <member name="metadata" type="string" stringMaxLength="2048"/>
    <member name="call_data" type="string" stringMaxLength="8192"/>
    <member name="result_data" type="string" stringMaxLength="8192"/>
    <member name="status_data" type="string" stringMaxLength="2048"/>
</struct>
```

## Key Components

### 1. FunctionRegistry (genesis_lib/function_discovery.py)
- Handles function registration and discovery events
- Manages function lifecycle and availability tracking
- Publishes monitoring events through DDS
- Key methods:
  - `register_function()`: Registers a function with metadata
  - `publish_monitoring_event()`: Publishes events to DDS
  - `handle_capability_advertisement()`: Processes function advertisements

### 2. EnhancedServiceBase (genesis_lib/enhanced_service_base.py)
- Base class for all GENESIS services
- Provides standardized monitoring interface
- Automatic event publication through function wrappers
- Key methods:
  - `register_enhanced_function()`: Registers functions with monitoring
  - `publish_function_call_event()`: Publishes function invocations
  - `publish_function_result_event()`: Publishes function results
  - `publish_function_error_event()`: Publishes function errors

### 3. ExtendedMonitoringApp (genesis_monitor_extended.py)
- Terminal-based monitoring visualization
- Real-time event display with color coding
- Filtering and search capabilities
- Key features:
  - Color-coded event types (see `EVENT_COLOR_PAIRS`)
  - Interactive filtering (source, level, event type)
  - Scrollable event history
  - Detailed event inspection

## Event Flow Examples

### 1. Function Registration and Discovery
From `enhanced_service_base.py:_advertise_functions()`:
```python
metadata = {
    "service": self.__class__.__name__,
    "is_first_function": i == 1,
    "is_last_function": i == total_functions,
    "total_functions": total_functions,
    "current_function": i,
    "provider_id": self.app_guid,
    "function_name": func_name,
    "capabilities": capabilities,
    "schema": schema
}

self.registry.publish_monitoring_event(
    event_type="FUNCTION_DISCOVERY",
    function_name=func_name,
    metadata=metadata,
    status_data={"status": "published", "state": "available"}
)
```

### 2. Function Call Events
From `enhanced_service_base.py:publish_function_call_event()`:
```python
self.registry.publish_monitoring_event(
    event_type="FUNCTION_CALL",
    function_name=function_name,
    call_data=call_data,
    request_info=request_info
)
```

### 3. Function Result Events
From `enhanced_service_base.py:publish_function_result_event()`:
```python
self.registry.publish_monitoring_event(
    event_type="FUNCTION_RESULT",
    function_name=function_name,
    result_data=result_data,
    request_info=request_info
)
```

## Visualization Properties

### Terminal Interface (genesis_monitor_extended.py)
- Color coding (defined in `EVENT_COLOR_PAIRS`):
  - FUNCTION_DISCOVERY: Blue
  - FUNCTION_CALL: White
  - FUNCTION_RESULT: Green
  - FUNCTION_STATUS: Cyan
  - UNKNOWN: Default color

### Keyboard Controls
- `q`: Quit
- `p`: Pause/resume
- `c`: Clear entries
- `l`: Change log level
- `s`: Change source filter
- `e`: Change event type filter
- `t`: Change entity type filter
- `d`: Toggle details
- `↑/↓`: Scroll through history

## Best Practices

### 1. Service Implementation
- Extend `EnhancedServiceBase` for consistent monitoring
- Use `register_enhanced_function()` for all function registrations
- Include proper metadata in function registrations
- Implement error handling with monitoring events

### 2. Event Publishing
- Use the provided event publishing methods:
  ```python
  self.publish_function_call_event()
  self.publish_function_result_event()
  self.publish_function_error_event()
  ```
- Include detailed metadata for event correlation
- Use consistent event types across services
- Follow the event ordering pattern (discovery -> call -> result)

### 3. DDS Configuration
- Use dedicated DDS participant for monitoring
- Configure appropriate QoS settings:
  ```python
  writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
  writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
  ```
- Handle participant lifecycle properly

### 4. Resource Management
- Clean up DDS resources on shutdown
- Implement proper error handling
- Use thread-safe event processing
- Maintain reasonable event history size

## Example Service Integration
See `test_functions/calculator_service.py` and `test_functions/letter_counter_service.py` for complete examples of services implementing the monitoring system.

## Running the Monitor
```bash
source setup.sh && python genesis_monitor_extended.py [--domain <id>] [--level <LOG_LEVEL>] [--max-entries <count>]
```

## Implementation Notes
- Monitor uses curses for terminal UI
- Events are stored in memory with configurable limit
- Supports filtering by multiple criteria
- Real-time updates with configurable refresh rate
- Thread-safe event processing

## Node Events (Component Status)

### Function Application Nodes
```
[timestamp] [NODE.FUNCTION_APP] Calculator app (id=uuid) joined domain
[timestamp] [STATE.AVAILABLE] Function app (id=uuid) advertised function 'add'
[timestamp] [STATE.AVAILABLE] Function app (id=uuid) ready with functions [add, subtract, multiply, divide]
[timestamp] [STATE.OFFLINE] Function app (id=uuid) disconnected
```

### Agent Nodes
```
[timestamp] [NODE.AGENT] Basic agent (id=uuid) joined domain
[timestamp] [NODE.AGENT] Specialized agent (id=uuid, type=image_processing) joined domain
[timestamp] [STATE.AVAILABLE] Agent (id=uuid) advertised capabilities [capability1, capability2]
[timestamp] [STATE.OFFLINE] Agent (id=uuid) disconnected
```

### Interface Nodes
```
[timestamp] [NODE.INTERFACE] Web interface (id=uuid) joined domain
[timestamp] [NODE.INTERFACE] CLI interface (id=uuid) joined domain
[timestamp] [STATE.OFFLINE] Interface (id=uuid) disconnected
```

## Edge Events (Interactions)

### Discovery Events
```
[timestamp] [EDGE.DISCOVERY] Interface (id=uuid1) discovered Agent (id=uuid2)
[timestamp] [EDGE.DISCOVERY] Agent (id=uuid1) discovered Function app (id=uuid2)
```

### Connection Events
```
[timestamp] [EDGE.CONNECTION] Interface (id=uuid1) connected to Agent (id=uuid2)
[timestamp] [EDGE.CONNECTION] Interface (id=uuid1) disconnected from Agent (id=uuid2)
```

### Request Flow Events
```
[timestamp] [EDGE.REQUEST] Interface (id=uuid1) -> Agent (id=uuid2) request initiated (request_id=uuid)
[timestamp] [EDGE.REQUEST] Agent (id=uuid) processing request (request_id=uuid)
[timestamp] [EDGE.RESPONSE] Agent (id=uuid1) -> Interface (id=uuid2) request completed (request_id=uuid)
```

### Function Call Events
```
[timestamp] [EDGE.CALL] Agent (id=uuid1) -> Function (id=uuid2) call initiated: add(x=10, y=5) (call_id=uuid)
[timestamp] [EDGE.CALL] Function (id=uuid) processing call (call_id=uuid)
[timestamp] [EDGE.RESPONSE] Function (id=uuid1) -> Agent (id=uuid2) result: 15 (call_id=uuid)
```

## System Health Events
```
[timestamp] [STATE.AVAILABLE] Component (type=agent, id=uuid) heartbeat received
[timestamp] [STATE.DEGRADED] Component (type=function_app, id=uuid) experiencing high latency
[timestamp] [STATE.OFFLINE] Component (type=interface, id=uuid) not responding
```

## Event Data Structure
Each event message contains:
- Timestamp (ISO format)
- Primary category (NODE, EDGE, STATE)
- Subcategory (specific event type)
- Source component ID
- Target component ID (for edges)
- Event-specific data
- Correlation IDs (request_id, call_id) for tracing
- Additional metadata

## Visualization Properties

### Node Properties
- Shape: Different shapes for FUNCTION_APP, AGENT, INTERFACE
- Color:
  - Green: STATE.AVAILABLE
  - Yellow: STATE.DEGRADED
  - Red: STATE.OFFLINE
  - Gray: Unknown/Initial state

### Edge Properties
- Style:
  - Dotted: EDGE.DISCOVERY
  - Solid: EDGE.CONNECTION
  - Animated: Active EDGE.REQUEST or EDGE.CALL
- Color:
  - Blue: Discovery/Connection
  - Green: Successful requests/calls
  - Red: Failed requests/calls
  - Yellow: In-progress requests/calls

## Usage Examples

### Complete System Interaction
```
[12:00:00.000] [NODE.FUNCTION_APP] Calculator app (id=calc-123) joined domain
[12:00:00.001] [STATE.AVAILABLE] Function app (id=calc-123) ready with functions [add, subtract]
[12:00:00.002] [NODE.AGENT] Basic agent (id=agent-456) joined domain
[12:00:00.003] [EDGE.DISCOVERY] Agent (id=agent-456) discovered Function app (id=calc-123)
[12:00:00.004] [NODE.INTERFACE] Web interface (id=web-789) joined domain
[12:00:00.005] [EDGE.DISCOVERY] Interface (id=web-789) discovered Agent (id=agent-456)
[12:00:00.006] [EDGE.CONNECTION] Interface (id=web-789) connected to Agent (id=agent-456)
[12:00:00.007] [EDGE.REQUEST] Interface (id=web-789) -> Agent (id=agent-456) request initiated (request_id=req-001)
[12:00:00.008] [EDGE.CALL] Agent (id=agent-456) -> Function (id=calc-123) call initiated: add(x=10, y=5) (call_id=call-001)
[12:00:00.009] [EDGE.RESPONSE] Function (id=calc-123) -> Agent (id=agent-456) result: 15 (call_id=call-001)
[12:00:00.010] [EDGE.RESPONSE] Agent (id=agent-456) -> Interface (id=web-789) request completed (request_id=req-001)
``` 
