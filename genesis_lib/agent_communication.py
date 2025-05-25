"""
Agent-to-Agent Communication Module

This module provides the AgentCommunicationMixin class that enables agent-to-agent
communication capabilities in Genesis. It can be mixed into GenesisAgent or 
MonitoredAgent to add agent discovery, connection management, and RPC communication
between agents.

Key Features:
- Agent discovery through AgentCapability announcements
- Dynamic RPC connection management
- Agent-to-agent request/reply handling
- Connection pooling and cleanup

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import rti.connextdds as dds
import rti.rpc as rpc
from .utils import get_datamodel_path

# Get logger
logger = logging.getLogger(__name__)

class AgentCommunicationMixin:
    """
    Mixin class that provides agent-to-agent communication capabilities.
    This can be mixed into GenesisAgent or MonitoredAgent.
    """
    
    def __init__(self):
        """Initialize agent communication capabilities"""
        logger.info("Initializing AgentCommunicationMixin")
        
        # Store active agent connections (agent_id -> rpc.Requester)
        self.agent_connections: Dict[str, rpc.Requester] = {}
        
        # Store discovered agents (agent_id -> agent_info)
        self.discovered_agents: Dict[str, Dict[str, Any]] = {}
        
        # Agent capability writer for advertising our capabilities
        self.agent_capability_writer = None
        
        # Initialize agent-to-agent RPC types
        self.agent_request_type = None
        self.agent_reply_type = None
        
        # Agent RPC replier for receiving requests from other agents
        self.agent_replier = None
        
        # Flag to track if agent communication is enabled
        self._agent_communication_enabled = False
        
        # Agent capability reader for discovering other agents
        self.agent_capability_reader = None
        
        logger.info("AgentCommunicationMixin initialized successfully")
    
    def _initialize_agent_rpc_types(self):
        """Load AgentAgentRequest and AgentAgentReply types from XML"""
        try:
            logger.info("Loading agent-to-agent RPC types from datamodel.xml")
            
            # Get types from XML
            config_path = get_datamodel_path()
            type_provider = dds.QosProvider(config_path)
            
            # Load agent-to-agent communication types
            self.agent_request_type = type_provider.type("genesis_lib", "AgentAgentRequest")
            self.agent_reply_type = type_provider.type("genesis_lib", "AgentAgentReply")
            
            logger.info("Successfully loaded AgentAgentRequest and AgentAgentReply types")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load agent-to-agent RPC types: {e}")
            return False
    
    def _get_agent_service_name(self, agent_id: str) -> str:
        """Generate unique RPC service name for an agent"""
        # Use pattern: {base_service_name}_{agent_id}
        if hasattr(self, 'base_service_name') and hasattr(self, 'app'):
            return f"{self.base_service_name}_{agent_id}"
        else:
            # Fallback pattern
            return f"AgentService_{agent_id}"
    
    def get_discovered_agents(self) -> Dict[str, Dict[str, Any]]:
        """Return dictionary of discovered agents"""
        return self.discovered_agents.copy()
    
    def is_agent_discovered(self, agent_id: str) -> bool:
        """Check if a specific agent has been discovered"""
        return agent_id in self.discovered_agents
    
    async def wait_for_agent(self, agent_id: str, timeout_seconds: float = 30.0) -> bool:
        """
        Wait for a specific agent to be discovered.
        
        Args:
            agent_id: ID of the agent to wait for
            timeout_seconds: Maximum time to wait
            
        Returns:
            True if agent was discovered, False if timeout
        """
        logger.info(f"Waiting for agent {agent_id} (timeout: {timeout_seconds}s)")
        
        start_time = asyncio.get_event_loop().time()
        
        while True:
            if self.is_agent_discovered(agent_id):
                logger.info(f"Agent {agent_id} discovered successfully")
                return True
            
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout_seconds:
                logger.warning(f"Timeout waiting for agent {agent_id} after {timeout_seconds}s")
                return False
            
            # Wait a bit before checking again
            await asyncio.sleep(0.1)
    
    def _setup_agent_discovery(self):
        """Set up agent discovery for agent-to-agent communication"""
        try:
            logger.info("Setting up agent discovery for agent-to-agent communication")
            
            # Ensure we have access to the DDS participant
            if not hasattr(self, 'app') or not hasattr(self.app, 'participant'):
                logger.error("Cannot set up agent discovery: no DDS participant available")
                return False
            
            # Get AgentCapability type from XML
            config_path = get_datamodel_path()
            type_provider = dds.QosProvider(config_path)
            agent_capability_type = type_provider.type("genesis_lib", "AgentCapability")
            
            # Create topic for AgentCapability
            topic = dds.Topic(
                self.app.participant,
                "AgentCapability",
                agent_capability_type
            )
            
            # Create DataReader for AgentCapability with listener
            class AgentCapabilityListener(dds.DynamicData.DataReaderListener):
                def __init__(self, agent_comm_mixin):
                    super().__init__()
                    self.agent_comm_mixin = agent_comm_mixin
                
                def on_data_available(self, reader):
                    try:
                        # Take all available samples
                        samples = reader.take()
                        for sample, info in samples:
                            if sample is None or info.state.instance_state != dds.InstanceState.ALIVE:
                                continue
                            
                            # Process the agent capability announcement
                            self.agent_comm_mixin._on_agent_capability_received(sample)
                            
                    except Exception as e:
                        logger.error(f"Error processing agent capability data: {e}")
            
            # Create reader with listener
            self.agent_capability_reader = dds.DataReader(
                dds.Subscriber(self.app.participant),
                topic
            )
            
            # Set up listener
            capability_listener = AgentCapabilityListener(self)
            mask = dds.StatusMask.DATA_AVAILABLE
            self.agent_capability_reader.set_listener(capability_listener, mask)
            
            logger.info("Agent discovery setup completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set up agent discovery: {e}")
            return False
    
    def _on_agent_capability_received(self, capability_sample):
        """Handle discovered agent capability announcements"""
        try:
            # Extract agent information from the capability sample
            agent_id = capability_sample.get_string("agent_id")
            agent_name = capability_sample.get_string("name")
            agent_type = capability_sample.get_string("agent_type")
            service_name = capability_sample.get_string("service_name")
            description = capability_sample.get_string("description")
            last_seen = capability_sample.get_int64("last_seen")
            
            # Skip our own announcements
            if hasattr(self, 'app') and agent_id == self.app.agent_id:
                return
            
            # Store agent information
            agent_info = {
                "agent_id": agent_id,
                "name": agent_name,
                "agent_type": agent_type,
                "service_name": service_name,
                "description": description,
                "last_seen": last_seen,
                "discovered_at": asyncio.get_event_loop().time()
            }
            
            # Check if this is a new agent or an update
            is_new_agent = agent_id not in self.discovered_agents
            self.discovered_agents[agent_id] = agent_info
            
            if is_new_agent:
                logger.info(f"Discovered new agent: {agent_name} (ID: {agent_id}, Type: {agent_type}, Service: {service_name})")
            else:
                logger.debug(f"Updated agent info: {agent_name} (ID: {agent_id})")
                
        except Exception as e:
            logger.error(f"Error processing agent capability: {e}")
    
    def get_agents_by_type(self, agent_type: str) -> List[Dict[str, Any]]:
        """Get all discovered agents of a specific type"""
        return [
            agent_info for agent_info in self.discovered_agents.values()
            if agent_info.get("agent_type") == agent_type
        ]
    
    def get_agents_by_capability(self, capability_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get agents that match a capability filter"""
        if capability_filter is None:
            return list(self.discovered_agents.values())
        
        # For now, filter by agent_type or service_name containing the capability
        matching_agents = []
        for agent_info in self.discovered_agents.values():
            if (capability_filter.lower() in agent_info.get("agent_type", "").lower() or
                capability_filter.lower() in agent_info.get("service_name", "").lower() or
                capability_filter.lower() in agent_info.get("description", "").lower()):
                matching_agents.append(agent_info)
        
        return matching_agents
    
    @abstractmethod
    async def process_agent_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a request from another agent.
        
        This method must be implemented by subclasses to handle agent-to-agent requests.
        
        Args:
            request: Dictionary containing the request data
            
        Returns:
            Dictionary containing the response data
        """
        pass
    
    def _cleanup_agent_connections(self):
        """Clean up all agent connections"""
        logger.info("Cleaning up agent connections")
        
        for agent_id, requester in self.agent_connections.items():
            try:
                if hasattr(requester, 'close'):
                    requester.close()
                logger.debug(f"Closed connection to agent {agent_id}")
            except Exception as e:
                logger.warning(f"Error closing connection to agent {agent_id}: {e}")
        
        self.agent_connections.clear()
        logger.info("Agent connections cleanup complete")
    
    async def close_agent_communication(self):
        """Clean up agent communication resources"""
        logger.info("Closing agent communication")
        
        try:
            # Clean up connections
            self._cleanup_agent_connections()
            
            # Close agent replier
            if self.agent_replier and hasattr(self.agent_replier, 'close'):
                self.agent_replier.close()
                self.agent_replier = None
            
            # Close agent capability writer
            if self.agent_capability_writer and hasattr(self.agent_capability_writer, 'close'):
                self.agent_capability_writer.close()
                self.agent_capability_writer = None
            
            # Close agent capability reader
            if self.agent_capability_reader and hasattr(self.agent_capability_reader, 'close'):
                self.agent_capability_reader.close()
                self.agent_capability_reader = None
            
            logger.info("Agent communication closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing agent communication: {e}") 