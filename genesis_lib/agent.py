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
from .agent_classifier import AgentClassifier
from genesis_lib.memory import SimpleMemoryAdapter

# Get logger
logger = logging.getLogger(__name__)

class GenesisAgent(ABC):
    """Base class for all Genesis agents"""
    registration_writer: Optional[dds.DynamicData.DataWriter] = None # Define at class level

    def __init__(self, agent_name: str, base_service_name: str, 
                 service_instance_tag: Optional[str] = None, agent_id: str = None,
                 enable_agent_communication: bool = False, memory_adapter=None):
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
        self.mcp_server = None  # Initialize MCP server to None
        
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
        self.agent_classifier = None  # For intelligent request routing
        self.memory = memory_adapter or SimpleMemoryAdapter()
        if enable_agent_communication:
            print(f"🚀 PRINT: Agent communication enabled for {self.agent_name}, calling _setup_agent_communication()")
            self._setup_agent_communication()
            # Initialize agent classifier for request routing with LLM support
            self.agent_classifier = AgentClassifier(
                openai_api_key=os.getenv('OPENAI_API_KEY'),
                model_name="gpt-4o-mini"
            )
        else:
            print(f"⏭️ PRINT: Agent communication disabled for {self.agent_name}")

    def enable_mcp(self, 
                   port=8000, 
                   toolname="ask_genesis_agent",
                   tooldesc="Ask the Genesis agent a question and get a response"):
        try:
            from mcp.server.fastmcp import FastMCP
        except ImportError:
            raise ImportError("FastMCP module not found. Install with: pip install fastmcp")
        try:
            import threading
        except ImportError:
            raise ImportError("Threading module not found")
        if not self.mcp_server:
            self.mcp_server = FastMCP(self.agent_name, port=port)
            self.mcp_server.add_tool(
                self.process_message,
                name=toolname,
                description=tooldesc)
            self._mcp_thread = threading.Thread(target=self.mcp_server.run, kwargs={"transport": "streamable-http"}, daemon=True)
            self._mcp_thread.start()

    def _setup_agent_communication(self):
        """Initialize agent-to-agent communication capabilities"""
        try:
            print(f"🚀 PRINT: _setup_agent_communication() starting for {self.agent_name}")
            logger.info(f"Setting up agent-to-agent communication for {self.agent_name}")
            
            # Create a communication mixin instance
            class AgentCommunicationWrapper(AgentCommunicationMixin):
                def __init__(self, parent_agent):
                    super().__init__()
                    self.parent_agent = parent_agent
                    # Share the app instance and agent attributes
                    self.app = parent_agent.app
                    self.base_service_name = parent_agent.base_service_name
                    self.agent_name = parent_agent.agent_name
                    self.agent_type = getattr(parent_agent, 'agent_type', 'AGENT')
                    self.description = getattr(parent_agent, 'description', f'Agent {parent_agent.agent_name}')
                
                async def process_agent_request(self, request):
                    """Delegate to parent agent's process_agent_request method"""
                    return await self.parent_agent.process_agent_request(request)
                
                def get_agent_capabilities(self):
                    """Delegate to parent agent's get_agent_capabilities method"""
                    return self.parent_agent.get_agent_capabilities()
            
            # Create the communication wrapper
            print("🏗️ PRINT: Creating AgentCommunicationWrapper...")
            self.agent_communication = AgentCommunicationWrapper(self)
            print("✅ PRINT: AgentCommunicationWrapper created")
            
            # Initialize RPC types
            print("🏗️ PRINT: Initializing agent RPC types...")
            if self.agent_communication._initialize_agent_rpc_types():
                print("✅ PRINT: Agent-to-agent RPC types loaded successfully")
                logger.info("Agent-to-agent RPC types loaded successfully")
            else:
                print("💥 PRINT: Failed to load agent-to-agent RPC types")
                logger.warning("Failed to load agent-to-agent RPC types")
                return
            
            # Set up agent discovery
            print("🏗️ PRINT: Setting up agent discovery...")
            if self.agent_communication._setup_agent_discovery():
                print("✅ PRINT: Agent discovery setup completed")
                logger.info("Agent discovery setup completed")
            else:
                print("💥 PRINT: Failed to set up agent discovery")
                logger.warning("Failed to set up agent discovery")
                return
            
            # Set up agent RPC service
            print("🏗️ PRINT: Setting up agent RPC service...")
            if self.agent_communication._setup_agent_rpc_service():
                print("✅ PRINT: Agent RPC service setup completed")
                logger.info("Agent RPC service setup completed")
            else:
                print("💥 PRINT: Failed to set up agent RPC service")
                logger.warning("Failed to set up agent RPC service")
                return
            
            # Set up agent capability publishing
            print("🏗️ PRINT: Setting up agent capability publishing...")
            if self.agent_communication._setup_agent_capability_publishing():
                print("✅ PRINT: Agent capability publishing setup completed")
                logger.info("Agent capability publishing setup completed")
                # Publish initial capability with enhanced information
                agent_capabilities = self.get_agent_capabilities()
                print(f"📊 PRINT: Publishing enhanced capabilities: {agent_capabilities}")
                self.agent_communication.publish_agent_capability(agent_capabilities)
            else:
                print("💥 PRINT: Failed to set up agent capability publishing")
                logger.warning("Failed to set up agent capability publishing")
            
            print(f"✅ PRINT: Agent-to-agent communication enabled for {self.agent_name}")
            logger.info(f"Agent-to-agent communication enabled for {self.agent_name}")
            
        except Exception as e:
            print(f"💥 PRINT: Failed to set up agent communication: {e}")
            logger.error(f"Failed to set up agent communication: {e}")
            import traceback
            print(f"💥 PRINT: Traceback: {traceback.format_exc()}")
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
    
    # Enhanced Discovery Methods (delegate to AgentCommunicationMixin)
    
    def find_agents_by_capability(self, capability: str) -> List[str]:
        """Find agents that advertise a specific capability"""
        if self.agent_communication:
            return self.agent_communication.find_agents_by_capability(capability)
        return []
    
    def find_agents_by_specialization(self, domain: str) -> List[str]:
        """Find agents with expertise in a specific domain"""
        if self.agent_communication:
            return self.agent_communication.find_agents_by_specialization(domain)
        return []
    
    def find_general_agents(self) -> List[str]:
        """Find agents that can handle general requests"""
        if self.agent_communication:
            return self.agent_communication.find_general_agents()
        return []
    
    def find_specialized_agents(self) -> List[str]:
        """Find agents that are specialized"""
        if self.agent_communication:
            return self.agent_communication.find_specialized_agents()
        return []
    
    async def get_best_agent_for_request(self, request: str) -> Optional[str]:
        """Use the classifier to find the best agent for a specific request"""
        if self.agent_communication:
            return await self.agent_communication.get_best_agent_for_request(request)
        return None
    
    def get_agents_by_performance_metric(self, metric_name: str, min_value: Optional[float] = None, max_value: Optional[float] = None) -> List[str]:
        """Find agents based on performance metrics"""
        if self.agent_communication:
            return self.agent_communication.get_agents_by_performance_metric(metric_name, min_value, max_value)
        return []
    
    def get_agent_info_by_capability(self, capability: str) -> List[Dict[str, Any]]:
        """Get full agent information for agents with a specific capability"""
        if self.agent_communication:
            return self.agent_communication.get_agent_info_by_capability(capability)
        return []
    
    def get_agents_by_model_type(self, model_type: str) -> List[str]:
        """Find agents using a specific model type"""
        if self.agent_communication:
            return self.agent_communication.get_agents_by_model_type(model_type)
        return []
    
    def get_agent_capabilities(self) -> Dict[str, Any]:
        """
        Define this agent's capabilities for advertisement.
        
        This method should be overridden by subclasses to provide specific
        capability information for agent discovery and classification.
        
        Returns:
            Dictionary containing agent capability information with keys:
            - agent_type: "general" or "specialized"
            - specializations: List of domain expertise areas
            - capabilities: List of specific capabilities/skills
            - classification_tags: List of keywords for request routing
            - model_info: Information about underlying models (for AI agents)
            - default_capable: Boolean indicating if agent can handle general requests
            - performance_metrics: Optional performance information
        """
        # Default implementation for base GenesisAgent
        return {
            "agent_type": "general",
            "specializations": [],
            "capabilities": ["general_assistance"],
            "classification_tags": ["general", "assistant"],
            "model_info": None,
            "default_capable": True,
            "performance_metrics": None
        }
    
    async def route_request_to_best_agent(self, request_message: str, 
                                        conversation_id: Optional[str] = None,
                                        timeout_seconds: float = 10.0) -> Optional[Dict[str, Any]]:
        """
        Intelligently route a request to the best available agent.
        
        This method uses the agent classifier to determine which agent is best
        suited to handle the request, then forwards the request accordingly.
        
        Args:
            request_message: The request to be processed
            conversation_id: Optional conversation ID for tracking
            timeout_seconds: Timeout for the agent request
            
        Returns:
            Response from the selected agent, or None if routing failed
        """
        if not self.agent_communication or not self.agent_classifier:
            logger.warning("Agent communication or classifier not available for routing")
            return None
        
        # Get discovered agents
        discovered_agents = self.get_discovered_agents()
        
        if not discovered_agents:
            logger.info("No agents discovered for routing")
            return None
        
        # Use classifier to find best agent
        try:
            best_agent_id = await self.agent_classifier.classify_request(
                request_message, discovered_agents
            )
            
            if not best_agent_id:
                logger.info("No suitable agent found for request")
                return None
            
            # Don't route to ourselves
            if hasattr(self, 'app') and best_agent_id == self.app.agent_id:
                logger.info("Best agent is self, handling locally")
                return None
            
            # Get explanation for routing decision
            explanation = self.agent_classifier.get_classification_explanation(
                request_message, best_agent_id, discovered_agents
            )
            logger.info(f"Routing decision: {explanation}")
            
            # Route the request
            response = await self.send_agent_request(
                target_agent_id=best_agent_id,
                message=request_message,
                conversation_id=conversation_id,
                timeout_seconds=timeout_seconds
            )
            
            if response and response.get('status') == 0:
                # Add routing metadata to response
                response['routed_to'] = best_agent_id
                response['routing_explanation'] = explanation
                logger.info(f"Successfully routed request to {best_agent_id}")
                return response
            else:
                logger.warning(f"Failed to get response from routed agent {best_agent_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error during request routing: {e}")
            return None
    
    async def process_request_with_routing(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a request with automatic intelligent routing to specialized agents.
        
        This method first tries to route the request to a specialized agent.
        If no suitable specialist is found or if routing fails, it falls back
        to processing the request locally.
        
        Args:
            request: Dictionary containing the request data
            
        Returns:
            Dictionary containing the response data
        """
        message = request.get('message', '')
        conversation_id = request.get('conversation_id', '')
        
        # Try intelligent routing first if enabled
        if self.agent_communication and self.agent_classifier:
            routed_response = await self.route_request_to_best_agent(
                request_message=message,
                conversation_id=conversation_id
            )
            
            if routed_response:
                # Add routing metadata to indicate this was routed
                routed_response['message'] = f"[Routed] {routed_response.get('message', '')}"
                return routed_response
        
        # Fallback to local processing
        return await self.process_request(request)

    @abstractmethod
    async def process_request(self, request: Any) -> Dict[str, Any]:
        """Process the request and return reply data as a dictionary"""
        pass

    async def run(self):
        """Main agent loop"""
        try:
            print(f"🚀 PRINT: GenesisAgent.run() starting for {self.agent_name}")
            # Announce presence
            print("📢 PRINT: About to announce agent presence...")
            logger.info("Announcing agent presence...")
            await self.announce_self()
            print("✅ PRINT: Agent presence announced successfully")
            
            # Main loop - handle agent requests if enabled
            print(f"👂 PRINT: {self.agent_name} listening for requests (Ctrl+C to exit)...")
            logger.info(f"{self.agent_name} listening for requests (Ctrl+C to exit)...")
            
            # Main event loop with agent request handling
            while True:
                try:
                    # Handle agent-to-agent requests if communication is enabled
                    if self.agent_communication:
                        await self.agent_communication._handle_agent_requests()
                    
                    # Small delay to prevent busy waiting
                    await asyncio.sleep(0.1)
                    
                except KeyboardInterrupt:
                    print(f"\n🛑 PRINT: KeyboardInterrupt in main loop, breaking...")
                    break
                except Exception as e:
                    logger.error(f"Error in main agent loop: {e}")
                    # Continue running despite errors
                    await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print(f"\n🛑 PRINT: KeyboardInterrupt in GenesisAgent.run(), shutting down {self.agent_name}...")
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

            # Close MCP server
            if hasattr(self, 'mcp_server') and self.mcp_server is not None and hasattr(self.mcp_server, "stop"):
                self.mcp_server.stop()

            # Wait for MCP thread to finish
            if hasattr(self, '_mcp_thread') and self._mcp_thread is not None:
                self._mcp_thread.join(timeout=5.0)
                if self._mcp_thread.is_alive():
                    logger.warning("MCP thread did not shut down within 5 seconds and may be stuck.")

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
            print(f"🚀 PRINT: Starting announce_self for agent {self.agent_name}")
            logger.info(f"Starting announce_self for agent {self.agent_name}")
            
            # Create registration dynamic data
            print("🏗️ PRINT: Creating registration dynamic data...")
            registration = dds.DynamicData(self.app.registration_type)
            print("✅ PRINT: Registration dynamic data created")
            
            print("📝 PRINT: Setting registration fields...")
            registration["message"] = f"Agent {self.agent_name} ({self.base_service_name}) announcing presence"
            registration["prefered_name"] = self.agent_name
            registration["default_capable"] = 1 # Assuming this means it can handle default requests for its service type
            registration["instance_id"] = self.app.agent_id
            registration["service_name"] = self.rpc_service_name # This is the name clients connect to for RPC
            print("✅ PRINT: Registration fields set")
            # TODO: If IDL is updated, add a separate field for self.base_service_name for better type discovery by interfaces.
            # For now, CLI will see self.rpc_service_name as 'Service' and can use it to connect.
            
            logger.debug(f"Created registration announcement: message='{registration['message']}', prefered_name='{registration['prefered_name']}', default_capable={registration['default_capable']}, instance_id='{registration['instance_id']}', service_name='{registration['service_name']}' (base_service_name: {self.base_service_name})")
            
            # Write and flush the registration announcement
            print("📤 PRINT: About to write registration announcement...")
            logger.debug("🔍 TRACE: About to write registration announcement...")
            write_result = self.registration_writer.write(registration)
            print(f"✅ PRINT: Registration announcement write result: {write_result}")
            logger.debug(f"✅ TRACE: Registration announcement write result: {write_result}")
            
            try:
                print("🔄 PRINT: About to flush registration writer...")
                logger.debug("🔍 TRACE: About to flush registration writer...")
                # Get writer status before flush
                status = self.registration_writer.datawriter_protocol_status
                logger.debug(f"📊 TRACE: Writer status before flush - Sent")
                
                self.registration_writer.flush()
                print("✅ PRINT: Registration writer flushed successfully")
                
                # Get writer status after flush
                status = self.registration_writer.datawriter_protocol_status
                logger.debug(f"📊 TRACE: Writer status after flush - Sent")
                logger.debug("✅ TRACE: Registration writer flushed successfully")
                logger.info("Successfully announced agent presence")
            except Exception as flush_error:
                print(f"💥 PRINT: Error flushing registration writer: {flush_error}")
                logger.error(f"💥 TRACE: Error flushing registration writer: {flush_error}")
                logger.error(traceback.format_exc())
                
        except Exception as e:
            print(f"💥 PRINT: Error in announce_self: {e}")
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
