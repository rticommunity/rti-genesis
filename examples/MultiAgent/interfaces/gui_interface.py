#!/usr/bin/env python3
"""
GUI Interface - Genesis Multi-Agent Demo

Modern web-based GUI for interacting with the Genesis multi-agent system.
Features a chat interface and real-time network monitoring visualization.

Features:
- Web-based chat interface for agent interaction
- Real-time Genesis network topology visualization
- Agent discovery and selection
- Live monitoring of agent communications
- Interactive network graph with node and edge information

"""

import asyncio
import logging
import os
import sys
import json
import time
import uuid
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import rti.connextdds as dds

# Add Genesis library to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from genesis_lib.monitored_interface import MonitoredInterface
from genesis_lib.utils import get_datamodel_path
from genesis_lib.graph_state import GraphService  # type: ignore
from genesis_lib.web.graph_viewer import register_graph_viewer  # type: ignore

# Configure logging to be less verbose for GUI
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class GenesisNetworkMonitor:
    """
    Monitor the Genesis network topology in real-time.
    Collects data from DDS monitoring topics to build a network graph.
    """
    
    def __init__(self, domain_id: int = 0):
        self.domain_id = domain_id
        self.nodes = {}  # node_id -> node_info
        self.edges = {}  # edge_id -> edge_info
        self.running = False
        self.socketio = None
        
        # DDS setup for monitoring
        self.participant = None
        self.subscriber = None
        self.lifecycle_reader = None
        self.chain_reader = None
        self.monitoring_reader = None
        
    def set_socketio(self, socketio):
        """Set SocketIO instance for real-time updates"""
        self.socketio = socketio
        
    def start_monitoring(self):
        """Start monitoring the Genesis network"""
        if self.running:
            return
            
        self.running = True
        
        try:
            # Create DDS entities
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
            
            # Set up legacy MonitoringEvent monitoring (where most events are still published)
            monitoring_type = provider.type("genesis_lib", "MonitoringEvent")
            monitoring_topic = dds.DynamicData.Topic(
                self.participant,
                "MonitoringEvent",
                monitoring_type
            )
            
            # Configure reader QoS for real-time monitoring
            reader_qos = dds.QosProvider.default.datareader_qos
            reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
            reader_qos.history.depth = 100
            
            # Create readers
            self.lifecycle_reader = dds.DynamicData.DataReader(
                self.subscriber, lifecycle_topic, reader_qos
            )
            self.chain_reader = dds.DynamicData.DataReader(
                self.subscriber, chain_topic, reader_qos
            )
            self.monitoring_reader = dds.DynamicData.DataReader(
                self.subscriber, monitoring_topic, reader_qos
            )
            
            # Start monitoring thread
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
            logger.info("Genesis network monitoring started")
            
        except Exception as e:
            logger.error(f"Failed to start network monitoring: {e}")
            self.running = False
    
    def stop_monitoring(self):
        """Stop monitoring the Genesis network"""
        self.running = False
        
        if self.lifecycle_reader:
            self.lifecycle_reader.close()
        if self.chain_reader:
            self.chain_reader.close()
        if self.monitoring_reader:
            self.monitoring_reader.close()
        if self.subscriber:
            self.subscriber.close()
        if self.participant:
            self.participant.close()
            
    def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Starting DDS monitoring loop...")
        
        while self.running:
            try:
                # Process lifecycle events
                lifecycle_samples = self.lifecycle_reader.take()
                if lifecycle_samples:
                    logger.info(f"Received {len(lifecycle_samples)} lifecycle samples")
                    for sample in lifecycle_samples:
                        if sample.info.valid:
                            logger.info(f"Processing valid lifecycle sample: {sample.data}")
                            self._process_lifecycle_event(sample.data)
                
                # Process chain events
                chain_samples = self.chain_reader.take()
                if chain_samples:
                    logger.info(f"Received {len(chain_samples)} chain samples")
                    for sample in chain_samples:
                        if sample.info.valid:
                            logger.info(f"Processing valid chain sample: {sample.data}")
                            self._process_chain_event(sample.data)
                
                # Process monitoring events
                monitoring_samples = self.monitoring_reader.take()
                if monitoring_samples:
                    logger.info(f"Received {len(monitoring_samples)} monitoring samples")
                    for sample in monitoring_samples:
                        if sample.info.valid:
                            logger.info(f"Processing valid monitoring sample: {sample.data}")
                            self._process_monitoring_event(sample.data)
                
                time.sleep(0.1)  # Small delay to prevent busy waiting
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(1.0)
    
    def _process_lifecycle_event(self, event_data):
        """Process a ComponentLifecycleEvent"""
        try:
            # Map event category enum to string (following genesis_monitor.py pattern)
            event_categories = ["NODE_DISCOVERY", "EDGE_DISCOVERY", "STATE_CHANGE", "AGENT_INIT", "AGENT_READY", "AGENT_SHUTDOWN", "DDS_ENDPOINT"]
            event_category_idx = int(event_data["event_category"])
            event_category = event_categories[event_category_idx] if 0 <= event_category_idx < len(event_categories) else "UNKNOWN"
            
            logger.info(f"Processing lifecycle event: {event_category} for component {event_data['component_id'] if event_data['component_id'] else 'unknown'}")
            
            if event_category == "NODE_DISCOVERY":
                self._handle_node_discovery(event_data)
            elif event_category == "EDGE_DISCOVERY":
                self._handle_edge_discovery(event_data)
            elif event_category == "STATE_CHANGE":
                self._handle_state_change(event_data)
                
        except Exception as e:
            logger.error(f"Error processing lifecycle event: {e}")
    
    def _process_chain_event(self, event_data):
        """Process a ChainEvent"""
        try:
            # Chain events represent communications between agents
            # Use direct field access (not .get()) following genesis_monitor.py pattern
            source_id = event_data["source_id"]
            target_id = event_data["target_id"]
            
            # Extract nodes from chain events too
            if source_id and source_id not in self.nodes:
                self._create_node_from_id(source_id, "UNKNOWN", "Chain Source")
            
            if target_id and target_id not in self.nodes:
                self._create_node_from_id(target_id, "UNKNOWN", "Chain Target")
            
            if source_id and target_id:
                self._handle_communication_event(event_data)
                
        except Exception as e:
            logger.error(f"Error processing chain event: {e}")
    
    def _process_monitoring_event(self, event_data):
        """Process a MonitoringEvent"""
        try:
            # MonitoringEvent contains the legacy monitoring data where most events are published
            event_type = event_data["event_type"] if event_data["event_type"] else "UNKNOWN"
            entity_type = event_data["entity_type"] if event_data["entity_type"] else "UNKNOWN"
            entity_id = event_data["entity_id"] if event_data["entity_id"] else "unknown"
            
            logger.info(f"Processing monitoring event: {event_type} for {entity_type} {entity_id}")
            
            # Parse metadata for additional info
            metadata = {}
            try:
                metadata_str = event_data["metadata"] if event_data["metadata"] else "{}"
                metadata = json.loads(metadata_str)
            except Exception:
                metadata = {}
            
            if event_type == "FUNCTION_DISCOVERY":
                self._handle_function_discovery_monitoring(event_data, metadata)
            elif event_type == "FUNCTION_CALL":
                self._handle_function_call_monitoring(event_data, metadata)
            elif event_type == "AGENT_DISCOVERY":
                self._handle_agent_discovery_monitoring(event_data, metadata)
                
        except Exception as e:
            logger.error(f"Error processing monitoring event: {e}")
    
    def _handle_function_discovery_monitoring(self, event_data, metadata):
        """Handle function discovery from MonitoringEvent"""
        try:
            entity_id = event_data["entity_id"]
            
            # Extract function information from metadata
            function_name = metadata.get("function_name")
            function_id = metadata.get("function_id") 
            provider_id = metadata.get("provider_id")
            interface_name = metadata.get("interface_name")
            service_name = metadata.get("service_name")
            
            # Create function node using function name as primary identifier
            if function_name:
                # Use function name as the node ID for better identification
                function_node_id = function_name
                
                # If we already have this function, don't duplicate it
                if function_node_id in self.nodes:
                    logger.info(f"Function {function_name} already discovered, skipping duplicate")
                    return
                
                node_info = {
                    "id": function_node_id,
                    "type": "FUNCTION", 
                    "name": function_name,
                    "service_name": service_name or "",
                    "description": f"Function: {function_name}",
                    "capabilities": [function_name],
                    "discovered_at": datetime.now().isoformat(),
                    "status": "available",
                    "function_uuid": function_id  # Keep UUID for reference
                }
                
                self.nodes[function_node_id] = node_info
                
                # Emit update to web clients
                if self.socketio:
                    self.socketio.emit('node_update', {
                        'action': 'add',
                        'node': node_info
                    })
                    
                logger.info(f"Function discovered from monitoring: {function_name}")
            
            # Create service/provider node if we have provider ID
            if provider_id and provider_id not in self.nodes:
                provider_name = service_name or interface_name or f"Service_{provider_id[:8]}"
                provider_type = "INTERFACE" if interface_name else "SERVICE"
                
                provider_info = {
                    "id": provider_id,
                    "type": provider_type,
                    "name": provider_name,
                    "service_name": service_name or "",
                    "description": f"Service/Interface: {provider_name}",
                    "capabilities": [],
                    "discovered_at": datetime.now().isoformat(),
                    "status": "available"
                }
                
                self.nodes[provider_id] = provider_info
                
                # Emit update to web clients
                if self.socketio:
                    self.socketio.emit('node_update', {
                        'action': 'add',
                        'node': provider_info
                    })
                    
                logger.info(f"Provider discovered from monitoring: {provider_name} ({provider_id[:8]})")
            
            # Create edge between provider and function if both exist
            if provider_id and function_name and provider_id in self.nodes and function_name in self.nodes:
                edge_id = f"{provider_id}->{function_name}"
                
                # Don't duplicate edges
                if edge_id in self.edges:
                    return
                
                edge_info = {
                    "id": edge_id,
                    "source": provider_id,
                    "target": function_name,  # Use function name as target
                    "type": "provides_function",
                    "discovered_at": datetime.now().isoformat(),
                    "status": "active"
                }
                
                self.edges[edge_id] = edge_info
                
                # Emit update to web clients
                if self.socketio:
                    self.socketio.emit('edge_update', {
                        'action': 'add',
                        'edge': edge_info
                    })
                
        except Exception as e:
            logger.error(f"Error handling function discovery monitoring: {e}")
    
    def _handle_function_call_monitoring(self, event_data, metadata):
        """Handle function call from MonitoringEvent"""
        try:
            # Function calls can indicate communication between agents
            # We can use this to infer edges/connections
            entity_id = event_data["entity_id"]
            provider_id = metadata.get("provider_id")
            
            if provider_id and entity_id and self.socketio:
                # Emit communication event for visualization
                self.socketio.emit('communication_event', {
                    'source': entity_id,
                    'target': provider_id,
                    'timestamp': datetime.now().isoformat(),
                    'event_type': 'function_call'
                })
                
        except Exception as e:
            logger.error(f"Error handling function call monitoring: {e}")
    
    def _handle_agent_discovery_monitoring(self, event_data, metadata):
        """Handle agent discovery from MonitoringEvent"""
        try:
            entity_id = event_data["entity_id"]
            
            # Create agent node with better naming
            agent_name = metadata.get("agent_name") or entity_id
            agent_type = metadata.get("agent_type", "PRIMARY_AGENT")
            service_name = metadata.get("service_name", "")
            
            # If entity_id is the agent name, use it directly; otherwise use a readable format
            if entity_id == agent_name:
                node_id = agent_name
                display_name = agent_name
            else:
                # Use a more readable format for the node ID
                node_id = agent_name if agent_name != entity_id else f"Agent_{entity_id[:8]}"
                display_name = agent_name
            
            # Don't duplicate agents
            if node_id in self.nodes:
                logger.info(f"Agent {display_name} already discovered, skipping duplicate")
                return
            
            node_info = {
                "id": node_id,
                "type": agent_type,
                "name": display_name,
                "service_name": service_name,
                "description": f"Agent: {display_name}",
                "capabilities": [],
                "discovered_at": datetime.now().isoformat(),
                "status": "available",
                "agent_uuid": entity_id  # Keep UUID for reference
            }
            
            self.nodes[node_id] = node_info
            
            # Emit update to web clients
            if self.socketio:
                self.socketio.emit('node_update', {
                    'action': 'add',
                    'node': node_info
                })
                
            logger.info(f"Agent discovered from monitoring: {display_name}")
            
        except Exception as e:
            logger.error(f"Error handling agent discovery monitoring: {e}")
    
    def _create_node_from_id(self, component_id, node_type="UNKNOWN", description="Discovered from network activity"):
        """Create a node from just an ID when we don't have full discovery info"""
        try:
            # Try to infer node type and name from the ID pattern
            node_name = component_id
            inferred_type = node_type
            
            # Heuristics to guess node type from ID patterns
            if len(component_id) == 32 and '-' not in component_id:
                # Long hex string - likely DDS participant ID (interface)
                inferred_type = "INTERFACE"
                node_name = f"Interface_{component_id[:8]}"
            elif component_id.count('-') == 4 and len(component_id) == 36:
                # UUID format - likely agent or function
                inferred_type = "PRIMARY_AGENT"
                node_name = f"Agent_{component_id[:8]}"
            elif "openai" in component_id.lower():
                inferred_type = "PRIMARY_AGENT"
                node_name = "OpenAI_Service"
            elif any(func in component_id.lower() for func in ['add', 'subtract', 'multiply', 'divide']):
                inferred_type = "FUNCTION"
                node_name = f"Function_{component_id[:8]}"
            
            node_info = {
                "id": component_id,
                "type": inferred_type,
                "name": node_name,
                "service_name": "",
                "description": description,
                "capabilities": [],
                "discovered_at": datetime.now().isoformat(),
                "status": "inferred"
            }
            
            self.nodes[component_id] = node_info
            
            # Emit update to web clients
            if self.socketio:
                self.socketio.emit('node_update', {
                    'action': 'add',
                    'node': node_info
                })
                
            logger.info(f"Inferred node: {node_name} ({inferred_type}) - {component_id}")
            
        except Exception as e:
            logger.error(f"Error creating node from ID {component_id}: {e}")
    
    def _handle_node_discovery(self, event_data):
        """Handle discovery of a new node"""
        try:
            component_id = event_data["component_id"]
            
            # Map component type enum to string (following genesis_monitor.py pattern)
            component_types = ["INTERFACE", "PRIMARY_AGENT", "SPECIALIZED_AGENT", "FUNCTION"]
            component_type_idx = int(event_data["component_type"])
            component_type = component_types[component_type_idx] if 0 <= component_type_idx < len(component_types) else "UNKNOWN"
            
            # Parse capabilities for additional info - handle different data types
            capabilities = {}
            try:
                capabilities_data = event_data["capabilities"]
                if isinstance(capabilities_data, str) and capabilities_data:
                    capabilities = json.loads(capabilities_data)
                elif isinstance(capabilities_data, dict):
                    capabilities = capabilities_data
                elif hasattr(capabilities_data, '__iter__') and not isinstance(capabilities_data, str):
                    # Handle list or other iterable types - convert to string
                    capabilities = {"raw_data": str(capabilities_data)}
                else:
                    capabilities = {}
            except Exception as cap_error:
                logger.warning(f"Could not parse capabilities: {cap_error}")
                capabilities = {}
            
            # For FUNCTION components, use the function name as the primary identifier
            if component_type == "FUNCTION":
                function_name = capabilities.get("function_name")
                if function_name:
                    # Use function name as the node ID
                    node_id = function_name
                    node_name = function_name
                    
                    # Don't duplicate functions
                    if node_id in self.nodes:
                        logger.info(f"Function {function_name} already discovered, updating")
                        return
                else:
                    # Fallback to component ID if no function name
                    node_id = component_id
                    node_name = f"Function_{component_id[:8]}"
            else:
                # For non-function components, use the preferred name or component ID
                node_id = component_id
                node_name = capabilities.get("prefered_name", component_id) if isinstance(capabilities, dict) else component_id
            
            node_info = {
                "id": node_id,
                "type": component_type,
                "name": node_name,
                "service_name": capabilities.get("service_name", "") if isinstance(capabilities, dict) else "",
                "description": capabilities.get("description", f"{component_type}: {node_name}") if isinstance(capabilities, dict) else f"{component_type}: {node_name}",
                "capabilities": capabilities.get("capabilities", []) if isinstance(capabilities, dict) else [],
                "discovered_at": datetime.now().isoformat(),
                "status": "discovered",
                "component_uuid": component_id  # Keep original UUID for reference
            }
            
            self.nodes[node_id] = node_info
            
            # Emit update to web clients
            if self.socketio:
                self.socketio.emit('node_update', {
                    'action': 'add',
                    'node': node_info
                })
                
            logger.info(f"Node discovered: {node_name} ({component_type})")
        except Exception as e:
            logger.error(f"Error handling node discovery: {e}")
    
    def _handle_edge_discovery(self, event_data):
        """Handle discovery of a new edge (connection)"""
        try:
            # Use direct field access and safe string conversion
            source_id = str(event_data["source_id"]) if event_data["source_id"] else ""
            target_id = str(event_data["target_id"]) if event_data["target_id"] else ""
            connection_type = str(event_data["connection_type"]) if event_data["connection_type"] else "UNKNOWN"
            reason = event_data["reason"] if event_data["reason"] else ""
            
            # Parse capabilities for function and agent information
            capabilities = {}
            try:
                capabilities_data = event_data["capabilities"]
                if isinstance(capabilities_data, str) and capabilities_data:
                    capabilities = json.loads(capabilities_data)
                elif isinstance(capabilities_data, dict):
                    capabilities = capabilities_data
            except Exception:
                capabilities = {}
            
            # Check if this edge discovery contains function information
            function_name = capabilities.get("function_name")
            function_id = capabilities.get("function_id")
            provider_id = capabilities.get("provider_id")
            client_id = capabilities.get("client_id")
            
            # Create function node if we have function information
            if function_name:
                # Use function name as the node ID for better identification
                function_node_id = function_name
                
                # Create or update function node
                if function_node_id not in self.nodes:
                    node_info = {
                        "id": function_node_id,
                        "type": "FUNCTION",
                        "name": function_name,
                        "service_name": "",
                        "description": f"Function: {function_name}",
                        "capabilities": [function_name],
                        "discovered_at": datetime.now().isoformat(),
                        "status": "available",
                        "function_uuid": function_id  # Keep UUID for reference
                    }
                    
                    self.nodes[function_node_id] = node_info
                    
                    # Emit update to web clients
                    if self.socketio:
                        self.socketio.emit('node_update', {
                            'action': 'add',
                            'node': node_info
                        })
                        
                    logger.info(f"Function discovered from edge: {function_name}")
            
            # Create provider/service node if we have provider ID
            if provider_id and provider_id not in self.nodes:
                service_name = f"Service_{provider_id[:8]}"
                
                provider_info = {
                    "id": provider_id,
                    "type": "SERVICE",
                    "name": service_name,
                    "service_name": service_name,
                    "description": f"Service: {service_name}",
                    "capabilities": [],
                    "discovered_at": datetime.now().isoformat(),
                    "status": "available"
                }
                
                self.nodes[provider_id] = provider_info
                
                # Emit update to web clients
                if self.socketio:
                    self.socketio.emit('node_update', {
                        'action': 'add',
                        'node': provider_info
                    })
                    
                logger.info(f"Service discovered from edge: {service_name}")
            
            # Create client/agent node if we have client ID
            if client_id and client_id not in self.nodes:
                agent_name = f"Agent_{client_id[:8]}"
                
                agent_info = {
                    "id": client_id,
                    "type": "PRIMARY_AGENT",
                    "name": agent_name,
                    "service_name": "",
                    "description": f"Agent: {agent_name}",
                    "capabilities": [],
                    "discovered_at": datetime.now().isoformat(),
                    "status": "available"
                }
                
                self.nodes[client_id] = agent_info
                
                # Emit update to web clients
                if self.socketio:
                    self.socketio.emit('node_update', {
                        'action': 'add',
                        'node': agent_info
                    })
                    
                logger.info(f"Agent discovered from edge: {agent_name}")
            
            # Extract agent information from edge discovery events
            # Look for patterns like "Interface X discovered agent Y (agent_id)"
            if reason and "discovered agent" in reason:
                # Extract agent name and ID from reason
                import re
                match = re.search(r'discovered agent (\w+) \(([^)]+)\)', reason)
                if match:
                    agent_name = match.group(1)
                    agent_id = match.group(2)
                    
                    # Create agent node if we haven't seen it before
                    if agent_id not in self.nodes:
                        node_info = {
                            "id": agent_id,
                            "type": "SPECIALIZED_AGENT" if "weather" in agent_name.lower() else "PRIMARY_AGENT",
                            "name": agent_name,
                            "service_name": capabilities.get("service_name", "") if isinstance(capabilities, dict) else "",
                            "description": f"Agent: {agent_name}",
                            "capabilities": [],
                            "discovered_at": datetime.now().isoformat(),
                            "status": "discovered"
                        }
                        
                        self.nodes[agent_id] = node_info
                        
                        # Emit update to web clients
                        if self.socketio:
                            self.socketio.emit('node_update', {
                                'action': 'add',
                                'node': node_info
                            })
                            
                        logger.info(f"Agent discovered from edge: {agent_name} ({agent_id[:8]})")
            
            # Discover nodes from ALL source/target IDs in edge events (fallback)
            if source_id and source_id not in self.nodes:
                self._create_node_from_id(source_id, "INTERFACE" if connection_type == "interface_to_agent" else "UNKNOWN", f"Edge source: {reason}")
            
            if target_id and target_id not in self.nodes:
                self._create_node_from_id(target_id, "PRIMARY_AGENT", f"Edge target: {reason}")
            
            # Create edges between discovered nodes
            if source_id and target_id:
                edge_id = f"{source_id}->{target_id}"
                
                # Don't duplicate edges
                if edge_id in self.edges:
                    return
                
                edge_info = {
                    "id": edge_id,
                    "source": source_id,
                    "target": target_id,
                    "type": connection_type.lower(),
                    "discovered_at": datetime.now().isoformat(),
                    "status": "active"
                }
                
                self.edges[edge_id] = edge_info
                
                # Emit update to web clients
                if self.socketio:
                    self.socketio.emit('edge_update', {
                        'action': 'add',
                        'edge': edge_info
                    })
            
            # Create edges for function relationships
            if provider_id and function_name and provider_id in self.nodes and function_name in self.nodes:
                edge_id = f"{provider_id}->{function_name}"
                
                # Don't duplicate edges
                if edge_id not in self.edges:
                    edge_info = {
                        "id": edge_id,
                        "source": provider_id,
                        "target": function_name,
                        "type": "provides_function",
                        "discovered_at": datetime.now().isoformat(),
                        "status": "active"
                    }
                    
                    self.edges[edge_id] = edge_info
                    
                    # Emit update to web clients
                    if self.socketio:
                        self.socketio.emit('edge_update', {
                            'action': 'add',
                            'edge': edge_info
                        })
            
            if client_id and function_name and client_id in self.nodes and function_name in self.nodes:
                edge_id = f"{client_id}->{function_name}"
                
                # Don't duplicate edges
                if edge_id not in self.edges:
                    edge_info = {
                        "id": edge_id,
                        "source": client_id,
                        "target": function_name,
                        "type": "uses_function",
                        "discovered_at": datetime.now().isoformat(),
                        "status": "active"
                    }
                    
                    self.edges[edge_id] = edge_info
                    
                    # Emit update to web clients
                    if self.socketio:
                        self.socketio.emit('edge_update', {
                            'action': 'add',
                            'edge': edge_info
                        })
        except Exception as e:
            logger.error(f"Error handling edge discovery: {e}")
    
    def _handle_state_change(self, event_data):
        """Handle state change of a node"""
        try:
            component_id = event_data["component_id"]
            
            # If we haven't seen this component before, create it from the state change
            if component_id not in self.nodes:
                # Map component type enum to string 
                component_types = ["INTERFACE", "PRIMARY_AGENT", "SPECIALIZED_AGENT", "FUNCTION"]
                component_type_idx = int(event_data["component_type"])
                component_type = component_types[component_type_idx] if 0 <= component_type_idx < len(component_types) else "UNKNOWN"
                
                reason = event_data["reason"] if event_data["reason"] else ""
                node_name = f"{component_type}_{component_id[:8]}"
                
                # Try to extract better name from reason
                if reason:
                    if "Agent" in reason:
                        node_name = f"Agent_{component_id[:8]}"
                    elif "Interface" in reason:
                        node_name = f"Interface_{component_id[:8]}"
                    elif "Function" in reason:
                        node_name = f"Function_{component_id[:8]}"
                
                node_info = {
                    "id": component_id,
                    "type": component_type,
                    "name": node_name,
                    "service_name": "",
                    "description": f"Discovered from state change: {reason}",
                    "capabilities": [],
                    "discovered_at": datetime.now().isoformat(),
                    "status": "discovered"
                }
                
                self.nodes[component_id] = node_info
                
                # Emit update to web clients
                if self.socketio:
                    self.socketio.emit('node_update', {
                        'action': 'add',
                        'node': node_info
                    })
                    
                logger.info(f"Node discovered from state change: {node_name} ({component_type}) - {component_id}")
            
            # Map state enum to string (following genesis_monitor.py pattern)
            states = ["JOINING", "DISCOVERING", "READY", "BUSY", "DEGRADED", "OFFLINE"]
            new_state_idx = int(event_data["new_state"])
            new_state = states[new_state_idx] if 0 <= new_state_idx < len(states) else "UNKNOWN"
            
            # Update the existing node status
            self.nodes[component_id]["status"] = new_state.lower()
            self.nodes[component_id]["last_update"] = datetime.now().isoformat()
            
            # Emit update to web clients
            if self.socketio:
                self.socketio.emit('node_update', {
                    'action': 'update',
                    'node': self.nodes[component_id]
                })
        except Exception as e:
            logger.error(f"Error handling state change: {e}")
    
    def _handle_communication_event(self, event_data):
        """Handle communication event between agents"""
        try:
            source_id = event_data["source_id"]
            target_id = event_data["target_id"]
            
            if source_id and target_id and self.socketio:
                # Emit communication event for visualization
                self.socketio.emit('communication_event', {
                    'source': source_id,
                    'target': target_id,
                    'timestamp': datetime.now().isoformat(),
                    'event_type': str(event_data["event_type"]) if event_data["event_type"] else "UNKNOWN"
                })
        except Exception as e:
            logger.error(f"Error handling communication event: {e}")
    
    def get_network_state(self):
        """Get current network state"""
        return {
            "nodes": list(self.nodes.values()),
            "edges": list(self.edges.values()),
            "stats": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "node_types": self._count_node_types(),
                "edge_types": self._count_edge_types()
            }
        }
    
    def _count_node_types(self):
        """Count nodes by type"""
        counts = {}
        for node in self.nodes.values():
            node_type = node["type"]
            counts[node_type] = counts.get(node_type, 0) + 1
        return counts
    
    def _count_edge_types(self):
        """Count edges by type"""
        counts = {}
        for edge in self.edges.values():
            edge_type = edge["type"]
            counts[edge_type] = counts.get(edge_type, 0) + 1
        return counts

class MultiAgentGUI:
    """
    Web-based GUI for Genesis Multi-Agent system.
    
    Provides a modern interface for agent interaction and network monitoring.
    """
    
    def __init__(self, host='127.0.0.1', port=5000):
        self.host = host
        self.port = port
        
        # Flask app setup
        self.app = Flask(__name__, 
                        template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
                        static_folder=os.path.join(os.path.dirname(__file__), 'static'))
        self.app.config['SECRET_KEY'] = str(uuid.uuid4())
        
        # SocketIO setup
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        # Embed the reusable graph viewer (dark-themed client) under /genesis-graph
        self.graph_service = GraphService(domain_id=int(os.getenv("GENESIS_DOMAIN", "0")))
        self.graph_service.start()
        register_graph_viewer(self.app, self.socketio, self.graph_service, url_prefix="/genesis-graph")
        
        # Genesis interface
        self.interface = None
        self.connected_agent = None
        self.conversation_id = "multi_agent_gui_demo"
        
        # Network monitor
        self.network_monitor = GenesisNetworkMonitor()
        self.network_monitor.set_socketio(self.socketio)
        
        # Setup routes and handlers
        self._setup_routes()
        self._setup_socketio_handlers()
        
        # Available agents cache
        self.available_agents = {}
        
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            return render_template('index.html')
        
        @self.app.route('/api/agents')
        def get_agents():
            """Get list of available agents"""
            if self.interface:
                agents = []
                for agent_id, agent_info in self.interface.available_agents.items():
                    agents.append({
                        'id': agent_id,
                        'name': agent_info.get('prefered_name', 'Unknown'),
                        'type': agent_info.get('agent_type', 'Unknown'),
                        'description': agent_info.get('description', 'No description'),
                        'capabilities': agent_info.get('capabilities', []),
                        'service_name': agent_info.get('service_name', '')
                    })
                return jsonify({'agents': agents})
            return jsonify({'agents': []})
        
        @self.app.route('/api/network')
        def get_network():
            """Get current network state"""
            return jsonify(self.network_monitor.get_network_state())
    
    def _setup_socketio_handlers(self):
        """Setup SocketIO event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            emit('status', {'message': 'Connected to Genesis GUI'})
            
            # Send current network state
            network_state = self.network_monitor.get_network_state()
            emit('network_state', network_state)
        
        @self.socketio.on('initialize_genesis')
        def handle_initialize():
            """Initialize Genesis interface"""
            # Use background task to handle async operations
            self.socketio.start_background_task(self._initialize_genesis_interface_wrapper)
        
        @self.socketio.on('connect_to_agent')
        def handle_connect_agent(data):
            """Connect to a specific agent"""
            agent_name = data.get('agent_name')
            if agent_name:
                # Use background task to handle async operations
                self.socketio.start_background_task(self._connect_to_agent_wrapper, agent_name)
        
        @self.socketio.on('send_message')
        def handle_send_message(data):
            """Send message to connected agent"""
            message = data.get('message')
            if message and self.connected_agent:
                # Use background task to handle async operations
                self.socketio.start_background_task(self._send_message_to_agent_wrapper, message)
        
        @self.socketio.on('disconnect_agent')
        def handle_disconnect():
            """Disconnect from current agent"""
            self.connected_agent = None
            emit('agent_disconnected')
    
    def _initialize_genesis_interface_wrapper(self):
        """Wrapper for async initialization that can be called from SocketIO background task"""
        import asyncio
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._initialize_genesis_interface())
        finally:
            loop.close()
    
    async def _initialize_genesis_interface(self):
        """Initialize the Genesis interface"""
        try:
            self.socketio.emit('status', {'message': 'Initializing Genesis interface...'})
            
            # Initialize Genesis interface
            self.interface = MonitoredInterface('MultiAgentGUI', 'InteractiveGUI')
            
            # Start network monitoring
            self.network_monitor.start_monitoring()
            
            # Wait for agent discovery
            await asyncio.sleep(3)
            
            # Get discovered agents
            agents = []
            for agent_id, agent_info in self.interface.available_agents.items():
                agents.append({
                    'id': agent_id,
                    'name': agent_info.get('prefered_name', 'Unknown'),
                    'type': agent_info.get('agent_type', 'Unknown'),
                    'description': agent_info.get('description', 'No description'),
                    'capabilities': agent_info.get('capabilities', []),
                    'service_name': agent_info.get('service_name', '')
                })
            
            self.socketio.emit('agents_discovered', {'agents': agents})
            self.socketio.emit('status', {'message': f'Discovered {len(agents)} agent(s)'})
            
        except Exception as e:
            self.socketio.emit('error', {'message': f'Failed to initialize Genesis: {str(e)}'})
    
    def _connect_to_agent_wrapper(self, agent_name: str):
        """Wrapper for async connection that can be called from SocketIO background task"""
        import asyncio
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._connect_to_agent(agent_name))
        finally:
            loop.close()
    
    async def _connect_to_agent(self, agent_name: str):
        """Connect to a specific agent"""
        try:
            if not self.interface:
                self.socketio.emit('error', {'message': 'Genesis interface not initialized'})
                return
            
            # Find agent by name
            target_agent_info = None
            for agent_id, agent_info in self.interface.available_agents.items():
                if agent_info.get('prefered_name') == agent_name:
                    target_agent_info = agent_info
                    break
            
            if not target_agent_info:
                self.socketio.emit('error', {'message': f'Agent {agent_name} not found'})
                return
            
            self.socketio.emit('status', {'message': f'Connecting to {agent_name}...'})
            
            # Connect to agent
            service_name = target_agent_info.get('service_name')
            connected = await self.interface.connect_to_agent(service_name)
            
            if connected:
                self.connected_agent = agent_name
                self.socketio.emit('agent_connected', {
                    'agent_name': agent_name,
                    'agent_info': target_agent_info
                })
                self.socketio.emit('status', {'message': f'Connected to {agent_name}'})
            else:
                self.socketio.emit('error', {'message': f'Failed to connect to {agent_name}'})
                
        except Exception as e:
            self.socketio.emit('error', {'message': f'Connection error: {str(e)}'})
    
    def _send_message_to_agent_wrapper(self, message: str):
        """Wrapper for async message sending that can be called from SocketIO background task"""
        import asyncio
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._send_message_to_agent(message))
        finally:
            loop.close()
    
    async def _send_message_to_agent(self, message: str):
        """Send message to connected agent"""
        try:
            if not self.interface or not self.connected_agent:
                self.socketio.emit('error', {'message': 'No agent connected'})
                return
            
            self.socketio.emit('message_sent', {
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
            
            # Send request to agent
            response = await self.interface.send_request({
                'message': message,
                'conversation_id': self.conversation_id
            }, timeout_seconds=30.0)
            
            if response and response.get('status') == 0:
                self.socketio.emit('agent_response', {
                    'message': response.get('message', 'No response'),
                    'agent_name': self.connected_agent,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                error_msg = response.get('message', 'Unknown error') if response else 'No response'
                self.socketio.emit('error', {'message': f'Agent error: {error_msg}'})
                
        except Exception as e:
            self.socketio.emit('error', {'message': f'Message error: {str(e)}'})
    
    def run(self):
        """Run the GUI server"""
        print(f"🌐 Genesis Multi-Agent GUI starting...")
        print(f"   📡 Host: {self.host}")
        print(f"   🔌 Port: {self.port}")
        print(f"   🌍 URL: http://{self.host}:{self.port}")
        print()
        print("🎯 Features:")
        print("   • Interactive chat with agents")
        print("   • Real-time network topology visualization")
        print("   • Live monitoring of agent communications")
        print("   • Dynamic agent discovery and selection")
        print()
        
        # Ensure templates directory exists
        templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
        if not os.path.exists(templates_dir):
            print(f"⚠️  Templates directory missing: {templates_dir}")
            print("   Creating basic template structure...")
            self._create_template_structure()
        
        # Start network monitoring automatically
        print("🔍 Starting network monitoring...")
        self.network_monitor.start_monitoring()
        print("   ✅ Network monitoring started")
        
        try:
            self.socketio.run(self.app, host=self.host, port=self.port, debug=False, allow_unsafe_werkzeug=True)
        except KeyboardInterrupt:
            print("\n🛑 GUI shutdown requested")
        finally:
            if self.network_monitor:
                self.network_monitor.stop_monitoring()
            if self.interface:
                asyncio.create_task(self.interface.close())
            try:
                if self.graph_service:
                    self.graph_service.stop()
            except Exception:
                pass
    
    def _create_template_structure(self):
        """Create basic template structure if missing"""
        templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        
        os.makedirs(templates_dir, exist_ok=True)
        os.makedirs(static_dir, exist_ok=True)
        
        # We'll create these files separately
        print(f"   ✅ Created {templates_dir}")
        print(f"   ✅ Created {static_dir}")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Genesis Multi-Agent GUI Interface")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    args = parser.parse_args()
    
    gui = MultiAgentGUI(host=args.host, port=args.port)
    gui.run()

if __name__ == "__main__":
    main() 