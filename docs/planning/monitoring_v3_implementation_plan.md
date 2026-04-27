# GENESIS Monitoring V3 Implementation Plan

## Overview
This document outlines the step-by-step plan for implementing GENESIS Monitoring V3, which focuses on unifying the monitoring architecture while maintaining compatibility with V2. The plan follows an iterative approach, focusing on architectural changes first, then enhancing the monitoring capabilities.

## Goals
1. Unify monitoring architecture across all endpoint types
2. Make all monitoring events data-centric and queryable
3. Maintain backward compatibility with V2
4. Enable better state management and relationship tracking
5. Keep clear separation between data and presentation

## Helpful info
The GUID format 01019468a04f6ea7aadc529580002103 is a standard DDS GUID format where:
The first part (01019468a04f6ea7) is typically the participant ID
The middle part (aadc5295) is the entity kind and key
The last part (80002103) identifies the specific DDS entity (in this case, the reply DataWriter)

## Core Architectural Changes

### Phase 1: Base Layer Implementation
**File: genesis_lib/genesis_base.py**
1. Create core entity management:
   - Entity registry
   - State tracking
   - Participant correlation
   - Basic event types
   Test: Verify basic entity management

2. Implement monitoring primitives:
   - Event definitions
   - State management
   - Relationship tracking
   Test: Verify monitoring capabilities

### Phase 2: Monitored Endpoint Layer
**File: genesis_lib/monitored_endpoint.py**
1. Create common monitoring behaviors:
   - Lifecycle management
   - Health monitoring
   - Event aggregation
   - Relationship tracking
   Test: Verify common behaviors

2. Implement information flow:
   - Event propagation
   - State synchronization
   - Configuration distribution
   Test: Verify information flow

### Phase 3: Specialized Endpoint Updates
**Files: service_base.py, interface_base.py, agent_base.py**
1. Refactor service base:
   - Migrate from enhanced_service_base.py
   - Integrate with monitored_endpoint
   - Maintain service-specific features
   Test: Verify service functionality

2. Refactor interface base:
   - Migrate from monitored_interface.py
   - Integrate with monitored_endpoint
   - Maintain interface-specific features
   Test: Verify interface functionality

3. Refactor agent base:
   - Migrate from monitored_agent.py
   - Integrate with monitored_endpoint
   - Maintain agent-specific features
   Test: Verify agent functionality

### Phase 4: Data Model Updates
**File: datamodel.xml**
1. Update entity definitions:
   ```xml
   <struct name="EntityInfo">
     <member name="primary_id" type="string"/>
     <member name="preferred_name" type="string"/>
     <member name="participants" type="StringSequence"/>
     <member name="role" type="EntityRole"/>
     <member name="state" type="EntityState"/>
     <member name="capabilities" type="StringSequence"/>
   </struct>
   ```
   Test: Verify schema updates

2. Add relationship tracking:
   ```xml
   <struct name="EntityRelationship">
     <member name="source_id" type="string"/>
     <member name="target_id" type="string"/>
     <member name="relationship_type" type="RelationType"/>
     <member name="metadata" type="string"/>
   </struct>
   ```
   Test: Verify relationship modeling

### Phase 5: Monitor Implementation
**File: genesis_monitor.py**
1. Update entity visualization:
   - Support new entity model
   - Show relationships
   - Display state information
   Test: Verify visualization

2. Implement analysis features:
   - Entity filtering
   - Relationship analysis
   - State tracking
   Test: Verify analysis capabilities

## Testing Strategy
For each phase:
1. Unit test new components
2. Integration test with existing components
3. Verify V2 compatibility:
   - Event structure
   - Visualization
   - Existing functionality
4. Test information flow:
   - Event propagation
   - State management
   - Configuration distribution

## Success Criteria
1. All endpoints use unified monitoring architecture
2. Entity management is consistent across system
3. V2 compatibility is maintained
4. Relationships are properly tracked
5. State management is reliable
6. Monitor displays unified view

## Rollback Plan
For each phase:
1. Keep V2 implementations as reference
2. Maintain separate branches
3. Document all changes
4. Test V2 compatibility
5. Prepare rollback procedures

## Timeline
- Phase 1: 3 days
- Phase 2: 3 days
- Phase 3: 4 days
- Phase 4: 2 days
- Phase 5: 3 days
- Testing and refinement: 3 days

Total estimated time: 18 days

## Graph Connectivity Testing Framework

### Overview
To ensure monitoring events properly represent the distributed system topology, we need comprehensive graph connectivity testing that validates:
1. All expected nodes exist in the monitoring data
2. All expected edges (connections) are present
3. No orphaned or missing components
4. Graph completeness matches system architecture

### Node Types and Identification Strategy
- **Agents**: Use DDS GUID for service endpoints, UUID for agent identity
- **Services**: Use DDS GUID from function capability writer
- **Interfaces**: Use DDS GUID from participant
- **Functions**: Use UUID (generated, as functions don't have DDS GUID)

### Edge Types to Monitor
- **Interface → Agent**: Discovery and connection events
- **Agent → Agent**: Agent-to-agent communication setup and requests
- **Agent → Service**: Function discovery and calls
- **Service → Function**: Internal function hosting relationship

### Testing Components

#### 1. Graph Data Collection
```python
class MonitoringGraphCollector:
    """Collect and organize monitoring events into graph structure"""
    
    def __init__(self):
        self.nodes = {}  # node_id -> node_info
        self.edges = {}  # (source_id, target_id) -> edge_info
        self.events = []  # Raw monitoring events
    
    def process_lifecycle_event(self, event):
        """Process ComponentLifecycleEvent into nodes/edges"""
        
    def process_chain_event(self, event):
        """Process ChainEvent into interaction edges"""
        
    def verify_graph_completeness(self, expected_topology):
        """Compare collected graph against expected system topology"""
```

#### 2. Expected Topology Definition
```python
class ExpectedTopology:
    """Define what nodes and edges should exist for a given test scenario"""
    
    def __init__(self, scenario_name):
        self.scenario = scenario_name
        self.expected_nodes = []
        self.expected_edges = []
        self.required_node_types = []
    
    def add_interface(self, interface_id, interface_name):
        """Add expected interface node"""
        
    def add_agent(self, agent_id, agent_name, capabilities):
        """Add expected agent node"""
        
    def add_service(self, service_id, service_name, functions):
        """Add expected service node with functions"""
        
    def add_connection(self, source_id, target_id, connection_type):
        """Add expected edge between components"""
```

#### 3. Graph Analysis Engine
```python
class GraphAnalyzer:
    """Analyze graph for completeness and correctness"""
    
    def __init__(self, collected_graph, expected_topology):
        self.graph = collected_graph
        self.expected = expected_topology
        
    def find_missing_nodes(self):
        """Identify nodes that should exist but weren't found"""
        
    def find_missing_edges(self):
        """Identify connections that should exist but weren't found"""
        
    def find_orphaned_nodes(self):
        """Identify nodes with no connections"""
        
    def verify_connectivity(self):
        """Verify graph is properly connected"""
        
    def generate_report(self):
        """Generate comprehensive analysis report"""
```

#### 4. RTIDDSSPY Integration
```python
class RTIDDSSpyAnalyzer:
    """Parse RTIDDSSPY output to verify DDS traffic matches monitoring events"""
    
    def capture_dds_traffic(self, duration_seconds):
        """Capture DDS traffic during test execution"""
        
    def correlate_with_monitoring(self, monitoring_events):
        """Correlate DDS traffic with monitoring events"""
        
    def verify_dds_consistency(self):
        """Verify DDS-level traffic matches high-level monitoring"""
```

### Test Scenarios

#### Scenario 1: Basic Interface-Agent-Service
```python
def test_basic_connectivity():
    """Test basic Interface → Agent → Service connectivity"""
    topology = ExpectedTopology("basic_connectivity")
    
    # Define expected components
    topology.add_interface("interface_1", "TestInterface")
    topology.add_agent("agent_1", "TestAgent", ["chat", "classification"])
    topology.add_service("service_1", "CalculatorService", ["add", "subtract"])
    
    # Define expected connections
    topology.add_connection("interface_1", "agent_1", "interface_agent")
    topology.add_connection("agent_1", "service_1", "agent_service")
    
    # Run test and verify
    collector = MonitoringGraphCollector()
    # ... run test scenario ...
    analyzer = GraphAnalyzer(collector.graph, topology)
    assert analyzer.verify_connectivity()
```

#### Scenario 2: Agent-to-Agent Communication
```python
def test_agent_to_agent_connectivity():
    """Test Agent → Agent communication monitoring"""
    topology = ExpectedTopology("agent_to_agent")
    
    # Define multi-agent scenario
    topology.add_interface("interface_1", "TestInterface")
    topology.add_agent("agent_1", "GeneralAgent", ["chat", "classification"])
    topology.add_agent("agent_2", "WeatherAgent", ["weather", "specialized"])
    topology.add_service("service_1", "WeatherService", ["get_weather"])
    
    # Define expected connections including agent-to-agent
    topology.add_connection("interface_1", "agent_1", "interface_agent")
    topology.add_connection("agent_1", "agent_2", "agent_agent")
    topology.add_connection("agent_2", "service_1", "agent_service")
    
    # Run test and verify
    # ... test implementation ...
```

### Integration with Existing Monitoring
The graph connectivity testing will integrate with:
- **Genesis Monitor**: Use existing ComponentLifecycleEvent and ChainEvent processing
- **MonitoredAgent**: Leverage existing monitoring event generation
- **MonitoredInterface**: Use existing interface monitoring
- **EnhancedServiceBase**: Use existing service and function monitoring

### Test Execution Strategy
1. **Setup Phase**: Start monitoring collection
2. **Execution Phase**: Run test scenario
3. **Collection Phase**: Gather all monitoring events
4. **Analysis Phase**: Build graph and verify connectivity
5. **Validation Phase**: Compare against expected topology
6. **Reporting Phase**: Generate detailed analysis report

### Success Criteria
- All expected nodes detected in monitoring events
- All expected edges detected in monitoring events  
- No missing or orphaned components
- Graph connectivity matches system architecture
- RTIDDSSPY traffic correlates with monitoring events
- Tests can detect regressions in monitoring coverage

## Notes
- Focus on architectural changes first
- Maintain backward compatibility throughout
- Document all architectural decisions
- Add comprehensive test coverage
- Update documentation with new architecture

## Future Architectural Considerations

### Monitoring Architecture Evolution
The current implementation maintains separate monitoring in `enhanced_service_base.py`, `monitored_interface.py`, and `monitored_agent.py`. A future refactor should consider a more unified approach:

```
genesis_base.py           - Core entity/monitoring logic
├── monitored_endpoint.py - Common monitoring behaviors
    ├── service_base.py   - Service-specific features
    ├── interface_base.py - Interface-specific features
    └── agent_base.py     - Agent-specific features
```

This refactor would need to address:

1. Information Flow:
   - Low-level libraries → Genesis Base → Monitored Endpoint → Specific Endpoint → App
   - Event propagation and aggregation
   - State management and synchronization
   - Configuration distribution

2. Key Challenges:
   - Maintaining backward compatibility
   - Preserving specialized behaviors
   - Managing state ownership
   - Handling cross-cutting concerns

3. Benefits:
   - Unified entity management
   - Consistent monitoring patterns
   - Clearer responsibility separation
   - Better scalability

This architectural evolution should be considered for future releases after V3 monitoring is stable and validated. 
> Status: Largely implemented via GraphMonitor (see docs/architecture/monitoring_system.md and genesis_lib/graph_monitoring.py). Remaining items consolidated under “Future Work”. Last reviewed: 2025-08-28.

### Remaining Future Work (V3+)

1. Unify Monitored Base Layers
   - Extract common monitored behaviors into a shared base (e.g., `monitored_endpoint.py`) used by services, interfaces, and agents.
   - Ensure consistent state transitions (DISCOVERING/READY/BUSY) and attribute vocab across all components.

2. Event Schema Alignment and Deprecation
   - Align legacy `MonitoringEvent` usages with graph-first patterns.
   - Formalize guidance on when to use `ChainEvent` vs. `GenesisGraph*` updates; deprecate redundant paths.

3. Performance and Liveliness
   - Validate QoS for high-churn topologies (history depth, durability, liveliness lease tuning).
   - Add stress tests covering bursts of node/edge updates and chain overlays.

4. Viewer/Tooling Enhancements
   - Fold graph connectivity tests into CI smoke checks.
   - Extend the Graph Interface viewer to toggle overlays (chain, liveliness, errors) and filter by component type.

5. Documentation and Playbooks
   - Consolidate this plan into `docs/architecture/monitoring_system.md` with “how to emit” recipes per component.
   - Add a troubleshooting guide (missing edges, duplicated nodes, QoS mismatch) with known remedies.
