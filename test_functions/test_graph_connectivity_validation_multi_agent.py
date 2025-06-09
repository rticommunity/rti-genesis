#!/usr/bin/env python3
"""
Multi-Agent Graph Connectivity Validation Test

This test validates the complete topology of a multi-agent Genesis system including:
- Interface → Primary Agent → Specialized Agent → Service → Functions
- Agent-to-agent communication paths
- Specialized agent discovery and classification
- Enhanced monitoring with agent-to-agent edges

Expected Topology:
- 1 INTERFACE (StaticInterfaceServiceInterface)
- 1 PRIMARY_AGENT (OpenAIChatAgent) 
- 1 SPECIALIZED_AGENT (WeatherAgent)
- 1 SERVICE (Calculator Service)
- 4 FUNCTIONS (add, divide, multiply, subtract)

Expected Edges:
- 1 INTERFACE_TO_AGENT (Interface → Primary Agent)
- 1 AGENT_TO_AGENT (Primary Agent → Weather Agent)
- 1 AGENT_TO_SERVICE (Primary Agent → Calculator Service)
- 4 SERVICE_TO_FUNCTION (Service → Functions)

Copyright (c) 2025, RTI & Jason Upchurch
"""

import subprocess
import time
import threading
import logging
import json
import sys
import os
from typing import Dict, Any, List, Set
from datetime import datetime
import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path

# Try to import NetworkX for graph analysis
try:
    import networkx as nx
    import matplotlib.pyplot as plt
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("⚠️ NetworkX not available. Graph visualization disabled.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GenesisMultiAgentSystemGraph:
    """
    Enhanced graph representation of the Genesis multi-agent system topology.
    Validates complex multi-agent scenarios with agent-to-agent communication.
    """
    
    def __init__(self):
        if HAS_NETWORKX:
            self.graph = nx.DiGraph()
        else:
            self.graph = None
        
        # Track nodes by type for validation
        self.nodes_by_type = {
            'INTERFACE': set(),
            'PRIMARY_AGENT': set(),
            'SPECIALIZED_AGENT': set(),
            'SERVICE': set(),
            'FUNCTION': set()
        }
        
        # Track edges by type for validation
        self.edges_by_type = {
            'INTERFACE_TO_AGENT': [],
            'AGENT_TO_AGENT': [],
            'AGENT_TO_SERVICE': [],
            'SERVICE_TO_FUNCTION': []
        }
        
        # Store raw events for analysis
        self.raw_events = []
    
    def add_node_from_event(self, event_data: Dict[str, Any]):
        """Add a node to the graph from a lifecycle event"""
        if event_data['event_category'] != 'NODE_DISCOVERY':
            return
            
        component_id = event_data['component_id']
        component_type = event_data['component_type']
        
        # Parse capabilities to get additional metadata
        capabilities = {}
        try:
            capabilities = json.loads(event_data.get('capabilities', '{}'))
        except:
            pass
        
        # Extract human-readable name from capabilities
        display_name = self._extract_display_name(component_type, capabilities, component_id)
        
        # Add node to NetworkX graph if available
        if self.graph is not None:
            self.graph.add_node(component_id, 
                              component_type=component_type,
                              display_name=display_name,
                              capabilities=capabilities)
        
        # Track by type
        self.nodes_by_type[component_type].add(component_id)
        
        logger.info(f"Added {component_type} node: {display_name} ({component_id})")
    
    def _extract_display_name(self, component_type: str, capabilities: Dict, component_id: str) -> str:
        """Extract a human-readable display name from capabilities"""
        if isinstance(capabilities, dict):
            # For functions, try to get function name
            if component_type == 'FUNCTION':
                if 'function_name' in capabilities:
                    return capabilities['function_name']
                elif 'name' in capabilities:
                    return capabilities['name']
            
            # For agents, try to get agent name or service name
            if component_type in ['PRIMARY_AGENT', 'SPECIALIZED_AGENT']:
                if 'agent_name' in capabilities:
                    return capabilities['agent_name']
                elif 'service' in capabilities:
                    return f"{capabilities['service']}Agent"
            
            # For interfaces, try to get interface name
            if component_type == 'INTERFACE':
                if 'interface_name' in capabilities:
                    return capabilities['interface_name']
                elif 'service' in capabilities:
                    return f"{capabilities['service']}Interface"
        
        # Fallback to component ID
        return component_id
    
    def add_edge_from_event(self, event_data: Dict[str, Any]):
        """Add an edge to the graph from a lifecycle event"""
        if event_data['event_category'] != 'EDGE_DISCOVERY':
            return
            
        source_id = event_data.get('source_id')
        target_id = event_data.get('target_id')
        connection_type = event_data.get('connection_type', 'unknown')
        
        if not source_id or not target_id or source_id == target_id:
            return
            
        # Parse capabilities for edge metadata
        capabilities = {}
        try:
            capabilities = json.loads(event_data.get('capabilities', '{}'))
        except:
            pass
        
        # Get human-readable names for source and target
        source_name = self._get_node_display_name(source_id)
        target_name = self._get_node_display_name(target_id)
        
        # Extract edge label from capabilities
        edge_label = self._extract_edge_label(capabilities, connection_type)
        
        # Add edge to NetworkX graph if available
        if self.graph is not None:
            self.graph.add_edge(source_id, target_id,
                              connection_type=connection_type,
                              edge_label=edge_label,
                              capabilities=capabilities)
        
        # Classify edge type for validation
        edge_type = self._classify_edge_type(source_id, target_id, connection_type, capabilities)
        self.edges_by_type[edge_type].append((source_id, target_id))
        
        logger.info(f"Added {edge_type} edge: {source_name} → {target_name} ({edge_label})")
    
    def _get_node_display_name(self, node_id: str) -> str:
        """Get the display name for a node"""
        if self.graph is not None and node_id in self.graph.nodes:
            return self.graph.nodes[node_id].get('display_name', node_id)
        return node_id
    
    def _extract_edge_label(self, capabilities: Dict, connection_type: str) -> str:
        """Extract a human-readable edge label from capabilities"""
        if isinstance(capabilities, dict):
            if 'function_name' in capabilities:
                return capabilities['function_name']
            elif 'agent_name' in capabilities:
                return f"to {capabilities['agent_name']}"
            elif 'service_name' in capabilities:
                return capabilities['service_name']
        
        return connection_type
    
    def _classify_edge_type(self, source_id: str, target_id: str, 
                          connection_type: str, capabilities: Dict) -> str:
        """Classify the type of edge based on node types and metadata"""
        
        # Get node types if they exist
        source_type = self.graph.nodes.get(source_id, {}).get('component_type', 'UNKNOWN') if self.graph else 'UNKNOWN'
        target_type = self.graph.nodes.get(target_id, {}).get('component_type', 'UNKNOWN') if self.graph else 'UNKNOWN'
        
        # First check explicit connection types from the events
        if connection_type == 'AGENT_TO_SERVICE':
            return 'AGENT_TO_SERVICE'
        elif connection_type == 'AGENT_TO_AGENT':
            return 'AGENT_TO_AGENT'
        elif connection_type == 'INTERFACE_TO_AGENT':
            return 'INTERFACE_TO_AGENT'
        elif connection_type == 'SERVICE_TO_FUNCTION':
            return 'SERVICE_TO_FUNCTION'
        elif connection_type == 'function_connection':
            return 'SERVICE_TO_FUNCTION'
        
        # Fallback to node type analysis
        if source_type == 'INTERFACE' and target_type in ['PRIMARY_AGENT', 'SPECIALIZED_AGENT']:
            return 'INTERFACE_TO_AGENT'
        elif source_type in ['PRIMARY_AGENT', 'SPECIALIZED_AGENT'] and target_type in ['PRIMARY_AGENT', 'SPECIALIZED_AGENT']:
            return 'AGENT_TO_AGENT'
        elif source_type in ['PRIMARY_AGENT', 'SPECIALIZED_AGENT'] and target_type == 'FUNCTION':
            return 'AGENT_TO_SERVICE'
        elif source_type == 'FUNCTION' and target_type == 'FUNCTION':
            return 'SERVICE_TO_FUNCTION'
        
        return 'UNKNOWN'
    
    def validate_expected_topology(self, expected_topology: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the graph against expected topology"""
        results = {
            'passed': True,
            'node_validation': {},
            'edge_validation': {},
            'missing_nodes': {},
            'missing_edges': {},
            'connectivity_validation': {}
        }
        
        # Validate nodes
        expected_nodes = expected_topology.get('expected_nodes', {})
        for node_type, expected_count in expected_nodes.items():
            actual_count = len(self.nodes_by_type.get(node_type, set()))
            results['node_validation'][node_type] = {
                'expected': expected_count,
                'actual': actual_count,
                'passed': actual_count >= expected_count
            }
            
            if actual_count < expected_count:
                results['passed'] = False
                results['missing_nodes'][node_type] = expected_count - actual_count
        
        # Validate edges
        expected_edges = expected_topology.get('expected_edges', {})
        for edge_type, expected_count in expected_edges.items():
            actual_count = len(self.edges_by_type.get(edge_type, []))
            results['edge_validation'][edge_type] = {
                'expected': expected_count,
                'actual': actual_count,
                'passed': actual_count >= expected_count
            }
            
            if actual_count < expected_count:
                results['passed'] = False
                results['missing_edges'][edge_type] = expected_count - actual_count
        
        # Validate connectivity requirements
        connectivity_requirements = expected_topology.get('connectivity_requirements', [])
        for requirement in connectivity_requirements:
            requirement_passed = self._check_connectivity_requirement(requirement)
            requirement_name = requirement.get('type', 'unknown')
            results['connectivity_validation'][requirement_name] = requirement_passed
            
            if not requirement_passed:
                results['passed'] = False
        
        return results
    
    def _check_connectivity_requirement(self, requirement: Dict[str, Any]) -> bool:
        """Check a specific connectivity requirement"""
        if not self.graph:
            return False
            
        req_type = requirement.get('type')
        
        if req_type == 'all_interfaces_connected':
            # Check that all interfaces have at least one outgoing edge
            for interface_id in self.nodes_by_type.get('INTERFACE', set()):
                if self.graph.out_degree(interface_id) == 0:
                    return False
            return True
            
        elif req_type == 'all_agents_have_services':
            # Check that all agents can reach at least one service
            for agent_type in ['PRIMARY_AGENT', 'SPECIALIZED_AGENT']:
                for agent_id in self.nodes_by_type.get(agent_type, set()):
                    # Check if agent has path to any service
                    has_service_path = False
                    for service_id in self.nodes_by_type.get('SERVICE', set()):
                        if nx.has_path(self.graph, agent_id, service_id):
                            has_service_path = True
                            break
                    if not has_service_path:
                        return False
            return True
            
        elif req_type == 'agent_to_agent_communication':
            # Check that primary agents can communicate with specialized agents
            primary_agents = self.nodes_by_type.get('PRIMARY_AGENT', set())
            specialized_agents = self.nodes_by_type.get('SPECIALIZED_AGENT', set())
            
            if not primary_agents or not specialized_agents:
                return len(specialized_agents) == 0  # Pass if no specialized agents expected
            
            # Check if there's at least one agent-to-agent connection
            for primary_id in primary_agents:
                for specialized_id in specialized_agents:
                    if self.graph.has_edge(primary_id, specialized_id) or self.graph.has_edge(specialized_id, primary_id):
                        return True
            return False
        
        return True
    
    def get_graph_summary(self) -> Dict[str, Any]:
        """Get a summary of the graph structure"""
        return {
            'total_nodes': sum(len(nodes) for nodes in self.nodes_by_type.values()),
            'nodes_by_type': {k: len(v) for k, v in self.nodes_by_type.items()},
            'total_edges': sum(len(edges) for edges in self.edges_by_type.values()),
            'edges_by_type': {k: len(v) for k, v in self.edges_by_type.items()},
            'has_networkx': HAS_NETWORKX
        }
    
    def save_graph_visualization(self, filename: str = 'genesis_multi_agent_graph.png'):
        """Save a visualization of the multi-agent graph"""
        if not HAS_NETWORKX:
            print("⚠️ Cannot save visualization without NetworkX and matplotlib")
            return
            
        try:
            plt.figure(figsize=(16, 12))
            
            # Position nodes using spring layout with more space
            pos = nx.spring_layout(self.graph, k=3, iterations=100, seed=42)
            
            # Draw nodes by type with different colors and shapes
            node_colors = {
                'INTERFACE': '#87CEEB',           # Sky blue
                'PRIMARY_AGENT': '#90EE90',       # Light green
                'SPECIALIZED_AGENT': '#FFB6C1',   # Light pink
                'SERVICE': '#DDA0DD',             # Plum
                'FUNCTION': '#F0E68C'             # Khaki
            }
            
            node_shapes = {
                'INTERFACE': 's',        # Square
                'PRIMARY_AGENT': 'o',    # Circle
                'SPECIALIZED_AGENT': '^', # Triangle
                'SERVICE': 'D',          # Diamond
                'FUNCTION': 'h'          # Hexagon
            }
            
            # Draw nodes by type
            for node_type, nodes in self.nodes_by_type.items():
                if nodes:
                    node_list = list(nodes)
                    labels = {node: self._get_node_display_name(node) for node in node_list}
                    
                    nx.draw_networkx_nodes(
                        self.graph, pos,
                        nodelist=node_list,
                        node_color=node_colors.get(node_type, '#CCCCCC'),
                        node_shape=node_shapes.get(node_type, 'o'),
                        node_size=2000,
                        alpha=0.8
                    )
            
            # Draw edges with different colors by type
            edge_colors = {
                'INTERFACE_TO_AGENT': '#FF6B6B',    # Red
                'AGENT_TO_AGENT': '#4ECDC4',        # Teal
                'AGENT_TO_SERVICE': '#45B7D1',      # Blue
                'SERVICE_TO_FUNCTION': '#96CEB4'    # Green
            }
            
            for edge_type, edges in self.edges_by_type.items():
                if edges:
                    nx.draw_networkx_edges(
                        self.graph, pos,
                        edgelist=edges,
                        edge_color=edge_colors.get(edge_type, '#CCCCCC'),
                        arrows=True,
                        arrowsize=20,
                        width=2,
                        alpha=0.7
                    )
            
            # Add labels with display names
            labels = {}
            for node in self.graph.nodes():
                display_name = self._get_node_display_name(node)
                # Truncate long names for better display
                if len(display_name) > 15:
                    display_name = display_name[:12] + "..."
                labels[node] = display_name
            
            nx.draw_networkx_labels(self.graph, pos, labels, font_size=8, font_weight='bold')
            
            # Add edge labels for important connections
            edge_labels = {}
            for edge in self.graph.edges(data=True):
                source, target, data = edge
                edge_label = data.get('edge_label', '')
                if edge_label and len(edge_label) < 10:
                    edge_labels[(source, target)] = edge_label
            
            if edge_labels:
                nx.draw_networkx_edge_labels(self.graph, pos, edge_labels, font_size=6)
            
            plt.title("Genesis Multi-Agent System Topology", fontsize=16, fontweight='bold')
            
            # Add legend
            legend_elements = []
            for node_type, color in node_colors.items():
                if self.nodes_by_type[node_type]:
                    legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', 
                                                    markerfacecolor=color, markersize=10, 
                                                    label=f'{node_type} ({len(self.nodes_by_type[node_type])})'))
            
            plt.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(0, 1))
            
            plt.axis('off')
            plt.tight_layout()
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"✅ Multi-agent graph visualization saved to {filename}")
            
        except Exception as e:
            print(f"❌ Error saving graph visualization: {e}")
    
    def _save_graph_summary(self, filename: str):
        """Save a detailed text summary of the graph"""
        try:
            with open(filename, 'w') as f:
                f.write("Genesis Multi-Agent System Topology Summary\n")
                f.write("=" * 50 + "\n\n")
                
                # Overall statistics
                summary = self.get_graph_summary()
                f.write(f"Total Nodes: {summary['total_nodes']}\n")
                f.write(f"Total Edges: {summary['total_edges']}\n\n")
                
                # Nodes by type
                f.write("Nodes by Type:\n")
                for node_type, count in summary['nodes_by_type'].items():
                    f.write(f"  {node_type}: {count}\n")
                f.write("\n")
                
                # Edges by type
                f.write("Edges by Type:\n")
                for edge_type, count in summary['edges_by_type'].items():
                    f.write(f"  {edge_type}: {count}\n")
                f.write("\n")
                
                # Detailed node list
                f.write("Detailed Node List:\n")
                for node in self.graph.nodes() if self.graph else []:
                    node_data = self.graph.nodes[node]
                    display_name = node_data.get('display_name', 'Unknown')
                    component_type = node_data.get('component_type', 'Unknown')
                    f.write(f"  {display_name} ({component_type})\n")
                    f.write(f"    ID: {node}\n")
                    
                    # Show capabilities if available
                    capabilities = node_data.get('capabilities', {})
                    if capabilities and isinstance(capabilities, dict):
                        for key, value in capabilities.items():
                            if key not in ['agent_id', 'component_id'] and value:
                                f.write(f"    {key}: {value}\n")
                    f.write("\n")
                
                # Detailed edge list
                f.write("Detailed Edge List:\n")
                for edge_type, edges in self.edges_by_type.items():
                    if edges:
                        f.write(f"  {edge_type}:\n")
                        for source, target in edges:
                            source_name = self._get_node_display_name(source)
                            target_name = self._get_node_display_name(target)
                            f.write(f"    {source_name} → {target_name}\n")
                        f.write("\n")
                
            print(f"✅ Multi-agent graph summary saved to {filename}")
            
        except Exception as e:
            print(f"❌ Error saving graph summary: {e}")


class MultiAgentGraphConnectivityValidator:
    """
    Enhanced validator for multi-agent Genesis system topology.
    Monitors and validates complex multi-agent communication patterns.
    """
    
    def __init__(self, domain_id: int = 0):
        self.domain_id = domain_id
        self.graph = GenesisMultiAgentSystemGraph()
        self.monitoring_active = False
        self.monitor_thread = None
        
        # Set up DDS monitoring
        self._setup_dds()
    
    def _setup_dds(self):
        """Set up DDS entities for monitoring"""
        try:
            # Create participant
            self.participant = dds.DomainParticipant(self.domain_id)
            self.subscriber = dds.Subscriber(self.participant)
            
            # Get types from XML
            config_path = get_datamodel_path()
            self.type_provider = dds.QosProvider(config_path)
            
            # Set up ComponentLifecycleEvent monitoring
            self.lifecycle_type = self.type_provider.type("genesis_lib", "ComponentLifecycleEvent")
            self.lifecycle_topic = dds.DynamicData.Topic(
                self.participant,
                "ComponentLifecycleEvent",
                self.lifecycle_type
            )
            
            # Configure reader QoS for reliable delivery
            reader_qos = dds.QosProvider.default.datareader_qos
            reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            reader_qos.history.kind = dds.HistoryKind.KEEP_ALL
            
            # Create reader
            self.lifecycle_reader = dds.DynamicData.DataReader(
                subscriber=self.subscriber,
                topic=self.lifecycle_topic,
                qos=reader_qos
            )
            
            logger.info(f"✅ DDS monitoring setup complete on domain {self.domain_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup DDS monitoring: {e}")
            raise
    
    def start_monitoring(self, duration_seconds: float = 45.0):
        """Start monitoring for the specified duration"""
        self.monitoring_active = True
        
        def monitor_thread():
            start_time = time.time()
            logger.info(f"🔍 Starting multi-agent topology monitoring for {duration_seconds} seconds...")
            
            while self.monitoring_active and (time.time() - start_time) < duration_seconds:
                try:
                    # Take samples from lifecycle events
                    samples = self.lifecycle_reader.take()
                    
                    for data, info in samples:
                        if data is not None and info.state.instance_state == dds.InstanceState.ALIVE:
                            self._process_lifecycle_event(data)
                    
                    time.sleep(0.1)  # Small delay to prevent busy waiting
                    
                except Exception as e:
                    logger.error(f"Error during monitoring: {e}")
                    time.sleep(1)
            
            logger.info("🔍 Multi-agent topology monitoring completed")
        
        self.monitor_thread = threading.Thread(target=monitor_thread)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def _process_lifecycle_event(self, data):
        """Process a ComponentLifecycleEvent"""
        try:
            # Map enum values to strings
            component_types = ["INTERFACE", "PRIMARY_AGENT", "SPECIALIZED_AGENT", "FUNCTION"]
            states = ["JOINING", "DISCOVERING", "READY", "BUSY", "DEGRADED", "OFFLINE"]
            event_categories = ["NODE_DISCOVERY", "EDGE_DISCOVERY", "STATE_CHANGE", "AGENT_INIT", "AGENT_READY", "AGENT_SHUTDOWN", "DDS_ENDPOINT"]
            
            # Convert enum values
            component_type_idx = int(data["component_type"])
            event_category_idx = int(data["event_category"])
            
            # Build event data
            event_data = {
                "event_category": event_categories[event_category_idx] if 0 <= event_category_idx < len(event_categories) else "UNKNOWN",
                "component_id": data["component_id"],
                "component_type": component_types[component_type_idx] if 0 <= component_type_idx < len(component_types) else "UNKNOWN",
                "source_id": str(data["source_id"]) if data["source_id"] else "",
                "target_id": str(data["target_id"]) if data["target_id"] else "",
                "connection_type": str(data["connection_type"]) if data["connection_type"] else "",
                "capabilities": data["capabilities"],
                "reason": data["reason"]
            }
            
            # Store raw event
            self.graph.raw_events.append(event_data)
            
            # Process based on event category
            if event_data["event_category"] == "NODE_DISCOVERY":
                self.graph.add_node_from_event(event_data)
            elif event_data["event_category"] == "EDGE_DISCOVERY":
                self.graph.add_edge_from_event(event_data)
                
        except Exception as e:
            logger.error(f"Error processing lifecycle event: {e}")
    
    def validate_system_topology(self) -> Dict[str, Any]:
        """Validate the complete multi-agent system topology"""
        
        # Define expected multi-agent topology
        expected_topology = {
            'expected_nodes': {
                'INTERFACE': 1,           # One interface
                'PRIMARY_AGENT': 1,       # One primary agent (OpenAI)
                'SPECIALIZED_AGENT': 1,   # One specialized agent (Weather)
                'FUNCTION': 5,            # Calculator service + 4 functions
            },
            'expected_edges': {
                'INTERFACE_TO_AGENT': 1,  # Interface connects to primary agent
                'AGENT_TO_AGENT': 1,      # Primary agent connects to weather agent
                'AGENT_TO_SERVICE': 1,    # Primary agent connects to service
                'SERVICE_TO_FUNCTION': 4, # Service connects to functions
            },
            'connectivity_requirements': [
                {'type': 'all_interfaces_connected'},
                {'type': 'all_agents_have_services'},
                {'type': 'agent_to_agent_communication'},
            ]
        }
        
        # Validate topology
        validation_results = self.graph.validate_expected_topology(expected_topology)
        
        # Generate summary and visualization
        self.graph.save_graph_visualization('genesis_multi_agent_topology_graph.png')
        self.graph._save_graph_summary('genesis_multi_agent_topology_graph_summary.txt')
        
        return validation_results
    
    def close(self):
        """Clean up resources"""
        self.stop_monitoring()
        
        if hasattr(self, 'lifecycle_reader'):
            self.lifecycle_reader.close()
        if hasattr(self, 'subscriber'):
            self.subscriber.close()
        if hasattr(self, 'participant'):
            self.participant.close()


def run_multi_agent_genesis_scenario():
    """Run the multi-agent Genesis test scenario"""
    logger.info("🚀 Starting multi-agent Genesis scenario...")
    
    # Start the multi-agent test script
    script_path = os.path.join(os.path.dirname(__file__), '..', 'run_scripts', 'run_interface_agent_agent_service_test.sh')
    
    if not os.path.exists(script_path):
        logger.error(f"❌ Multi-agent test script not found: {script_path}")
        logger.info("📝 Please create the multi-agent test script first")
        return None
    
    try:
        # Run the test scenario
        process = subprocess.Popen(
            ['bash', script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for scenario to complete
        stdout, stderr = process.communicate(timeout=60)
        
        if process.returncode == 0:
            logger.info("✅ Multi-agent Genesis scenario completed successfully")
            return True
        else:
            logger.error(f"❌ Multi-agent Genesis scenario failed with return code {process.returncode}")
            logger.error(f"STDERR: {stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Multi-agent Genesis scenario timed out")
        process.kill()
        return False
    except Exception as e:
        logger.error(f"❌ Error running multi-agent Genesis scenario: {e}")
        return False


def main():
    """Main test function"""
    print("🧪 Genesis Multi-Agent Graph Connectivity Validation Test")
    print("=" * 60)
    
    if not HAS_NETWORKX:
        print("⚠️ NetworkX not available. Install with: pip install networkx matplotlib")
        print("   Graph analysis will be limited without NetworkX")
    
    # Create validator
    validator = MultiAgentGraphConnectivityValidator(domain_id=0)
    
    try:
        # Start monitoring
        validator.start_monitoring(duration_seconds=45.0)
        
        # Run the multi-agent Genesis scenario
        scenario_result = run_multi_agent_genesis_scenario()
        
        if scenario_result is None:
            print("⚠️ Multi-agent scenario script not found - monitoring existing system")
        elif not scenario_result:
            print("❌ Multi-agent scenario failed - analyzing partial results")
        
        # Wait for monitoring to complete
        time.sleep(2)
        validator.stop_monitoring()
        
        # Validate topology
        print("\n🔍 Validating multi-agent system topology...")
        results = validator.validate_system_topology()
        
        # Print results
        print("\n📊 Multi-Agent Topology Validation Results:")
        print("-" * 50)
        
        # Node validation
        print("Node Validation:")
        for node_type, validation in results['node_validation'].items():
            status = "✅" if validation['passed'] else "❌"
            print(f"  {status} {node_type}: {validation['actual']}/{validation['expected']}")
        
        # Edge validation
        print("\nEdge Validation:")
        for edge_type, validation in results['edge_validation'].items():
            status = "✅" if validation['passed'] else "❌"
            print(f"  {status} {edge_type}: {validation['actual']}/{validation['expected']}")
        
        # Connectivity validation
        print("\nConnectivity Validation:")
        for requirement, passed in results['connectivity_validation'].items():
            status = "✅" if passed else "❌"
            print(f"  {status} {requirement}")
        
        # Overall result
        print(f"\n🎯 Overall Result: {'✅ PASSED' if results['passed'] else '❌ FAILED'}")
        
        # Show missing components if any
        if results['missing_nodes']:
            print("\n❌ Missing Nodes:")
            for node_type, count in results['missing_nodes'].items():
                print(f"  - {node_type}: {count} missing")
        
        if results['missing_edges']:
            print("\n❌ Missing Edges:")
            for edge_type, count in results['missing_edges'].items():
                print(f"  - {edge_type}: {count} missing")
        
        # Graph summary
        summary = validator.graph.get_graph_summary()
        print(f"\n📈 Graph Summary:")
        print(f"  Total Nodes: {summary['total_nodes']}")
        print(f"  Total Edges: {summary['total_edges']}")
        print(f"  NetworkX Available: {summary['has_networkx']}")
        
        if HAS_NETWORKX:
            print(f"\n📁 Files Generated:")
            print(f"  - genesis_multi_agent_topology_graph.png (visualization)")
            print(f"  - genesis_multi_agent_topology_graph_summary.txt (detailed summary)")
        
        return results['passed']
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        validator.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 