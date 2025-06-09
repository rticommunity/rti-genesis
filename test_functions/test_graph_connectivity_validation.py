#!/usr/bin/env python3
"""
Graph Connectivity Validation Test

This test builds actual graph structures from monitoring events and validates that all expected
nodes and edges are present for a Genesis system topology. Uses NetworkX for graph analysis.
"""

import asyncio
import logging
import subprocess
import sys
import time
import threading
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
import re

import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path

# NetworkX for graph analysis
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import networkx as nx
    import matplotlib.pyplot as plt
    HAS_NETWORKX = True
except ImportError:
    print("⚠️ NetworkX not available. Install with: pip install networkx matplotlib")
    HAS_NETWORKX = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("GraphConnectivityTest")

class GenesisSystemGraph:
    """Represents the actual topology of a Genesis system as a directed graph"""
    
    def __init__(self):
        if not HAS_NETWORKX:
            raise ImportError("NetworkX is required for graph analysis")
            
        self.graph = nx.DiGraph()  # Directed graph for Genesis topology
        self.nodes_by_type = {
            'INTERFACE': set(),
            'PRIMARY_AGENT': set(),
            'SPECIALIZED_AGENT': set(), 
            'SERVICE': set(),
            'FUNCTION': set()
        }
        self.edges_by_type = {
            'INTERFACE_TO_AGENT': set(),
            'AGENT_TO_AGENT': set(),
            'AGENT_TO_SERVICE': set(),
            'SERVICE_TO_FUNCTION': set(),
            'FUNCTION_CONNECTION': set(),
            'AGENT_CONNECTION': set()
        }
        self.edge_discovery_events = []
        self.node_discovery_events = []
        
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
        
        # Add node to graph with attributes
        self.graph.add_node(component_id, 
                          component_type=component_type,
                          display_name=display_name,
                          capabilities=capabilities,
                          event_data=event_data)
        
        # Track by type
        if component_type in self.nodes_by_type:
            self.nodes_by_type[component_type].add(component_id)
        
        self.node_discovery_events.append(event_data)
        print(f"🔵 Added {component_type} node: {display_name} ({component_id[:8]}...)")
    
    def _extract_display_name(self, component_type: str, capabilities: Dict, component_id: str) -> str:
        """Extract a human-readable display name from capabilities"""
        
        # For functions, look for function_name
        if component_type == 'FUNCTION':
            if 'function_name' in capabilities:
                return capabilities['function_name']
            elif 'name' in capabilities:
                return capabilities['name']
        
        # For agents, look for agent_name or service info
        elif component_type in ['PRIMARY_AGENT', 'SPECIALIZED_AGENT']:
            if 'agent_name' in capabilities:
                return capabilities['agent_name']
            elif 'service' in capabilities:
                return f"{capabilities['service']}Agent"
            elif 'agent_type' in capabilities:
                return f"{capabilities['agent_type']}"
        
        # For interfaces, look for interface info
        elif component_type == 'INTERFACE':
            if 'interface_type' in capabilities:
                interface_type = capabilities['interface_type']
                service = capabilities.get('service', 'Unknown')
                return f"{service}Interface"
            elif 'service' in capabilities:
                return f"{capabilities['service']}Interface"
        
        # For services, look for service name
        elif component_type == 'SERVICE':
            if 'service_name' in capabilities:
                return capabilities['service_name']
            elif 'service' in capabilities:
                return capabilities['service']
        
        # Fallback to shortened component_id
        return f"{component_type}_{component_id[:8]}"
        
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
            
        # Add edge to graph
        self.graph.add_edge(source_id, target_id,
                          connection_type=connection_type,
                          edge_label=edge_label,
                          capabilities=capabilities,
                          event_data=event_data)
        
        # Classify edge type
        edge_type = self._classify_edge_type(source_id, target_id, connection_type, capabilities)
        if edge_type in self.edges_by_type:
            self.edges_by_type[edge_type].add((source_id, target_id))
        
        self.edge_discovery_events.append(event_data)
        print(f"🔗 Added {edge_type} edge: {source_name} → {target_name} ({edge_label})")
    
    def _get_node_display_name(self, node_id: str) -> str:
        """Get the display name for a node, or return shortened ID if not found"""
        if node_id in self.graph.nodes:
            return self.graph.nodes[node_id].get('display_name', f"{node_id[:8]}...")
        return f"{node_id[:8]}..."
    
    def _extract_edge_label(self, capabilities: Dict, connection_type: str) -> str:
        """Extract a human-readable label for the edge"""
        
        # Look for function name in capabilities
        if 'function_name' in capabilities:
            return capabilities['function_name']
        
        # Look for edge type description
        if 'edge_type' in capabilities:
            edge_type = capabilities['edge_type']
            if edge_type == 'interface_to_agent':
                return 'connects'
            elif edge_type == 'agent_function':
                return 'calls'
            elif edge_type == 'function_connection':
                return 'provides'
            elif edge_type == 'agent_to_service':
                return 'uses'
        
        # Use connection type as fallback
        return connection_type.lower().replace('_', ' ')
    
    def _classify_edge_type(self, source_id: str, target_id: str, 
                          connection_type: str, capabilities: Dict) -> str:
        """Classify the type of edge based on node types and metadata"""
        
        # Get node types if they exist
        source_type = self.graph.nodes.get(source_id, {}).get('component_type', 'UNKNOWN')
        target_type = self.graph.nodes.get(target_id, {}).get('component_type', 'UNKNOWN')
        
        # First check explicit connection types from the events
        if connection_type == 'AGENT_TO_SERVICE':
            return 'AGENT_TO_SERVICE'
        elif connection_type == 'FUNCTION_CONNECTION':
            return 'FUNCTION_CONNECTION'
        elif connection_type == 'INTERFACE_TO_AGENT':
            return 'INTERFACE_TO_AGENT'
        elif connection_type == 'function_connection':
            return 'SERVICE_TO_FUNCTION'
        elif connection_type == 'agent_connection' or connection_type == 'AGENT_COMMUNICATION':
            return 'AGENT_TO_AGENT'
        elif 'function_name' in capabilities:
            return 'FUNCTION_CONNECTION'
            
        # Classify based on node types (fallback)
        if source_type == 'INTERFACE' and target_type in ['PRIMARY_AGENT', 'SPECIALIZED_AGENT']:
            return 'INTERFACE_TO_AGENT'
        elif source_type in ['PRIMARY_AGENT', 'SPECIALIZED_AGENT'] and target_type in ['PRIMARY_AGENT', 'SPECIALIZED_AGENT']:
            return 'AGENT_TO_AGENT'
        elif source_type in ['PRIMARY_AGENT', 'SPECIALIZED_AGENT'] and target_type == 'SERVICE':
            return 'AGENT_TO_SERVICE'
        elif source_type == 'SERVICE' and target_type == 'FUNCTION':
            return 'SERVICE_TO_FUNCTION'
        else:
            return 'UNKNOWN'
    
    def validate_expected_topology(self, expected_topology: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that the graph matches expected topology"""
        results = {
            'nodes_valid': True,
            'edges_valid': True,
            'missing_nodes': [],
            'missing_edges': [],
            'extra_nodes': [],
            'extra_edges': [],
            'orphaned_nodes': [],
            'connectivity_issues': []
        }
        
        # Validate expected nodes
        expected_nodes = expected_topology.get('expected_nodes', {})
        for node_type, expected_count in expected_nodes.items():
            actual_count = len(self.nodes_by_type.get(node_type, set()))
            if actual_count < expected_count:
                results['missing_nodes'].append({
                    'type': node_type,
                    'expected': expected_count,
                    'actual': actual_count,
                    'missing': expected_count - actual_count
                })
                results['nodes_valid'] = False
        
        # Validate expected edges
        expected_edges = expected_topology.get('expected_edges', {})
        for edge_type, expected_count in expected_edges.items():
            actual_count = len(self.edges_by_type.get(edge_type, set()))
            if actual_count < expected_count:
                results['missing_edges'].append({
                    'type': edge_type,
                    'expected': expected_count,
                    'actual': actual_count,
                    'missing': expected_count - actual_count
                })
                results['edges_valid'] = False
        
        # Find orphaned nodes (nodes with no edges)
        for node in self.graph.nodes():
            if self.graph.degree(node) == 0:
                results['orphaned_nodes'].append(node)
        
        # Check connectivity requirements
        connectivity_requirements = expected_topology.get('connectivity_requirements', [])
        for requirement in connectivity_requirements:
            if not self._check_connectivity_requirement(requirement):
                results['connectivity_issues'].append(requirement)
        
        return results
    
    def _check_connectivity_requirement(self, requirement: Dict[str, Any]) -> bool:
        """Check a specific connectivity requirement"""
        req_type = requirement.get('type')
        
        if req_type == 'all_interfaces_connected':
            # All interfaces should have at least one outgoing edge
            for interface in self.nodes_by_type.get('INTERFACE', set()):
                if self.graph.out_degree(interface) == 0:
                    return False
            return True
            
        elif req_type == 'all_agents_reachable':
            # All agents should be reachable from interfaces
            interfaces = list(self.nodes_by_type.get('INTERFACE', set()))
            agents = list(self.nodes_by_type.get('PRIMARY_AGENT', set())) + list(self.nodes_by_type.get('SPECIALIZED_AGENT', set()))
            
            for agent in agents:
                reachable = False
                for interface in interfaces:
                    if nx.has_path(self.graph, interface, agent):
                        reachable = True
                        break
                if not reachable:
                    return False
            return True
            
        elif req_type == 'all_functions_accessible':
            # All functions should be accessible from agents
            agents = list(self.nodes_by_type.get('PRIMARY_AGENT', set())) + list(self.nodes_by_type.get('SPECIALIZED_AGENT', set()))
            functions = list(self.nodes_by_type.get('FUNCTION', set()))
            
            for function in functions:
                accessible = False
                for agent in agents:
                    if nx.has_path(self.graph, agent, function):
                        accessible = True
                        break
                if not accessible:
                    return False
            return True
        
        return True
    
    def get_graph_summary(self) -> Dict[str, Any]:
        """Get a summary of the graph structure"""
        return {
            'total_nodes': self.graph.number_of_nodes(),
            'total_edges': self.graph.number_of_edges(),
            'nodes_by_type': {k: len(v) for k, v in self.nodes_by_type.items()},
            'edges_by_type': {k: len(v) for k, v in self.edges_by_type.items()},
            'is_connected': nx.is_weakly_connected(self.graph),
            'number_of_components': nx.number_weakly_connected_components(self.graph),
            'average_degree': sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes() if self.graph.number_of_nodes() > 0 else 0
        }
    
    def save_graph_visualization(self, filename: str = 'genesis_graph.png'):
        """Save a visualization of the graph"""
        if not HAS_NETWORKX:
            print("⚠️ Cannot save visualization without NetworkX and matplotlib")
            return
            
        try:
            plt.figure(figsize=(16, 12))
            
            # Position nodes using spring layout with more space
            pos = nx.spring_layout(self.graph, k=3, iterations=100, seed=42)
            
            # Draw nodes by type with different colors and shapes
            node_colors = {
                'INTERFACE': '#87CEEB',      # Sky blue
                'PRIMARY_AGENT': '#90EE90',  # Light green
                'SPECIALIZED_AGENT': '#98FB98', # Pale green
                'FUNCTION': '#FFB6C1',       # Light pink
                'SERVICE': '#F0E68C'         # Khaki
            }
            
            # Draw nodes with better styling
            for node_type, color in node_colors.items():
                nodes = [n for n in self.graph.nodes() 
                        if self.graph.nodes[n].get('component_type') == node_type]
                if nodes:
                    nx.draw_networkx_nodes(self.graph, pos, 
                                         nodelist=nodes, 
                                         node_color=color, 
                                         node_size=1500,
                                         alpha=0.9,
                                         edgecolors='black',
                                         linewidths=2)
            
            # Draw edges with better styling
            nx.draw_networkx_edges(self.graph, pos, 
                                 alpha=0.7, 
                                 arrows=True, 
                                 arrowsize=20,
                                 edge_color='gray',
                                 width=2,
                                 arrowstyle='->')
            
            # Create human-readable labels using display names
            labels = {}
            for node in self.graph.nodes():
                display_name = self.graph.nodes[node].get('display_name', node)
                # Wrap long names
                if len(display_name) > 15:
                    words = display_name.split()
                    if len(words) > 1:
                        mid = len(words) // 2
                        display_name = '\n'.join([' '.join(words[:mid]), ' '.join(words[mid:])])
                    else:
                        display_name = display_name[:12] + '...'
                labels[node] = display_name
            
            # Draw node labels
            nx.draw_networkx_labels(self.graph, pos, labels, font_size=10, font_weight='bold')
            
            # Draw edge labels if they exist
            edge_labels = {}
            for edge in self.graph.edges():
                edge_data = self.graph.edges[edge]
                edge_label = edge_data.get('edge_label', '')
                if edge_label and edge_label != 'unknown':
                    # Shorten edge labels
                    if len(edge_label) > 10:
                        edge_label = edge_label[:8] + '..'
                    edge_labels[edge] = edge_label
            
            if edge_labels:
                nx.draw_networkx_edge_labels(self.graph, pos, edge_labels, font_size=8, alpha=0.8)
            
            # Add a legend
            legend_elements = []
            for node_type, color in node_colors.items():
                if any(self.graph.nodes[n].get('component_type') == node_type for n in self.graph.nodes()):
                    legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', 
                                                    markerfacecolor=color, markersize=10, 
                                                    label=node_type, markeredgecolor='black'))
            
            if legend_elements:
                plt.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(0, 1))
            
            # Add title and summary
            summary = self.get_graph_summary()
            title = f'Genesis System Topology Graph\n'
            title += f'Nodes: {summary["total_nodes"]} | Edges: {summary["total_edges"]} | '
            title += f'Connected: {"Yes" if summary["is_connected"] else "No"}'
            
            plt.title(title, fontsize=14, fontweight='bold', pad=20)
            plt.axis('off')
            plt.tight_layout()
            plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
            plt.close()
            
            print(f"📊 Enhanced graph visualization saved to {filename}")
            
            # Also save a detailed summary
            self._save_graph_summary(filename.replace('.png', '_summary.txt'))
            
        except Exception as e:
            print(f"⚠️ Could not save graph visualization: {e}")
            import traceback
            traceback.print_exc()
    
    def _save_graph_summary(self, filename: str):
        """Save a detailed text summary of the graph"""
        try:
            with open(filename, 'w') as f:
                f.write("Genesis System Graph Summary\n")
                f.write("=" * 50 + "\n\n")
                
                # Graph statistics
                summary = self.get_graph_summary()
                f.write("Graph Statistics:\n")
                f.write(f"  Total Nodes: {summary['total_nodes']}\n")
                f.write(f"  Total Edges: {summary['total_edges']}\n")
                f.write(f"  Is Connected: {summary['is_connected']}\n")
                f.write(f"  Components: {summary['number_of_components']}\n")
                f.write(f"  Average Degree: {summary['average_degree']:.2f}\n\n")
                
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
                for node in self.graph.nodes():
                    node_data = self.graph.nodes[node]
                    display_name = node_data.get('display_name', 'Unknown')
                    component_type = node_data.get('component_type', 'Unknown')
                    f.write(f"  {display_name} ({component_type})\n")
                    f.write(f"    ID: {node}\n")
                    
                    # Show capabilities if available
                    capabilities = node_data.get('capabilities', {})
                    if capabilities and isinstance(capabilities, dict):
                        for key, value in capabilities.items():
                            if key in ['function_name', 'agent_name', 'service', 'description']:
                                f.write(f"    {key}: {value}\n")
                    elif capabilities and isinstance(capabilities, list):
                        f.write(f"    capabilities: {', '.join(str(c) for c in capabilities)}\n")
                    f.write("\n")
                
                # Detailed edge list
                f.write("Detailed Edge List:\n")
                for edge in self.graph.edges():
                    source, target = edge
                    edge_data = self.graph.edges[edge]
                    
                    source_name = self._get_node_display_name(source)
                    target_name = self._get_node_display_name(target)
                    connection_type = edge_data.get('connection_type', 'unknown')
                    edge_label = edge_data.get('edge_label', '')
                    
                    f.write(f"  {source_name} → {target_name}\n")
                    f.write(f"    Type: {connection_type}\n")
                    if edge_label:
                        f.write(f"    Label: {edge_label}\n")
                    f.write(f"    Source ID: {source}\n")
                    f.write(f"    Target ID: {target}\n")
                    f.write("\n")
            
            print(f"📄 Graph summary saved to {filename}")
            
        except Exception as e:
            print(f"⚠️ Could not save graph summary: {e}")

class GraphConnectivityValidator:
    """Monitors events and validates graph connectivity"""
    
    def __init__(self, domain_id: int = 0):
        self.domain_id = domain_id
        self.system_graph = GenesisSystemGraph()
        self.monitoring_active = False
        
        # Set up DDS monitoring
        self._setup_dds()
    
    def _setup_dds(self):
        """Set up DDS monitoring"""
        try:
            print(f"🔧 Setting up DDS monitoring on domain {self.domain_id}")
            
            # Create DDS entities
            self.participant = dds.DomainParticipant(self.domain_id)
            self.subscriber = dds.Subscriber(self.participant)
            
            # Get type provider
            provider = dds.QosProvider(get_datamodel_path())
            
            # Set up ComponentLifecycleEvent
            self.lifecycle_type = provider.type("genesis_lib", "ComponentLifecycleEvent")
            self.lifecycle_topic = dds.DynamicData.Topic(
                self.participant, "ComponentLifecycleEvent", self.lifecycle_type
            )
            
            # Configure reader QoS
            reader_qos = dds.QosProvider.default.datareader_qos
            reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
            reader_qos.history.depth = 1000
            
            # Create reader
            self.lifecycle_reader = dds.DynamicData.DataReader(
                subscriber=self.subscriber,
                topic=self.lifecycle_topic,
                qos=reader_qos
            )
            
            print("✅ DDS monitoring setup complete")
            
        except Exception as e:
            print(f"❌ Failed to setup DDS monitoring: {e}")
            raise
    
    def start_monitoring(self, duration_seconds: float = 30.0):
        """Start monitoring and building the graph"""
        print(f"🚀 Starting graph monitoring for {duration_seconds} seconds")
        self.monitoring_active = True
        
        def monitor_thread():
            start_time = time.time()
            while self.monitoring_active and (time.time() - start_time) < duration_seconds:
                try:
                    # Check for lifecycle events
                    lifecycle_samples = self.lifecycle_reader.take()
                    for data, info in lifecycle_samples:
                        if data is not None and info.state.instance_state == dds.InstanceState.ALIVE:
                            self._process_lifecycle_event(data)
                    
                    time.sleep(0.1)  # Small sleep to prevent busy waiting
                    
                except Exception as e:
                    print(f"❌ Error during monitoring: {e}")
            
            print("⏹️ Graph monitoring thread completed")
        
        # Start monitoring in background thread
        self.monitor_thread = threading.Thread(target=monitor_thread, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring"""
        print("🛑 Stopping graph monitoring")
        self.monitoring_active = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=5)
    
    def _process_lifecycle_event(self, data):
        """Process ComponentLifecycleEvent and build graph"""
        try:
            # Map enum values to strings
            component_types = ["INTERFACE", "PRIMARY_AGENT", "SPECIALIZED_AGENT", "FUNCTION"]
            states = ["JOINING", "DISCOVERING", "READY", "BUSY", "DEGRADED", "OFFLINE"]
            event_categories = ["NODE_DISCOVERY", "EDGE_DISCOVERY", "STATE_CHANGE", "AGENT_INIT", "AGENT_READY", "AGENT_SHUTDOWN", "DDS_ENDPOINT"]
            
            event_data = {
                "component_id": data["component_id"],
                "component_type": component_types[int(data["component_type"])],
                "previous_state": states[int(data["previous_state"])],
                "new_state": states[int(data["new_state"])],
                "event_category": event_categories[int(data["event_category"])],
                "timestamp": int(data["timestamp"]),
                "reason": data["reason"],
                "capabilities": data["capabilities"],
                "source_id": data["source_id"] if data["source_id"] else "",
                "target_id": data["target_id"] if data["target_id"] else "",
                "connection_type": data["connection_type"] if data["connection_type"] else ""
            }
            
            # Add to graph based on event type
            if event_data['event_category'] == 'NODE_DISCOVERY':
                self.system_graph.add_node_from_event(event_data)
            elif event_data['event_category'] == 'EDGE_DISCOVERY':
                self.system_graph.add_edge_from_event(event_data)
            
        except Exception as e:
            print(f"❌ Error processing lifecycle event: {e}")
    
    def validate_system_topology(self) -> Dict[str, Any]:
        """Validate the discovered system topology against expected patterns"""
        
        # Define expected topology for Interface-Agent-Service test
        expected_topology = {
            'expected_nodes': {
                'INTERFACE': 1,  # One interface
                'PRIMARY_AGENT': 1,  # One agent  
                'FUNCTION': 5,  # Calculator service + 4 functions (add, divide, multiply, subtract)
            },
            'expected_edges': {
                'INTERFACE_TO_AGENT': 1,  # Interface connects to agent
                'AGENT_TO_SERVICE': 1,  # Agent connects to service
                'SERVICE_TO_FUNCTION': 4,  # Service connects to functions
            },
            'connectivity_requirements': [
                {'type': 'all_interfaces_connected'},
                {'type': 'all_agents_reachable'},
                {'type': 'all_functions_accessible'}
            ]
        }
        
        return self.system_graph.validate_expected_topology(expected_topology)
    
    def close(self):
        """Clean up resources"""
        try:
            self.stop_monitoring()
            if hasattr(self, 'lifecycle_reader'):
                self.lifecycle_reader.close()
            if hasattr(self, 'subscriber'):
                self.subscriber.close()
            if hasattr(self, 'participant'):
                self.participant.close()
        except Exception as e:
            print(f"⚠️ Warning during cleanup: {e}")

def run_genesis_scenario():
    """Run the Genesis interface-agent-service test scenario"""
    try:
        script_dir = Path(__file__).parent.parent / "run_scripts"
        script_path = script_dir / "run_interface_agent_service_test.sh"
        
        if not script_path.exists():
            print(f"❌ Test scenario script not found: {script_path}")
            return False
        
        print("🎬 Starting Genesis scenario...")
        result = subprocess.run(
            [str(script_path)],
            cwd=script_dir,
            timeout=30.0,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Genesis scenario completed successfully")
            return True
        else:
            print(f"❌ Genesis scenario failed with return code {result.returncode}")
            print(f"Error output: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Genesis scenario timed out")
        return False
    except Exception as e:
        print(f"❌ Error running Genesis scenario: {e}")
        return False

def main():
    """Main test runner"""
    print("🚀 Starting Graph Connectivity Validation Test")
    print("=" * 70)
    
    if not HAS_NETWORKX:
        print("❌ NetworkX is required. Please install with: pip install networkx matplotlib")
        return False
    
    # Check environment
    if not os.path.exists("genesis_lib"):
        print("❌ Please run from the project root directory")
        return False
    
    validator = GraphConnectivityValidator(domain_id=0)
    
    try:
        # Start monitoring
        validator.start_monitoring(duration_seconds=35.0)
        
        # Wait a moment for monitoring to initialize
        time.sleep(2)
        
        # Run Genesis scenario
        scenario_success = run_genesis_scenario()
        
        # Wait for monitoring to complete
        print("⏳ Waiting for graph monitoring to complete...")
        time.sleep(8)
        
        # Stop monitoring and analyze results
        validator.stop_monitoring()
        
        # Get graph summary
        graph_summary = validator.system_graph.get_graph_summary()
        
        print("\n" + "=" * 70)
        print("📊 GRAPH TOPOLOGY ANALYSIS")
        print("=" * 70)
        print(f"Total Nodes: {graph_summary['total_nodes']}")
        print(f"Total Edges: {graph_summary['total_edges']}")
        print(f"Graph Connected: {graph_summary['is_connected']}")
        print(f"Components: {graph_summary['number_of_components']}")
        print(f"Average Degree: {graph_summary['average_degree']:.2f}")
        
        print("\n📋 Nodes by Type:")
        for node_type, count in graph_summary['nodes_by_type'].items():
            if count > 0:
                print(f"  {node_type}: {count}")
        
        print("\n🔗 Edges by Type:")
        for edge_type, count in graph_summary['edges_by_type'].items():
            if count > 0:
                print(f"  {edge_type}: {count}")
        
        # Validate topology
        validation_results = validator.validate_system_topology()
        
        print("\n" + "=" * 70)
        print("🔍 TOPOLOGY VALIDATION RESULTS")
        print("=" * 70)
        
        if validation_results['nodes_valid'] and validation_results['edges_valid']:
            print("✅ TOPOLOGY VALIDATION PASSED")
            print("✅ All expected nodes and edges are present")
        else:
            print("❌ TOPOLOGY VALIDATION FAILED")
            
            if validation_results['missing_nodes']:
                print("\n❌ Missing Nodes:")
                for missing in validation_results['missing_nodes']:
                    print(f"  {missing['type']}: expected {missing['expected']}, got {missing['actual']}")
            
            if validation_results['missing_edges']:
                print("\n❌ Missing Edges:")
                for missing in validation_results['missing_edges']:
                    print(f"  {missing['type']}: expected {missing['expected']}, got {missing['actual']}")
        
        if validation_results['orphaned_nodes']:
            print(f"\n⚠️ Orphaned Nodes: {validation_results['orphaned_nodes']}")
        
        if validation_results['connectivity_issues']:
            print(f"\n⚠️ Connectivity Issues: {validation_results['connectivity_issues']}")
        
        # Save graph visualization
        validator.system_graph.save_graph_visualization('genesis_topology_graph.png')
        
        # Determine overall success
        success_criteria = [
            scenario_success,  # Genesis scenario must succeed
            graph_summary['total_nodes'] > 0,  # Must have nodes
            graph_summary['total_edges'] > 0,  # Must have edges
            validation_results['nodes_valid'],  # Node validation must pass
            validation_results['edges_valid']   # Edge validation must pass
        ]
        
        overall_success = all(success_criteria)
        
        print("\n" + "=" * 70)
        if overall_success:
            print("✅ GRAPH CONNECTIVITY TEST PASSED")
            print("✅ Genesis system topology is complete and valid")
        else:
            print("❌ GRAPH CONNECTIVITY TEST FAILED")
            if not scenario_success:
                print("❌ Genesis scenario failed")
            if graph_summary['total_nodes'] == 0:
                print("❌ No nodes discovered")
            if graph_summary['total_edges'] == 0:
                print("❌ No edges discovered")
            if not validation_results['nodes_valid']:
                print("❌ Node validation failed")
            if not validation_results['edges_valid']:
                print("❌ Edge validation failed")
        
        print("=" * 70)
        return overall_success
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        validator.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 