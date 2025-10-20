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
from genesis_lib.advertisement_bus import AdvertisementBus
from .agent_communication import AgentCommunicationMixin
from .agent_classifier import AgentClassifier
from genesis_lib.memory import SimpleMemoryAdapter

# Get logger
logger = logging.getLogger(__name__)

class GenesisAgent(ABC):
    """Base class for all Genesis agents"""
    # registration_writer removed - now using unified Advertisement topic via AdvertisementBus

    def __init__(self, agent_name: str, base_service_name: str, 
                 agent_id: str = None,
                 enable_agent_communication: bool = False, memory_adapter=None,
                 auto_run: bool = True, service_instance_tag: str = ""):
        """
        Initialize the agent.
        
        Args:
            agent_name: Name of the agent (for display, identification)
            base_service_name: The fundamental type of service offered (e.g., "Chat", "ImageGeneration")
            agent_id: Optional UUID for the agent (if None, will generate one)
            enable_agent_communication: Whether to enable agent-to-agent communication capabilities
            memory_adapter: Optional custom memory adapter for conversation history
            auto_run: Whether to automatically start the agent's run loop
            service_instance_tag: Optional tag for content filtering (e.g., "production", "staging", "v2")
                                 Used for migrations and A/B testing via content filtering, not topic names
        
        Note:
            RPC v2 uses unified topics with GUID-based targeting. All agents of the same
            base_service_name share the same DDS topics (e.g., rti/connext/genesis/rpc/OpenAIChatRequest).
            Individual agents are targeted using their unique replier_guid, not separate topic names.
            The optional service_instance_tag enables content filtering for migration scenarios.
        """
        logger.info(f"GenesisAgent {agent_name} STARTING initializing with agent_id {agent_id}, base_service_name: {base_service_name}, tag: {service_instance_tag}")
        self.agent_name = agent_name
        self.mcp_server = None  # Initialize MCP server to None
        
        # RPC v2: Use base_service_name directly - no instance tags needed
        # All instances share unified topics, targeted by GUID
        self.base_service_name = base_service_name
        self.rpc_service_name = base_service_name
        self.service_instance_tag = service_instance_tag  # Optional tag for content filtering
        
        logger.info(f"RPC v2 service name: {self.rpc_service_name} (unified topics, tag: {service_instance_tag or 'none'})")

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

        # --- Auto-run state ---
        # Task handle for the background run loop and flags for idempotency
        self._run_task: Optional[asyncio.Task] = None
        self._run_started: bool = False
        self._auto_run_requested: bool = auto_run


        # Legacy GenesisRegistration writer removed - now using unified Advertisement topic via AdvertisementBus
        logger.debug("✅ TRACE: Agent will use unified Advertisement topic for announcements")

        # Create replier with data available listener
        class RequestListener(dds.DynamicData.DataReaderListener):
            def __init__(self, agent):
                super().__init__()  # Call parent class __init__
                self.agent = agent
                
            def on_data_available(self, reader):
                # ALWAYS print to verify callback is invoked
                print(f"🔔🔔🔔 PRINT: RequestListener.on_data_available() CALLED for {self.agent.agent_name}!")
                logger.info(f"RequestListener.on_data_available() CALLED for {self.agent.agent_name}")
                
                # Get all available samples
                samples = self.agent.replier.take_requests()
                print(f"📊 PRINT: RequestListener got {len(samples)} request samples")
                
                for request, info in samples:
                    if request is None or info.state.instance_state != dds.InstanceState.ALIVE:
                        print(f"⏭️ PRINT: Skipping invalid request sample")
                        continue
                        
                    # RPC v2: Content filtering based on target_service_guid
                    # Extract target_service_guid from request if present
                    try:
                        target_guid = request.get_string("target_service_guid")
                        service_tag = request.get_string("service_instance_tag")
                        
                        # Check if this is a broadcast (empty target_guid) or targeted to us
                        is_broadcast = not target_guid or target_guid == ""
                        is_targeted_to_us = target_guid == self.agent.replier_guid
                        
                        # Check if service_instance_tag matches (if set)
                        tag_matches = True
                        if service_tag and hasattr(self.agent, 'service_instance_tag'):
                            tag_matches = service_tag == self.agent.service_instance_tag
                        
                        if not is_broadcast and not is_targeted_to_us:
                            logger.debug(f"⏭️ Skipping request targeted to different agent (target: {target_guid}, us: {self.agent.replier_guid})")
                            continue
                            
                        if not tag_matches:
                            logger.debug(f"⏭️ Skipping request with non-matching service_instance_tag")
                            continue
                            
                        logger.debug(f"✅ Processing request ({'broadcast' if is_broadcast else 'targeted'}, tag: {service_tag or 'none'})")
                        
                    except Exception as e:
                        # If fields don't exist, fall back to processing (backward compat)
                        logger.warning(f"Could not read RPC v2 fields from request, processing anyway: {e}")
                        
                    print(f"✅ PRINT: Processing valid Interface-to-Agent request")
                    logger.info(f"Received request: {request}")
                    
                    try:
                        # Create task to process request asynchronously
                        asyncio.run_coroutine_threadsafe(self._process_request(request, info), self.agent.loop)
                    except Exception as e:
                        print(f"💥 PRINT: Error creating request processing task: {e}")
                        logger.error(f"Error creating request processing task: {e}")
                        logger.error(traceback.format_exc())
                        
            async def _process_request(self, request, info):
                print(f"🚀 PRINT: _process_request() started for {self.agent.agent_name}")
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

                    print(f"📝 PRINT: Converted request to dict: {request_dict}")
                    # Get reply data from concrete implementation, passing the dictionary
                    print(f"🔄 PRINT: Calling process_request()...")
                    reply_data = await self.agent.process_request(request_dict)
                    print(f"✅ PRINT: process_request() returned: {reply_data}")
                    
                    # Create reply - explicitly set all required fields including RPC v2 fields
                    print(f"📤 PRINT: Creating DDS reply...")
                    reply = dds.DynamicData(self.agent.reply_type)
                    reply["message"] = str(reply_data.get("message", ""))
                    reply["status"] = int(reply_data.get("status", 0))
                    reply["conversation_id"] = str(reply_data.get("conversation_id", ""))
                    
                    # RPC v2: Include our replier_guid for subsequent targeted requests
                    reply["replier_service_guid"] = self.agent.replier_guid
                    
                    # Echo back the service_instance_tag if present in request
                    service_tag = request_dict.get("service_instance_tag", "")
                    reply["service_instance_tag"] = service_tag
                    
                    print(f"📤 PRINT: Sending reply via replier...")
                    # Send reply
                    self.agent.replier.send_reply(reply, info)
                    print(f"✅ PRINT: Reply sent successfully!")
                    logger.info(f"Sent reply: {reply}")
                except Exception as e:
                    logger.error(f"Error processing request: {e}")
                    logger.error(traceback.format_exc())
                    # Send error reply - explicitly set all required fields including RPC v2 fields
                    reply = dds.DynamicData(self.agent.reply_type)
                    reply["message"] = f"Error: {str(e)}"
                    reply["status"] = 1  # Error status
                    reply["conversation_id"] = ""  # Empty conversation ID for errors
                    reply["replier_service_guid"] = self.agent.replier_guid  # RPC v2
                    reply["service_instance_tag"] = ""  # RPC v2
                    self.agent.replier.send_reply(reply, info)
        
        # Create replier with listener using unified RPC v2 naming
        self.replier = rpc.Replier(
            request_type=self.request_type,
            reply_type=self.reply_type,
            participant=self.app.participant,
            service_name=f"rti/connext/genesis/rpc/{self.rpc_service_name}"
        )
        
        # Store replier GUID for RPC v2 targeted requests
        from genesis_lib.utils.guid_utils import format_guid
        self.replier_guid = format_guid(self.replier.reply_datawriter.instance_handle)
        logger.info(f"Agent {self.agent_name} replier_guid: {self.replier_guid}")
        
        # Set listener on replier's DataReader with status mask for data available
        self.request_listener = RequestListener(self)
        mask = dds.StatusMask.DATA_AVAILABLE
        self.replier.request_datareader.set_listener(self.request_listener, mask)
        
        # Store discovered functions
        # self.discovered_functions = [] # Removed as per event-driven plan
        
        # Initialize internal tools cache for @genesis_tool decorated methods
        self.internal_tools_cache = {}
        
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

        # Optionally auto-start the agent service loop if an event loop is running.
        # This makes the agent discoverable without requiring users to call run().
        if self._auto_run_requested:
            try:
                running_loop = asyncio.get_running_loop()
                # Schedule background run; run() is idempotent and will no-op if already started.
                self._run_task = running_loop.create_task(self.run())
                logger.info(f"Auto-started run() for {self.agent_name} in background task")
            except RuntimeError:
                # No running loop yet (common in sync contexts). User can still call `await run()` later.
                logger.debug("No running event loop at construction; deferring auto-start of run().")

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
                    # Ensure RPC service name (with tag) is visible to the mixin
                    self.rpc_service_name = getattr(parent_agent, 'rpc_service_name', None)
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
    
    def _auto_generate_capabilities(self) -> Dict[str, Any]:
        """
        Auto-generate capability metadata from @genesis_tool methods and init fields.
        Subclasses can override get_agent_capabilities for custom behavior.
        """
        try:
            tool_methods: List[Dict[str, Any]] = []
            for attr_name in dir(self):
                if attr_name.startswith('_'):
                    continue
                attr = getattr(self, attr_name)
                if callable(attr) and hasattr(attr, '__is_genesis_tool__'):
                    meta = getattr(attr, '__genesis_tool_meta__', {}) or {}
                    if meta:
                        tool_methods.append(meta)
            # Build capabilities list from function names and operation types
            capability_items: List[str] = []
            classification_tags: List[str] = []
            for meta in tool_methods:
                func_name = meta.get('function_name')
                if func_name:
                    capability_items.append(func_name)
                    classification_tags.extend(str(func_name).lower().replace('_', ' ').split())
                op_type = meta.get('operation_type')
                if op_type:
                    capability_items.append(str(op_type))
                    classification_tags.extend(str(op_type).lower().split())
                desc = meta.get('description')
                if isinstance(desc, str) and desc:
                    # Pick a few keywords from description (very lightweight heuristic)
                    for token in desc.lower().split():
                        if token.isalpha() and len(token) >= 4:
                            classification_tags.append(token)
            # Add context from init fields
            base_service = getattr(self, 'base_service_name', None)
            if isinstance(base_service, str) and base_service:
                classification_tags.extend(base_service.lower().split('_'))
            agent_name = getattr(self, 'agent_name', None)
            if isinstance(agent_name, str) and agent_name:
                classification_tags.extend(agent_name.lower().split('_'))
            # Deduplicate while preserving order
            def _dedupe(seq: List[str]) -> List[str]:
                seen = set()
                result: List[str] = []
                for item in seq:
                    if item not in seen:
                        seen.add(item)
                        result.append(item)
                return result
            capability_items = _dedupe([c for c in capability_items if isinstance(c, str) and c])
            classification_tags = _dedupe([t for t in classification_tags if isinstance(t, str) and t])
            # Heuristic specializations: common domains often occur in names/tags
            specializations: List[str] = []
            domain_hints = ['weather', 'finance', 'math', 'translation', 'graph', 'image', 'audio', 'diagnostic']
            for hint in domain_hints:
                if any(hint in t for t in classification_tags):
                    specializations.append(hint)
            specializations = _dedupe(specializations)
            # Model info from common attributes
            model_info: Optional[Dict[str, Any]] = None
            model_name = getattr(self, 'model_name', None)
            if isinstance(model_name, str) and model_name:
                model_info = {
                    'llm_model': model_name,
                    'auto_discovery': bool(tool_methods)
                }
            # Default capable: true when we have no strong specialization hints
            default_capable = not bool(specializations)
            # Build result
            return {
                'agent_type': 'general',
                'specializations': specializations,
                'capabilities': capability_items if capability_items else ['general_assistance'],
                'classification_tags': classification_tags if classification_tags else ['general', 'assistant'],
                'model_info': model_info,
                'default_capable': default_capable if capability_items else True,
                'performance_metrics': None,
            }
        except Exception as e:
            logger.warning(f"Auto capability generation failed, falling back to defaults: {e}")
            return {
                'agent_type': 'general',
                'specializations': [],
                'capabilities': ['general_assistance'],
                'classification_tags': ['general', 'assistant'],
                'model_info': None,
                'default_capable': True,
                'performance_metrics': None,
            }

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
        # Default implementation for base GenesisAgent uses auto-generation.
        return self._auto_generate_capabilities()
    
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

    def _get_available_functions(self) -> Dict[str, Any]:
        """
        Get currently available functions from FunctionRegistry via GenericFunctionClient.
        This is the single source of truth for function availability, querying DDS directly.
        Available to all agents regardless of LLM backend (OpenAI, Anthropic, custom).
        
        Returns:
            Dict[str, Dict]: Dictionary keyed by function name, containing:
                - function_id: Unique identifier for the function
                - description: Human-readable description
                - schema: JSON schema for function parameters
                - provider_id: ID of the service providing this function
        """
        # Lazy init GenericFunctionClient if needed
        if not hasattr(self, '_generic_client'):
            from genesis_lib.generic_function_client import GenericFunctionClient
            self._generic_client = GenericFunctionClient(
                function_registry=self.app.function_registry
            )
        
        functions = self._generic_client.list_available_functions()
        result = {}
        for func_data in functions:
            func_name = func_data["name"]
            result[func_name] = {
                "function_id": func_data["function_id"],
                "description": func_data["description"],
                "schema": func_data["schema"],
                "provider_id": func_data.get("provider_id"),
            }
        return result

    def _generate_capability_based_tool_names(self, agent_info, capabilities, specializations, service_name):
        """
        Generate tool names based on agent capabilities and specializations instead of agent names.
        This ensures the LLM can discover functionality rather than needing to know agent names.
        Available to all agents regardless of LLM backend.
        """
        tool_names = {}
        
        # Generate tools based on specializations (most specific)
        for specialization in specializations:
            tool_name = f"get_{specialization.lower().replace(' ', '_').replace('-', '_')}_info"
            tool_description = f"Get information and assistance related to {specialization}. " + \
                             f"This tool connects to a specialized {specialization} agent."
            tool_names[tool_name] = tool_description
        
        # Generate tools based on service type
        if service_name and service_name != 'UnknownService':
            # Create service-based tool name
            service_clean = service_name.lower().replace('service', '').replace(' ', '_').replace('-', '_')
            if service_clean:
                tool_name = f"use_{service_clean}_service"
                tool_description = f"Access {service_name} capabilities. " + \
                                 f"Description: {agent_info.get('description', 'Specialized service')}"
                tool_names[tool_name] = tool_description
        
        # Generate tools based on capabilities
        for capability in capabilities:
            capability_clean = capability.lower().replace(' ', '_').replace('-', '_')
            tool_name = f"request_{capability_clean}"
            tool_description = f"Request {capability} functionality from a specialized agent. " + \
                             f"Service: {service_name}"
            tool_names[tool_name] = tool_description
        
        # Fallback: if no specific capabilities/specializations, create a generic tool
        if not tool_names:
            agent_type_clean = agent_info.get('agent_type', 'agent').lower().replace('_', '_')
            tool_name = f"consult_{agent_type_clean}"
            tool_description = f"Consult a {agent_info.get('agent_type', 'general')} agent. " + \
                             f"Service: {service_name}. " + \
                             f"Description: {agent_info.get('description', 'General purpose agent')}"
            tool_names[tool_name] = tool_description
        
        return tool_names

    def _get_available_agent_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Get currently available agents as capability-based tools.
        Queries discovered_agents dynamically and transforms to tool format.
        This is the single source of truth queried from DDS via AgentCommunicationMixin.
        Available to all agents regardless of LLM backend.
        
        Returns:
            Dict[str, Dict]: Dictionary keyed by tool name, containing agent metadata
        """
        # Skip if agent communication is not enabled
        if not hasattr(self, 'agent_communication') or not self.agent_communication:
            return {}
        
        # Get discovered agents from the communication mixin (source of truth)
        discovered_agents = self.get_discovered_agents()
        
        if not discovered_agents:
            return {}
        
        agent_tools = {}
        
        for agent_id, agent_info in discovered_agents.items():
            # Skip self to avoid circular calls
            if agent_id == self.app.agent_id:
                continue
            
            # Extract capability information
            agent_name = agent_info.get('name', agent_id)
            agent_type = agent_info.get('agent_type', 'AGENT')
            service_name = agent_info.get('service_name', 'UnknownService')
            description = agent_info.get('description', f'Agent {agent_name}')
            capabilities = agent_info.get('capabilities', [])
            specializations = agent_info.get('specializations', [])
            
            # Generate capability-based tool names
            tool_names = self._generate_capability_based_tool_names(
                agent_info, capabilities, specializations, service_name
            )
            
            # Create tool entries for each capability/specialization
            for tool_name, tool_description in tool_names.items():
                agent_tools[tool_name] = {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "agent_type": agent_type,
                    "service_name": service_name,
                    "description": description,
                    "tool_description": tool_description,
                    "capabilities": capabilities,
                    "specializations": specializations,
                    "is_capability_based": True
                }
        
        return agent_tools

    async def _call_function(self, function_name: str, **kwargs) -> Any:
        """
        Call a function using the generic client.
        Available to all agents regardless of LLM backend.
        
        Args:
            function_name: Name of the function to call
            **kwargs: Function arguments
            
        Returns:
            Function result (extracted from dict if present)
        """
        logger.debug(f"===== TRACING: Calling function {function_name} =====")
        logger.debug(f"===== TRACING: Function arguments: {json.dumps(kwargs, indent=2)} =====")
        
        available_functions = self._get_available_functions()
        if function_name not in available_functions:
            error_msg = f"Function not found: {function_name}"
            logger.error(f"===== TRACING: {error_msg} =====")
            raise ValueError(error_msg)
        
        try:
            # Call the function through the generic client
            start_time = time.time()
            result = await self._generic_client.call_function(
                available_functions[function_name]["function_id"],
                **kwargs
            )
            end_time = time.time()
            
            logger.debug(f"===== TRACING: Function call completed in {end_time - start_time:.2f} seconds =====")
            logger.debug(f"===== TRACING: Function result: {result} =====")
            
            # Extract result value if in dict format
            if isinstance(result, dict) and "result" in result:
                return result["result"]
            return result
            
        except Exception as e:
            logger.error(f"===== TRACING: Error calling function {function_name}: {str(e)} =====")
            logger.error(traceback.format_exc())
            raise

    async def _call_agent(self, agent_tool_name: str, **kwargs) -> Any:
        """
        Call an agent using the UNIVERSAL AGENT SCHEMA.
        Available to all agents regardless of LLM backend.
        
        All agents use the same simple interface:
        - Input: message (string)
        - Output: response (string)
        
        This eliminates the need for agents to handle custom tool schemas.
        
        Args:
            agent_tool_name: Name of the agent tool to call
            **kwargs: Agent arguments (expects 'message' key)
            
        Returns:
            Agent response (extracted from dict if present)
        """
        logger.debug(f"===== TRACING: Calling agent tool {agent_tool_name} =====")
        logger.debug(f"===== TRACING: Agent arguments: {json.dumps(kwargs, indent=2)} =====")
        
        available_agent_tools = self._get_available_agent_tools()
        if agent_tool_name not in available_agent_tools:
            error_msg = f"Agent tool not found: {agent_tool_name}"
            logger.error(f"===== TRACING: {error_msg} =====")
            raise ValueError(error_msg)
        
        agent_info = available_agent_tools[agent_tool_name]
        target_agent_id = agent_info["agent_id"]
        
        # Extract message from universal schema (simplified from query/context pattern)
        message = kwargs.get("message", "")
        if not message:
            # Fallback for backward compatibility with old query/context pattern
            query = kwargs.get("query", "")
            context = kwargs.get("context", "")
            message = f"{query} {context}".strip() if context else query
        
        if not message:
            raise ValueError("No message provided for agent call")
        
        try:
            # Use monitored agent communication if available
            if hasattr(self, 'send_agent_request_monitored'):
                logger.debug(f"===== TRACING: Using monitored agent communication =====")
                start_time = time.time()
                result = await self.send_agent_request_monitored(
                    target_agent_id=target_agent_id,
                    message=message,
                    conversation_id=None,  # Simplified - no separate conversation tracking
                    timeout_seconds=30.0
                )
                end_time = time.time()
            else:
                # Fallback to basic agent communication
                logger.debug(f"===== TRACING: Using basic agent communication =====")
                start_time = time.time()
                result = await self.send_agent_request(
                    target_agent_id=target_agent_id,
                    message=message,
                    conversation_id=None,  # Simplified - no separate conversation tracking
                    timeout_seconds=30.0
                )
                end_time = time.time()
            
            logger.debug(f"===== TRACING: Agent call completed in {end_time - start_time:.2f} seconds =====")
            logger.debug(f"===== TRACING: Agent result: {result} =====")
            
            # Extract result message if in dict format (universal response handling)
            if isinstance(result, dict):
                if "message" in result:
                    return result["message"]
                elif "response" in result:
                    return result["response"]
                else:
                    return str(result)
            return str(result)
            
        except Exception as e:
            logger.error(f"===== TRACING: Error calling agent {agent_tool_name}: {str(e)} =====")
            logger.error(traceback.format_exc())
            raise

    async def _ensure_internal_tools_discovered(self):
        """
        Discover and register internal methods decorated with @genesis_tool.
        Available to all agents regardless of LLM backend.
        
        This method automatically scans the agent for methods decorated with @genesis_tool,
        generates appropriate tool schemas, and stores them for automatic injection
        into LLM clients.
        """
        logger.debug("===== TRACING: Discovering internal @genesis_tool methods =====")
        
        # Initialize internal tools cache if not exists (safety check)
        if not hasattr(self, 'internal_tools_cache'):
            self.internal_tools_cache = {}
        
        # Scan all methods for @genesis_tool decorator
        tool_methods = []
        for attr_name in dir(self):
            if attr_name.startswith('_'):  # Skip private methods
                continue
                
            attr = getattr(self, attr_name)
            if callable(attr) and hasattr(attr, '__is_genesis_tool__'):
                tool_meta = getattr(attr, '__genesis_tool_meta__', {})
                if tool_meta:
                    tool_methods.append((attr_name, attr, tool_meta))
                    logger.debug(f"===== TRACING: Found @genesis_tool method: {attr_name} =====")
        
        if not tool_methods:
            logger.debug("===== TRACING: No @genesis_tool methods found =====")
            return
        
        logger.debug(f"===== TRACING: Processing {len(tool_methods)} @genesis_tool methods =====")
        
        # Generate tool schemas for discovered methods
        for method_name, method, tool_meta in tool_methods:
            # Store method reference and metadata
            self.internal_tools_cache[method_name] = {
                "method": method,
                "metadata": tool_meta,
                "function_name": tool_meta.get("function_name", method_name)
            }
            
            logger.debug(f"===== TRACING: Registered internal tool: {method_name} =====")
            logger.debug(f"===== TRACING: Tool metadata: {tool_meta} =====")

    async def _call_internal_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Call an internal @genesis_tool decorated method.
        Available to all agents regardless of LLM backend.
        
        Args:
            tool_name: Name of the internal tool/method to call
            **kwargs: Arguments to pass to the method
            
        Returns:
            Result from the internal method
        """
        logger.debug(f"===== TRACING: Calling internal tool {tool_name} =====")
        logger.debug(f"===== TRACING: Tool arguments: {json.dumps(kwargs, indent=2)} =====")
        
        if not hasattr(self, 'internal_tools_cache') or tool_name not in self.internal_tools_cache:
            error_msg = f"Internal tool not found: {tool_name}"
            logger.error(f"===== TRACING: {error_msg} =====")
            raise ValueError(error_msg)
        
        tool_info = self.internal_tools_cache[tool_name]
        method = tool_info["method"]
        
        try:
            start_time = time.time()
            
            # Call the internal method
            if asyncio.iscoroutinefunction(method):
                result = await method(**kwargs)
            else:
                result = method(**kwargs)
                
            end_time = time.time()
            
            logger.debug(f"===== TRACING: Internal tool call completed in {end_time - start_time:.2f} seconds =====")
            logger.debug(f"===== TRACING: Internal tool result: {result} =====")
            
            return result
            
        except Exception as e:
            logger.error(f"===== TRACING: Error calling internal tool {tool_name}: {str(e)} =====")
            logger.error(traceback.format_exc())
            raise

    @abstractmethod
    async def process_request(self, request: Any) -> Dict[str, Any]:
        """Process the request and return reply data as a dictionary"""
        pass

    async def run(self):
        """Main agent loop"""
        try:
            # Idempotency: if already started, return immediately so duplicate calls don't stack
            if getattr(self, "_run_started", False):
                logger.info(f"run() already started for {self.agent_name}; joining existing loop")
                # Preserve historical behavior: if the caller explicitly awaits run(),
                # and a background run task exists, await it so this call blocks.
                try:
                    if getattr(self, "_run_task", None) is not None:
                        await self._run_task
                except Exception:
                    # If awaiting fails or no task, just return
                    pass
                return
            self._run_started = True
            # Track the current running task so other callers can await it
            try:
                self._run_task = asyncio.current_task()
            except Exception:
                self._run_task = None

            print(f"🚀 PRINT: GenesisAgent.run() starting for {self.agent_name}")
            # Announce presence
            print("📢 PRINT: About to announce agent presence...")
            logger.info("Announcing agent presence via unified advertisement...")
            await self.announce_self()
            print("✅ PRINT: Agent presence announced successfully")
            
            # Main loop - handle agent requests if enabled
            print(f"👂 PRINT: {self.agent_name} listening for requests (Ctrl+C to exit)...")
            logger.info(f"{self.agent_name} listening for requests (Ctrl+C to exit)...")
            
            # Main event loop with agent request handling
            loop_count = 0
            while True:
                try:
                    loop_count += 1
                    # Print every 100 iterations to verify loop is running
                    if loop_count % 100 == 1:
                        print(f"🔄 PRINT: Main event loop iteration #{loop_count}, agent_communication={self.agent_communication is not None}")
                    
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
        finally:
            # Allow future restarts if the loop exits
            self._run_started = False
            self._run_task = None

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
        """Publish a unified GenesisAdvertisement(kind=AGENT) for this agent."""
        try:
            print(f"🚀 PRINT: Starting announce_self for agent {self.agent_name}")
            logger.info(f"Starting announce_self for agent {self.agent_name}")

            # Use shared advertisement bus (reuses topic/writer per participant)
            bus = AdvertisementBus.get(self.app.participant)
            ad_type = bus.ad_type
            writer = bus.writer

            # Build advertisement sample (AGENT)
            ad = dds.DynamicData(ad_type)
            ad["advertisement_id"] = self.app.agent_id
            ad["kind"] = 1  # AGENT
            ad["name"] = self.agent_name
            ad["description"] = self.base_service_name or ""
            ad["service_name"] = self.rpc_service_name
            ad["provider_id"] = str(writer.instance_handle)
            ad["last_seen"] = int(time.time() * 1000)
            payload = {
                "agent_type": getattr(self, 'agent_type', 'AGENT'),
                "prefered_name": self.agent_name,
                "replier_guid": getattr(self, 'replier_guid', ''),  # RPC v2: for GUID-based targeting
            }
            ad["payload"] = json.dumps(payload)

            # Write and flush
            logger.debug("Writing unified agent advertisement...")
            writer.write(ad)
            writer.flush()
            logger.info("Successfully announced agent presence via GenesisAdvertisement")

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
