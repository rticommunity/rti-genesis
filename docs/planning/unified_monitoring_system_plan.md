# Genesis Unified Monitoring System Plan

## Executive Summary

The Genesis monitoring system has evolved through multiple iterations, resulting in a disjointed implementation with three different event types (MonitoringEvent, ComponentLifecycleEvent, ChainEvent) and inconsistent patterns. This plan consolidates everything into a unified, graph-based monitoring system that provides:

1. **Real-time network visualization** through node/edge discovery
2. **Complete audit trail** for reinforcement learning and debugging
3. **DDS-native implementation** leveraging RTI DDS Spy for validation
4. **Simplified API** with consistent patterns across all components

## Current State Analysis

### Problems with Current Implementation

1. **Multiple Event Types**:
   - `MonitoringEvent` - Legacy event type still used in some places
   - `ComponentLifecycleEvent` - Newer but overloaded with multiple purposes
   - `ChainEvent` - Separate system for tracking request chains
   - Mixed usage patterns across components

2. **Inconsistent Publishing**:
   - `GraphMonitor` class provides unified interface but not used everywhere
   - Direct DDS publishing still happens in monitored_agent's `_setup_monitoring`
   - Some components publish to multiple topics redundantly

3. **Unclear Durability**:
   - Node/edge discovery should be durable (TRANSIENT_LOCAL)
   - Chain events are currently durable but should be transient
   - Inconsistent QoS settings across publishers

4. **Complex Implementation**:
   - Too many abstraction layers
   - Redundant event publishing (e.g., both GraphMonitor and legacy methods)
   - Difficult to understand what events are published where

## Proposed Unified Design

### Core Principles

1. **Two Primary Topics**:
   - `GenesisGraph` - Durable topic for network structure (nodes/edges)
   - `GenesisActivity` - Transient topic for activity/chain events

2. **Single Publishing API**:
   - All components use `GraphMonitor` class exclusively
   - No direct DDS publishing in application code
   - Consistent patterns across interfaces, agents, and services

3. **Clear Semantics**:
   - Nodes = Components (interfaces, agents, services, functions)
   - Edges = Relationships (can_call, provides, connected_to)
   - Activities = Transient events (requests, responses, chains)

### Data Model (datamodel.xml)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<dds xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:noNamespaceSchemaLocation="http://community.rti.com/schema/7.3.0/rti_dds_qos_profiles.xsd"
     version="7.3.0">
  <type_library name="genesis_lib">

    <!-- Unified Graph Event for persistent network structure -->
    <struct name="GenesisGraphEvent">
      <member name="event_id" type="string" key="true" stringMaxLength="128"/>
      <member name="timestamp" type="int64"/>
      <member name="event_type" type="string" stringMaxLength="32"/> <!-- NODE_STATE, EDGE_STATE -->
      
      <!-- Node information (when event_type = NODE_STATE) -->
      <member name="node_id" type="string" stringMaxLength="128"/>
      <member name="node_type" type="string" stringMaxLength="32"/> <!-- INTERFACE, AGENT, SERVICE, FUNCTION -->
      <member name="node_state" type="string" stringMaxLength="32"/> <!-- ONLINE, READY, BUSY, DEGRADED, OFFLINE -->
      <member name="node_name" type="string" stringMaxLength="256"/>
      <member name="node_metadata" type="string" stringMaxLength="8192"/> <!-- JSON metadata -->
      
      <!-- Edge information (when event_type = EDGE_STATE) -->
      <member name="source_id" type="string" stringMaxLength="128"/>
      <member name="target_id" type="string" stringMaxLength="128"/>
      <member name="edge_type" type="string" stringMaxLength="32"/> <!-- CAN_CALL, PROVIDES, CONNECTED_TO -->
      <member name="edge_state" type="string" stringMaxLength="32"/> <!-- ESTABLISHED, BROKEN -->
      <member name="edge_metadata" type="string" stringMaxLength="2048"/> <!-- JSON metadata -->
    </struct>

    <!-- Activity Event for transient operations -->
    <struct name="GenesisActivityEvent">
      <member name="event_id" type="string" key="true" stringMaxLength="128"/>
      <member name="chain_id" type="string" stringMaxLength="128"/> <!-- Groups related activities -->
      <member name="timestamp" type="int64"/>
      <member name="activity_type" type="string" stringMaxLength="32"/> <!-- REQUEST, RESPONSE, CALL, RESULT, ERROR -->
      
      <!-- Activity participants -->
      <member name="source_id" type="string" stringMaxLength="128"/>
      <member name="source_type" type="string" stringMaxLength="32"/>
      <member name="target_id" type="string" stringMaxLength="128"/>
      <member name="target_type" type="string" stringMaxLength="32"/>
      
      <!-- Activity details -->
      <member name="operation" type="string" stringMaxLength="256"/> <!-- Function name, agent request type, etc -->
      <member name="status" type="int32"/> <!-- 0=success, >0=error -->
      <member name="duration_ms" type="int64"/> <!-- For completed activities -->
      <member name="payload" type="string" stringMaxLength="8192"/> <!-- JSON payload data -->
      <member name="error_message" type="string" stringMaxLength="1024"/>
    </struct>

    <!-- Keep existing types for backward compatibility during migration -->
    <!-- These will be deprecated after migration -->
    
  </type_library>
</dds>
```

### Topic Configuration

1. **GenesisGraph Topic**:
   - Topic Name: `GenesisGraph`
   - Type: `GenesisGraphEvent`
   - Durability: TRANSIENT_LOCAL
   - History: KEEP_LAST with depth 1 per key
   - Reliability: RELIABLE

2. **GenesisActivity Topic**:
   - Topic Name: `GenesisActivity`
   - Type: `GenesisActivityEvent`
   - Durability: VOLATILE
   - History: KEEP_ALL
   - Reliability: RELIABLE

### GraphMonitor API

```python
class GraphMonitor:
    """Unified monitoring interface for Genesis framework"""
    
    def __init__(self, participant: dds.DomainParticipant):
        """Initialize with existing participant"""
        
    # Node Management
    def publish_node_online(self, node_id: str, node_type: str, node_name: str, metadata: dict = None):
        """Publish that a node has come online"""
        
    def publish_node_state(self, node_id: str, state: str, reason: str = None):
        """Update node state (READY, BUSY, DEGRADED, etc)"""
        
    def publish_node_offline(self, node_id: str, reason: str = None):
        """Publish that a node is going offline"""
        
    # Edge Management  
    def publish_edge_established(self, source_id: str, target_id: str, edge_type: str, metadata: dict = None):
        """Publish that an edge has been established"""
        
    def publish_edge_broken(self, source_id: str, target_id: str, reason: str = None):
        """Publish that an edge has been broken"""
        
    # Activity Tracking
    def start_activity(self, activity_type: str, source_id: str, target_id: str, 
                      operation: str, chain_id: str = None) -> str:
        """Start an activity and return activity_id"""
        
    def complete_activity(self, activity_id: str, status: int = 0, 
                         result_payload: dict = None, error_message: str = None):
        """Complete an activity with result"""
        
    def publish_activity(self, activity_type: str, source_id: str, target_id: str,
                        operation: str, payload: dict = None, chain_id: str = None):
        """Publish a standalone activity event"""
```

### GraphMonitor Subscription and Graph Building

The `GraphMonitor` class should also provide subscription capabilities to build and maintain a real-time graph of the Genesis network. This creates a complete bidirectional monitoring solution.

#### Extended GraphMonitor API

```python
class GraphMonitor:
    """Unified monitoring interface for Genesis framework - publishing and subscription"""
    
    def __init__(self, participant: dds.DomainParticipant, enable_subscription: bool = False):
        """
        Initialize with existing participant
        
        Args:
            participant: DDS participant to use
            enable_subscription: If True, subscribes to monitoring topics and builds graph
        """
        # Publishing infrastructure (as above)
        self._setup_publishers()
        
        # Subscription and graph building
        if enable_subscription:
            self._setup_subscribers()
            self._graph = GenesisNetworkGraph()
            self._activity_buffer = deque(maxlen=10000)  # Circular buffer for activities
            self._start_graph_maintenance_thread()
    
    # ========== Subscription API ==========
    
    def get_graph_snapshot(self) -> 'GenesisNetworkGraph':
        """Get current snapshot of the network graph"""
        with self._graph_lock:
            return copy.deepcopy(self._graph)
    
    def get_node(self, node_id: str) -> Optional[NodeInfo]:
        """Get information about a specific node"""
        return self._graph.get_node(node_id)
    
    def get_edges_from(self, node_id: str) -> List[EdgeInfo]:
        """Get all edges originating from a node"""
        return self._graph.get_edges_from(node_id)
    
    def get_edges_to(self, node_id: str) -> List[EdgeInfo]:
        """Get all edges terminating at a node"""
        return self._graph.get_edges_to(node_id)
    
    def get_activities(self, chain_id: str = None, since: datetime = None) -> List[ActivityInfo]:
        """Get activities, optionally filtered by chain_id or time"""
        activities = list(self._activity_buffer)
        if chain_id:
            activities = [a for a in activities if a.chain_id == chain_id]
        if since:
            activities = [a for a in activities if a.timestamp > since]
        return activities
    
    # ========== Graph Export API ==========
    
    def export_graph_json(self) -> str:
        """Export graph as JSON for visualization tools"""
        return self._graph.to_json()
    
    def export_graph_dot(self) -> str:
        """Export graph as Graphviz DOT format"""
        return self._graph.to_dot()
    
    def export_graph_cytoscape(self) -> dict:
        """Export graph in Cytoscape.js format for web visualization"""
        return self._graph.to_cytoscape()
    
    def export_graph_networkx(self) -> 'networkx.Graph':
        """Export as NetworkX graph for analysis"""
        return self._graph.to_networkx()
    
    # ========== Real-time Event Streaming ==========
    
    def add_graph_change_listener(self, callback: Callable[[GraphChangeEvent], None]):
        """Add callback for real-time graph changes"""
        self._graph_change_listeners.append(callback)
    
    def add_activity_listener(self, callback: Callable[[ActivityInfo], None]):
        """Add callback for real-time activity events"""
        self._activity_listeners.append(callback)
    
    def stream_graph_changes(self) -> AsyncIterator[GraphChangeEvent]:
        """Async iterator for graph changes (for web streaming)"""
        queue = asyncio.Queue()
        self.add_graph_change_listener(queue.put_nowait)
        try:
            while True:
                yield await queue.get()
        finally:
            self._graph_change_listeners.remove(queue.put_nowait)
```

#### GenesisNetworkGraph Data Structure

```python
@dataclass
class NodeInfo:
    node_id: str
    node_type: str
    node_name: str
    node_state: str
    last_seen: datetime
    metadata: dict
    
@dataclass
class EdgeInfo:
    source_id: str
    target_id: str
    edge_type: str
    edge_state: str
    established_time: datetime
    metadata: dict

@dataclass
class ActivityInfo:
    event_id: str
    chain_id: str
    timestamp: datetime
    activity_type: str
    source_id: str
    target_id: str
    operation: str
    status: int
    duration_ms: Optional[int]
    payload: dict
    error_message: Optional[str]

class GenesisNetworkGraph:
    """Thread-safe graph representation of Genesis network"""
    
    def __init__(self):
        self._nodes: Dict[str, NodeInfo] = {}
        self._edges: Dict[Tuple[str, str], List[EdgeInfo]] = {}
        self._lock = threading.RLock()
    
    def add_or_update_node(self, node_info: NodeInfo):
        """Add or update a node in the graph"""
        with self._lock:
            self._nodes[node_info.node_id] = node_info
            
    def remove_node(self, node_id: str):
        """Remove a node and all its edges"""
        with self._lock:
            # Remove node
            self._nodes.pop(node_id, None)
            # Remove all edges involving this node
            self._edges = {
                k: v for k, v in self._edges.items() 
                if node_id not in k
            }
            
    def add_edge(self, edge_info: EdgeInfo):
        """Add an edge to the graph"""
        with self._lock:
            key = (edge_info.source_id, edge_info.target_id)
            if key not in self._edges:
                self._edges[key] = []
            self._edges[key].append(edge_info)
            
    def remove_edge(self, source_id: str, target_id: str, edge_type: str = None):
        """Remove an edge from the graph"""
        with self._lock:
            key = (source_id, target_id)
            if edge_type and key in self._edges:
                self._edges[key] = [
                    e for e in self._edges[key] 
                    if e.edge_type != edge_type
                ]
            else:
                self._edges.pop(key, None)
```

#### Web Interface Integration

```python
class GenesisMonitoringWebServer:
    """Web server for real-time monitoring visualization"""
    
    def __init__(self, graph_monitor: GraphMonitor, port: int = 8080):
        self.graph_monitor = graph_monitor
        self.app = FastAPI()
        self._setup_routes()
        
    def _setup_routes(self):
        @self.app.get("/api/graph")
        async def get_graph():
            """Get current graph snapshot"""
            return self.graph_monitor.export_graph_cytoscape()
            
        @self.app.websocket("/api/graph/stream")
        async def stream_graph_changes(websocket: WebSocket):
            """Stream real-time graph updates via WebSocket"""
            await websocket.accept()
            try:
                async for change in self.graph_monitor.stream_graph_changes():
                    await websocket.send_json(change.to_dict())
            except WebSocketDisconnect:
                pass
                
        @self.app.get("/api/activities")
        async def get_activities(chain_id: Optional[str] = None, 
                               since: Optional[datetime] = None):
            """Get recent activities"""
            return [
                a.to_dict() for a in 
                self.graph_monitor.get_activities(chain_id, since)
            ]
            
        @self.app.get("/")
        async def serve_ui():
            """Serve the monitoring UI"""
            return FileResponse("genesis_monitor_ui/index.html")
```

#### Usage Example

```python
# Monitoring producer (in a service/agent)
monitor = GraphMonitor(participant)
monitor.publish_node_online("service_123", "SERVICE", "CalculatorService")

# Monitoring consumer (in a monitoring tool)
monitor = GraphMonitor(participant, enable_subscription=True)

# Get current network state
graph = monitor.get_graph_snapshot()
print(f"Network has {len(graph.nodes)} nodes and {len(graph.edges)} edges")

# Export for visualization
with open("genesis_network.dot", "w") as f:
    f.write(monitor.export_graph_dot())

# Start web interface
web_server = GenesisMonitoringWebServer(monitor)
uvicorn.run(web_server.app, host="0.0.0.0", port=8080)

# Stream updates to external system
async def handle_graph_changes():
    async for change in monitor.stream_graph_changes():
        await external_system.send(change)
```

### DDS Durability and Graph State Management

The monitoring system leverages DDS durability to ensure the graph state is automatically maintained and synchronized across all subscribers, even if they join late or experience temporary disconnections.

#### How DDS Durability Maintains Graph State

1. **TRANSIENT_LOCAL Durability for GenesisGraph Topic**:
   - All node and edge state events are kept by DDS
   - Late-joining subscribers automatically receive the current state
   - No need for explicit state persistence or recovery logic
   - Graph is automatically reconstructed from durable events

2. **Automatic State Synchronization**:
   ```python
   class GraphMonitor:
       def _setup_subscribers(self):
           # GenesisGraph subscriber with TRANSIENT_LOCAL
           graph_reader_qos = dds.QosProvider.default.datareader_qos
           graph_reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
           graph_reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
           graph_reader_qos.history.depth = 1  # Per key (node_id/edge pair)
           
           self._graph_reader = dds.DataReader(
               subscriber=self._subscriber,
               topic=self._graph_topic,
               qos=graph_reader_qos,
               listener=self._graph_listener
           )
           
       def _on_graph_data_available(self, reader):
           """Process durable graph events to build/update graph"""
           samples = reader.take()
           for data, info in samples:
               if info.state == dds.InstanceState.ALIVE:
                   self._process_graph_event(data)
               elif info.state == dds.InstanceState.NOT_ALIVE_DISPOSED:
                   # Handle node/edge removal
                   self._process_removal_event(data)
   ```

3. **Key-Based State Management**:
   - Each node has a unique key (node_id)
   - Each edge has a composite key (source_id, target_id, edge_type)
   - DDS maintains the latest state per key automatically
   - Disposal of keys removes nodes/edges from the graph

4. **Fault Tolerance**:
   - If GraphMonitor crashes and restarts, it rebuilds the graph from DDS
   - Multiple GraphMonitor instances see the same consistent graph
   - No central database or state server required

#### Graph State Lifecycle

```python
# When a service starts
monitor.publish_node_online("calc_service", "SERVICE", "Calculator")
# DDS stores this with node_id as key

# When service state changes  
monitor.publish_node_state("calc_service", "BUSY")
# DDS updates the existing key with new state

# When service shuts down
monitor.publish_node_offline("calc_service")
# DDS marks the instance as disposed, removing it from durable storage

# Late-joining monitor automatically receives:
# 1. All ALIVE node states
# 2. All ALIVE edge states
# 3. Builds complete graph without querying anyone
```

#### Benefits of DDS-Based State Management

1. **No Single Point of Failure**: Every GraphMonitor has the complete state
2. **Automatic Recovery**: Restart/reconnect rebuilds graph automatically
3. **Consistent View**: All monitors see the same graph state
4. **Efficient Updates**: Only changes are transmitted
5. **Built-in History**: Can replay events for debugging
6. **Zero Configuration**: No database setup or management

### Implementation Patterns

#### MonitoredInterface Pattern

```python
class MonitoredInterface(GenesisInterface):
    def __init__(self, interface_name: str, service_name: str):
        super().__init__(interface_name, service_name)
        self.monitor = GraphMonitor(self.app.participant)
        self.node_id = str(self.app.participant.instance_handle)
        
        # Announce ourselves
        self.monitor.publish_node_online(
            node_id=self.node_id,
            node_type="INTERFACE",
            node_name=interface_name,
            metadata={
                "service": service_name,
                "capabilities": ["user_interaction"]
            }
        )
        self.monitor.publish_node_state(self.node_id, "READY")
        
    async def _handle_agent_discovered(self, agent_info: dict):
        # Publish edge discovery
        self.monitor.publish_edge_established(
            source_id=self.node_id,
            target_id=agent_info['instance_id'],
            edge_type="CAN_CALL",
            metadata={
                "agent_name": agent_info['prefered_name'],
                "discovery_time": time.time()
            }
        )
        
    async def send_request(self, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Track activity
        activity_id = self.monitor.start_activity(
            activity_type="REQUEST",
            source_id=self.node_id,
            target_id=self._connected_agent_id,
            operation="send_request"
        )
        
        try:
            self.monitor.publish_node_state(self.node_id, "BUSY")
            result = await super().send_request(request_data)
            self.monitor.complete_activity(activity_id, status=0, result_payload=result)
            return result
        except Exception as e:
            self.monitor.complete_activity(activity_id, status=1, error_message=str(e))
            raise
        finally:
            self.monitor.publish_node_state(self.node_id, "READY")
            
    async def close(self):
        self.monitor.publish_node_offline(self.node_id)
        await super().close()
```

#### MonitoredAgent Pattern

```python
class MonitoredAgent(GenesisAgent):
    def __init__(self, ...):
        super().__init__(...)
        self.monitor = GraphMonitor(self.app.participant)
        self.node_id = self.app.agent_id
        
        # Announce ourselves
        self.monitor.publish_node_online(
            node_id=self.node_id,
            node_type="AGENT",
            node_name=agent_name,
            metadata={
                "agent_type": agent_type,
                "service": base_service_name,
                "description": description
            }
        )
        self.monitor.publish_node_state(self.node_id, "READY")
        
    def _on_function_discovered(self, function_id: str, function_info: dict):
        # Publish edge to service
        if provider_id := function_info.get('provider_id'):
            self.monitor.publish_edge_established(
                source_id=self.node_id,
                target_id=provider_id,
                edge_type="CAN_CALL",
                metadata={
                    "function_id": function_id,
                    "function_name": function_info['name']
                }
            )
            
    async def process_request(self, request: Any) -> Dict[str, Any]:
        chain_id = str(uuid.uuid4())
        activity_id = self.monitor.start_activity(
            activity_type="PROCESS",
            source_id=self.node_id,
            target_id=self.node_id,
            operation="process_request",
            chain_id=chain_id
        )
        
        try:
            self.monitor.publish_node_state(self.node_id, "BUSY")
            result = await self._process_request(request)
            self.monitor.complete_activity(activity_id, status=0, result_payload=result)
            return result
        except Exception as e:
            self.monitor.complete_activity(activity_id, status=1, error_message=str(e))
            self.monitor.publish_node_state(self.node_id, "DEGRADED")
            raise
        finally:
            self.monitor.publish_node_state(self.node_id, "READY")
```

#### EnhancedServiceBase Pattern

```python
class EnhancedServiceBase(GenesisRPCService):
    def __init__(self, service_name: str, ...):
        super().__init__(service_name)
        self.monitor = GraphMonitor(self.participant)
        self.node_id = str(self.registry.capability_writer.instance_handle)
        
        # Announce service
        self.monitor.publish_node_online(
            node_id=self.node_id,
            node_type="SERVICE", 
            node_name=service_name,
            metadata={
                "capabilities": capabilities
            }
        )
        
    def _advertise_functions(self):
        # Announce each function as a node
        for func_name, func_data in self.functions.items():
            func_id = str(uuid.uuid4())
            
            # Create function node
            self.monitor.publish_node_online(
                node_id=func_id,
                node_type="FUNCTION",
                node_name=func_name,
                metadata={
                    "description": func_data["description"],
                    "service": self.service_name
                }
            )
            
            # Create edge from service to function
            self.monitor.publish_edge_established(
                source_id=self.node_id,
                target_id=func_id,
                edge_type="PROVIDES",
                metadata={
                    "function_name": func_name
                }
            )
            
    def function_wrapper(self, func_name: str):
        def decorator(func):
            def wrapper(*args, **kwargs):
                activity_id = self.monitor.start_activity(
                    activity_type="CALL",
                    source_id="unknown",  # Would be filled from request context
                    target_id=self.node_id,
                    operation=func_name
                )
                
                try:
                    self.monitor.publish_node_state(self.node_id, "BUSY")
                    result = func(*args, **kwargs)
                    self.monitor.complete_activity(activity_id, status=0)
                    return result
                except Exception as e:
                    self.monitor.complete_activity(activity_id, status=1, error_message=str(e))
                    raise
                finally:
                    self.monitor.publish_node_state(self.node_id, "READY")
            return wrapper
        return decorator
```

## Migration Plan

### Phase 1: Publisher-First Development with RTI DDS Spy Validation (Week 1)

**Critical: Develop Publishers First, Validate with RTI DDS Spy**

This phase focuses EXCLUSIVELY on the publishing side of the unified monitoring system. We will NOT develop subscribers yet - RTI DDS Spy will serve as our validation tool to ensure the published events are correct before proceeding to subscriber development.

1. **Update Data Model**:
   - Update datamodel.xml with GenesisGraphEvent and GenesisActivityEvent
   - Generate types and ensure DDS connectivity

2. **Update GraphMonitor Publishing API**:
   - Implement new publishing methods (publish_node_online, publish_edge_established, etc.)
   - Keep existing methods as deprecated wrappers for backward compatibility
   - Focus ONLY on publishing - no subscription logic yet

3. **Validate Publishing with RTI DDS Spy**:
   ```bash
   # Validate graph events
   $NDDSHOME/bin/rtiddsspy -printSample -topicRegex "GenesisGraph"
   
   # Validate activity events  
   $NDDSHOME/bin/rtiddsspy -printSample -topicRegex "GenesisActivity"
   ```

4. **Success Criteria for Phase 1**:
   - RTI DDS Spy shows well-formed GenesisGraphEvent messages
   - RTI DDS Spy shows well-formed GenesisActivityEvent messages
   - Events have correct durability (Graph=TRANSIENT_LOCAL, Activity=VOLATILE)
   - NO subscription or graph building code yet

### Phase 2: Update Components to Use New Publishers (Week 2)

**Continue Publisher-First Approach**

Update all components to use the new publishing patterns while continuing to validate with RTI DDS Spy.

1. **Update MonitoredInterface**:
   - Use new GraphMonitor publishing methods
   - Validate interface lifecycle events with RTI DDS Spy

2. **Update MonitoredAgent**:
   - Use new GraphMonitor publishing methods
   - Validate agent lifecycle and function discovery events with RTI DDS Spy

3. **Update EnhancedServiceBase**:
   - Use new GraphMonitor publishing methods
   - Validate service and function lifecycle events with RTI DDS Spy

4. **Continuous Validation**:
   - Run existing test suite
   - Use RTI DDS Spy to verify all events are published correctly
   - Ensure no regressions in functionality

5. **Success Criteria for Phase 2**:
   - All components publish unified events visible in RTI DDS Spy
   - Existing tests pass (functionality unchanged)
   - Clean event patterns observed in RTI DDS Spy output

### Phase 3: Develop Subscription and Graph Building (Week 3)

**Now Add Subscriber Side**

Only after publishers are proven correct with RTI DDS Spy, develop the subscription side.

1. **Add Subscription to GraphMonitor**:
   - Implement subscriber setup methods
   - Add GenesisNetworkGraph data structure
   - Implement graph building from DDS events
   - Add real-time event streaming capabilities

2. **Validate Subscription**:
   - Test that late-joining subscribers rebuild graph correctly
   - Verify DDS durability works as expected for graph state
   - Test graph export functions (JSON, DOT, etc.)

3. **Add Web Interface**:
   - Implement GenesisMonitoringWebServer
   - Create real-time visualization endpoints
   - Test WebSocket streaming of graph changes

4. **Success Criteria for Phase 3**:
   - Subscribers automatically rebuild complete graph from DDS
   - Multiple subscribers see consistent graph state
   - Web interface shows real-time network updates

### Phase 4: Update Tests and Documentation (Week 4)

1. **Update Test Suite**:
   - Update test_agent_to_agent_communication.py to use new event patterns
   - Update test_monitoring.sh to verify unified events
   - Add new tests for graph subscription and export

2. **Create Documentation**:
   - Migration guide for external users
   - API documentation for new GraphMonitor methods
   - Examples of using subscription and visualization features

3. **Deprecate Legacy**:
   - Mark old event types as deprecated
   - Remove legacy publishing code
   - Clean up unused monitoring infrastructure

**Key Principle: Publisher-First with RTI DDS Spy Validation**

Throughout this migration, we prioritize:
1. ✅ Get publishing right first (validate with RTI DDS Spy)
2. ✅ Ensure all components publish correctly (validate with RTI DDS Spy)  
3. ✅ Only then develop subscription and graph building
4. ✅ RTI DDS Spy remains our ground truth for event correctness

## Validation Using RTI DDS Spy

**RTI DDS Spy is our PRIMARY validation tool during publisher development phases**

The publisher-first approach relies heavily on RTI DDS Spy to validate that our unified monitoring events are being published correctly before we develop any subscription logic. This ensures we get the data model and publishing patterns right from the start.

### Phase 1 & 2 Validation Commands

During publisher development, use these commands to validate events:

#### Viewing Graph Events (Durable Network Structure)
```bash
$NDDSHOME/bin/rtiddsspy -printSample -topicRegex "GenesisGraph"
```

Expected output during service startup:
```
[timestamp] GenesisGraph
  event_type: "NODE_STATE"
  node_id: "0101eec50448da20504d15aa80000002"
  node_type: "SERVICE"
  node_state: "ONLINE"
  node_name: "CalculatorService"
  node_metadata: {"capabilities": ["calculator", "math"]}

[timestamp] GenesisGraph
  event_type: "NODE_STATE"  
  node_id: "func_add_uuid"
  node_type: "FUNCTION"
  node_state: "ONLINE"
  node_name: "add"
  node_metadata: {"description": "Add two numbers", "service": "CalculatorService"}

[timestamp] GenesisGraph
  event_type: "EDGE_STATE"
  source_id: "0101eec50448da20504d15aa80000002"
  target_id: "func_add_uuid"
  edge_type: "PROVIDES"
  edge_state: "ESTABLISHED"
  edge_metadata: {"function_name": "add"}
```

#### Viewing Activity Events (Transient Operations)
```bash
$NDDSHOME/bin/rtiddsspy -printSample -topicRegex "GenesisActivity"
```

Expected output during function calls:
```
[timestamp] GenesisActivity
  activity_type: "REQUEST"
  chain_id: "chain_456"
  source_id: "agent_123"
  target_id: "0101eec50448da20504d15aa80000002"
  operation: "add"
  payload: {"x": 5, "y": 3}

[timestamp] GenesisActivity
  activity_type: "RESPONSE"
  chain_id: "chain_456"
  source_id: "0101eec50448da20504d15aa80000002"
  target_id: "agent_123"
  operation: "add"
  status: 0
  duration_ms: 15
  payload: {"result": 8}
```

#### Viewing All Genesis Topics
```bash
$NDDSHOME/bin/rtiddsspy -printSample -topicRegex "Genesis.*"
```

### Validation Checklist for Publishers

During Phases 1 & 2, verify these patterns in RTI DDS Spy output:

**Graph Events (GenesisGraph topic)**:
- ✅ Service nodes appear with NODE_STATE events
- ✅ Function nodes appear with NODE_STATE events  
- ✅ Agent nodes appear with NODE_STATE events
- ✅ Interface nodes appear with NODE_STATE events
- ✅ Service→Function edges appear with EDGE_STATE events
- ✅ Agent→Service edges appear with EDGE_STATE events
- ✅ Interface→Agent edges appear with EDGE_STATE events
- ✅ Node state transitions (ONLINE→READY→BUSY→READY) are visible
- ✅ Durability: Late-joining spy sees existing nodes/edges

**Activity Events (GenesisActivity topic)**:
- ✅ REQUEST activities appear for function calls
- ✅ RESPONSE activities appear with same chain_id
- ✅ CALL activities appear for internal operations
- ✅ ERROR activities appear for failures with proper error_message
- ✅ Duration tracking works for completed activities
- ✅ Volatility: Only real-time activities visible (no history)

**Quality Checks**:
- ✅ No malformed JSON in metadata/payload fields
- ✅ UUIDs are properly formatted
- ✅ Timestamps are reasonable
- ✅ No duplicate event_id values
- ✅ Chain_id properly links related activities

### Example Publisher Validation Session

```bash
# Terminal 1: Start RTI DDS Spy
$NDDSHOME/bin/rtiddsspy -printSample -topicRegex "Genesis.*"

# Terminal 2: Start service with new unified monitoring
python -m test_functions.calculator_service

# Expected in spy output:
# 1. Service NODE_STATE: ONLINE
# 2. Function NODE_STATE: ONLINE (for each function)
# 3. Service→Function EDGE_STATE: ESTABLISHED (for each function)
# 4. Service NODE_STATE: READY

# Terminal 3: Run agent test
python -m run_scripts.test_agent_to_agent_communication

# Expected in spy output:
# 1. Agent NODE_STATE: ONLINE
# 2. Agent→Service EDGE_STATE: ESTABLISHED
# 3. REQUEST/RESPONSE activity pairs with matching chain_id
# 4. Proper duration tracking
```

This validation approach ensures that when we get to Phase 3 (subscription development), we already have a proven, well-formed event stream to work with.

## Benefits

1. **Simplified Mental Model**: 
   - Nodes = Things in the network
   - Edges = Relationships between things
   - Activities = Things happening

2. **Clear Durability Semantics**:
   - Graph events are durable (build network picture)
   - Activity events are transient (see what's happening)
   - Automatic state synchronization via DDS

3. **Better Tooling Support**:
   - Easy to build visualization tools
   - Natural fit for graph databases
   - Simple to record for ML training
   - Multiple export formats (JSON, DOT, Cytoscape, NetworkX)

4. **Reduced Complexity**:
   - Single API (GraphMonitor) for both publishing and subscription
   - Consistent patterns
   - Clear documentation
   - No separate monitoring infrastructure needed

5. **Performance**:
   - Fewer topics to manage
   - Optimized QoS settings
   - Reduced redundant publishing
   - Efficient graph updates using DDS keys

6. **Complete Bidirectional Solution**:
   - Publish monitoring events from any component
   - Subscribe and build real-time graph from anywhere
   - Export graph for visualization and analysis
   - Stream updates to web interfaces
   - No central monitoring server required

## Success Metrics

1. All Genesis components publish to only 2 topics
2. RTI DDS Spy shows clear, understandable events
3. Network visualization tools can build complete graph
4. Activity chains can be traced end-to-end
5. Tests pass with updated event detection 
> Status: Implemented (see docs/architecture/monitoring_system.md and code in genesis_lib/graph_monitoring.py, genesis_lib/graph_state.py). Last reviewed: 2025-08-28.
