"""
Genesis Agent Base Class

This module provides the abstract base class `GenesisAgent` for all agents
within the Genesis framework. It establishes the core agent lifecycle,
communication patterns, and integration with the underlying DDS infrastructure
managed by `GenesisApp`.

Key responsibilities include:
- Initializing the agent's identity and DDS presence via `GenesisApp`.
- Handling agent registration on the Genesis network.
- Setting up an RPC replier to receive and process requests for the agent's service.
- Defining an abstract `process_request` method that concrete subclasses must implement
  to handle service-specific logic.
- Providing utilities for agent lifecycle management (`run`, `close`).
- Offering mechanisms for function discovery within the Genesis network.

This class serves as the foundation upon which specialized agents, like
`MonitoredAgent`, are built.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import sys
import time
import logging
import os
import json
import asyncio
import traceback
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
import rti.connextdds as dds
import rti.rpc as rpc
from .genesis_app import GenesisApp
from .llm import ChatAgent, AnthropicChatAgent
from .utils import get_datamodel_path
from .agent_communication import AgentCommunicationMixin

# Get logger
logger = logging.getLogger(__name__)

class GenesisAgent(ABC):
    """Base class for all Genesis agents"""
    registration_writer: Optional[dds.DynamicData.DataWriter] = None # Define at class level

    def __init__(self, agent_name: str, base_service_name: str, 
                 service_instance_tag: Optional[str] = None, agent_id: str = None,
                 enable_agent_communication: bool = False):
        """
        Initialize the agent.
        
        Args:
            agent_name: Name of the agent (for display, identification)
            base_service_name: The fundamental type of service offered (e.g., "Chat", "ImageGeneration")
            service_instance_tag: Optional tag to make this instance's RPC service name unique (e.g., "Primary", "User1")
            agent_id: Optional UUID for the agent (if None, will generate one)
            enable_agent_communication: Whether to enable agent-to-agent communication capabilities
        """
        logger.info(f"GenesisAgent {agent_name} STARTING initializing with agent_id {agent_id}, base_service_name: {base_service_name}, tag: {service_instance_tag}")
        self.agent_name = agent_name
        
        self.base_service_name = base_service_name
        if service_instance_tag:
            self.rpc_service_name = f"{base_service_name}_{service_instance_tag}"
        else:
            self.rpc_service_name = base_service_name
        
        logger.info(f"Determined RPC service name: {self.rpc_service_name}")

        logger.debug("===== DDS TRACE: Creating GenesisApp in GenesisAgent =====")
        self.app = GenesisApp(preferred_name=self.agent_name, agent_id=agent_id)
        logger.debug(f"===== DDS TRACE: GenesisApp created with agent_id {self.app.agent_id} =====")
        logger.info(f"GenesisAgent {self.agent_name} initialized with app {self.app.agent_id}")


        # Get types from XML
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        # Initialize RPC types
        self.request_type = self.type_provider.type("genesis_lib", "InterfaceAgentRequest")
        self.reply_type = self.type_provider.type("genesis_lib", "InterfaceAgentReply")
        logger.info(f"GenesisAgent {self.agent_name} initialized with hardcoded InterfaceAgent RPC types")
        # Create event loop for async operations
        self.loop = asyncio.get_event_loop()
        logger.info(f"GenesisAgent {self.agent_name} initialized with loop {self.loop}")


        # Create registration writer with QoS
        writer_qos = dds.QosProvider.default.datawriter_qos
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.history.kind = dds.HistoryKind.KEEP_LAST
        writer_qos.history.depth = 500
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.liveliness.kind = dds.LivelinessKind.AUTOMATIC
        writer_qos.liveliness.lease_duration = dds.Duration(seconds=2)
        writer_qos.ownership.kind = dds.OwnershipKind.SHARED

        # Create registration writer
        self.registration_writer = dds.DynamicData.DataWriter(
            self.app.publisher,
            self.app.registration_topic,
            qos=writer_qos
        )
        logger.debug("✅ TRACE: Registration writer created with QoS settings")

        # Create replier with data available listener
        class RequestListener(dds.DynamicData.DataReaderListener):
            def __init__(self, agent):
                super().__init__()  # Call parent class __init__
                self.agent = agent
                
            def on_data_available(self, reader):
                # Get all available samples
                samples = self.agent.replier.take_requests()
                for request, info in samples:
                    if request is None or info.state.instance_state != dds.InstanceState.ALIVE:
                        continue
                        
                    logger.info(f"Received request: {request}")
                    
                    try:
                        # Create task to process request asynchronously
                        asyncio.run_coroutine_threadsafe(self._process_request(request, info), self.agent.loop)
                    except Exception as e:
                        logger.error(f"Error creating request processing task: {e}")
                        logger.error(traceback.format_exc())
                        
            async def _process_request(self, request, info):
                try:
                    request_dict = {}
                    if hasattr(self.agent.request_type, 'members') and callable(self.agent.request_type.members):
                        for member in self.agent.request_type.members():
                            member_name = member.name
                            try:
                                # Check member type and use appropriate getter
                                # Assuming InterfaceAgentRequest has only string members for now
                                # A more robust solution would check member.type.kind
                                if member.type.kind == dds.TypeKind.STRING_TYPE:
                                    request_dict[member_name] = request.get_string(member_name)
                                # TODO: Add handling for other types (INT32, BOOLEAN, etc.) if InterfaceAgentRequest evolves
                                else:
                                    logger.warning(f"Unsupported member type for '{member_name}' during DDS-to-dict conversion. Attempting direct assignment (may fail).")
                                    # This part is risky and likely incorrect for non-basic types if not handled properly
                                    request_dict[member_name] = request[member_name] 
                            except Exception as e:
                                logger.warning(f"Could not convert member '{member_name}' from DDS request to dict: {e}")
                    else:
                        logger.error("Cannot convert DDS request to dict: self.agent.request_type does not have a members() method. THIS IS A PROBLEM.")
                        # If we can't determine members, we can't reliably convert.
                        # Passing the raw request here would be inconsistent with agents expecting a dict.
                        # It's better to let it fail or send an error reply if conversion is impossible.
                        raise TypeError("Failed to introspect request_type members for DDS-to-dict conversion.")

                    # Get reply data from concrete implementation, passing the dictionary
                    reply_data = await self.agent.process_request(request_dict)
                    
                    # Create reply
                    reply = dds.DynamicData(self.agent.reply_type)
                    for key, value in reply_data.items():
                        reply[key] = value
                        
                    # Send reply
                    self.agent.replier.send_reply(reply, info)
                    logger.info(f"Sent reply: {reply}")
                except Exception as e:
                    logger.error(f"Error processing request: {e}")
                    logger.error(traceback.format_exc())
                    # Send error reply
                    reply = dds.DynamicData(self.agent.reply_type)
                    reply["status"] = 1  # Error status
                    reply["message"] = f"Error: {str(e)}"
                    self.agent.replier.send_reply(reply, info)
        
        # Create replier with listener
        self.replier = rpc.Replier(
            request_type=self.request_type,
            reply_type=self.reply_type,
            participant=self.app.participant,
            service_name=self.rpc_service_name
        )
        
        # Set listener on replier's DataReader with status mask for data available
        self.request_listener = RequestListener(self)
        mask = dds.StatusMask.DATA_AVAILABLE
        self.replier.request_datareader.set_listener(self.request_listener, mask)
        
        # Store discovered functions
        # self.discovered_functions = [] # Removed as per event-driven plan
        
        # Initialize agent-to-agent communication if enabled
        self.enable_agent_communication = enable_agent_communication
        self.agent_communication = None
        if enable_agent_communication:
            self._setup_agent_communication()

    def _setup_agent_communication(self):
        """Initialize agent-to-agent communication capabilities"""
        try:
            logger.info(f"Setting up agent-to-agent communication for {self.agent_name}")
            
            # Create a communication mixin instance
            class AgentCommunicationWrapper(AgentCommunicationMixin):
                def __init__(self, parent_agent):
                    super().__init__()
                    self.parent_agent = parent_agent
                    # Share the app instance
                    self.app = parent_agent.app
                    self.base_service_name = parent_agent.base_service_name
                
                async def process_agent_request(self, request):
                    """Delegate to parent agent's process_agent_request method"""
                    return await self.parent_agent.process_agent_request(request)
            
            # Create the communication wrapper
            self.agent_communication = AgentCommunicationWrapper(self)
            
            # Initialize RPC types
            if self.agent_communication._initialize_agent_rpc_types():
                logger.info("Agent-to-agent RPC types loaded successfully")
            else:
                logger.warning("Failed to load agent-to-agent RPC types")
                return
            
            # Set up agent discovery
            if self.agent_communication._setup_agent_discovery():
                logger.info("Agent discovery setup completed")
            else:
                logger.warning("Failed to set up agent discovery")
                return
            
            # Set up agent RPC service
            if self.agent_communication._setup_agent_rpc_service():
                logger.info("Agent RPC service setup completed")
            else:
                logger.warning("Failed to set up agent RPC service")
                return
            
            logger.info(f"Agent-to-agent communication enabled for {self.agent_name}")
            
        except Exception as e:
            logger.error(f"Failed to set up agent communication: {e}")
            self.agent_communication = None
    
    async def process_agent_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a request from another agent.
        
        This method should be overridden by subclasses that want to handle
        agent-to-agent communication. The default implementation returns an error.
        
        Args:
            request: Dictionary containing the request data
            
        Returns:
            Dictionary containing the response data
        """
        return {
            "message": f"Agent {self.agent_name} does not support agent-to-agent communication",
            "status": -1,
            "conversation_id": request.get("conversation_id", "")
        }
    
    # Agent-to-agent communication convenience methods
    async def send_agent_request(self, target_agent_id: str, message: str, 
                               conversation_id: Optional[str] = None,
                               timeout_seconds: float = 10.0) -> Optional[Dict[str, Any]]:
        """Send a request to another agent (if agent communication is enabled)"""
        if not self.agent_communication:
            logger.error("Agent communication not enabled")
            return None
        
        return await self.agent_communication.send_agent_request(
            target_agent_id, message, conversation_id, timeout_seconds
        )
    
    async def wait_for_agent(self, agent_id: str, timeout_seconds: float = 30.0) -> bool:
        """Wait for a specific agent to be discovered (if agent communication is enabled)"""
        if not self.agent_communication:
            logger.error("Agent communication not enabled")
            return False
        
        return await self.agent_communication.wait_for_agent(agent_id, timeout_seconds)
    
    def get_discovered_agents(self) -> Dict[str, Dict[str, Any]]:
        """Get list of discovered agents (if agent communication is enabled)"""
        if not self.agent_communication:
            return {}
        
        return self.agent_communication.get_discovered_agents()

    @abstractmethod
    async def process_request(self, request: Any) -> Dict[str, Any]:
        """Process the request and return reply data as a dictionary"""
        pass

    async def run(self):
        """Main agent loop"""
        try:
            # Announce presence
            logger.info("Announcing agent presence...")
            await self.announce_self()
            
            # Main loop - handle agent requests if enabled
            logger.info(f"{self.agent_name} listening for requests (Ctrl+C to exit)...")
            
            if self.agent_communication:
                # Run loop with agent request handling
                while True:
                    try:
                        # Handle agent-to-agent requests
                        await self.agent_communication._handle_agent_request()
                        # Small delay to prevent busy waiting
                        await asyncio.sleep(0.01)
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(f"Error in agent communication loop: {e}")
                        await asyncio.sleep(0.1)
            else:
                # Original behavior - just keep the event loop running
                shutdown_event = asyncio.Event()
                await shutdown_event.wait()
                
        except KeyboardInterrupt:
            logger.info(f"\nShutting down {self.agent_name}...")
            await self.close()
            sys.exit(0)

    async def close(self):
        """Clean up resources"""
        try:
            # Close agent communication first
            if hasattr(self, 'agent_communication') and self.agent_communication is not None:
                await self.agent_communication.close_agent_communication()
                
            # Close replier
            if hasattr(self, 'replier') and not getattr(self.replier, '_closed', False):
                self.replier.close()
                
            # Close app last since it handles registration
            if hasattr(self, 'app') and self.app is not None and not getattr(self.app, '_closed', False):
                await self.app.close()
                
            logger.info(f"GenesisAgent {self.agent_name} closed successfully")
        except Exception as e:
            logger.error(f"Error closing GenesisAgent: {str(e)}")
            logger.error(traceback.format_exc())

    # Sync version of close for backward compatibility
    def close_sync(self):
        """Synchronous version of close for backward compatibility"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.close())
        finally:
            loop.close()

    async def announce_self(self):
        """Publish a GenesisRegistration announcement for this agent."""
        try:
            logger.info(f"Starting announce_self for agent {self.agent_name}")
            
            # Create registration dynamic data
            registration = dds.DynamicData(self.app.registration_type)
            registration["message"] = f"Agent {self.agent_name} ({self.base_service_name}) announcing presence"
            registration["prefered_name"] = self.agent_name
            registration["default_capable"] = 1 # Assuming this means it can handle default requests for its service type
            registration["instance_id"] = self.app.agent_id
            registration["service_name"] = self.rpc_service_name # This is the name clients connect to for RPC
            # TODO: If IDL is updated, add a separate field for self.base_service_name for better type discovery by interfaces.
            # For now, CLI will see self.rpc_service_name as 'Service' and can use it to connect.
            
            logger.debug(f"Created registration announcement: message='{registration['message']}', prefered_name='{registration['prefered_name']}', default_capable={registration['default_capable']}, instance_id='{registration['instance_id']}', service_name='{registration['service_name']}' (base_service_name: {self.base_service_name})")
            
            # Write and flush the registration announcement
            logger.debug("🔍 TRACE: About to write registration announcement...")
            write_result = self.registration_writer.write(registration)
            logger.debug(f"✅ TRACE: Registration announcement write result: {write_result}")
            
            try:
                logger.debug("🔍 TRACE: About to flush registration writer...")
                # Get writer status before flush
                status = self.registration_writer.datawriter_protocol_status
                logger.debug(f"📊 TRACE: Writer status before flush - Sent")
                
                self.registration_writer.flush()
                
                # Get writer status after flush
                status = self.registration_writer.datawriter_protocol_status
                logger.debug(f"📊 TRACE: Writer status after flush - Sent")
                logger.debug("✅ TRACE: Registration writer flushed successfully")
                logger.info("Successfully announced agent presence")
            except Exception as flush_error:
                logger.error(f"💥 TRACE: Error flushing registration writer: {flush_error}")
                logger.error(traceback.format_exc())
                
        except Exception as e:
            logger.error(f"Error in announce_self: {e}")
            logger.error(traceback.format_exc())

class GenesisAnthropicChatAgent(GenesisAgent, AnthropicChatAgent):
    """Genesis agent that uses Anthropic's Claude model"""
    def __init__(self, model_name: str = "claude-3-opus-20240229", api_key: Optional[str] = None,
                 system_prompt: Optional[str] = None, max_history: int = 10):
        GenesisAgent.__init__(self, "Claude", "Chat")
        AnthropicChatAgent.__init__(self, model_name, api_key, system_prompt, max_history)
        
    async def process_request(self, request: Any) -> Dict[str, Any]:
        """Process chat request using Claude"""
        message = request["message"]
        conversation_id = request["conversation_id"]
        
        response, status = await self.generate_response(message, conversation_id)
        
        return {
            "response": response,
            "status": status
        } 