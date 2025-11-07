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
import threading
import traceback
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
import rti.connextdds as dds
import rti.rpc as rpc
from .genesis_app import GenesisApp
from .llm import ChatAgent, AnthropicChatAgent
from .utils import get_datamodel_path
from .utils.guid_utils import format_guid
from genesis_lib.advertisement_bus import AdvertisementBus
from .agent_communication import AgentCommunicationMixin
from .agent_classifier import AgentClassifier
from genesis_lib.memory import SimpleMemoryAdapter

# Get logger
logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS AND CONFIGURATION
# =============================================================================

class AgentCapabilities:
    """Constants for agent capability definitions."""
    DEFAULT_TYPE = "general"
    DEFAULT_CAPABILITIES = ["general_assistance"]
    DEFAULT_TAGS = ["general", "assistant"]
    DEFAULT_SPECIALIZATIONS = []
    DEFAULT_INTERACTION_PATTERNS = []
    DEFAULT_STRENGTHS = []
    DEFAULT_LIMITATIONS = []
    DEFAULT_PERFORMANCE_METRICS = {}

class AgentConfig:
    """Configuration constants for agent behavior."""
    # Timeout settings
    DEFAULT_REQUEST_TIMEOUT = 10.0
    DEFAULT_AGENT_WAIT_TIMEOUT = 30.0
    DEFAULT_AGENT_CALL_TIMEOUT = 30.0
    MCP_THREAD_JOIN_TIMEOUT = 5.0
    
    # Default agent type
    DEFAULT_AGENT_TYPE = "AGENT"
    
    # System prompts
    DEFAULT_GENERAL_SYSTEM_PROMPT = "You are a helpful assistant."
    DEFAULT_FUNCTION_SYSTEM_PROMPT = "You are a helpful assistant with access to tools."

class GenesisAgent(ABC):
    """Base class for all Genesis agents"""
    # registration_writer removed - now using unified Advertisement topic via AdvertisementBus

    def __init__(self, agent_name: str, base_service_name: str, 
                 agent_id: str = None,
                 domain_id: int = 0,
                 enable_agent_communication: bool = False, memory_adapter=None,
                 auto_run: bool = True, service_instance_tag: str = "",
                 classifier_llm=None, classifier_provider: str = "openai", classifier_model: str = "gpt-5-mini"):
        """
        Initialize the agent.
        
        Args:
            agent_name: Name of the agent (for display, identification)
            base_service_name: The fundamental type of service offered (e.g., "Chat", "ImageGeneration")
            agent_id: Optional UUID for the agent (if None, will generate one)
            domain_id: DDS domain ID (default 0)
            enable_agent_communication: Whether to enable agent-to-agent communication capabilities
            memory_adapter: Optional custom memory adapter for conversation history
            auto_run: Whether to automatically start the agent's run loop
            service_instance_tag: Optional tag for content filtering (e.g., "production", "staging", "v2")
                                 Used for migrations and A/B testing via content filtering, not topic names
            classifier_llm: Optional LLM instance for agent classification (AnthropicChatAgent, or similar).
                           If provided, this takes precedence over classifier_provider/classifier_model.
            classifier_provider: Provider name for classifier (default: "openai").
                                Set to None to auto-detect from available API keys.
            classifier_model: Model name for classifier (default: "gpt-5-mini").
                             Set to None to use provider's default classifier model.
        
        Note:
            RPC v2 uses unified topics with GUID-based targeting. All agents of the same
            base_service_name share the same DDS topics (e.g., rti/connext/genesis/rpc/OpenAIChatRequest).
            Individual agents are targeted using their unique replier_guid, not separate topic names.
            The optional service_instance_tag enables content filtering for migration scenarios.
        """
        logger.info(f"GenesisAgent {agent_name} STARTING initializing with agent_id {agent_id}, base_service_name: {base_service_name}, tag: {service_instance_tag}")
        self.agent_name = agent_name
        self.mcp_server = None  # Initialize MCP server to None
        
        # RPC v2: All instances share unified topics, targeted by GUID
        self.base_service_name = base_service_name
        self.service_instance_tag = service_instance_tag  # Optional tag for content filtering
        
        logger.info(f"RPC v2 service name: {self.base_service_name} (unified topics, tag: {service_instance_tag or 'none'})")

        # ===== DDS Infrastructure via Composition (Has-A Pattern) =====
        # 
        # We use composition (has-a) rather than inheritance (is-a) with GenesisApp because:
        #
        # 1. FLEXIBILITY: GenesisApp accepts an optional 'participant' argument, allowing
        #    multiple components to share a single DDS participant if needed (e.g., for
        #    testing or resource-constrained environments). With inheritance, each agent
        #    would BE a DDS application, making participant sharing impossible.
        #    Current usage: Each agent creates its own GenesisApp with its own participant,
        #    but the architecture supports sharing if needed in the future.
        #
        # 2. MULTIPLE COMPONENT TYPES: GenesisApp provides DDS infrastructure to different
        #    component types (GenesisAgent, GenesisInterface, GenesisReplier, etc.).
        #    These components are fundamentally different and can't all inherit from the
        #    same base class using single inheritance in Python.
        #
        # 3. SEPARATION OF CONCERNS: GenesisApp = "DDS infrastructure provider"
        #    (participant, publishers, subscribers, function registry).
        #    GenesisAgent = "LLM-powered request processor" (orchestration, tool routing).
        #    These are orthogonal concerns that compose well but shouldn't be in the
        #    same inheritance hierarchy.
        #
        # This follows the "favor composition over inheritance" principle - we delegate
        # DDS infrastructure concerns to GenesisApp rather than being both an infrastructure
        # provider AND a request processor simultaneously.
        logger.debug("===== DDS TRACE: Creating GenesisApp in GenesisAgent =====")
        self.app = GenesisApp(preferred_name=self.agent_name, agent_id=agent_id, domain_id=domain_id)
        logger.debug(f"===== DDS TRACE: GenesisApp created with agent_id {self.app.agent_id} on domain {domain_id} =====")
        logger.info(f"GenesisAgent {self.agent_name} initialized with app {self.app.agent_id} on domain {domain_id}")


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



        # Create replier with data available listener
        class RequestListener(dds.DynamicData.DataReaderListener):
            def __init__(self, agent):
                super().__init__()  # Call parent class __init__
                self.agent = agent
                
            def on_data_available(self, reader):
                logger.debug(f"RequestListener.on_data_available() called for {self.agent.agent_name}")
                
                samples = self.agent.replier.take_requests()
                logger.debug(f"RequestListener got {len(samples)} request samples")
                
                for request, info in samples:
                    if request is None or info.state.instance_state != dds.InstanceState.ALIVE:
                        logger.debug("Skipping invalid request sample")
                        continue
                    
                    # RPC v2: Filter requests based on target_service_guid and service_instance_tag
                    if not self._should_process_request(request):
                        continue
                    
                    logger.info(f"Received request: {request}")
                    
                    try:
                        asyncio.run_coroutine_threadsafe(
                            self._process_request(request, info), 
                            self.agent.loop
                        )
                    except Exception as e:
                        logger.error(f"Error creating request processing task: {e}")
                        logger.error(traceback.format_exc())
            
            def _should_process_request(self, request) -> bool:
                """
                Determine if this agent should process the given request based on
                RPC v2 targeting (target_service_guid) and optional tag filtering.
                
                Returns True if:
                - Request is broadcast (empty target_guid), OR
                - Request is targeted to this agent's replier_guid
                AND
                - Service instance tag matches (if tags are being used)
                """
                try:
                    target_guid = request.get_string("target_service_guid")
                    service_tag = request.get_string("service_instance_tag")
                    
                    # Check GUID targeting
                    is_broadcast = not target_guid
                    is_for_us = (is_broadcast or target_guid == self.agent.replier_guid)
                    
                    if not is_for_us:
                        logger.debug(
                            f"Skipping request targeted to {target_guid}, "
                            f"we are {self.agent.replier_guid}"
                        )
                        return False
                    
                    # Check service instance tag if configured
                    if service_tag and hasattr(self.agent, 'service_instance_tag'):
                        if service_tag != self.agent.service_instance_tag:
                            logger.debug(
                                f"Skipping request with tag '{service_tag}', "
                                f"we require '{self.agent.service_instance_tag}'"
                            )
                            return False
                    
                    logger.debug(
                        f"Accepting {'broadcast' if is_broadcast else 'targeted'} request "
                        f"(tag: {service_tag or 'none'})"
                    )
                    return True
                    
                except Exception as e:
                    # If RPC v2 fields are missing, accept the request
                    # (allows graceful handling of legacy or malformed requests)
                    logger.warning(
                        f"Could not read RPC v2 targeting fields, accepting request: {e}"
                    )
                    return True
                        
            async def _process_request(self, request, info):
                """
                Process an incoming DDS request and send a reply.
                
                This internal method:
                1. Converts the DDS request to a Python dict
                2. Calls the agent's process_request() method
                3. Converts the reply dict back to DDS format
                4. Sends the reply via the replier
                
                Args:
                    request: DDS DynamicData request object
                    info: DDS SampleInfo for the request
                    
                Note: Errors are caught and returned as error replies rather than
                propagating, ensuring the caller always gets a response.
                """
                logger.debug(f"Processing request for {self.agent.agent_name}")
                
                try:
                    # Convert DDS request to dict
                    request_dict = self._convert_request_to_dict(request)
                    
                    # Process the request through the concrete agent implementation
                    reply_data = await self.agent.process_request(request_dict)
                    
                    # Create and send success reply
                    reply = self._create_reply(reply_data, request_dict)
                    self.agent.replier.send_reply(reply, info)
                    logger.info(f"Sent reply: {reply}")
                    
                except Exception as e:
                    logger.error(f"Error processing request: {e}")
                    logger.error(traceback.format_exc())
                    
                    # Create and send error reply
                    reply = self._create_error_reply(str(e))
                    self.agent.replier.send_reply(reply, info)
            
            def _convert_request_to_dict(self, request) -> Dict[str, Any]:
                """
                Convert a DDS DynamicData request to a Python dictionary.
                
                Raises:
                    TypeError: If request type cannot be introspected
                    ValueError: If member conversion fails
                """
                if not hasattr(self.agent.request_type, 'members') or \
                   not callable(self.agent.request_type.members):
                    raise TypeError(
                        "Request type does not support member introspection. "
                        "Cannot convert DDS request to dict."
                    )
                
                request_dict = {}
                for member in self.agent.request_type.members():
                    member_name = member.name
                    try:
                        # Use appropriate getter based on type
                        if member.type.kind == dds.TypeKind.STRING_TYPE:
                            request_dict[member_name] = request.get_string(member_name)
                        elif member.type.kind == dds.TypeKind.INT32_TYPE:
                            request_dict[member_name] = request.get_int32(member_name)
                        elif member.type.kind == dds.TypeKind.BOOLEAN_TYPE:
                            request_dict[member_name] = request.get_boolean(member_name)
                        elif member.type.kind == dds.TypeKind.INT64_TYPE:
                            request_dict[member_name] = request.get_int64(member_name)
                        else:
                            logger.warning(
                                f"Unsupported type {member.type.kind} for member '{member_name}', "
                                f"attempting generic access"
                            )
                            request_dict[member_name] = request[member_name]
                    except Exception as e:
                        logger.warning(
                            f"Failed to convert member '{member_name}': {e}. "
                            f"Setting to None."
                        )
                        request_dict[member_name] = None
                
                return request_dict
            
            def _create_reply(self, reply_data: Dict[str, Any], 
                             request_dict: Dict[str, Any]) -> dds.DynamicData:
                """
                Create a DDS reply from the agent's response data.
                
                Args:
                    reply_data: Dict returned from process_request()
                    request_dict: Original request dict (for echoing tags)
                    
                Returns:
                    DDS DynamicData reply object
                """
                reply = dds.DynamicData(self.agent.reply_type)
                
                # Standard reply fields
                reply["message"] = str(reply_data.get("message", ""))
                reply["status"] = int(reply_data.get("status", 0))  # 0 = success
                reply["conversation_id"] = str(reply_data.get("conversation_id", ""))
                
                # RPC v2 fields
                reply["replier_service_guid"] = self.agent.replier_guid
                reply["service_instance_tag"] = request_dict.get("service_instance_tag", "")
                
                return reply
            
            def _create_error_reply(self, error_message: str) -> dds.DynamicData:
                """
                Create a DDS error reply.
                
                Args:
                    error_message: Human-readable error description
                    
                Returns:
                    DDS DynamicData reply object with error status
                """
                reply = dds.DynamicData(self.agent.reply_type)
                reply["message"] = f"Error: {error_message}"
                reply["status"] = 1  # 1 = error
                reply["conversation_id"] = ""
                reply["replier_service_guid"] = self.agent.replier_guid
                reply["service_instance_tag"] = ""
                return reply
        
        # Create replier with listener using unified RPC v2 naming
        self.replier = rpc.Replier(
            request_type=self.request_type,
            reply_type=self.reply_type,
            participant=self.app.participant,
            service_name=f"rti/connext/genesis/rpc/{self.base_service_name}"
        )
        
        # Store replier GUID for RPC v2 targeted requests
        self.replier_guid = format_guid(self.replier.reply_datawriter.instance_handle)
        logger.info(f"Agent {self.agent_name} replier_guid: {self.replier_guid}")
        
        # Set listener on replier's DataReader with status mask for data available
        self.request_listener = RequestListener(self)
        mask = dds.StatusMask.DATA_AVAILABLE
        self.replier.request_datareader.set_listener(self.request_listener, mask)
        
        # Initialize internal tools cache for @genesis_tool decorated methods
        self.internal_tools_cache = {}
        
        # Initialize agent-to-agent communication components
        self.enable_agent_communication = enable_agent_communication
        self.agent_communication = None
        self.agent_classifier = None
        self.memory = memory_adapter or SimpleMemoryAdapter()
        
        if enable_agent_communication:
            logger.debug(f"Agent communication enabled for {self.agent_name}")
            self._setup_agent_communication()
            
            # Initialize agent classifier for intelligent request routing
            # Pass provider/model config or custom LLM - AgentClassifier handles LLM creation
            self.agent_classifier = AgentClassifier(
                provider=classifier_provider,
                model=classifier_model,
                custom_llm=classifier_llm
            )
        else:
            logger.debug(f"Agent communication disabled for {self.agent_name}")

        # Auto-start the agent's run loop if requested and an event loop is available
        # This allows the agent to begin listening for requests immediately
        if self._auto_run_requested:
            try:
                running_loop = asyncio.get_running_loop()
                # Schedule run() as a background task (idempotent - won't start twice)
                self._run_task = running_loop.create_task(self.run())
                logger.info(f"Auto-started run() for {self.agent_name} in background task")
            except RuntimeError:
                # No event loop running yet - common in synchronous contexts
                # User must call `await agent.run()` explicitly
                logger.debug("No running event loop detected; deferring agent.run() until explicitly called")

    def enable_mcp(self, 
                   port: int = 8000, 
                   toolname: str = "ask_genesis_agent",
                   tooldesc: str = "Ask the Genesis agent a question and get a response") -> None:
        """
        Enable Model Context Protocol (MCP) server for this agent.
        
        MCP allows external applications (like IDEs, chat applications, or other tools)
        to interact with this agent through a standardized protocol. Once enabled, the
        agent will expose its `process_message` method as an MCP tool that can be called
        by MCP clients.
        
        The MCP server runs in a background daemon thread and uses streamable-http
        transport for communication. The server will automatically shut down when the
        main application exits.
        
        Args:
            port: Port number for the MCP server (default: 8000)
            toolname: Name of the exposed MCP tool (default: "ask_genesis_agent")
            tooldesc: Description of the MCP tool for clients (default: "Ask the Genesis agent a question and get a response")
        
        Raises:
            ImportError: If the mcp package is not installed (install with: pip install mcp)
            RuntimeError: If the server fails to start or port is already in use
        
        Example:
            ```python
            agent = HelloWorldAgent()
            agent.enable_mcp(port=8000)
            # Agent is now accessible via MCP at http://localhost:8000
            ```
        
        Note:
            - Calling this method multiple times is safe - it will only create one server
            - The server runs as a daemon thread and will not prevent application shutdown
            - Requires the 'mcp' package: pip install mcp
        """
        try:
            from mcp.server.fastmcp import FastMCP
        except ImportError:
            raise ImportError(
                "FastMCP module not found. Install with: pip install mcp\n"
                "MCP (Model Context Protocol) enables external tools to interact with this agent.\n"
                "See: https://github.com/modelcontextprotocol"
            )
        
        # Only create server if not already initialized
        if not self.mcp_server:
            try:
                self.mcp_server = FastMCP(self.agent_name, port=port)
                self.mcp_server.add_tool(
                    self.process_message,
                    name=toolname,
                    description=tooldesc
                )
                
                # Start server in daemon thread (auto-terminates with main process)
                self._mcp_thread = threading.Thread(
                    target=self.mcp_server.run, 
                    kwargs={"transport": "streamable-http"}, 
                    daemon=True
                )
                self._mcp_thread.start()
                
                logger.info(
                    f"MCP server enabled for '{self.agent_name}' on port {port} "
                    f"with tool '{toolname}'"
                )
            except Exception as e:
                logger.error(f"Failed to start MCP server: {e}")
                self.mcp_server = None
                raise RuntimeError(f"Failed to start MCP server on port {port}: {e}")
        else:
            logger.debug(f"MCP server already enabled for '{self.agent_name}'")

    def _setup_agent_communication(self):
        """
        Initialize agent-to-agent communication capabilities.
        
        Sets up:
        1. Communication mixin wrapper
        2. RPC types for agent-to-agent messaging
        3. Agent discovery (listening for other agents)
        4. Agent RPC service (handling incoming agent requests)
        5. Capability publishing (advertising this agent's skills)
        """
        logger.info(f"Setting up agent-to-agent communication for {self.agent_name}")
        
        try:
            # Create communication wrapper that shares our DDS infrastructure
            self.agent_communication = self._create_agent_communication_wrapper()
            
            # Execute setup steps in order - each returns boolean success
            setup_steps = [
                ("RPC types", self.agent_communication._initialize_agent_rpc_types),
                ("agent discovery", self.agent_communication._setup_agent_discovery),
                ("agent RPC service", self.agent_communication._setup_agent_rpc_service),
                ("capability publishing", self.agent_communication._setup_agent_capability_publishing),
            ]
            
            for step_name, setup_func in setup_steps:
                if not setup_func():
                    logger.error(f"Failed to set up {step_name} - agent communication disabled")
                    self.agent_communication = None
                    return
                logger.info(f"✓ {step_name.capitalize()} setup completed")
            
            # Publish initial capabilities now that everything is set up
            agent_capabilities = self.get_agent_capabilities()
            logger.debug(f"Publishing initial capabilities: {agent_capabilities}")
            self.agent_communication.publish_agent_capability(agent_capabilities)
            
            logger.info(f"✓ Agent-to-agent communication fully enabled for {self.agent_name}")
            
        except Exception as e:
            logger.error(f"Failed to set up agent communication: {e}")
            logger.error(traceback.format_exc())
            self.agent_communication = None
    
    def _create_agent_communication_wrapper(self):
        """
        Create a communication mixin wrapper that shares our DDS infrastructure.
        
        This wrapper allows AgentCommunicationMixin to access our DDS participant,
        agent metadata, and delegate request handling back to us.
        
        Returns:
            AgentCommunicationWrapper instance
        """
        class AgentCommunicationWrapper(AgentCommunicationMixin):
            """Wrapper that connects AgentCommunicationMixin to parent agent."""
            
            def __init__(wrapper_self, parent_agent):
                super().__init__()
                wrapper_self.parent_agent = parent_agent
                
                # Share DDS infrastructure from parent
                wrapper_self.app = parent_agent.app
                wrapper_self.base_service_name = parent_agent.base_service_name
                wrapper_self.agent_name = parent_agent.agent_name
                wrapper_self.agent_type = getattr(parent_agent, 'agent_type', AgentConfig.DEFAULT_AGENT_TYPE)
                wrapper_self.description = getattr(parent_agent, 'description', f'Agent {parent_agent.agent_name}')
            
            async def process_agent_request(wrapper_self, request):
                """Delegate agent requests to parent's handler."""
                return await wrapper_self.parent_agent.process_agent_request(request)
            
            def get_agent_capabilities(wrapper_self):
                """Delegate capability queries to parent."""
                return wrapper_self.parent_agent.get_agent_capabilities()
        
        return AgentCommunicationWrapper(self)

    # =============================================================================
    # AGENT COMMUNICATION AND REQUEST ROUTING
    # =============================================================================
    # Methods for agent-to-agent communication and intelligent request routing
    
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
    
    # ========================================================================
    # Agent-to-Agent Communication API
    # ========================================================================
    # 
    # These methods provide a clean public API for agent-to-agent communication
    # by delegating to AgentCommunicationMixin when enabled. This delegation
    # pattern offers several benefits:
    #
    # 1. GRACEFUL DEGRADATION: Methods return sensible defaults (empty lists, None)
    #    when agent communication is disabled, avoiding AttributeErrors.
    #
    # 2. TYPE SAFETY: Each method has explicit type hints, enabling IDE 
    #    autocomplete and static type checking.
    #
    # 3. DISCOVERABILITY: Methods appear on GenesisAgent, making the API easy
    #    to explore via dir() or IDE inspection.
    #
    # 4. DOCUMENTATION: Each method can have its own docstring explaining
    #    its specific purpose and return values.
    #
    # 5. STABLE API: If AgentCommunicationMixin changes internally, these
    #    wrapper methods provide a stable interface for users.
    #
    # The alternative approaches (e.g., __getattr__ magic, direct exposure)
    # sacrifice type safety and clarity for reduced boilerplate. For RTI's
    # use case where API stability and discoverability are critical, the
    # explicit delegation pattern is preferred despite the repetition.
    #
    # Design note: These are intentionally simple one-liners rather than using
    # a helper method, as the pattern is immediately clear to readers and
    # optimizes for readability over DRY (Don't Repeat Yourself).
    # ========================================================================
    
    async def send_agent_request(self, target_agent_id: str, message: str,
                               conversation_id: Optional[str] = None,
                               timeout_seconds: float = AgentConfig.DEFAULT_REQUEST_TIMEOUT) -> Optional[Dict[str, Any]]:
        """
        Send a request to another agent.
        
        Args:
            target_agent_id: UUID of the target agent
            message: Message to send to the agent
            conversation_id: Optional conversation tracking ID
            timeout_seconds: Request timeout in seconds
            
        Returns:
            Response dict from the agent, or None if communication disabled or request failed
        """
        return await self.agent_communication.send_agent_request(
            target_agent_id, message, conversation_id, timeout_seconds
        ) if self.agent_communication else None
    
    async def wait_for_agent(self, agent_id: str, timeout_seconds: float = AgentConfig.DEFAULT_AGENT_WAIT_TIMEOUT) -> bool:
        """
        Wait for a specific agent to be discovered.
        
        Args:
            agent_id: UUID of the agent to wait for
            timeout_seconds: How long to wait before giving up
            
        Returns:
            True if agent was discovered, False otherwise
        """
        return await self.agent_communication.wait_for_agent(agent_id, timeout_seconds) \
               if self.agent_communication else False
    
    def get_discovered_agents(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all currently discovered agents.
        
        Returns:
            Dict mapping agent_id to agent info (capabilities, specializations, etc.)
        """
        return self.agent_communication.get_discovered_agents() \
               if self.agent_communication else {}
    
    # --- Agent Discovery by Capability/Specialization ---
    
    def find_agents_by_capability(self, capability: str) -> List[str]:
        """
        Find agents that advertise a specific capability.
        
        Args:
            capability: Capability name to search for (e.g., "weather", "calculation")
            
        Returns:
            List of agent IDs that have this capability
        """
        return self.agent_communication.find_agents_by_capability(capability) \
               if self.agent_communication else []
    
    def find_agents_by_specialization(self, domain: str) -> List[str]:
        """
        Find agents with expertise in a specific domain.
        
        Args:
            domain: Domain/specialization to search for (e.g., "finance", "medical")
            
        Returns:
            List of agent IDs specialized in this domain
        """
        return self.agent_communication.find_agents_by_specialization(domain) \
               if self.agent_communication else []
    
    def find_general_agents(self) -> List[str]:
        """
        Find agents that can handle general requests.
        
        Returns:
            List of agent IDs marked as general-purpose
        """
        return self.agent_communication.find_general_agents() \
               if self.agent_communication else []
    
    def find_specialized_agents(self) -> List[str]:
        """
        Find agents that are specialized (not general-purpose).
        
        Returns:
            List of agent IDs marked as specialized
        """
        return self.agent_communication.find_specialized_agents() \
               if self.agent_communication else []
    
    async def get_best_agent_for_request(self, request: str) -> Optional[str]:
        """
        Use the classifier to find the best agent for a specific request.
        
        Uses semantic LLM classification to intelligently route requests
        based on agent capabilities, specializations, and request intent.
        
        Args:
            request: The request text to classify
            
        Returns:
            Agent ID of the best match, or None if no suitable agent found
        """
        return await self.agent_communication.get_best_agent_for_request(request) \
               if self.agent_communication else None
    
    # --- Agent Discovery by Metadata ---
    
    def get_agents_by_performance_metric(self, metric_name: str, 
                                        min_value: Optional[float] = None, 
                                        max_value: Optional[float] = None) -> List[str]:
        """
        Find agents based on performance metrics.
        
        Args:
            metric_name: Name of the metric (e.g., "response_time", "accuracy")
            min_value: Optional minimum value for the metric
            max_value: Optional maximum value for the metric
            
        Returns:
            List of agent IDs matching the metric criteria
        """
        return self.agent_communication.get_agents_by_performance_metric(
            metric_name, min_value, max_value
        ) if self.agent_communication else []
    
    def get_agent_info_by_capability(self, capability: str) -> List[Dict[str, Any]]:
        """
        Get full agent information for agents with a specific capability.
        
        Args:
            capability: Capability name to search for
            
        Returns:
            List of agent info dicts (not just IDs) for matching agents
        """
        return self.agent_communication.get_agent_info_by_capability(capability) \
               if self.agent_communication else []
    
    def get_agents_by_model_type(self, model_type: str) -> List[str]:
        """
        Find agents using a specific model type.
        
        Args:
            model_type: LLM model type (e.g., "gpt-4", "claude-3")
            
        Returns:
            List of agent IDs using this model type
        """
        return self.agent_communication.get_agents_by_model_type(model_type) \
               if self.agent_communication else []
    
    # --- Intelligent Request Routing ---
    
    async def route_request_to_best_agent(self, request_message: str, 
                                        conversation_id: Optional[str] = None,
                                        timeout_seconds: float = AgentConfig.DEFAULT_REQUEST_TIMEOUT) -> Optional[Dict[str, Any]]:
        """
        Intelligently route a request to the best available agent.
        
        Uses the agent classifier to determine which agent is best suited
        to handle the request, then forwards the request accordingly.
        
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
        
        discovered_agents = self.get_discovered_agents()
        if not discovered_agents:
            logger.info("No agents discovered for routing")
            return None
        
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
    
    # ========================================================================
    # End of Agent-to-Agent Communication API
    # ========================================================================
    
    # ========================================================================
    # Agent Capability Advertisement
    # ========================================================================
    # These methods define and expose THIS agent's capabilities for discovery
    # by other agents. This is separate from discovering OTHER agents.
    # ========================================================================
    
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
    
    # ========================================================================
    # Agent Capability System - Intelligent Metadata Generation
    # ========================================================================
    #
    # ARCHITECTURAL OVERVIEW:
    # ======================
    #
    # The Genesis capability system implements a three-tier intelligent approach
    # that balances user control with automated intelligence:
    #
    # 1. USER-DEFINED CAPABILITIES (Highest Priority)
    #    - Provides consistency across implementations
    #    - Enables domain-specific terminology and branding
    #    - Supports custom performance characteristics
    #    - Multiple definition patterns: method override, instance attr, class attr
    #
    # 2. MODEL-BASED GENERATION (Intelligent Fallback)
    #    - Uses agent's own model to analyze its capabilities
    #    - Generates rich metadata from @genesis_tool methods
    #    - Provides domain specialization detection
    #    - Creates performance metrics and interaction patterns
    #
    # 3. HEURISTIC GENERATION (Final Fallback)
    #    - Simple keyword extraction from method names
    #    - Basic domain hint matching
    #    - Ensures system always works
    #    - Provides sensible defaults
    #
    # DESIGN PRINCIPLES:
    # ==================
    # - Backward Compatibility: Existing agents work unchanged
    # - Progressive Enhancement: Optional rich metadata when needed
    # - Graceful Degradation: Always provides working capabilities
    # - User Control: Override any level when desired
    # - Intelligent Defaults: Model-based analysis when available
    #
    # ========================================================================
    # End of Agent Capability Advertisement
    # ========================================================================
    
    def _auto_generate_capabilities(self) -> Dict[str, Any]:
        """
        Auto-generate capability metadata with intelligent fallback strategy.
        
        This method implements a three-tier capability generation system that balances
        user control with intelligent automation:
        
        ARCHITECTURE RATIONALE:
        =====================
        
        1. **User-Defined (Highest Priority)**: 
           - Provides consistency across implementations
           - Enables domain-specific terminology and branding
           - Allows performance characteristics to be known ahead of time
           - Supports custom interaction patterns and use cases
        
        2. **Model-Based Generation (Intelligent Fallback)**:
           - Uses the agent's own model to analyze its capabilities
           - Generates rich, contextual metadata from @genesis_tool methods
           - Provides domain specialization detection
           - Creates performance metrics and interaction patterns
           - Falls back gracefully if model unavailable
        
        3. **Heuristic Generation (Final Fallback)**:
           - Simple keyword extraction from method names and descriptions
           - Basic domain hint matching (weather, finance, math, etc.)
           - Ensures system always works even without model access
           - Provides sensible defaults for all required fields
        
        DESIGN PRINCIPLES:
        ==================
        
        - **Backward Compatibility**: Existing agents work unchanged
        - **Progressive Enhancement**: Optional rich metadata when needed
        - **Graceful Degradation**: Always provides working capabilities
        - **User Control**: Override any level when desired
        - **Intelligent Defaults**: Model-based analysis when available
        
        Returns:
            Dict containing comprehensive agent capability metadata
        """
        # First, check for user-defined capabilities
        user_capabilities = self._get_user_defined_capabilities()
        if user_capabilities:
            logger.debug("Using user-defined capabilities")
            return user_capabilities
        
        # Second, try model-based generation
        try:
            model_capabilities = self._generate_capabilities_with_model()
            if model_capabilities:
                logger.debug("Using model-generated capabilities")
                return model_capabilities
        except Exception as e:
            logger.debug(f"Model-based capability generation failed: {e}")
        
        # Fallback to heuristic approach
        logger.debug("Using heuristic capability generation")
        return self._generate_capabilities_heuristic()
    
    def _get_user_defined_capabilities(self) -> Optional[Dict[str, Any]]:
        """
        Check for user-defined capabilities using multiple discovery patterns.
        
        This method implements a comprehensive capability discovery system that
        supports multiple user definition patterns for maximum flexibility:
        
        DISCOVERY PATTERNS (in priority order):
        =====================================
        
        1. **Method Override Pattern**:
           ```python
           def get_agent_capabilities(self) -> dict:
               return {'agent_type': 'specialist', ...}
           ```
           - Most explicit and flexible
           - Supports dynamic logic and state-based capabilities
           - Enables complex capability computation
        
        2. **Instance Attribute Pattern**:
           ```python
           self.capabilities = {'agent_type': 'specialist', ...}
           # or
           self.capabilities = lambda: {'agent_type': 'specialist', ...}
           ```
           - Simple and direct
           - Supports both static dicts and callable functions
           - Good for runtime capability updates
        
        3. **Class Attribute Pattern**:
           ```python
           class MyAgent(GenesisAgent):
               CAPABILITIES = {'agent_type': 'specialist', ...}
           ```
           - Static, reusable definitions
           - Perfect for agent templates and base classes
           - Enables capability inheritance
        
        ARCHITECTURE BENEFITS:
        =====================
        
        - **Multiple Interfaces**: Supports different user preferences and use cases
        - **Graceful Fallback**: Each pattern checked independently
        - **Error Isolation**: Failures in one pattern don't affect others
        - **Validation**: All patterns go through same validation pipeline
        - **Consistency**: Unified capability schema regardless of definition method
        
        Returns:
            Validated user-defined capabilities dict or None if not defined
        """
        # Check if user overrode get_agent_capabilities
        if hasattr(self, 'get_agent_capabilities') and self.get_agent_capabilities.__func__ != GenesisAgent.get_agent_capabilities:
            try:
                user_caps = self.get_agent_capabilities()
                if user_caps and isinstance(user_caps, dict):
                    return self._validate_user_capabilities(user_caps)
            except Exception as e:
                logger.warning(f"User-defined get_agent_capabilities() failed: {e}")
        
        # Check for self.capabilities attribute
        if hasattr(self, 'capabilities') and self.capabilities:
            try:
                if isinstance(self.capabilities, dict):
                    return self._validate_user_capabilities(self.capabilities)
                elif callable(self.capabilities):
                    user_caps = self.capabilities()
                    if user_caps and isinstance(user_caps, dict):
                        return self._validate_user_capabilities(user_caps)
            except Exception as e:
                logger.warning(f"User-defined capabilities attribute failed: {e}")
        
        # Check for class-level capabilities
        if hasattr(self.__class__, 'CAPABILITIES') and self.__class__.CAPABILITIES:
            try:
                if isinstance(self.__class__.CAPABILITIES, dict):
                    return self._validate_user_capabilities(self.__class__.CAPABILITIES)
            except Exception as e:
                logger.warning(f"Class-level CAPABILITIES failed: {e}")
        
        return None
    
    def _validate_user_capabilities(self, capabilities: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize user-defined capabilities.
        
        Ensures all required fields exist and are properly formatted.
        """
        # Define the complete capability schema
        required_fields = {
            'agent_type': 'general',
            'specializations': [],
            'capabilities': ['general_assistance'],
            'classification_tags': ['general', 'assistant'],
            'model_info': {},
            'default_capable': True,
            'performance_metrics': {},
            'interaction_patterns': [],
            'strengths': [],
            'limitations': []
        }
        
        # Start with defaults and merge user capabilities
        result = required_fields.copy()
        result.update(capabilities)
        
        # Validate and clean each field
        result['agent_type'] = str(result.get('agent_type', 'general'))
        
        # Ensure lists are actually lists
        list_fields = ['specializations', 'capabilities', 'classification_tags', 
                      'interaction_patterns', 'strengths', 'limitations']
        for field in list_fields:
            if not isinstance(result[field], list):
                result[field] = []
        
        # Ensure model_info is a dict
        if not isinstance(result['model_info'], dict):
            result['model_info'] = {}
        
        # Add model info from agent if available
        if hasattr(self, 'model_name') and self.model_name:
            result['model_info']['llm_model'] = self.model_name
            result['model_info']['auto_discovery'] = bool(self._get_tool_methods())
        
        # Ensure boolean fields are boolean
        result['default_capable'] = bool(result['default_capable'])
        
        # Ensure performance_metrics is a dict
        if not isinstance(result['performance_metrics'], dict):
            result['performance_metrics'] = {}
        
        logger.debug(f"Validated user capabilities: {len(result.get('capabilities', []))} capabilities, {len(result.get('specializations', []))} specializations")
        
        return result

    # =============================================================================
    # TOOL MANAGEMENT AND EXECUTION
    # =============================================================================
    # Methods for discovering, managing, and executing tools (external functions,
    # agent tools, and internal @genesis_tool methods)
    
    def _get_tool_methods(self) -> List[Dict[str, Any]]:
        """Get list of @genesis_tool methods for capability analysis."""
        tool_methods = []
        for attr_name in dir(self):
            if attr_name.startswith('_'):
                continue
            attr = getattr(self, attr_name)
            if callable(attr) and hasattr(attr, '__is_genesis_tool__'):
                meta = getattr(attr, '__genesis_tool_meta__', {}) or {}
                if meta:
                    tool_methods.append(meta)
        return tool_methods
    
    def _generate_capabilities_with_model(self) -> Optional[Dict[str, Any]]:
        """
        Use the agent's own model to generate rich, accurate capability metadata.
        
        This method implements intelligent capability analysis by leveraging the
        agent's own LLM to understand and describe its capabilities. This approach
        provides several architectural advantages:
        
        INTELLIGENT ANALYSIS BENEFITS:
        =============================
        
        1. **Contextual Understanding**: Model understands the agent's tools and methods
        2. **Domain Specialization**: Automatically detects weather, finance, math, etc.
        3. **Rich Metadata**: Generates performance metrics, interaction patterns
        4. **Accurate Classification**: Better agent type and specialization detection
        5. **Self-Describing**: Agent uses its own intelligence to describe itself
        
        ANALYSIS PROCESS:
        =================
        
        1. **Agent Introspection**: Collects @genesis_tool methods, class info, attributes
        2. **Structured Prompting**: Creates focused analysis prompt for the model
        3. **Model Analysis**: Uses agent's model to analyze its own capabilities
        4. **Response Parsing**: Extracts and validates JSON capability metadata
        5. **Schema Validation**: Ensures all required fields with proper types
        
        FALLBACK BEHAVIOR:
        ==================
        
        - Returns None if model unavailable (graceful degradation)
        - Returns None if model call fails (error isolation)
        - Returns None if response parsing fails (robust validation)
        - System automatically falls back to heuristic generation
        
        Returns:
            Rich capability metadata dict or None if model analysis fails
        """
        try:
            # Collect agent information for model analysis
            agent_info = self._collect_agent_info_for_analysis()
            
            # Create a focused prompt for capability analysis
            analysis_prompt = self._create_capability_analysis_prompt(agent_info)
            
            # Use the model to analyze capabilities
            messages = [
                {"role": "system", "content": "You are an expert at analyzing AI agent capabilities and generating structured metadata."},
                {"role": "user", "content": analysis_prompt}
            ]
            
            # Call the model (this will use the agent's own model)
            response = asyncio.run(self._call_llm(messages, tools=None, tool_choice="none"))
            text_response = self._extract_text_response(response)
            
            # Parse the model's response into structured capabilities
            capabilities = self._parse_model_capability_response(text_response, agent_info)
            
            if capabilities:
                logger.debug("Successfully generated capabilities using model")
                return capabilities
                
        except Exception as e:
            logger.debug(f"Model-based capability generation failed: {e}")
        
        return None
    
    def _collect_agent_info_for_analysis(self) -> Dict[str, Any]:
        """Collect comprehensive agent information for model analysis."""
        agent_info = {
            'class_name': self.__class__.__name__,
            'module_name': self.__class__.__module__,
            'agent_name': getattr(self, 'agent_name', 'Unknown'),
            'base_service_name': getattr(self, 'base_service_name', 'Unknown'),
            'model_name': getattr(self, 'model_name', None),
            'tools': [],
            'methods': [],
            'attributes': {}
        }
        
        # Collect @genesis_tool methods
        for attr_name in dir(self):
            if attr_name.startswith('_'):
                continue
            attr = getattr(self, attr_name)
            if callable(attr) and hasattr(attr, '__is_genesis_tool__'):
                meta = getattr(attr, '__genesis_tool_meta__', {}) or {}
                if meta:
                    agent_info['tools'].append({
                        'name': meta.get('function_name', attr_name),
                        'description': meta.get('description', ''),
                        'operation_type': meta.get('operation_type', ''),
                        'parameters': meta.get('parameters', {}),
                        'method_name': attr_name
                    })
        
        # Collect other public methods (non-tool)
        for attr_name in dir(self):
            if attr_name.startswith('_'):
                continue
            attr = getattr(self, attr_name)
            if callable(attr) and not hasattr(attr, '__is_genesis_tool__'):
                if attr_name not in ['process_request', 'get_agent_capabilities', '_auto_generate_capabilities']:
                    agent_info['methods'].append({
                        'name': attr_name,
                        'docstring': getattr(attr, '__doc__', '') or ''
                    })
        
        # Collect relevant attributes
        relevant_attrs = ['agent_name', 'base_service_name', 'model_name', 'system_prompt']
        for attr_name in relevant_attrs:
            if hasattr(self, attr_name):
                value = getattr(self, attr_name)
                if value is not None:
                    agent_info['attributes'][attr_name] = str(value)
        
        return agent_info
    
    def _create_capability_analysis_prompt(self, agent_info: Dict[str, Any]) -> str:
        """Create a focused prompt for the model to analyze agent capabilities."""
        tools_text = ""
        if agent_info['tools']:
            tools_text = "\n\nAvailable Tools:\n"
            for tool in agent_info['tools']:
                tools_text += f"- {tool['name']}: {tool['description']}\n"
                if tool['operation_type']:
                    tools_text += f"  Type: {tool['operation_type']}\n"
                if tool['parameters']:
                    tools_text += f"  Parameters: {tool['parameters']}\n"
        
        methods_text = ""
        if agent_info['methods']:
            methods_text = "\n\nOther Methods:\n"
            for method in agent_info['methods']:
                methods_text += f"- {method['name']}: {method['docstring'][:100]}...\n"
        
        attributes_text = ""
        if agent_info['attributes']:
            attributes_text = "\n\nAgent Attributes:\n"
            for key, value in agent_info['attributes'].items():
                attributes_text += f"- {key}: {value}\n"
        
        return f"""Analyze this AI agent and generate comprehensive capability metadata.

Agent Information:
- Class: {agent_info['class_name']}
- Name: {agent_info['agent_name']}
- Service: {agent_info['base_service_name']}
- Model: {agent_info['model_name']}{tools_text}{methods_text}{attributes_text}

Please analyze this agent and provide a JSON response with the following structure:

{{
    "agent_type": "string (e.g., 'specialist', 'general', 'tool_agent', 'conversational')",
    "specializations": ["list of domain specializations like 'weather', 'finance', 'math', etc."],
    "capabilities": ["list of specific capabilities the agent can perform"],
    "classification_tags": ["list of tags for categorization and discovery"],
    "model_info": {{
        "llm_model": "model name if available",
        "auto_discovery": true/false,
        "reasoning_capability": "basic|intermediate|advanced"
    }},
    "default_capable": true/false,
    "performance_metrics": {{
        "estimated_response_time": "fast|medium|slow",
        "complexity_handling": "simple|moderate|complex",
        "domain_expertise": "general|specialized|expert"
    }},
    "interaction_patterns": ["list of how this agent typically interacts"],
    "strengths": ["list of key strengths"],
    "limitations": ["list of known limitations"]
}}

Focus on:
1. What domains/specializations this agent excels in
2. What specific tasks it can perform well
3. How it should be categorized for discovery
4. What its interaction patterns are
5. What its strengths and limitations are

Be specific and accurate based on the actual tools and methods available."""
    
    def _parse_model_capability_response(self, response_text: str, agent_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse the model's response into structured capability metadata."""
        try:
            import json
            import re
            
            # Extract JSON from response (handle cases where model adds extra text)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                capabilities = json.loads(json_str)
                
                # Validate and clean the response
                return self._validate_and_clean_capabilities(capabilities, agent_info)
            
        except Exception as e:
            logger.debug(f"Failed to parse model capability response: {e}")
        
        return None
    
    def _validate_and_clean_capabilities(self, capabilities: Dict[str, Any], agent_info: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean the model-generated capabilities."""
        # Ensure required fields exist with defaults
        result = {
            'agent_type': capabilities.get('agent_type', 'general'),
            'specializations': capabilities.get('specializations', []),
            'capabilities': capabilities.get('capabilities', ['general_assistance']),
            'classification_tags': capabilities.get('classification_tags', ['general', 'assistant']),
            'model_info': capabilities.get('model_info', {}),
            'default_capable': capabilities.get('default_capable', True),
            'performance_metrics': capabilities.get('performance_metrics', {}),
            'interaction_patterns': capabilities.get('interaction_patterns', []),
            'strengths': capabilities.get('strengths', []),
            'limitations': capabilities.get('limitations', [])
        }
        
        # Ensure model_info has the right structure
        if not isinstance(result['model_info'], dict):
            result['model_info'] = {}
        
        # Add model info from agent if available
        if agent_info.get('model_name'):
            result['model_info']['llm_model'] = agent_info['model_name']
            result['model_info']['auto_discovery'] = bool(agent_info.get('tools'))
        
        # Ensure lists are actually lists
        for key in ['specializations', 'capabilities', 'classification_tags', 'interaction_patterns', 'strengths', 'limitations']:
            if not isinstance(result[key], list):
                result[key] = []
        
        # Ensure boolean fields are boolean
        result['default_capable'] = bool(result['default_capable'])
        
        return result
    
    def _generate_capabilities_heuristic(self) -> Dict[str, Any]:
        """
        Fallback heuristic-based capability generation.
        This is the original implementation for when model-based generation fails.
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
                'agent_type': AgentCapabilities.DEFAULT_TYPE,
                'specializations': specializations,
                'capabilities': capability_items if capability_items else AgentCapabilities.DEFAULT_CAPABILITIES,
                'classification_tags': classification_tags if classification_tags else AgentCapabilities.DEFAULT_TAGS,
                'model_info': model_info,
                'default_capable': default_capable if capability_items else True,
                'performance_metrics': AgentCapabilities.DEFAULT_PERFORMANCE_METRICS,
            }
        except Exception as e:
            logger.warning(f"Auto capability generation failed, falling back to defaults: {e}")
            return {
                'agent_type': AgentCapabilities.DEFAULT_TYPE,
                'specializations': AgentCapabilities.DEFAULT_SPECIALIZATIONS,
                'capabilities': AgentCapabilities.DEFAULT_CAPABILITIES,
                'classification_tags': AgentCapabilities.DEFAULT_TAGS,
                'model_info': None,
                'default_capable': True,
                'performance_metrics': AgentCapabilities.DEFAULT_PERFORMANCE_METRICS,
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

    # =============================================================================
    # CAPABILITY MANAGEMENT AND DEFINITION
    # =============================================================================
    # Methods for defining, managing, and discovering agent capabilities
    
    def define_capabilities(self, 
                           agent_type: str = "general",
                           specializations: List[str] = None,
                           capabilities: List[str] = None,
                           classification_tags: List[str] = None,
                           performance_metrics: Dict[str, Any] = None,
                           interaction_patterns: List[str] = None,
                           strengths: List[str] = None,
                           limitations: List[str] = None,
                           default_capable: bool = True) -> None:
        """
        Define agent capabilities using a clean, structured interface.
        
        ARCHITECTURAL DECISION: Capability-Based Discovery
        ==================================================
        Agents advertise capabilities rather than names to enable intelligent
        routing and discovery. This allows:
        1. Dynamic agent selection based on task requirements
        2. Better scalability as agent count grows
        3. Natural language understanding of agent abilities
        4. Automatic tool generation from capability descriptions
        
        This method provides the primary interface for user-defined capabilities,
        offering a clean, type-safe way to define rich agent metadata without
        needing to understand the underlying capability schema.
        
        ARCHITECTURAL BENEFITS:
        ======================
        
        - **Type Safety**: Clear parameter types and validation
        - **Structured Interface**: Organized, logical parameter grouping
        - **Validation**: Automatic schema validation and normalization
        - **Flexibility**: Supports both simple and complex capability definitions
        - **Consistency**: Standardized interface across all agent types
        
        USAGE PATTERNS:
        ===============
        
        1. **Simple Definition**: Basic agent type and capabilities
        2. **Rich Definition**: Comprehensive metadata with performance metrics
        3. **Domain Specialization**: Detailed specializations and limitations
        4. **Runtime Updates**: Dynamic capability management
        
        This method stores capabilities as instance attributes for the discovery
        system to find and use, taking priority over automatic generation.
        
        Args:
            agent_type: Type of agent ("general", "specialist", "tool_agent", etc.)
            specializations: List of domain specializations (e.g., ["weather", "finance"])
            capabilities: List of specific capabilities the agent can perform
            classification_tags: List of tags for categorization and discovery
            performance_metrics: Dict with performance characteristics
            interaction_patterns: List of how this agent typically interacts
            strengths: List of key strengths
            limitations: List of known limitations
            default_capable: Whether this agent can handle general requests
        
        Example:
            agent.define_capabilities(
                agent_type="specialist",
                specializations=["weather", "meteorology"],
                capabilities=["weather_forecasting", "climate_analysis"],
                classification_tags=["weather", "forecast", "climate"],
                performance_metrics={
                    "estimated_response_time": "fast",
                    "complexity_handling": "moderate"
                },
                strengths=["Accurate weather data", "Multi-day forecasting"],
                limitations=["Requires location input", "Weather domain only"]
            )
        """
        capabilities_dict = {
            'agent_type': agent_type,
            'specializations': specializations or AgentCapabilities.DEFAULT_SPECIALIZATIONS,
            'capabilities': capabilities or AgentCapabilities.DEFAULT_CAPABILITIES,
            'classification_tags': classification_tags or AgentCapabilities.DEFAULT_TAGS,
            'performance_metrics': performance_metrics or AgentCapabilities.DEFAULT_PERFORMANCE_METRICS,
            'interaction_patterns': interaction_patterns or AgentCapabilities.DEFAULT_INTERACTION_PATTERNS,
            'strengths': strengths or AgentCapabilities.DEFAULT_STRENGTHS,
            'limitations': limitations or AgentCapabilities.DEFAULT_LIMITATIONS,
            'default_capable': default_capable
        }
        
        # Store as instance attribute for _get_user_defined_capabilities to find
        self._store_capabilities(capabilities_dict)
        self._log_capability_definition(capabilities_dict, agent_type)
    
    def _store_capabilities(self, capabilities_dict: Dict[str, Any]) -> None:
        """Store capabilities as instance attribute."""
        self.capabilities = capabilities_dict
    
    def _log_capability_definition(self, capabilities_dict: Dict[str, Any], agent_type: str) -> None:
        """Log capability definition information."""
        capability_count = len(capabilities_dict.get('capabilities', []))
        logger.info(f"Defined capabilities for {self.__class__.__name__}: {agent_type} agent with {capability_count} capabilities")
    
    def add_capability(self, capability: str, description: str = None) -> None:
        """
        Add a single capability to the agent.
        
        Args:
            capability: The capability name to add
            description: Optional description of the capability
        """
        if not hasattr(self, 'capabilities') or not self.capabilities:
            # Initialize with defaults
            self.define_capabilities()
        
        if capability not in self.capabilities.get('capabilities', []):
            self.capabilities['capabilities'].append(capability)
            logger.debug(f"Added capability '{capability}' to {self.__class__.__name__}")
    
    def add_specialization(self, specialization: str) -> None:
        """
        Add a domain specialization to the agent.
        
        Args:
            specialization: The specialization to add (e.g., "weather", "finance")
        """
        if not hasattr(self, 'capabilities') or not self.capabilities:
            # Initialize with defaults
            self.define_capabilities()
        
        if specialization not in self.capabilities.get('specializations', []):
            self.capabilities['specializations'].append(specialization)
            logger.debug(f"Added specialization '{specialization}' to {self.__class__.__name__}")
    
    def set_performance_metric(self, metric: str, value: Any) -> None:
        """
        Set a performance metric for the agent.
        
        Args:
            metric: The metric name (e.g., "estimated_response_time", "complexity_handling")
            value: The metric value
        """
        if not hasattr(self, 'capabilities') or not self.capabilities:
            # Initialize with defaults
            self.define_capabilities()
        
        if 'performance_metrics' not in self.capabilities:
            self.capabilities['performance_metrics'] = {}
        
        self.capabilities['performance_metrics'][metric] = value
        logger.debug(f"Set performance metric '{metric}' to '{value}' for {self.__class__.__name__}")
    
    def _get_available_functions(self) -> Dict[str, Any]:
        """
        Get currently available functions by reading from DDS directly via DDSFunctionDiscovery.
        Uses DDS DataReader as the single source of truth (no caching).
        Available to all agents regardless of LLM backend (OpenAI, Anthropic, custom).
        
        Returns:
            Dict[str, Dict]: Dictionary keyed by function name, containing:
                - function_id: Unique identifier
                - description: Human-readable description
                - schema: JSON schema for parameters
                - provider_id: ID of the service providing this function
        """
        # Lazy init GenericFunctionClient if needed
        if not hasattr(self, '_generic_client'):
            from genesis_lib.generic_function_client import GenericFunctionClient
            # Pass the DDSFunctionDiscovery from app
            self._generic_client = GenericFunctionClient(
                discovery=self.app.function_discovery
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
            agent_type = agent_info.get('agent_type', AgentConfig.DEFAULT_AGENT_TYPE)
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

    def _get_agent_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get provider-agnostic tool schemas for discovered agents.
        
        This uses the UNIVERSAL AGENT SCHEMA pattern where all agents
        accept a 'message' parameter regardless of their internal implementation.
        
        Returns:
            List of agent tool schemas with 'name', 'description', and 'parameters'
        """
        agent_schemas = []
        
        available_agent_tools = self._get_available_agent_tools()
        for tool_name, agent_info in available_agent_tools.items():
            agent_name = agent_info.get('agent_name', 'Unknown Agent')
            capabilities = agent_info.get('capabilities', [])
            
            # Create capability-based description for the LLM
            if capabilities:
                capability_desc = f"Specialized agent for {', '.join(capabilities[:3])}"
                if len(capabilities) > 3:
                    capability_desc += f" and {len(capabilities)-3} more capabilities"
            else:
                capability_desc = f"General purpose agent ({agent_name})"
            
            # UNIVERSAL AGENT SCHEMA - provider-agnostic
            agent_schemas.append({
                "name": tool_name,
                "description": f"{capability_desc}. Send natural language queries and receive responses.",
                "parameters": {
                    "message": {
                        "type": "string",
                        "description": "Natural language query or request to send to the agent"
                    }
                },
                "required": ["message"]
            })
            
            logger.debug(f"Generated universal schema for agent tool: {tool_name}")
        
        logger.debug(f"Generated {len(agent_schemas)} universal agent tool schemas")
        return agent_schemas

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
        logger.debug(f"Function call started: {function_name}")
        logger.debug(f"Function arguments: {json.dumps(kwargs, indent=2)}")
        
        available_functions = self._get_available_functions()
        if function_name not in available_functions:
            error_msg = f"Function not found: {function_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        try:
            # Call the function through the generic client
            start_time = time.time()
            result = await self._generic_client.call_function(
                available_functions[function_name]["function_id"],
                **kwargs
            )
            end_time = time.time()
            
            logger.debug(f"Function call completed in {end_time - start_time:.2f} seconds")
            logger.debug(f"Function result: {result}")
            
            # Extract result value if in dict format
            if isinstance(result, dict) and "result" in result:
                return result["result"]
            return result
            
        except Exception as e:
            logger.error(f"Error calling function {function_name}: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def _call_agent(self, agent_tool_name: str, **kwargs) -> Any:
        """
        Call an agent using the UNIVERSAL AGENT SCHEMA.
        Available to all agents regardless of LLM backend.
        
        ARCHITECTURAL DECISION: Universal Agent Schema
        ==============================================
        We use a simple message/response pattern for all agent communication
        rather than custom schemas per agent. This enables:
        1. Easier LLM integration (consistent interface)
        2. Better agent discovery (capability-based, not name-based)
        3. Reduced complexity in agent-to-agent communication
        
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
        logger.debug(f"Agent call started: {agent_tool_name}")
        logger.debug(f"Agent arguments: {json.dumps(kwargs, indent=2)}")
        
        available_agent_tools = self._get_available_agent_tools()
        if agent_tool_name not in available_agent_tools:
            error_msg = f"Agent tool not found: {agent_tool_name}"
            logger.error(error_msg)
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
                logger.debug("Using monitored agent communication")
                start_time = time.time()
                result = await self.send_agent_request_monitored(
                    target_agent_id=target_agent_id,
                    message=message,
                    conversation_id=None,  # Simplified - no separate conversation tracking
                    timeout_seconds=AgentConfig.DEFAULT_AGENT_CALL_TIMEOUT
                )
                end_time = time.time()
            else:
                # Fallback to basic agent communication
                logger.debug("Using basic agent communication")
                start_time = time.time()
                result = await self.send_agent_request(
                    target_agent_id=target_agent_id,
                    message=message,
                    conversation_id=None,  # Simplified - no separate conversation tracking
                    timeout_seconds=AgentConfig.DEFAULT_AGENT_CALL_TIMEOUT
                )
                end_time = time.time()
            
            logger.debug(f"Agent call completed in {end_time - start_time:.2f} seconds")
            logger.debug(f"Agent result: {result}")
            
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
            logger.error(f"Error calling agent {agent_tool_name}: {str(e)}")
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
        logger.debug("Discovering internal @genesis_tool methods")
        
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
                    logger.debug(f"Found @genesis_tool method: {attr_name}")
        
        if not tool_methods:
            logger.debug("No @genesis_tool methods found")
            return
        
        logger.debug(f"Processing {len(tool_methods)} @genesis_tool methods")
        
        # Generate tool schemas for discovered methods
        for method_name, method, tool_meta in tool_methods:
            # Store method reference and metadata
            self.internal_tools_cache[method_name] = {
                "method": method,
                "metadata": tool_meta,
                "function_name": tool_meta.get("function_name", method_name)
            }
            
            logger.debug(f"Registered internal tool: {method_name}")
            logger.debug(f"Tool metadata: {tool_meta}")

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
        logger.debug(f"Internal tool call started: {tool_name}")
        logger.debug(f"Tool arguments: {json.dumps(kwargs, indent=2)}")
        
        if not hasattr(self, 'internal_tools_cache') or tool_name not in self.internal_tools_cache:
            error_msg = f"Internal tool not found: {tool_name}"
            logger.error(error_msg)
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
            
            logger.debug(f"Internal tool call completed in {end_time - start_time:.2f} seconds")
            logger.debug(f"Internal tool result: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calling internal tool {tool_name}: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    # =============================================================================
    # REQUEST PROCESSING AND ORCHESTRATION
    # =============================================================================
    # Methods for processing requests and orchestrating LLM interactions

    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a request using the LLM with tool support.
        Provider-agnostic orchestration - delegates provider-specific logic to abstract methods.
        
        Args:
            request: Request dict with 'message' key
            
        Returns:
            Response dict with 'message' and 'status' keys
        """
        user_message = request.get("message", "")
        
        # Store user message for tool classification (used by provider implementations)
        self._current_user_message = user_message
        
        # Ensure internal tools are discovered
        await self._ensure_internal_tools_discovered()
        
        # Check what tools are available
        available_functions = self._get_available_functions()
        agent_tools = self._get_available_agent_tools()
        
        # Select appropriate system prompt
        system_prompt = self._select_system_prompt(available_functions, agent_tools)
        
        # Get tools in provider-specific format
        tools = await self._get_tool_schemas()
        
        # Clear the message after tool schema generation
        self._current_user_message = None
        
        if not tools:
            # Simple conversation (no tools available)
            memory_items = self.memory.retrieve(k=8)
            messages = self._format_messages(user_message, system_prompt, memory_items)
            response = await self._call_llm(messages)
            text = self._extract_text_response(response)
            
            self.memory.write(user_message, metadata={"role": "user"})
            self.memory.write(text, metadata={"role": "assistant"})
            return {"message": text, "status": 0}
        
        # Tool-based conversation (orchestrated by this class)
        tool_choice = self._get_tool_choice()
        return await self._orchestrate_tool_request(
            user_message=user_message,
            tools=tools,
            system_prompt=system_prompt,
            tool_choice=tool_choice
        )

    async def process_agent_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a request from another agent (agent-to-agent communication).
        Provider-agnostic wrapper that adds agent-specific tracing.
        
        Args:
            request: Request dict with 'message' key and metadata about source agent
            
        Returns:
            Response dict with 'message' and 'status' keys
        """
        # Extract source agent info for tracing
        source_agent = request.get("source_agent", "unknown")
        user_message = request.get("message", "")
        
        if getattr(self, 'enable_tracing', False):
            logger.info(f"🤝 Agent-to-Agent Request from '{source_agent}': {user_message[:100]}")
        
        # Process using standard flow
        result = await self.process_request(request)
        
        if getattr(self, 'enable_tracing', False):
            response_msg = result.get("message", "")
            logger.info(f"🤝 Agent-to-Agent Response to '{source_agent}': {response_msg[:100]}")
        
        return result

    # =============================================================================
    # ABSTRACT METHODS FOR LLM PROVIDER IMPLEMENTATIONS
    # =============================================================================
    # These methods must be implemented by concrete subclasses to provide
    # provider-specific functionality (OpenAI, Anthropic, etc.)
    
    @abstractmethod
    async def _call_llm(self, messages: List[Dict], tools: Optional[List[Dict]] = None, 
                        tool_choice: str = "auto") -> Any:
        """
        Call the LLM provider's API.
        
        Args:
            messages: Conversation history in provider-specific format
            tools: Tool schemas in provider-specific format
            tool_choice: How the LLM should use tools ("auto", "required", "none")
        
        Returns:
            Provider-specific response object
        """
        pass

    @abstractmethod
    def _format_messages(self, user_message: str, system_prompt: str, 
                         memory_items: List[Dict]) -> List[Dict]:
        """
        Format conversation history in provider-specific message format.
        
        Args:
            user_message: Current user message
            system_prompt: System prompt to use
            memory_items: Retrieved memory items
        
        Returns:
            List of messages in provider's expected format
        """
        pass

    @abstractmethod
    def _extract_tool_calls(self, response: Any) -> Optional[List[Dict]]:
        """
        Extract tool calls from provider's response.
        
        Args:
            response: Provider-specific response object
        
        Returns:
            List of tool calls with 'name', 'id', 'arguments' keys, or None
        """
        pass

    @abstractmethod
    def _extract_text_response(self, response: Any) -> str:
        """
        Extract text response from provider's response.
        
        Args:
            response: Provider-specific response object
        
        Returns:
            Text response string
        """
        pass

    @abstractmethod
    def _create_assistant_message(self, response: Any) -> Dict:
        """
        Create an assistant message dict from provider's response for conversation history.
        
        This is used to add the assistant's message (with or without tool_calls) to 
        the conversation history for multi-turn conversations.
        
        Args:
            response: Provider-specific response object
            
        Returns:
            Dict representing the assistant message in provider's expected format
        """
        pass

    @abstractmethod
    async def _get_tool_schemas(self) -> List[Dict]:
        """
        Get all tool schemas in provider-specific format.
        
        This should return schemas for:
        - External functions (discovered via DDS)
        - Agent tools (other agents)
        - Internal tools (@genesis_tool decorated methods)
        
        Returns:
            List of tool schemas formatted for the specific LLM provider
        """
        pass

    @abstractmethod
    def _get_tool_choice(self) -> str:
        """
        Get provider-specific tool choice setting.
        
        Returns:
            Tool choice string (e.g., "auto", "required", "none" for OpenAI)
        """
        pass

    # =============================================================================
    # PROVIDER-AGNOSTIC UTILITY METHODS
    # =============================================================================
    # These methods provide common functionality that works across all LLM providers

    def _select_system_prompt(self, available_functions: Dict, agent_tools: Dict) -> str:
        """
        Select appropriate system prompt based on available tools.
        Provider-agnostic logic.
        
        Args:
            available_functions: Dict of available external functions
            agent_tools: Dict of available agent tools
        
        Returns:
            Selected system prompt string
        """
        if not available_functions and not agent_tools:
            return getattr(self, 'general_system_prompt', AgentConfig.DEFAULT_GENERAL_SYSTEM_PROMPT)
        else:
            return getattr(self, 'function_based_system_prompt', 
                          AgentConfig.DEFAULT_FUNCTION_SYSTEM_PROMPT)

    def _trace_llm_call(self, context: str, tools: List[Dict], user_message: str, 
                        tool_responses: Optional[List[Dict]] = None):
        """
        Enhanced tracing: LLM API call details.
        Provider-agnostic tracing for debugging LLM interactions.
        
        Args:
            context: Description of the call context
            tools: Tool schemas being sent to LLM
            user_message: User's message
            tool_responses: Optional tool responses being sent
        """
        if not getattr(self, 'enable_tracing', False):
            return
            
        logger.debug(f"🚀 TRACE: === CALLING LLM: {context} ===")
        logger.debug(f"🚀 TRACE: User message: {user_message}")
        
        if tools:
            logger.debug(f"🚀 TRACE: Tools provided: {len(tools)} tools")
            for i, tool in enumerate(tools):
                # Handle different tool schema formats
                tool_name = (tool.get('function', {}).get('name') or 
                           tool.get('name', 'Unknown'))
                logger.debug(f"🚀 TRACE: Tool {i+1}: {tool_name}")
        else:
            logger.debug(f"🚀 TRACE: NO TOOLS PROVIDED TO LLM")
        
        if tool_responses:
            logger.debug(f"🚀 TRACE: Tool responses included: {len(tool_responses)} responses")
            for i, response in enumerate(tool_responses):
                tool_name = response.get('name', 'Unknown')
                logger.debug(f"🚀 TRACE: Tool response {i+1}: {tool_name}")

    def _trace_llm_response(self, response: Any, provider_name: str = "LLM"):
        """
        Enhanced tracing: LLM response analysis.
        Provider-agnostic tracing for debugging LLM responses.
        
        Args:
            response: Provider-specific response object
            provider_name: Name of the LLM provider (for logging)
        """
        if not getattr(self, 'enable_tracing', False):
            return
            
        logger.debug(f"🎯 TRACE: === {provider_name} RESPONSE RECEIVED ===")
        logger.debug(f"🎯 TRACE: Response type: {type(response)}")
        
        # Try to extract text response using the provider's method
        try:
            text = self._extract_text_response(response)
            if text:
                logger.debug(f"🎯 TRACE: Response content length: {len(text)} characters")
                logger.debug(f"🎯 TRACE: Response content preview: {text[:100]}{'...' if len(text) > 100 else ''}")
            else:
                logger.debug(f"🎯 TRACE: No text content in response")
        except Exception:
            logger.debug(f"🎯 TRACE: Could not extract text content")
        
        # Try to extract tool calls using the provider's method
        try:
            tool_calls = self._extract_tool_calls(response)
            if tool_calls:
                logger.debug(f"🎯 TRACE: *** TOOL CALLS DETECTED: {len(tool_calls)} ***")
                for i, tool_call in enumerate(tool_calls):
                    tool_name = tool_call.get('name', 'Unknown')
                    tool_args = tool_call.get('arguments', {})
                    logger.debug(f"🎯 TRACE: Tool call {i+1}: {tool_name}")
                    logger.debug(f"🎯 TRACE: Tool call args: {tool_args}")
            else:
                logger.debug(f"🎯 TRACE: *** NO TOOL CALLS - DIRECT RESPONSE ***")
        except Exception:
            logger.debug(f"🎯 TRACE: Could not extract tool calls")

    async def _orchestrate_tool_request(self, user_message: str, tools: List[Dict],
                                        system_prompt: str, tool_choice: str = "auto") -> Dict[str, Any]:
        """
        Provider-agnostic orchestration of tool-based LLM requests.
        
        This method handles:
        1. Formatting conversation with memory
        2. Calling LLM
        3. Routing tool calls (functions/agents/internal tools)
        4. Multi-turn conversation loop
        5. Memory management
        
        Args:
            user_message: User's message
            tools: Tool schemas in provider-specific format
            system_prompt: System prompt to use
            tool_choice: How LLM should use tools
        
        Returns:
            Dict with 'message' and 'status' keys
        """
        # 1. Format messages (provider-specific)
        memory_items = self.memory.retrieve(k=8)
        messages = self._format_messages(user_message, system_prompt, memory_items)
        
        # Trace LLM call if tracing enabled
        if getattr(self, 'enable_tracing', False):
            self._trace_llm_call("initial orchestration", tools, user_message)
        
        # 2. Call LLM (provider-specific)
        response = await self._call_llm(messages, tools, tool_choice)
        
        # Trace LLM response if tracing enabled
        if getattr(self, 'enable_tracing', False):
            provider_name = self.__class__.__name__.replace("GenesisAgent", "")
            self._trace_llm_response(response, provider_name or "LLM")
        
        # 3. Extract tool calls (provider-specific)
        tool_calls = self._extract_tool_calls(response)
        
        # 4. If no tool calls, return text response
        if not tool_calls:
            text_response = self._extract_text_response(response)
            self.memory.write(user_message, metadata={"role": "user"})
            self.memory.write(text_response, metadata={"role": "assistant"})
            return {"message": text_response, "status": 0}
        
        # 5. Execute tool calls
        tool_responses = []
        for tool_call in tool_calls:
            result = await self._route_tool_call(
                tool_name=tool_call['name'],
                tool_args=tool_call['arguments']
            )
            tool_responses.append({
                "tool_call_id": tool_call['id'],
                "role": "tool",
                "name": tool_call['name'],
                "content": str(result)
            })
        
        # 6. Multi-turn loop
        max_turns = 5
        turn_count = 0
        final_message = None
        
        # Add assistant message with tool_calls, then tool responses to conversation
        assistant_message = self._create_assistant_message(response)
        messages.append(assistant_message)
        messages.extend(tool_responses)
        
        while turn_count < max_turns:
            turn_count += 1
            
            # Trace multi-turn call if tracing enabled
            if getattr(self, 'enable_tracing', False):
                self._trace_llm_call(f"multi-turn loop (turn {turn_count})", tools, user_message, tool_responses)
            
            # Call LLM with tool results (always use 'auto' in multi-turn)
            response = await self._call_llm(messages, tools, tool_choice='auto')
            
            # Trace response if tracing enabled
            if getattr(self, 'enable_tracing', False):
                provider_name = self.__class__.__name__.replace("GenesisAgent", "")
                self._trace_llm_response(response, f"{provider_name or 'LLM'} (turn {turn_count})")
            
            tool_calls = self._extract_tool_calls(response)
            
            # Check if we got a text response
            if not tool_calls:
                final_message = self._extract_text_response(response)
                break
            
            # LLM wants to make more tool calls - add assistant message first
            assistant_message = self._create_assistant_message(response)
            messages.append(assistant_message)
            
            # Execute additional tool calls
            new_tool_responses = []
            for tool_call in tool_calls:
                result = await self._route_tool_call(
                    tool_name=tool_call['name'],
                    tool_args=tool_call['arguments']
                )
                new_tool_responses.append({
                    "tool_call_id": tool_call['id'],
                    "role": "tool",
                    "name": tool_call['name'],
                    "content": str(result)
                })
            
            # Add tool responses to conversation
            messages.extend(new_tool_responses)
        
        if turn_count >= max_turns:
            final_message = "Response processing exceeded maximum turns"
        
        # Write to memory
        self.memory.write(user_message, metadata={"role": "user"})
        if final_message:
            self.memory.write(final_message, metadata={"role": "assistant"})
        
        return {"message": final_message, "status": 0}

    async def _route_tool_call(self, tool_name: str, tool_args: Dict) -> Any:
        """
        Route a tool call to the appropriate handler.
        Provider-agnostic - works for all LLM providers.
        
        Args:
            tool_name: Name of the tool to call
            tool_args: Arguments for the tool
        
        Returns:
            Tool execution result
        """
        # Check what type of tool this is
        functions = self._get_available_functions()
        agents = self._get_available_agent_tools()
        internal_tools = getattr(self, 'internal_tools_cache', {})
        
        if tool_name in functions:
            # External function via RPC
            result = await self._call_function(tool_name, **tool_args)
        elif tool_name in agents:
            # Agent-to-agent call
            result = await self._call_agent(tool_name, **tool_args)
        elif tool_name in internal_tools:
            # Internal @genesis_tool method
            result = await self._call_internal_tool(tool_name, **tool_args)
        else:
            raise ValueError(f"Tool not found: {tool_name}")
        
        # Extract result if in dict format
        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        
        return result

    # =============================================================================
    # AGENT LIFECYCLE MANAGEMENT
    # =============================================================================
    # Methods for agent initialization, execution, and cleanup

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

            logger.info(f"GenesisAgent.run() starting for {self.agent_name}")
            # Announce presence
            logger.info("Announcing agent presence via unified advertisement...")
            await self.announce_self()
            logger.info("Agent presence announced successfully")
            
            # Main loop - handle agent requests if enabled
            logger.info(f"{self.agent_name} listening for requests (Ctrl+C to exit)...")
            
            # Main event loop with agent request handling
            loop_count = 0
            while True:
                try:
                    loop_count += 1
                    # Log every 100 iterations to verify loop is running
                    if loop_count % 100 == 1:
                        logger.debug(f"Main event loop iteration #{loop_count}, agent_communication={self.agent_communication is not None}")
                    
                    # Handle agent-to-agent requests if communication is enabled
                    if self.agent_communication:
                        await self.agent_communication._handle_agent_requests()
                    
                    # Small delay to prevent busy waiting
                    await asyncio.sleep(0.1)
                    
                except KeyboardInterrupt:
                    logger.info("KeyboardInterrupt in main loop, breaking...")
                    break
                except Exception as e:
                    logger.error(f"Error in main agent loop: {e}")
                    # Continue running despite errors
                    await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info(f"KeyboardInterrupt in GenesisAgent.run(), shutting down {self.agent_name}...")
            await self.close()
            sys.exit(0)
        finally:
            # Allow future restarts if the loop exits
            self._run_started = False
            self._run_task = None

    # =============================================================================
    # DDS/RPC INFRASTRUCTURE AND SETUP
    # =============================================================================
    # Methods for DDS infrastructure setup, RPC handling, and system integration

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
                self._mcp_thread.join(timeout=AgentConfig.MCP_THREAD_JOIN_TIMEOUT)
                if self._mcp_thread.is_alive():
                    logger.warning("MCP thread did not shut down within 5 seconds and may be stuck.")

            logger.info(f"GenesisAgent {self.agent_name} closed successfully")
        except Exception as e:
            logger.error(f"Error closing GenesisAgent: {str(e)}")
            logger.error(traceback.format_exc())

    # =============================================================================
    # AGENT ADVERTISEMENT AND DISCOVERY
    # =============================================================================
    # Methods for agent presence announcement and discovery

    async def announce_self(self):
        """Publish a unified GenesisAdvertisement(kind=AGENT) for this agent."""
        try:
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
            ad["service_name"] = self.base_service_name
            ad["provider_id"] = str(writer.instance_handle)
            ad["last_seen"] = int(time.time() * 1000)
            payload = {
                "agent_type": getattr(self, 'agent_type', AgentConfig.DEFAULT_AGENT_TYPE),
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
