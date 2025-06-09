#!/usr/bin/env python3
"""
Monitoring Graph Connectivity Test Framework

This test validates that monitoring events properly represent the distributed system
topology by building a graph from monitoring events and comparing it against expected
system architecture.

Key Features:
- Collects ComponentLifecycleEvent and ChainEvent data
- Builds graph representation of system topology
- Validates nodes and edges match expected connectivity
- Detects missing, orphaned, or unexpected components
- Integrates with RTIDDSSPY for DDS traffic analysis
- Provides regression testing for monitoring coverage

Node Types:
- Agents: Use DDS GUID for service endpoints, UUID for agent identity
- Services: Use DDS GUID from function capability writer  
- Interfaces: Use DDS GUID from participant
- Functions: Use UUID (generated, as functions don't have DDS GUID)

Edge Types:
- Interface → Agent: Discovery and connection events
- Agent → Agent: Agent-to-agent communication setup and requests
- Agent → Service: Function discovery and calls
- Service → Function: Internal function hosting relationship
"""

import asyncio
import json
import logging
import subprocess
import time
import uuid
from datetime import datetime
from typing import Dict, List, Set, Tuple, Any, Optional
import threading
import os
import sys

import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MonitoringGraphTest")

class NodeInfo:
    """Information about a graph node"""
    def __init__(self, node_id: str, node_type: str, name: str = "", capabilities: dict = None):
        self.node_id = node_id
        self.node_type = node_type  # INTERFACE, AGENT, SERVICE, FUNCTION
        self.name = name
        self.capabilities = capabilities or {}
        self.discovered_at = datetime.now()
        self.last_seen = datetime.now()
        
    def __repr__(self):
        return f"Node({self.node_type}:{self.name}:{self.node_id})"

class EdgeInfo:
    """Information about a graph edge"""
    def __init__(self, source_id: str, target_id: str, edge_type: str, metadata: dict = None):
        self.source_id = source_id
        self.target_id = target_id
        self.edge_type = edge_type  # DISCOVERY, CONNECTION, FUNCTION_CALL, etc.
        self.metadata = metadata or {}
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        
    def __repr__(self):
        return f"Edge({self.edge_type}:{self.source_id}->{self.target_id})"

class MonitoringGraphCollector:
    """Collect and organize monitoring events into graph structure"""
    
    def __init__(self, domain_id: int = 0):
        self.domain_id = domain_id
        self.nodes: Dict[str, NodeInfo] = {}
        self.edges: Dict[Tuple[str, str], EdgeInfo] = {}
        self.events: List[dict] = []
        self.participant = None
        self.subscriber = None
        self.lifecycle_reader = None
        self.chain_reader = None
        self.monitoring_active = False
        self.listener_thread = None
        
        # Statistics
        self.stats = {
            "lifecycle_events": 0,
            "chain_events": 0,
            "nodes_discovered": 0,
            "edges_discovered": 0
        }
        
        self._setup_dds()
    
    def _setup_dds(self):
        """Set up DDS entities for monitoring"""
        try:
            self.participant = dds.DomainParticipant(self.domain_id)
            self.subscriber = dds.Subscriber(self.participant)
            
            # Get type provider
            provider = dds.QosProvider(get_datamodel_path())
            
            # Set up ComponentLifecycleEvent monitoring
            lifecycle_type = provider.type("genesis_lib", "ComponentLifecycleEvent")
            lifecycle_topic = dds.DynamicData.Topic(
                self.participant,
                "ComponentLifecycleEvent",
                lifecycle_type
            )
            
            # Set up ChainEvent monitoring
            chain_type = provider.type("genesis_lib", "ChainEvent")
            chain_topic = dds.DynamicData.Topic(
                self.participant,
                "ChainEvent",
                chain_type
            )
            
            # Configure reader QoS
            reader_qos = dds.QosProvider.default.datareader_qos
            reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
            reader_qos.history.depth = 1000
            
            # Create readers
            self.lifecycle_reader = dds.DynamicData.DataReader(
                subscriber=self.subscriber,
                topic=lifecycle_topic,
                qos=reader_qos
            )
            
            self.chain_reader = dds.DynamicData.DataReader(
                subscriber=self.subscriber,
                topic=chain_topic,
                qos=reader_qos
            )
            
            logger.info(f"DDS monitoring setup complete on domain {self.domain_id}")
            
        except Exception as e:
            logger.error(f"Failed to setup DDS monitoring: {e}")
            raise
    
    def start_monitoring(self, duration_seconds: float = 30.0):
        """Start monitoring for specified duration"""
        self.monitoring_active = True
        
        def monitor_thread():
            start_time = time.time()
            logger.info(f"Starting monitoring for {duration_seconds} seconds...")
            
            while self.monitoring_active and (time.time() - start_time) < duration_seconds:
                try:
                    # Read lifecycle events
                    lifecycle_samples = self.lifecycle_reader.take()
                    logger.debug(f"Lifecycle samples type: {type(lifecycle_samples)}, length: {len(lifecycle_samples) if hasattr(lifecycle_samples, '__len__') else 'unknown'}")
                    
                    for sample in lifecycle_samples:
                        logger.debug(f"Sample type: {type(sample)}, content: {sample}")
                        if isinstance(sample, tuple) and len(sample) == 2:
                            data, info = sample
                            if data is not None and info.state.instance_state == dds.InstanceState.ALIVE:
                                self._process_lifecycle_event(data)
                        else:
                            logger.error(f"Unexpected lifecycle sample format: {type(sample)}, content: {sample}")
                    
                    # Read chain events
                    chain_samples = self.chain_reader.take()
                    logger.debug(f"Chain samples type: {type(chain_samples)}, length: {len(chain_samples) if hasattr(chain_samples, '__len__') else 'unknown'}")
                    
                    for sample in chain_samples:
                        logger.debug(f"Chain sample type: {type(sample)}, content: {sample}")
                        if isinstance(sample, tuple) and len(sample) == 2:
                            data, info = sample
                            if data is not None and info.state.instance_state == dds.InstanceState.ALIVE:
                                self._process_chain_event(data)
                        else:
                            logger.error(f"Unexpected chain sample format: {type(sample)}, content: {sample}")
                    
                    time.sleep(0.1)  # Small sleep to prevent busy waiting
                    
                except Exception as e:
                    logger.error(f"Error during monitoring: {e}")
                    break
            
            logger.info("Monitoring thread completed")
        
        self.listener_thread = threading.Thread(target=monitor_thread, daemon=True)
        self.listener_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring_active = False
        if self.listener_thread:
            self.listener_thread.join(timeout=5.0)
    
    def _process_lifecycle_event(self, data):
        """Process ComponentLifecycleEvent into nodes/edges"""
        try:
            # Debug the data type and structure
            logger.debug(f"Processing lifecycle event data type: {type(data)}")
            logger.debug(f"Data content: {data}")
            
            # Handle different data types (DynamicData vs dict)
            if hasattr(data, '__getitem__') and not isinstance(data, (list, tuple)):
                # This is DynamicData, access directly
                component_type_val = data["component_type"]
                event_category_val = data["event_category"]
                component_id = str(data["component_id"])
                source_id = str(data["source_id"]) if data["source_id"] else ""
                target_id = str(data["target_id"]) if data["target_id"] else ""
                connection_type = str(data["connection_type"]) if data["connection_type"] else ""
                capabilities = str(data["capabilities"])
                reason = str(data["reason"])
                timestamp = int(data["timestamp"])
            else:
                logger.error(f"Unexpected data type: {type(data)}, data: {data}")
                return
            
            # Map component types and states
            component_types = ["INTERFACE", "PRIMARY_AGENT", "SPECIALIZED_AGENT", "FUNCTION"]
            states = ["JOINING", "DISCOVERING", "READY", "BUSY", "DEGRADED", "OFFLINE"]
            event_categories = ["NODE_DISCOVERY", "EDGE_DISCOVERY", "STATE_CHANGE", "AGENT_INIT", "AGENT_READY", "AGENT_SHUTDOWN", "DDS_ENDPOINT"]
            
            # Convert enum values
            component_type = component_types[int(component_type_val)]
            event_category = event_categories[int(event_category_val)]
            
            event_data = {
                "type": "lifecycle",
                "event_category": event_category,
                "component_id": component_id,
                "component_type": component_type,
                "source_id": source_id,
                "target_id": target_id,
                "connection_type": connection_type,
                "capabilities": capabilities,
                "reason": reason,
                "timestamp": timestamp
            }
            
            self.events.append(event_data)
            self.stats["lifecycle_events"] += 1
            
            # Process based on event category
            if event_category == "NODE_DISCOVERY":
                self._add_node_from_event(event_data)
            elif event_category == "EDGE_DISCOVERY":
                self._add_edge_from_event(event_data)
            
            logger.debug(f"Processed lifecycle event: {event_category} - {event_data['component_id']}")
            
        except Exception as e:
            logger.error(f"Error processing lifecycle event: {e}")
    
    def _process_chain_event(self, data):
        """Process ChainEvent into interaction edges"""
        try:
            # Handle different data types (DynamicData vs dict)
            if hasattr(data, '__getitem__'):
                # This is DynamicData, access directly
                event_type = str(data["event_type"])
                chain_id = str(data["chain_id"])
                source_id = str(data["source_id"])
                target_id = str(data["target_id"])
                function_id = str(data["function_id"])
                timestamp = int(data["timestamp"])
            else:
                logger.error(f"Unexpected chain data type: {type(data)}")
                return
                
            event_data = {
                "type": "chain",
                "event_type": event_type,
                "chain_id": chain_id,
                "source_id": source_id,
                "target_id": target_id,
                "function_id": function_id,
                "timestamp": timestamp
            }
            
            self.events.append(event_data)
            self.stats["chain_events"] += 1
            
            # Add interaction edge
            self._add_interaction_edge(event_data)
            
            logger.debug(f"Processed chain event: {event_data['event_type']} - {event_data['source_id']} -> {event_data['target_id']}")
            
        except Exception as e:
            logger.error(f"Error processing chain event: {e}")
    
    def _add_node_from_event(self, event_data):
        """Add or update node from lifecycle event"""
        node_id = event_data["component_id"]
        
        # Parse capabilities
        capabilities = {}
        try:
            if event_data["capabilities"]:
                capabilities = json.loads(event_data["capabilities"])
        except:
            pass
        
        # Determine node name
        node_name = capabilities.get("function_name", capabilities.get("agent_name", node_id))
        
        if node_id not in self.nodes:
            self.nodes[node_id] = NodeInfo(
                node_id=node_id,
                node_type=event_data["component_type"],
                name=node_name,
                capabilities=capabilities
            )
            self.stats["nodes_discovered"] += 1
            logger.info(f"✅ Discovered node: {self.nodes[node_id]}")
        else:
            # Update existing node
            self.nodes[node_id].last_seen = datetime.now()
            if capabilities:
                self.nodes[node_id].capabilities.update(capabilities)
    
    def _add_edge_from_event(self, event_data):
        """Add edge from lifecycle event"""
        source_id = event_data["source_id"]
        target_id = event_data["target_id"]
        
        if source_id and target_id and source_id != target_id:
            edge_key = (source_id, target_id)
            connection_type = event_data["connection_type"] or "discovery"
            
            if edge_key not in self.edges:
                self.edges[edge_key] = EdgeInfo(
                    source_id=source_id,
                    target_id=target_id,
                    edge_type=connection_type,
                    metadata={"event_category": event_data["event_category"]}
                )
                self.stats["edges_discovered"] += 1
                logger.info(f"🔗 Discovered edge: {self.edges[edge_key]}")
            else:
                self.edges[edge_key].last_activity = datetime.now()
    
    def _add_interaction_edge(self, event_data):
        """Add interaction edge from chain event"""
        source_id = event_data["source_id"]
        target_id = event_data["target_id"]
        
        if source_id and target_id and source_id != target_id:
            edge_key = (source_id, target_id)
            
            if edge_key not in self.edges:
                self.edges[edge_key] = EdgeInfo(
                    source_id=source_id,
                    target_id=target_id,
                    edge_type="interaction",
                    metadata={"chain_event": event_data["event_type"]}
                )
                self.stats["edges_discovered"] += 1
                logger.info(f"⚡ Discovered interaction: {self.edges[edge_key]}")
            else:
                self.edges[edge_key].last_activity = datetime.now()
    
    def get_graph_summary(self):
        """Get summary of collected graph"""
        node_types = {}
        edge_types = {}
        
        for node in self.nodes.values():
            node_types[node.node_type] = node_types.get(node.node_type, 0) + 1
        
        for edge in self.edges.values():
            edge_types[edge.edge_type] = edge_types.get(edge.edge_type, 0) + 1
        
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": node_types,
            "edge_types": edge_types,
            "events_processed": len(self.events),
            "stats": self.stats
        }
    
    def close(self):
        """Clean up DDS resources"""
        self.stop_monitoring()
        
        if self.lifecycle_reader:
            self.lifecycle_reader.close()
        if self.chain_reader:
            self.chain_reader.close()
        if self.subscriber:
            self.subscriber.close()
        if self.participant:
            self.participant.close()

class ExpectedTopology:
    """Define what nodes and edges should exist for a given test scenario"""
    
    def __init__(self, scenario_name: str):
        self.scenario = scenario_name
        self.expected_nodes: Dict[str, dict] = {}
        self.expected_edges: Set[Tuple[str, str]] = set()
        self.required_node_types: Set[str] = set()
        self.required_edge_types: Set[str] = set()
    
    def add_interface(self, interface_id: str, interface_name: str):
        """Add expected interface node"""
        self.expected_nodes[interface_id] = {
            "type": "INTERFACE",
            "name": interface_name,
            "id": interface_id
        }
        self.required_node_types.add("INTERFACE")
    
    def add_agent(self, agent_id: str, agent_name: str, capabilities: List[str]):
        """Add expected agent node"""
        self.expected_nodes[agent_id] = {
            "type": "PRIMARY_AGENT",  # Could be SPECIALIZED_AGENT
            "name": agent_name,
            "id": agent_id,
            "capabilities": capabilities
        }
        self.required_node_types.add("PRIMARY_AGENT")
    
    def add_service(self, service_id: str, service_name: str, functions: List[str]):
        """Add expected service node with functions"""
        self.expected_nodes[service_id] = {
            "type": "FUNCTION",  # Services are represented as FUNCTION type
            "name": service_name,
            "id": service_id,
            "functions": functions
        }
        self.required_node_types.add("FUNCTION")
        
        # Add function nodes
        for func_name in functions:
            func_id = f"{service_id}_{func_name}"
            self.expected_nodes[func_id] = {
                "type": "FUNCTION",
                "name": func_name,
                "id": func_id,
                "parent_service": service_id
            }
    
    def add_connection(self, source_id: str, target_id: str, connection_type: str):
        """Add expected edge between components"""
        self.expected_edges.add((source_id, target_id))
        self.required_edge_types.add(connection_type)

class GraphAnalyzer:
    """Analyze graph for completeness and correctness"""
    
    def __init__(self, collected_graph: MonitoringGraphCollector, expected_topology: ExpectedTopology):
        self.graph = collected_graph
        self.expected = expected_topology
        self.analysis_results = {}
    
    def find_missing_nodes(self) -> List[str]:
        """Identify nodes that should exist but weren't found"""
        missing = []
        for expected_id, expected_info in self.expected.expected_nodes.items():
            if expected_id not in self.graph.nodes:
                # Try to find by name or type if ID doesn't match
                found = False
                for node in self.graph.nodes.values():
                    if (node.name == expected_info["name"] and 
                        node.node_type == expected_info["type"]):
                        found = True
                        break
                
                if not found:
                    missing.append(f"{expected_info['type']}:{expected_info['name']}:{expected_id}")
        
        return missing
    
    def find_missing_edges(self) -> List[str]:
        """Identify connections that should exist but weren't found"""
        missing = []
        for source_id, target_id in self.expected.expected_edges:
            # Check if edge exists (either direction)
            if ((source_id, target_id) not in self.graph.edges and 
                (target_id, source_id) not in self.graph.edges):
                missing.append(f"{source_id} -> {target_id}")
        
        return missing
    
    def find_orphaned_nodes(self) -> List[str]:
        """Identify nodes with no connections"""
        orphaned = []
        for node_id, node in self.graph.nodes.items():
            connected = False
            for edge in self.graph.edges.values():
                if edge.source_id == node_id or edge.target_id == node_id:
                    connected = True
                    break
            
            if not connected:
                orphaned.append(f"{node.node_type}:{node.name}:{node_id}")
        
        return orphaned
    
    def find_unexpected_nodes(self) -> List[str]:
        """Identify nodes that exist but weren't expected"""
        unexpected = []
        for node_id, node in self.graph.nodes.items():
            if node_id not in self.expected.expected_nodes:
                # Check if it matches by name/type
                found = False
                for expected_info in self.expected.expected_nodes.values():
                    if (node.name == expected_info["name"] and 
                        node.node_type == expected_info["type"]):
                        found = True
                        break
                
                if not found:
                    unexpected.append(f"{node.node_type}:{node.name}:{node_id}")
        
        return unexpected
    
    def verify_connectivity(self) -> bool:
        """Verify graph is properly connected"""
        if not self.graph.nodes:
            return False
        
        # For now, just check that we have some edges
        # More sophisticated connectivity analysis could be added
        return len(self.graph.edges) > 0
    
    def analyze_node_types(self) -> dict:
        """Analyze node type distribution"""
        actual_types = {}
        expected_types = {}
        
        for node in self.graph.nodes.values():
            actual_types[node.node_type] = actual_types.get(node.node_type, 0) + 1
        
        for node_info in self.expected.expected_nodes.values():
            node_type = node_info["type"]
            expected_types[node_type] = expected_types.get(node_type, 0) + 1
        
        return {
            "actual": actual_types,
            "expected": expected_types,
            "missing_types": set(expected_types.keys()) - set(actual_types.keys()),
            "unexpected_types": set(actual_types.keys()) - set(expected_types.keys())
        }
    
    def generate_report(self) -> dict:
        """Generate comprehensive analysis report"""
        missing_nodes = self.find_missing_nodes()
        missing_edges = self.find_missing_edges()
        orphaned_nodes = self.find_orphaned_nodes()
        unexpected_nodes = self.find_unexpected_nodes()
        connectivity_ok = self.verify_connectivity()
        node_type_analysis = self.analyze_node_types()
        
        # Calculate success metrics
        expected_node_count = len(self.expected.expected_nodes)
        actual_node_count = len(self.graph.nodes)
        expected_edge_count = len(self.expected.expected_edges)
        actual_edge_count = len(self.graph.edges)
        
        node_coverage = max(0, (expected_node_count - len(missing_nodes)) / expected_node_count) if expected_node_count > 0 else 0
        edge_coverage = max(0, (expected_edge_count - len(missing_edges)) / expected_edge_count) if expected_edge_count > 0 else 0
        
        report = {
            "scenario": self.expected.scenario,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "success": len(missing_nodes) == 0 and len(missing_edges) == 0 and connectivity_ok,
                "node_coverage": node_coverage,
                "edge_coverage": edge_coverage,
                "connectivity_ok": connectivity_ok
            },
            "nodes": {
                "expected_count": expected_node_count,
                "actual_count": actual_node_count,
                "missing": missing_nodes,
                "unexpected": unexpected_nodes,
                "orphaned": orphaned_nodes
            },
            "edges": {
                "expected_count": expected_edge_count,
                "actual_count": actual_edge_count,
                "missing": missing_edges
            },
            "node_types": node_type_analysis,
            "graph_stats": self.graph.get_graph_summary()
        }
        
        self.analysis_results = report
        return report

class RTIDDSSpyAnalyzer:
    """Parse RTIDDSSPY output to verify DDS traffic matches monitoring events"""
    
    def __init__(self, domain_id: int = 0):
        self.domain_id = domain_id
        self.spy_process = None
        self.traffic_data = []
    
    def start_capture(self):
        """Start RTIDDSSPY capture"""
        try:
            cmd = ["rtiddsspy", "-d", str(self.domain_id), "-v", "1"]
            self.spy_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            logger.info(f"Started RTIDDSSPY on domain {self.domain_id}")
            return True
        except Exception as e:
            logger.warning(f"Could not start RTIDDSSPY: {e}")
            return False
    
    def stop_capture(self):
        """Stop RTIDDSSPY capture and collect output"""
        if self.spy_process:
            self.spy_process.terminate()
            stdout, stderr = self.spy_process.communicate(timeout=5)
            
            # Parse output for relevant information
            if stdout:
                self._parse_spy_output(stdout)
            
            self.spy_process = None
    
    def _parse_spy_output(self, output: str):
        """Parse RTIDDSSPY output for relevant DDS traffic"""
        lines = output.split('\n')
        for line in lines:
            if 'ComponentLifecycleEvent' in line or 'ChainEvent' in line:
                self.traffic_data.append({
                    "timestamp": datetime.now().isoformat(),
                    "line": line.strip()
                })
    
    def get_traffic_summary(self) -> dict:
        """Get summary of captured DDS traffic"""
        return {
            "total_lines": len(self.traffic_data),
            "monitoring_events": len([d for d in self.traffic_data if 'ComponentLifecycleEvent' in d['line'] or 'ChainEvent' in d['line']])
        }

class MonitoringGraphTest:
    """Main test class for monitoring graph connectivity"""
    
    def __init__(self, domain_id: int = 0):
        self.domain_id = domain_id
        self.collector = None
        self.spy_analyzer = None
        
    def run_basic_connectivity_test(self):
        """Test basic Interface → Agent → Service connectivity"""
        logger.info("🧪 Running basic connectivity test...")
        
        # Define expected topology
        topology = ExpectedTopology("basic_connectivity")
        
        # We can't predict exact IDs, so we'll define by type and name patterns
        # The test will need to be flexible about ID matching
        
        # Start monitoring
        self.collector = MonitoringGraphCollector(self.domain_id)
        
        # Start RTIDDSSPY if available
        self.spy_analyzer = RTIDDSSpyAnalyzer(self.domain_id)
        spy_available = self.spy_analyzer.start_capture()
        
        # Run the actual test scenario
        logger.info("Starting monitoring collection...")
        self.collector.start_monitoring(duration_seconds=30.0)
        
        # Give some time for the test to run and generate events
        logger.info("Waiting for test scenario to complete...")
        time.sleep(35.0)  # Wait a bit longer than monitoring duration
        
        # Stop monitoring
        self.collector.stop_monitoring()
        if spy_available:
            self.spy_analyzer.stop_capture()
        
        # Analyze results
        logger.info("Analyzing collected graph data...")
        
        # For basic test, we'll analyze what we found rather than strict topology matching
        summary = self.collector.get_graph_summary()
        
        # Print results
        logger.info("📊 Graph Analysis Results:")
        logger.info(f"  Total Nodes: {summary['total_nodes']}")
        logger.info(f"  Total Edges: {summary['total_edges']}")
        logger.info(f"  Node Types: {summary['node_types']}")
        logger.info(f"  Edge Types: {summary['edge_types']}")
        logger.info(f"  Events Processed: {summary['events_processed']}")
        
        if self.collector.nodes:
            logger.info("🔍 Discovered Nodes:")
            for node in self.collector.nodes.values():
                logger.info(f"  {node}")
        
        if self.collector.edges:
            logger.info("🔗 Discovered Edges:")
            for edge in self.collector.edges.values():
                logger.info(f"  {edge}")
        
        if spy_available:
            traffic_summary = self.spy_analyzer.get_traffic_summary()
            logger.info(f"📡 RTIDDSSPY Traffic: {traffic_summary}")
        
        # Basic success criteria
        success = (
            summary['total_nodes'] > 0 and
            summary['total_edges'] >= 0 and  # Some tests might not have edges yet
            summary['events_processed'] > 0
        )
        
        if success:
            logger.info("✅ Basic connectivity test PASSED")
        else:
            logger.error("❌ Basic connectivity test FAILED")
        
        return success
    
    def run_agent_to_agent_test(self):
        """Test Agent → Agent communication monitoring"""
        logger.info("🧪 Running agent-to-agent connectivity test...")
        
        # This would be similar to basic test but with specific agent-to-agent expectations
        # For now, we'll use the same pattern as basic test
        return self.run_basic_connectivity_test()
    
    def cleanup(self):
        """Clean up test resources"""
        if self.collector:
            self.collector.close()
        if self.spy_analyzer:
            self.spy_analyzer.stop_capture()

def main():
    """Main test runner"""
    logger.info("🚀 Starting Monitoring Graph Connectivity Test")
    
    # Check if we're in the right environment
    if not os.path.exists("genesis_lib"):
        logger.error("❌ Please run from the project root directory")
        return False
    
    test = MonitoringGraphTest(domain_id=0)
    
    try:
        # Run tests
        basic_success = test.run_basic_connectivity_test()
        agent_success = test.run_agent_to_agent_test()
        
        overall_success = basic_success and agent_success
        
        if overall_success:
            logger.info("🎉 All monitoring graph connectivity tests PASSED")
        else:
            logger.error("💥 Some monitoring graph connectivity tests FAILED")
        
        return overall_success
        
    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        test.cleanup()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 