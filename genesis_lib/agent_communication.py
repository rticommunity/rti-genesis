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
            
            logger.info("Agent communication closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing agent communication: {e}") 