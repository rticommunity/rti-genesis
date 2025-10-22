#!/usr/bin/env python3
"""
MonitoredAgent Base Class for Genesis Agents (Unified Graph Monitoring)

This module provides the MonitoredAgent class, which sits between GenesisAgent (base logic)
and provider-specific implementations (OpenAIGenesisAgent, AnthropicGenesisAgent, etc.).
It adds automatic monitoring, observability, and graph topology tracking to all agents.

=================================================================================================
ARCHITECTURE POSITION - Where MonitoredAgent Fits
=================================================================================================

GenesisAgent (genesis_lib/agent.py)
├─ Provider-Agnostic Business Logic:
│  ├─ process_request() - Main request processing flow
│  ├─ _orchestrate_tool_request() - Multi-turn conversation orchestration
│  ├─ _route_tool_call() - Routes tool calls to functions/agents/internal tools
│  ├─ _call_function() - Executes external function via RPC
│  └─ Abstract methods for LLM provider implementations
│
    ↓ inherits
│
MonitoredAgent (THIS FILE - genesis_lib/monitored_agent.py)
├─ Observability & Monitoring (AUTOMATIC - No Provider Implementation Needed):
│  ├─ __init__() - Sets up monitoring infrastructure during initialization
│  │              Publishes DISCOVERING → READY state transitions
│  ├─ process_request() - Wraps parent with READY → BUSY → READY state publishing
│  │                      Handles DEGRADED state on errors with automatic recovery
│  ├─ GraphMonitor integration - Publishes node/edge topology events
│  ├─ _publish_llm_call_start/complete() - Tracks LLM API calls
│  ├─ _publish_function_call_start/complete() - Tracks function executions
│  ├─ _publish_agent_chain_event() - Tracks agent-to-agent interactions
│  ├─ _publish_classification_node() - Tracks function classification
│  └─ publish_monitoring_event() - General event publishing
│
    ↓ inherits
│
Provider Implementation (e.g., OpenAIGenesisAgent, AnthropicGenesisAgent)
└─ Provider-Specific Implementation:
   ├─ Implements 7 abstract methods for LLM provider
   ├─ All monitoring is AUTOMATIC from MonitoredAgent
   └─ No monitoring code needed in provider implementations

=================================================================================================
WHAT MONITORED AGENT PROVIDES - Automatic Observability
=================================================================================================

When you inherit from MonitoredAgent (via provider implementation), you automatically get:

1. **State Machine Tracking**:
   - DISCOVERING: Agent has active DDS listeners discovering network capabilities
   - READY: Agent can accept and process requests
   - BUSY: Agent is currently processing a request
   - DEGRADED: Agent encountered an error (with automatic recovery attempts)
   - OFFLINE: Agent is shutting down

2. **Graph Topology Publishing**:
   - Node events: Agent lifecycle, function discovery, state transitions
   - Edge events: Agent→Function connections, Agent→Agent connections, Service→Function
   - Consumed by: GraphState subscribers, monitoring UI, network visualization

3. **Chain Event Tracking**:
   - LLM call start/complete events
   - Function call start/complete events
   - Agent-to-agent communication events
   - Classification result events
   - Consumed by: Chain tracing, performance monitoring, debugging tools

4. **Distributed Tracing**:
   - Automatic chain_id and call_id propagation
   - Cross-component event correlation
   - Request/response pairing validation
   - Consumed by: Distributed tracing tools, performance analysis

5. **Error Handling & Recovery**:
   - Automatic DEGRADED state on exceptions
   - Automatic recovery attempts to READY
   - Error event publishing for alerting
   - Consumed by: Monitoring dashboards, alerting systems

=================================================================================================
INITIALIZATION SEQUENCE - Understanding the Monitored Agent Startup
=================================================================================================

The initialization sequence is carefully ordered to ensure monitoring is ready before
the agent starts handling requests:

Step 1: Store Pre-Initialization Attributes
   - agent_type, description, domain_id stored before super().__init__
   - Required for state publishing after GraphMonitor is created

Step 2: Initialize Base GenesisAgent (super().__init__)
   - Creates GenesisApp with DDS participant
   - Creates FunctionRegistry with ACTIVE DDS listeners
   - Creates RPC replier for handling incoming requests
   - ⚠️ IMPORTANT: After this returns, discovery is already happening asynchronously!

Step 3: Initialize Function Client
   - Sets up GenericFunctionClient (doesn't actively discover yet)
   - Creates function cache for discovered functions

Step 4: Create GraphMonitor
   - Uses DDS participant from GenesisApp
   - Enables publishing of topology events (nodes and edges)

Step 5: Publish DISCOVERING State
   - Announces: "I have active DDS listeners discovering capabilities"
   - This is an ongoing passive state, not a one-time phase
   - Genesis is fully asynchronous - discovery happens continuously

Step 6: Setup Monitoring Infrastructure
   - Creates DDS readers/writers for Event topic (V2 unified monitoring)
   - Configures QoS for reliable delivery
   - Enables chain event publishing

Step 7: Publish READY State
   - Announces: "I am ready to accept and process requests"
   - Agent is now both DISCOVERING (passive listeners) and READY (can handle RPC)

Step 8: Initialize State Tracking
   - Sets current_state to "READY"
   - Initializes state history and event correlation tracking

=================================================================================================
STATE SEMANTICS - Understanding Genesis State Machine
=================================================================================================

MonitoredAgent implements a state machine for agent lifecycle:

DISCOVERING:
   - Indicates active DDS listeners continuously discovering network capabilities
   - This is an ongoing passive state, NOT a one-time initialization phase
   - Functions/agents arrive asynchronously via DDS advertisements over time
   - Agent remains in DISCOVERING state throughout its lifetime

READY:
   - Indicates agent can accept and process new requests
   - Published after initialization completes
   - Re-published after each request completes
   - Agent is both DISCOVERING and READY simultaneously

BUSY:
   - Published when process_request() is called
   - Indicates agent is actively processing a request
   - Helps with load balancing and capacity planning
   - Transitions back to READY when request completes

DEGRADED:
   - Published when an exception occurs during request processing
   - Triggers automatic recovery attempts
   - May indicate: LLM API issues, function call failures, memory problems
   - Agent attempts to recover to READY state

OFFLINE:
   - Published during agent shutdown (close() method)
   - Signals to network that agent is no longer available
   - Allows clean removal from network topology

=================================================================================================
MONITORING INTEGRATION - How Monitoring Data is Used
=================================================================================================

MonitoredAgent publishes data to DDS topics consumed by various systems:

1. **GraphTopology Topic** (Durable):
   - Node and edge lifecycle events
   - Consumed by: Network visualization UI, topology analyzers
   - Enables: Real-time network topology graph, capability discovery

2. **Event Topic** (Volatile):
   - Chain events: LLM calls, function calls, agent communication
   - Consumed by: Tracing systems, performance monitors, debuggers
   - Enables: Distributed tracing, performance analysis, debugging

3. **Graph Monitoring Systems**:
   - GraphState: Maintains live network topology in memory
   - GraphSubscriber: Subscribes to topology changes
   - Viewer Export: Exports topology for web UI visualization

Copyright (c) 2025, RTI & Jason Upchurch
"""

import logging
import time
import uuid
import json
from typing import Any, Dict, Optional, List
from datetime import datetime
import asyncio
import traceback
import rti.connextdds as dds

from .agent import GenesisAgent
from genesis_lib.generic_function_client import GenericFunctionClient
from genesis_lib.graph_monitoring import (
    GraphMonitor,
    COMPONENT_TYPE,
    STATE,
    EDGE_TYPE,
    _UNIFIED_TOPIC_REGISTRY,
)
from genesis_lib.utils import get_datamodel_path

logger = logging.getLogger(__name__)

# Event type mapping for monitoring events
EVENT_TYPE_MAP = {
    "AGENT_DISCOVERY": 0,  # FUNCTION_DISCOVERY enum value
    "AGENT_REQUEST": 1,    # FUNCTION_CALL enum value
    "AGENT_RESPONSE": 2,   # FUNCTION_RESULT enum value
    "AGENT_STATUS": 3      # FUNCTION_STATUS enum value
}

# Reverse mapping: enum value -> enum name (for consistent Event message field)
EVENT_TYPE_ENUM_NAMES = {
    0: "FUNCTION_DISCOVERY",
    1: "FUNCTION_CALL",
    2: "FUNCTION_RESULT",
    3: "FUNCTION_STATUS"
}

# Agent type mapping
AGENT_TYPE_MAP = {
    "AGENT": 1,            # PRIMARY_AGENT
    "SPECIALIZED_AGENT": 2, # SPECIALIZED_AGENT
    "INTERFACE": 0         # INTERFACE
}

class MonitoredAgent(GenesisAgent):
    """
    Base class for agents with monitoring capabilities.
    Extends GenesisAgent to add standardized monitoring.
    """

    _function_client_initialized = False

    def __init__(self, agent_name: str, base_service_name: str,
                 agent_type: str = "AGENT",
                 agent_id: str = None, description: str = None, domain_id: int = 0,
                 enable_agent_communication: bool = False, memory_adapter=None,
                 auto_run: bool = True, service_instance_tag: str = ""):
        """
        Initialize a MonitoredAgent with full observability and graph monitoring.
        
        Args:
            agent_name: Human-readable name for the agent (e.g., "WeatherAgent")
            base_service_name: DDS service name for RPC topics (e.g., "OpenAIChatService")
            agent_type: Type of agent - "AGENT" for primary or "SPECIALIZED_AGENT" for specialized
            agent_id: Optional unique ID; auto-generated if None
            description: Human-readable description of agent capabilities
            domain_id: DDS domain ID (default 0)
            enable_agent_communication: Enable agent-to-agent communication via DDS
            memory_adapter: Optional memory backend for conversation history
            auto_run: Whether to automatically start the RPC listener loop
            service_instance_tag: Optional tag for content filtering (e.g., "production", "staging")
        
        Initialization Sequence:
            1. Store attributes needed for state publishing before super().__init__
            2. Call super().__init__() → creates GenesisApp → creates FunctionRegistry with active listeners
            3. Initialize function client (for calling external functions)
            4. Create GraphMonitor for publishing topology events
            5. Publish DISCOVERING state (announce "I have active DDS listeners")
            6. Setup monitoring infrastructure (DDS readers/writers for events)
            7. Publish READY state (announce "I can accept requests")
            
        State Semantics:
            - DISCOVERING: Indicates active DDS listeners continuously discovering capabilities
                          This is an ongoing passive state, not a one-time phase
            - READY: Indicates the agent can accept and process requests
                     The agent is both DISCOVERING and READY simultaneously
            - BUSY: Published during request processing (by process_request wrapper)
            - DEGRADED: Published on errors with automatic recovery attempts
        """
        logger.info(f"🚀 TRACE: MonitoredAgent {agent_name} STARTING initializing with agent_id {agent_id}")

        # ===== Step 1: Store attributes before super().__init__() =====
        # These are needed for state publishing after GraphMonitor creation
        self.agent_type = agent_type
        self.description = description or f"A {agent_type} providing {base_service_name} service"
        self.domain_id = domain_id

        # ===== Step 2: Initialize base GenesisAgent =====
        # This creates:
        #   - GenesisApp with DDS participant
        #   - FunctionRegistry with ACTIVE discovery listeners
        #   - RPC replier for handling incoming requests
        # After this call returns, discovery is already happening asynchronously!
        super().__init__(
            agent_name=agent_name,
            base_service_name=base_service_name,
            agent_id=agent_id,
            enable_agent_communication=enable_agent_communication,
            memory_adapter=memory_adapter,
            auto_run=auto_run,
            service_instance_tag=service_instance_tag
        )
        logger.info(f"✅ TRACE: MonitoredAgent {agent_name} initialized with base class")

        # Note: At this point, FunctionRegistry listeners are already active and
        # passively discovering function advertisements from the network

        # ===== Step 3: Initialize function client and caching =====
        self.monitor = None  # Legacy monitoring (unused in V2)
        self.subscription = None  # Legacy monitoring (unused in V2)

        self._initialize_function_client()  # Sets up GenericFunctionClient (no active discovery yet)
        self.function_cache: Dict[str, Dict[str, Any]] = {}  # Cache for discovered functions
        
        # Register callback for agent discovery (if agent communication enabled)
        if hasattr(self, 'agent_communication') and self.agent_communication:
            logger.info(f"🔗 Registering agent discovery callback for {agent_name}")
            self.agent_communication.add_agent_discovery_callback(self._on_agent_discovered)

        # Agent capabilities metadata for advertisements
        self.agent_capabilities = {
            "agent_type": agent_type,
            "service": base_service_name,
            "functions": [],  # Populated dynamically as functions are discovered
            "supported_tasks": [],  # Can be populated by subclasses
            "prefered_name": self.agent_name,
            "agent_name": self.agent_name,
        }

        # ===== Step 4: Create unified graph monitor =====
        # Uses the DDS participant from GenesisApp for publishing topology events
        self.graph = GraphMonitor(self.app.participant)
        
        # ===== Step 5: Publish DISCOVERING state =====
        # Announces to the network: "I have active DDS listeners discovering capabilities"
        # This is an ongoing state - the agent continuously discovers as new advertisements arrive
        print(f"MonitoredAgent __init__: publishing DISCOVERING for {agent_name} ({self.app.agent_id})")
        self.graph.publish_node(
            component_id=self.app.agent_id,
            component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"],
            state=STATE["DISCOVERING"],
            attrs={
                "agent_type": agent_type,
                "service": base_service_name,
                "description": self.description,
                "agent_id": self.app.agent_id,
                "prefered_name": self.agent_name,
                "agent_name": self.agent_name,
                "reason": f"Agent {agent_name} is discovering network capabilities"
            }
        )
        
        # ===== Step 6: Setup monitoring infrastructure =====
        # Creates DDS readers/writers for Event topic (V2 unified monitoring)
        self._setup_monitoring()

        # ===== Step 7: Publish READY state =====
        # Announces to the network: "I am ready to accept and process requests"
        # The agent is now both DISCOVERING (passive listeners) and READY (can handle RPC)
        print(f"MonitoredAgent __init__: publishing READY for {agent_name} ({self.app.agent_id})")
        self.graph.publish_node(
            component_id=self.app.agent_id,
            component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"],
            state=STATE["READY"],
            attrs={
                "agent_type": agent_type,
                "service": base_service_name,
                "description": self.description,
                "agent_id": self.app.agent_id,
                "prefered_name": self.agent_name,
                "agent_name": self.agent_name,
                "reason": f"{agent_name} ready for requests"
            }
        )

        # ===== Step 8: Initialize state tracking =====
        self.current_state = "READY"  # Track current state for state machine
        self.last_state_change = datetime.now()  # Timestamp of last state transition
        self.state_history = []  # Historical record of state transitions
        self.event_correlation = {}  # Map of correlated monitoring events

        logger.info(f"✅ TRACE: Monitored agent {agent_name} initialized with type {agent_type}, agent_id={self.app.agent_id}, dds_guid={getattr(self.app, 'dds_guid', None)}")

    def _initialize_function_client(self) -> None:
        if not self.app or not self.app.participant:
            logger.error("Cannot initialize function client: DDS Participant not available.")
            return
        
        # Register callback to publish graph topology when functions are discovered
        # This is critical for network monitoring and visualization
        if hasattr(self.app, 'function_registry') and self.app.function_registry:
            logger.info(f"✅ Registering discovery callback for agent {self.agent_name} (ID: {self.app.agent_id})")
            self.app.function_registry.add_discovery_callback(self._on_function_discovered)
        else:
            logger.error(f"❌ CRITICAL: Cannot register discovery callback - function_registry not available for agent {self.agent_name}")
    
    def _on_function_discovered(self, function_id: str, function_info: Dict[str, Any]):
        """
        Callback invoked by FunctionRegistry when a new function is discovered via DDS.
        Publishes graph topology events (nodes and edges) for monitoring/visualization.
        
        This bridges the gap between DDS discovery (source of truth) and graph monitoring
        (visualization/management layer).
        
        Args:
            function_id: Unique identifier for the discovered function
            function_info: Dict with keys: name, description, provider_id, schema, capabilities, etc.
        """
        logger.info(f"🔔 _on_function_discovered callback invoked for {function_info.get('name', 'unknown')} (ID: {function_id[:8]}...)")
        try:
            # Convert single function to list format expected by publish_discovered_functions
            functions_list = [{
                'function_id': function_id,
                'name': function_info.get('name', 'unknown'),
                'description': function_info.get('description', ''),
                'provider_id': function_info.get('provider_id', ''),
                'schema': function_info.get('schema', {}),
                'capabilities': function_info.get('capabilities', []),
                'service_name': function_info.get('service_name', 'UnknownService')
            }]
            
            # Publish to graph topology (creates nodes and edges)
            self.publish_discovered_functions(functions_list)
            
        except Exception as e:
            logger.error(f"Error in _on_function_discovered callback: {e}")
    
    def _on_agent_discovered(self, agent_info: Dict[str, Any]) -> None:
        """
        Callback invoked when a new agent is discovered via DDS Advertisement.
        Publishes graph topology edge from this agent to the discovered agent.
        
        This is critical for visualizing agent-to-agent communication patterns
        in the monitoring UI. Without this, agent discovery happens but no edges
        are shown in the graph.
        
        Args:
            agent_info: Dict with keys: agent_id, name, prefered_name, service_name, 
                       agent_type, description, capabilities, etc.
        """
        agent_id = agent_info.get('agent_id', 'unknown')
        agent_name = agent_info.get('prefered_name') or agent_info.get('name', 'Unknown')
        logger.info(f"🤝 _on_agent_discovered callback invoked for {agent_name} ({agent_id[:8]}...)")
        
        # Publish edge: this agent → discovered agent
        try:
            self.graph.publish_edge(
                source_id=self.app.agent_id,
                target_id=agent_id,
                edge_type=EDGE_TYPE["AGENT_COMMUNICATION"],
                attrs={
                    "edge_type": "agent_to_agent",
                    "source_agent": self.agent_name,
                    "target_agent": agent_name,
                    "reason": f"Agent {self.agent_name} discovered agent {agent_name}"
                },
                component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"]
            )
            logger.info(f"✅ Published agent→agent edge: {self.agent_name} → {agent_name}")
        except Exception as e:
            logger.error(f"Error publishing agent discovery edge: {e}")
            logger.error(traceback.format_exc())
    
    def _setup_monitoring(self) -> None:
        """
        Set up monitoring resources for publishing agent lifecycle events.
        
        Creates DDS readers/writers for the Event topic (V2 unified monitoring).
        
        **Topic Sharing Pattern**:
        Genesis uses a shared topic registry to handle scenarios where multiple components
        (e.g., Interface + Agent + Services) run in the same process and need to publish
        to the same DDS monitoring topics.
        
        DDS Constraint: Within a single DDS Participant, each topic name must be unique.
        You cannot create the same topic twice, even if it has the same configuration.
        
        Solution: The _UNIFIED_TOPIC_REGISTRY acts as a process-wide cache:
        - Key: (participant_id, topic_name)
        - Value: DDS Topic object
        - First component to need a topic creates it and caches it
        - Subsequent components reuse the cached Topic object
        
        Example Scenario:
            Process contains:
            1. OpenAIGenesisAgent (needs "Event" topic)
            2. SimpleGenesisInterface (also needs "Event" topic)
            3. Both share the same DDS Participant
            
            Without registry: Second component would fail with "topic already exists" error
            With registry: Second component reuses the Topic created by the first
        
        **Failure Handling**:
        Gracefully handles DDS setup failures by setting monitoring attributes to None,
        allowing the agent to function without monitoring if DDS infrastructure is unavailable.
        
        Raises:
            No exceptions - failures are logged but don't propagate
        """
        try:
            # Get types from XML
            config_path = get_datamodel_path()
            self.type_provider = dds.QosProvider(config_path)
            
            # Create monitoring publisher with QoS
            publisher_qos = dds.QosProvider.default.publisher_qos
            publisher_qos.partition.name = [""]  # Default partition
            self.monitoring_publisher = dds.Publisher(
                participant=self.app.participant,
                qos=publisher_qos
            )
            
            # Create unified monitoring event writer (Event)
            # Use shared topic registry to avoid creating the same topic twice.
            self.unified_event_type = self.type_provider.type("genesis_lib", "MonitoringEventUnified")
            participant_id = id(self.app.participant)
            event_key = (participant_id, "Event")
            
            if event_key in _UNIFIED_TOPIC_REGISTRY:
                self.unified_event_topic = _UNIFIED_TOPIC_REGISTRY[event_key]
                logger.debug("MonitoredAgent: Reusing Event topic from shared registry")
            else:
                self.unified_event_topic = dds.DynamicData.Topic(
                    self.app.participant,
                    "rti/connext/genesis/monitoring/Event",
                    self.unified_event_type
                )
                _UNIFIED_TOPIC_REGISTRY[event_key] = self.unified_event_topic
                logger.debug("MonitoredAgent: Created and registered Event topic")
            
            volatile_qos = dds.QosProvider.default.datawriter_qos
            volatile_qos.durability.kind = dds.DurabilityKind.VOLATILE
            volatile_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            self.unified_event_writer = dds.DynamicData.DataWriter(
                pub=self.monitoring_publisher,
                topic=self.unified_event_topic,
                qos=volatile_qos
            )
            
            logger.info("MonitoredAgent: Event monitoring setup completed successfully")
            
        except Exception as e:
            logger.error(f"MonitoredAgent: Error setting up monitoring: {str(e)}")
            logger.error(traceback.format_exc())
            # Set monitoring attributes to None so the publish methods can handle gracefully
            self.unified_event_writer = None
            self.unified_event_type = None

    async def process_request(self, request: Any) -> Dict[str, Any]:
        """
        Process incoming request with automatic state machine monitoring.
        
        **DECORATOR PATTERN - Monitoring Wrapper Only**:
        This method ONLY adds observability around the parent's process_request().
        All actual request processing logic lives in GenesisAgent.process_request().
        
        **What This Method Does** (Monitoring Only):
        1. Publish READY state if agent was in another state
        2. Publish BUSY state when processing starts
        3. Call parent's process_request() ← ACTUAL WORK HAPPENS HERE
        4. Publish READY state when processing completes successfully
        5. On error: Publish DEGRADED → attempt recovery to READY
        
        **What The Parent Does** (Actual Work):
        GenesisAgent.process_request() handles:
        - Internal tool discovery (@genesis_tool methods)
        - External function discovery (DDS advertisements)
        - Agent-to-agent tool discovery
        - System prompt selection
        - Tool schema generation (provider-specific format)
        - LLM orchestration with multi-turn tool execution
        - Memory management (conversation history)
        
        **Call Chain**:
        ```
        User Request
            ↓
        MonitoredAgent.process_request()     ← THIS METHOD (monitoring wrapper)
            ↓
            super().process_request()        ← Calls parent
            ↓
        GenesisAgent.process_request()       ← Actual business logic
            ↓
            _call_llm()                      ← Abstract method
            ↓
        OpenAIGenesisAgent._call_llm()       ← Provider implementation
        ```
        
        **Inheritance Chain**:
        - GenesisAgent: Defines abstract process_request with business logic
        - MonitoredAgent (THIS CLASS): Wraps with state machine monitoring
        - OpenAIGenesisAgent: Inherits monitored version, implements _call_llm()
        
        **State Transitions**:
        - Success: READY → BUSY → READY
        - Failure: READY → BUSY → DEGRADED → READY (recovery attempt)
        
        **Graph Events Published**:
        - Node state changes (visible in network topology UI)
        - Includes: component_id, state, reason, timestamp
        - Consumed by: GraphState, monitoring dashboards, visualization tools
        
        Args:
            request: Request dict with at minimum a 'message' key
                    May include: conversation_id, source_agent, service_instance_tag
        
        Returns:
            Response dict with 'message' and 'status' keys
            Status: 0 = success, non-zero = error
        
        Raises:
            Exception: Re-raises any exception from parent after publishing DEGRADED state
        """
        print(f"MonitoredAgent.process_request called for {self.agent_type} ({self.app.agent_id}) with request: {request}")
        chain_id = str(uuid.uuid4())
        call_id = str(uuid.uuid4())

        try:
            if self.current_state != "READY":
                self.graph.publish_node(
                    component_id=self.app.agent_id,
                    component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"],
                    state=STATE["READY"],
                    attrs={
                        "agent_type": self.agent_type,
                        "service": self.base_service_name,
                        "description": self.description,
                        "agent_id": self.app.agent_id,
                        "prefered_name": self.agent_name,
                        "agent_name": self.agent_name,
                        "reason": f"Transitioning to READY state before processing request"
                    }
                )
                self.current_state = "READY"

            self.graph.publish_node(
                component_id=self.app.agent_id,
                component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"],
                state=STATE["BUSY"],
                attrs={
                    "agent_type": self.agent_type,
                    "service": self.base_service_name,
                    "description": self.description,
                    "agent_id": self.app.agent_id,
                    "prefered_name": self.agent_name,
                    "agent_name": self.agent_name,
                    "reason": f"Processing request: {str(request)}"
                }
            )
            self.current_state = "BUSY"

            # Call parent's process_request (from GenesisAgent)
            result = await super().process_request(request)

            self.graph.publish_node(
                component_id=self.app.agent_id,
                component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"],
                state=STATE["READY"],
                attrs={
                    "agent_type": self.agent_type,
                    "service": self.base_service_name,
                    "description": self.description,
                    "agent_id": self.app.agent_id,
                    "prefered_name": self.agent_name,
                    "agent_name": self.agent_name,
                    "reason": f"Request processed successfully: {str(result)}"
                }
            )
            self.current_state = "READY"
            return result

        except Exception as e:
            self.graph.publish_node(
                component_id=self.app.agent_id,
                component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"],
                state=STATE["DEGRADED"],
                attrs={
                    "agent_type": self.agent_type,
                    "service": self.base_service_name,
                    "description": self.description,
                    "agent_id": self.app.agent_id,
                    "prefered_name": self.agent_name,
                    "agent_name": self.agent_name,
                    "reason": f"Error processing request: {str(e)}"
                }
            )
            self.current_state = "DEGRADED"
            try:
                self.graph.publish_node(
                    component_id=self.app.agent_id,
                    component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"],
                    state=STATE["READY"],
                    attrs={
                        "agent_type": self.agent_type,
                        "service": self.base_service_name,
                        "description": self.description,
                        "agent_id": self.app.agent_id,
                        "prefered_name": self.agent_name,
                        "agent_name": self.agent_name,
                        "reason": "Attempting recovery to READY state"
                    }
                )
                self.current_state = "READY"
            except Exception as recovery_error:
                logger.error(f"Failed to recover from DEGRADED state: {recovery_error}")
            raise

    async def close(self) -> None:
        """
        Gracefully shut down the agent with automatic state notification.
        
        **DECORATOR PATTERN - Monitoring Wrapper Only**:
        Similar to process_request(), this method wraps the parent's cleanup logic
        with monitoring state transitions.
        
        **Shutdown Sequence**:
        1. Publish OFFLINE state to network (announces agent is shutting down)
        2. Clear internal state tracking (state_history, event_correlation)
        3. Call parent's close() ← ACTUAL CLEANUP HAPPENS HERE
           - GenesisApp.close() shuts down DDS participant, RPC service, etc.
        
        **Why OFFLINE State Matters**:
        - Notifies network topology that agent is no longer available
        - Allows monitoring systems to update agent status in real-time
        - Enables clean removal from network graphs/dashboards
        - Prevents routing requests to dead agents
        
        **What Gets Cleaned Up** (in parent GenesisApp.close()):
        - DDS Participant (closes all topics, readers, writers)
        - RPC Replier (stops accepting requests)
        - Function Registry (cleanup discovery listeners)
        - Memory adapter (if using persistent storage)
        
        **State Transition**:
        - Normal: ANY_STATE → OFFLINE
        - On error: ANY_STATE → DEGRADED (then raises exception)
        
        **Graph Events Published**:
        - Node state: OFFLINE with reason "Shutting down monitoring"
        - Consumed by: Network topology viewers for agent lifecycle tracking
        
        Raises:
            Exception: Re-raises any exception from cleanup after setting DEGRADED state
        """
        try:
            print(f"MonitoredAgent.close: publishing OFFLINE for {self.agent_type} ({self.app.agent_id})")
            self.graph.publish_node(
                component_id=self.app.agent_id,
                component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"],
                state=STATE["OFFLINE"],
                attrs={
                    "agent_type": self.agent_type,
                    "service": self.base_service_name,
                    "description": self.description,
                    "agent_id": self.app.agent_id,
                    "prefered_name": self.agent_name,
                    "agent_name": self.agent_name,
                    "reason": "Shutting down monitoring"
                }
            )
            self.current_state = "OFFLINE"
            self.last_state_change = datetime.now()
            self.state_history = []
            self.event_correlation = {}
            if hasattr(self, 'app'):
                await self.app.close()
        except Exception as e:
            logger.error(f"Error during monitoring shutdown: {e}")
            self.current_state = "DEGRADED"
            raise

    def publish_discovered_functions(self, functions: List[Dict[str, Any]]) -> None:
        """
        Publish graph topology events for discovered functions.
        
        **CRITICAL FOR NETWORK MONITORING**:
        This method is the bridge between DDS discovery (source of truth) and
        graph topology visualization (management layer). Without this, the
        monitoring UI would only see agents but no functions or connections.
        
        **When This Is Called**:
        - Automatically via _on_function_discovered() callback when FunctionRegistry
          discovers functions via DDS advertisements
        - Each function discovery triggers this individually
        
        **What Gets Published to Graph**:
        1. Function nodes (with metadata: name, description, schema, provider_id)
        2. AGENT→SERVICE edges (this agent can call functions from this service)
           - Note: We publish agent->service edges instead of agent->function edges
           - This prevents edge explosion (10 agents × 20 services × 4 functions = 800 edges)
           - Service->function edges are already published by EnhancedServiceBase
        3. REQUESTER→PROVIDER edges (DDS RPC connection topology)
        4. EXPLICIT_CONNECTION edges (direct connections)
        5. Final READY state for agent (with discovered function count)
        
        **Why This Matters**:
        In a large distributed system with 20 services and 80 functions:
        - Operators need to see what functions are available
        - Debugging requires knowing which agents can call which functions
        - Network topology visualization shows service dependencies
        - Without this: Only agents visible, no functions/services/connections!
        
        **Architecture**:
        ```
        Service advertises → DDS → FunctionRegistry.handle_advertisement()
                                   → Calls discovery_callbacks
                                   → _on_function_discovered()
                                   → publish_discovered_functions()  ← THIS METHOD
                                   → GraphMonitor publishes nodes/edges
                                   → Monitoring UI shows topology
        ```
        
        Args:
            functions: List of function dicts, each containing:
                      - function_id: Unique identifier
                      - name: Function name
                      - description: Human-readable description
                      - provider_id: GUID of service providing this function
                      - schema: JSON schema for parameters
                      - capabilities: List of capability tags
        """
        logger.debug(f"Publishing {len(functions)} discovered functions as monitoring events")
        function_requester_guid = None
        if hasattr(self, 'function_client'):
            function_requester_guid = self._get_requester_guid(self.function_client)
            if function_requester_guid:
                self.function_requester_guid = function_requester_guid

        provider_guids = set()
        function_provider_guid = None
        # Track services discovered to avoid duplicate agent->service edges
        services_discovered = set()

        for func in functions:
            if 'provider_id' in func and func['provider_id']:
                provider_guid = func['provider_id']
                provider_guids.add(provider_guid)
                self.store_function_provider_guid(provider_guid)
                if function_provider_guid is None:
                    function_provider_guid = provider_guid

        for func in functions:
            function_id = func.get('function_id', str(uuid.uuid4()))
            function_name = func.get('name', 'unknown')
            provider_id = func.get('provider_id', '')

            # Node for function (still publish for visualization/debugging)
            self.graph.publish_node(
                component_id=function_id,
                component_type=COMPONENT_TYPE["FUNCTION"],
                state=STATE["DISCOVERING"],
                attrs={
                    "function_id": function_id,
                    "function_name": function_name,
                    "function_description": func.get('description', ''),
                    "function_schema": func.get('schema', {}),
                    "provider_id": provider_id,
                    "provider_name": func.get('provider_name', ''),
                    "reason": f"Function discovered: {function_name} ({function_id})"
                }
            )
            
            # VISUALIZATION SIMPLIFICATION: Instead of agent->function edges,
            # publish agent->service edges. The service->function edges are
            # already published by EnhancedServiceBase, so the path is implied.
            # This prevents edge explosion in large topologies (10 agents × 20 services × 4 functions = 800 edges).
            if provider_id and provider_id not in services_discovered:
                services_discovered.add(provider_id)
                self.graph.publish_edge(
                    source_id=self.app.agent_id,
                    target_id=provider_id,
                    edge_type=EDGE_TYPE["FUNCTION_CONNECTION"],
                    attrs={
                        "edge_type": "agent_service",
                        "service_id": provider_id,
                        "service_name": func.get('provider_name', 'unknown'),
                        "reason": f"Agent {self.agent_name} discovered service {func.get('provider_name', 'unknown')}"
                    },
                    component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"]
                )

        if function_requester_guid:
            for provider_guid in provider_guids:
                if provider_guid:
                    self.graph.publish_edge(
                        source_id=function_requester_guid,
                        target_id=provider_guid,
                        edge_type=EDGE_TYPE["FUNCTION_CONNECTION"],
                        attrs={
                            "edge_type": "requester_provider",
                            "requester_guid": function_requester_guid,
                            "provider_guid": provider_guid,
                            "agent_id": self.app.agent_id,
                            "agent_name": self.agent_name,
                            "reason": f"Function requester connects to provider: {function_requester_guid} -> {provider_guid}"
                        },
                        component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"]
                    )
        if function_provider_guid and function_requester_guid:
            self.graph.publish_edge(
                source_id=function_requester_guid,
                target_id=function_provider_guid,
                edge_type=EDGE_TYPE["EXPLICIT_CONNECTION"],
                attrs={
                    "edge_type": "direct_connection",
                    "requester_guid": function_requester_guid,
                    "provider_guid": function_provider_guid,
                    "agent_id": self.app.agent_id,
                    "agent_name": self.agent_name,
                    "service_name": self.base_service_name,
                    "reason": f"Direct connection: {function_requester_guid} -> {function_provider_guid}"
                },
                component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"]
            )

        function_names = [f.get('name', 'unknown') for f in functions]
        self.graph.publish_node(
            component_id=self.app.agent_id,
            component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"],
            state=STATE["READY"],
            attrs={
                "agent_type": self.agent_type,
                "service": self.base_service_name,
                "discovered_functions": len(functions),
                "function_names": function_names,
                "prefered_name": self.agent_name,
                "agent_name": self.agent_name,
                "reason": f"Agent {self.agent_name} discovered {len(functions)} functions and is ready"
            }
        )

    def create_requester_provider_edge(self, requester_guid: str, provider_guid: str):
        try:
            self.graph.publish_edge(
                source_id=requester_guid,
                target_id=provider_guid,
                edge_type=EDGE_TYPE["EXPLICIT_CONNECTION"],
                attrs={
                    "edge_type": "explicit_connection",
                    "requester_guid": requester_guid,
                    "provider_guid": provider_guid,
                    "agent_id": self.app.agent_id,
                    "agent_name": self.agent_name,
                    "service_name": self.base_service_name,
                    "reason": f"Explicit connection: {requester_guid} -> {provider_guid}"
                },
                component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"]
            )
            return True
        except Exception as e:
            logger.error(f"Error publishing explicit requester-to-provider edge: {e}")
            logger.error(traceback.format_exc())
            return False

    def set_agent_capabilities(self, supported_tasks: list[str] = None, additional_capabilities: dict = None):
        if supported_tasks:
            self.agent_capabilities["supported_tasks"] = supported_tasks
        if additional_capabilities:
            self.agent_capabilities.update(additional_capabilities)
        self.graph.publish_node(
            component_id=self.app.agent_id,
            component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"],
            state=STATE["READY"],
            attrs={
                **self.agent_capabilities,
                "prefered_name": self.agent_name,
                "agent_name": self.agent_name,
                "reason": "Agent capabilities updated"
            }
        )

    # ChainEvent and agent-to-agent monitoring logic is unchanged and remains below.
    # ... (rest of the class unchanged, including agent communication, ChainEvent, etc.)

    # --- ChainEvent publishing methods needed by OpenAIGenesisAgent and others ---

    def _publish_agent_chain_event(self, chain_id: str, call_id: str, event_type: str,
                                   source_id: str, target_id: str, status: int = 0):
        """Publish chain event for agent-to-agent interactions to Event"""
        if not hasattr(self, "unified_event_writer") or not self.unified_event_writer:
            return
        try:
            import rti.connextdds as dds
            unified_event = dds.DynamicData(self.unified_event_type)
            unified_event["event_id"] = call_id
            unified_event["kind"] = 0  # CHAIN
            unified_event["timestamp"] = int(time.time() * 1000)
            unified_event["component_id"] = source_id
            unified_event["severity"] = "INFO"
            unified_event["message"] = f"Agent chain event: {event_type}"
            # Pack ChainEvent data into payload
            chain_payload = {
                "chain_id": chain_id,
                "call_id": call_id,
                "interface_id": str(self.app.participant.instance_handle),
                "primary_agent_id": self.app.agent_id,
                "specialized_agent_ids": target_id if target_id != self.app.agent_id else "",
                "function_id": "agent_communication",
                "query_id": call_id,
                "event_type": event_type,
                "source_id": source_id,
                "target_id": target_id,
                "status": status
            }
            unified_event["payload"] = json.dumps(chain_payload)
            self.unified_event_writer.write(unified_event)
            self.unified_event_writer.flush()
        except Exception:
            pass

    def _publish_llm_call_start(self, chain_id: str, call_id: str, model_identifier: str):
        """Publish chain event for LLM call start to Event"""
        if not hasattr(self, "unified_event_writer") or not self.unified_event_writer:
            return
        try:
            import rti.connextdds as dds
            unified_event = dds.DynamicData(self.unified_event_type)
            unified_event["event_id"] = call_id
            unified_event["kind"] = 0  # CHAIN
            unified_event["timestamp"] = int(time.time() * 1000)
            unified_event["component_id"] = str(self.app.participant.instance_handle)
            unified_event["severity"] = "INFO"
            unified_event["message"] = "LLM_CALL_START"
            chain_payload = {
                "chain_id": chain_id,
                "call_id": call_id,
                "interface_id": str(self.app.participant.instance_handle),
                "primary_agent_id": self.app.agent_id,
                "specialized_agent_ids": "",
                "function_id": model_identifier,
                "query_id": str(uuid.uuid4()),
                "event_type": "LLM_CALL_START",
                "source_id": str(self.app.participant.instance_handle),
                "target_id": "OpenAI",
                "status": 0
            }
            unified_event["payload"] = json.dumps(chain_payload)
            self.unified_event_writer.write(unified_event)
            self.unified_event_writer.flush()
        except Exception:
            pass

    def _publish_llm_call_complete(self, chain_id: str, call_id: str, model_identifier: str):
        """Publish chain event for LLM call completion to Event"""
        if not hasattr(self, "unified_event_writer") or not self.unified_event_writer:
            return
        try:
            import rti.connextdds as dds
            unified_event = dds.DynamicData(self.unified_event_type)
            unified_event["event_id"] = call_id
            unified_event["kind"] = 0  # CHAIN
            unified_event["timestamp"] = int(time.time() * 1000)
            unified_event["component_id"] = "OpenAI"
            unified_event["severity"] = "INFO"
            unified_event["message"] = "LLM_CALL_COMPLETE"
            chain_payload = {
                "chain_id": chain_id,
                "call_id": call_id,
                "interface_id": str(self.app.participant.instance_handle),
                "primary_agent_id": self.app.agent_id,
                "specialized_agent_ids": "",
                "function_id": model_identifier,
                "query_id": str(uuid.uuid4()),
                "event_type": "LLM_CALL_COMPLETE",
                "source_id": "OpenAI",
                "target_id": str(self.app.participant.instance_handle),
                "status": 0
            }
            unified_event["payload"] = json.dumps(chain_payload)
            self.unified_event_writer.write(unified_event)
            self.unified_event_writer.flush()
        except Exception:
            pass

    def _publish_classification_result(self, chain_id: str, call_id: str, classified_function_name: str, classified_function_id: str):
        """Publish chain event for function classification result to Event"""
        if not hasattr(self, "unified_event_writer") or not self.unified_event_writer:
            return
        try:
            import rti.connextdds as dds
            unified_event = dds.DynamicData(self.unified_event_type)
            unified_event["event_id"] = call_id
            unified_event["kind"] = 0  # CHAIN
            unified_event["timestamp"] = int(time.time() * 1000)
            unified_event["component_id"] = str(self.app.participant.instance_handle)
            unified_event["severity"] = "INFO"
            unified_event["message"] = "CLASSIFICATION_RESULT"
            chain_payload = {
                "chain_id": chain_id,
                "call_id": call_id,
                "interface_id": str(self.app.participant.instance_handle),
                "primary_agent_id": self.app.agent_id,
                "specialized_agent_ids": "",
                "function_id": classified_function_id,
                "query_id": str(uuid.uuid4()),
                "event_type": "CLASSIFICATION_RESULT",
                "source_id": str(self.app.participant.instance_handle),
                "target_id": classified_function_id,
                "status": 0
            }
            unified_event["payload"] = json.dumps(chain_payload)
            self.unified_event_writer.write(unified_event)
            self.unified_event_writer.flush()
        except Exception:
            pass

    def _publish_classification_node(self, func_name: str, func_desc: str, reason: str):
        """Publish classification node to graph for monitoring/visualization"""
        try:
            self.graph.publish_node(
                component_id=self.app.agent_id,
                component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"],
                state=STATE["READY"],
                attrs={
                    "function_name": func_name,
                    "description": func_desc,
                    "reason": reason
                }
            )
        except Exception:
            pass

    def _publish_function_call_start(self, chain_id: str, call_id: str, function_name: str, function_id: str, target_provider_id: str = None):
        """Publish chain event for function call start to Event"""
        if not hasattr(self, "unified_event_writer") or not self.unified_event_writer:
            return
        try:
            import rti.connextdds as dds
            unified_event = dds.DynamicData(self.unified_event_type)
            unified_event["event_id"] = call_id
            unified_event["kind"] = 0  # CHAIN
            unified_event["timestamp"] = int(time.time() * 1000)
            unified_event["component_id"] = str(self.app.participant.instance_handle)
            unified_event["severity"] = "INFO"
            unified_event["message"] = "FUNCTION_CALL_START"
            chain_payload = {
                "chain_id": chain_id,
                "call_id": call_id,
                "interface_id": str(self.app.participant.instance_handle),
                "primary_agent_id": "",
                "specialized_agent_ids": "",
                "function_id": function_id,
                "query_id": str(uuid.uuid4()),
                "event_type": "FUNCTION_CALL_START",
                "source_id": str(self.app.participant.instance_handle),
                "target_id": function_id,
                "status": 0
            }
            unified_event["payload"] = json.dumps(chain_payload)
            self.unified_event_writer.write(unified_event)
            self.unified_event_writer.flush()
            
            # Also emit AGENT->SERVICE activation if provider known
            if target_provider_id:
                unified_event2 = dds.DynamicData(self.unified_event_type)
                unified_event2["event_id"] = call_id
                unified_event2["kind"] = 0  # CHAIN
                unified_event2["timestamp"] = int(time.time() * 1000)
                unified_event2["component_id"] = self.app.agent_id
                unified_event2["severity"] = "INFO"
                unified_event2["message"] = "AGENT_TO_SERVICE_START"
                chain_payload2 = {
                    "chain_id": chain_id,
                    "call_id": call_id,
                    "interface_id": str(self.app.participant.instance_handle),
                    "primary_agent_id": self.app.agent_id,
                    "specialized_agent_ids": "",
                    "function_id": function_id,
                    "query_id": str(uuid.uuid4()),
                    "event_type": "AGENT_TO_SERVICE_START",
                    "source_id": self.app.agent_id,
                    "target_id": target_provider_id,
                    "status": 0
                }
                unified_event2["payload"] = json.dumps(chain_payload2)
                self.unified_event_writer.write(unified_event2)
                self.unified_event_writer.flush()
        except Exception as e:
            logger.debug(f"Error publishing function call start event: {e}")
            pass

    def _publish_function_call_complete(self, chain_id: str, call_id: str, function_name: str, function_id: str, source_provider_id: str = None):
        """Publish chain event for function call completion to Event"""
        if not hasattr(self, "unified_event_writer") or not self.unified_event_writer:
            return
        try:
            import rti.connextdds as dds
            unified_event = dds.DynamicData(self.unified_event_type)
            unified_event["event_id"] = call_id
            unified_event["kind"] = 0  # CHAIN
            unified_event["timestamp"] = int(time.time() * 1000)
            unified_event["component_id"] = function_id
            unified_event["severity"] = "INFO"
            unified_event["message"] = "FUNCTION_CALL_COMPLETE"
            chain_payload = {
                "chain_id": chain_id,
                "call_id": call_id,
                "interface_id": str(self.app.participant.instance_handle),
                "primary_agent_id": "",
                "specialized_agent_ids": "",
                "function_id": function_id,
                "query_id": str(uuid.uuid4()),
                "event_type": "FUNCTION_CALL_COMPLETE",
                "source_id": function_id,
                "target_id": str(self.app.participant.instance_handle),
                "status": 0
            }
            unified_event["payload"] = json.dumps(chain_payload)
            self.unified_event_writer.write(unified_event)
            self.unified_event_writer.flush()
            
            # Also emit SERVICE->AGENT completion if provider known
            if source_provider_id:
                unified_event2 = dds.DynamicData(self.unified_event_type)
                unified_event2["event_id"] = call_id
                unified_event2["kind"] = 0  # CHAIN
                unified_event2["timestamp"] = int(time.time() * 1000)
                unified_event2["component_id"] = source_provider_id
                unified_event2["severity"] = "INFO"
                unified_event2["message"] = "SERVICE_TO_AGENT_COMPLETE"
                chain_payload2 = {
                    "chain_id": chain_id,
                    "call_id": call_id,
                    "interface_id": str(self.app.participant.instance_handle),
                    "primary_agent_id": self.app.agent_id,
                    "specialized_agent_ids": "",
                    "function_id": function_id,
                    "query_id": str(uuid.uuid4()),
                    "event_type": "SERVICE_TO_AGENT_COMPLETE",
                    "source_id": source_provider_id,
                    "target_id": self.app.agent_id,
                    "status": 0
                }
                unified_event2["payload"] = json.dumps(chain_payload2)
                self.unified_event_writer.write(unified_event2)
                self.unified_event_writer.flush()
        except Exception:
            pass

    async def _call_function(self, function_name: str, **kwargs) -> Any:
        """
        DECORATOR PATTERN - Monitoring Wrapper for Function Calls
        
        Overrides GenesisAgent._call_function() to add chain event monitoring.
        This is where agent→service→function interactions are tracked.
        
        **What This Method Does** (Monitoring Layer):
        1. Generate chain_id and call_id for distributed tracing
        2. Lookup function metadata (function_id, provider_id) from registry
        3. Publish FUNCTION_CALL_START event (agent→function)
        4. Publish AGENT_TO_SERVICE_START event (agent→service) if provider known
        5. Call parent implementation (actual RPC function call)
        6. Publish FUNCTION_CALL_COMPLETE event (function→agent)
        7. Publish AGENT_TO_SERVICE_COMPLETE event (service→agent) if provider known
        
        **What the Parent Does** (Business Logic - GenesisAgent._call_function):
        - Validates function exists in registry
        - Makes actual RPC call via GenericFunctionClient
        - Returns function result
        
        **Chain Event Flow**:
        ```
        Interface → Agent (INTERFACE_REQUEST)
          ├─ Agent → Service (AGENT_TO_SERVICE_START)    ← This method publishes
          │  └─ Service → Function (execution)
          │     └─ Function → Result
          └─ Service → Agent (AGENT_TO_SERVICE_COMPLETE) ← This method publishes
        Agent → Interface (INTERFACE_REPLY)
        ```
        
        Args:
            function_name: Name of the function to call
            **kwargs: Function arguments
            
        Returns:
            Function result (from parent implementation)
        """
        # Generate IDs for distributed tracing
        chain_id = str(uuid.uuid4())
        call_id = str(uuid.uuid4())
        
        # Lookup function metadata from registry
        available_functions = self._get_available_functions()
        function_metadata = available_functions.get(function_name, {})
        function_id = function_metadata.get('function_id', function_name)
        provider_id = function_metadata.get('provider_id', None)
        
        # Publish start events
        self._publish_function_call_start(
            chain_id=chain_id,
            call_id=call_id,
            function_name=function_name,
            function_id=function_id,
            target_provider_id=provider_id,
        )
        
        try:
            # Call parent implementation (actual RPC function call)
            result = await super()._call_function(function_name, **kwargs)
            
            # Publish complete events
            self._publish_function_call_complete(
                chain_id=chain_id,
                call_id=call_id,
                function_name=function_name,
                function_id=function_id,
                source_provider_id=provider_id,
            )
            
            return result
        except Exception as e:
            # Publish error event but still raise the exception
            logger.error(f"Function call failed: {function_name} - {e}")
            # TODO: Publish error event to monitoring
            raise
    
    async def _call_agent(self, agent_tool_name: str, **kwargs) -> Any:
        """
        DECORATOR PATTERN - Monitoring Wrapper for Agent-to-Agent Calls
        
        Overrides GenesisAgent._call_agent() to add chain event monitoring.
        This is where agent→agent interactions are tracked.
        
        **What This Method Does** (Monitoring Layer):
        1. Generate chain_id and call_id for distributed tracing
        2. Lookup agent metadata (agent_id) from registry
        3. Publish AGENT_TO_AGENT_START event
        4. Call parent implementation (actual agent RPC call)
        5. Publish AGENT_TO_AGENT_COMPLETE event
        
        **What the Parent Does** (Business Logic - GenesisAgent._call_agent):
        - Validates agent exists in registry
        - Makes actual RPC call via agent communication
        - Returns agent response
        
        **Chain Event Flow**:
        ```
        Agent A → Agent B (AGENT_TO_AGENT_START)    ← This method publishes
          └─ Agent B processes request
             └─ Agent B → Result
        Agent B → Agent A (AGENT_TO_AGENT_COMPLETE) ← This method publishes
        ```
        
        Args:
            agent_tool_name: Name of the agent tool to call
            **kwargs: Agent arguments (expects 'message' key)
            
        Returns:
            Agent response (from parent implementation)
        """
        # Generate IDs for distributed tracing
        chain_id = str(uuid.uuid4())
        call_id = str(uuid.uuid4())
        
        # Lookup agent metadata from registry
        available_agent_tools = self._get_available_agent_tools()
        agent_metadata = available_agent_tools.get(agent_tool_name, {})
        target_agent_id = agent_metadata.get('agent_id', agent_tool_name)
        
        # Publish start event
        self._publish_agent_to_agent_start(
            chain_id=chain_id,
            call_id=call_id,
            agent_name=agent_tool_name,
            target_agent_id=target_agent_id,
        )
        
        try:
            # Call parent implementation (actual agent RPC call)
            result = await super()._call_agent(agent_tool_name, **kwargs)
            
            # Publish complete event
            self._publish_agent_to_agent_complete(
                chain_id=chain_id,
                call_id=call_id,
                agent_name=agent_tool_name,
                target_agent_id=target_agent_id,
            )
            
            return result
        except Exception as e:
            # Publish error event but still raise the exception
            logger.error(f"Agent call failed: {agent_tool_name} - {e}")
            # TODO: Publish error event to monitoring
            raise
    
    def _publish_agent_to_agent_start(self, chain_id: str, call_id: str, agent_name: str, target_agent_id: str):
        """Publish chain event for agent-to-agent call start"""
        if not hasattr(self, "unified_event_writer") or not self.unified_event_writer:
            return
        try:
            import rti.connextdds as dds
            unified_event = dds.DynamicData(self.unified_event_type)
            unified_event["event_id"] = call_id
            unified_event["kind"] = 0  # CHAIN
            unified_event["timestamp"] = int(time.time() * 1000)
            unified_event["component_id"] = self.app.agent_id
            unified_event["severity"] = "INFO"
            unified_event["message"] = "AGENT_TO_AGENT_START"
            chain_payload = {
                "chain_id": chain_id,
                "call_id": call_id,
                "interface_id": str(self.app.participant.instance_handle),
                "primary_agent_id": self.app.agent_id,
                "specialized_agent_ids": target_agent_id,
                "function_id": "",
                "query_id": str(uuid.uuid4()),
                "event_type": "AGENT_TO_AGENT_START",
                "source_id": self.app.agent_id,
                "target_id": target_agent_id,
                "status": 0
            }
            unified_event["payload"] = json.dumps(chain_payload)
            self.unified_event_writer.write(unified_event)
            self.unified_event_writer.flush()
        except Exception as e:
            logger.debug(f"Error publishing agent-to-agent start event: {e}")
    
    def _publish_agent_to_agent_complete(self, chain_id: str, call_id: str, agent_name: str, target_agent_id: str):
        """Publish chain event for agent-to-agent call completion"""
        if not hasattr(self, "unified_event_writer") or not self.unified_event_writer:
            return
        try:
            import rti.connextdds as dds
            unified_event = dds.DynamicData(self.unified_event_type)
            unified_event["event_id"] = call_id
            unified_event["kind"] = 0  # CHAIN
            unified_event["timestamp"] = int(time.time() * 1000)
            unified_event["component_id"] = target_agent_id
            unified_event["severity"] = "INFO"
            unified_event["message"] = "AGENT_TO_AGENT_COMPLETE"
            chain_payload = {
                "chain_id": chain_id,
                "call_id": call_id,
                "interface_id": str(self.app.participant.instance_handle),
                "primary_agent_id": self.app.agent_id,
                "specialized_agent_ids": target_agent_id,
                "function_id": "",
                "query_id": str(uuid.uuid4()),
                "event_type": "AGENT_TO_AGENT_COMPLETE",
                "source_id": target_agent_id,
                "target_id": self.app.agent_id,
                "status": 0
            }
            unified_event["payload"] = json.dumps(chain_payload)
            self.unified_event_writer.write(unified_event)
            self.unified_event_writer.flush()
        except Exception as e:
            logger.debug(f"Error publishing agent-to-agent complete event: {e}")
    
    async def execute_function_with_monitoring(self,
                                               function_name: str,
                                               function_id: str,
                                               provider_id: str | None,
                                               tool_args: dict,
                                               chain_id: str,
                                               call_id: str):
        """DEPRECATED: Use _call_function() override instead.
        
        This method was the original approach for monitoring function calls,
        but it required callers to explicitly use it. The new approach overrides
        _call_function() directly so ALL function calls are automatically monitored.
        
        Kept for backward compatibility but should not be used going forward.
        """
        # Start events
        self._publish_function_call_start(
            chain_id=chain_id,
            call_id=call_id,
            function_name=function_name,
            function_id=function_id,
            target_provider_id=provider_id,
        )
        # Execute underlying function via parent implementation
        result = await super()._call_function(function_name, **tool_args)
        # Complete events
        self._publish_function_call_complete(
            chain_id=chain_id,
            call_id=call_id,
            function_name=function_name,
            function_id=function_id,
            source_provider_id=provider_id,
        )
        return result

    async def _orchestrate_tool_request(self, user_message: str, tools: List[Dict],
                                        system_prompt: str, tool_choice: str = "auto") -> Dict[str, Any]:
        """
        Monitored wrapper around tool orchestration.
        Adds monitoring events before/after calling parent orchestration.
        """
        chain_id = str(uuid.uuid4())
        call_id = str(uuid.uuid4())
        
        # Publish monitoring events
        self._publish_llm_call_start(chain_id, call_id, f"{self.__class__.__name__}.orchestration")
        
        try:
            # Call parent orchestration (GenesisAgent)
            result = await super()._orchestrate_tool_request(
                user_message, tools, system_prompt, tool_choice
            )
            
            self._publish_llm_call_complete(chain_id, call_id, f"{self.__class__.__name__}.orchestration")
            return result
            
        except Exception as e:
            self._publish_llm_call_complete(chain_id, call_id, f"{self.__class__.__name__}.orchestration.error")
            raise

    def _get_requester_guid(self, function_client) -> str:
        requester_guid = None
        try:
            if hasattr(function_client, 'requester') and hasattr(function_client.requester, 'request_datawriter'):
                requester_guid = str(function_client.requester.request_datawriter.instance_handle)
            elif hasattr(function_client, 'requester') and hasattr(function_client.requester, 'participant'):
                requester_guid = str(function_client.requester.participant.instance_handle)
            elif hasattr(function_client, 'participant'):
                requester_guid = str(function_client.participant.instance_handle)
        except Exception as e:
            logger.error(f"Error getting requester GUID: {e}")
            logger.error(traceback.format_exc())
        return requester_guid

    def store_function_requester_guid(self, guid: str):
        self.function_requester_guid = guid
        if hasattr(self, 'function_provider_guids'):
            for provider_guid in self.function_provider_guids:
                try:
                    self.graph.publish_edge(
                        source_id=guid,
                        target_id=provider_guid,
                        edge_type=EDGE_TYPE["EXPLICIT_CONNECTION"],
                        attrs={
                            "edge_type": "direct_connection",
                            "requester_guid": guid,
                            "provider_guid": provider_guid,
                            "agent_id": self.app.agent_id,
                            "agent_name": self.agent_name,
                            "service_name": self.base_service_name,
                            "reason": f"Direct connection: {guid} -> {provider_guid}"
                        },
                        component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"]
                    )
                except Exception as e:
                    logger.error(f"Error publishing direct requester-to-provider edge: {e}")
                    logger.error(traceback.format_exc())

    def store_function_provider_guid(self, guid: str):
        if not hasattr(self, 'function_provider_guids'):
            self.function_provider_guids = set()
        self.function_provider_guids.add(guid)
        if hasattr(self, 'function_requester_guid') and self.function_requester_guid:
            try:
                self.graph.publish_edge(
                    source_id=self.function_requester_guid,
                    target_id=guid,
                    edge_type=EDGE_TYPE["EXPLICIT_CONNECTION"],
                    attrs={
                        "edge_type": "direct_connection",
                        "requester_guid": self.function_requester_guid,
                        "provider_guid": guid,
                        "agent_id": self.app.agent_id,
                        "agent_name": self.agent_name,
                        "service_name": self.base_service_name,
                        "reason": f"Direct connection: {self.function_requester_guid} -> {guid}"
                    },
                    component_type=COMPONENT_TYPE["AGENT_PRIMARY"] if self.agent_type == "AGENT" else COMPONENT_TYPE["AGENT_SPECIALIZED"]
                )
            except Exception as e:
                logger.error(f"Error publishing direct requester-to-provider edge: {e}")
                logger.error(traceback.format_exc())

    def publish_monitoring_event(self, 
                               event_type: str,
                               metadata: Optional[Dict[str, Any]] = None,
                               call_data: Optional[Dict[str, Any]] = None,
                               result_data: Optional[Dict[str, Any]] = None,
                               status_data: Optional[Dict[str, Any]] = None,
                               request_info: Optional[Any] = None) -> None:
        """
        Publish a monitoring event to Event (Phase 7: V2 Only).
        
        Args:
            event_type: Type of event (AGENT_DISCOVERY, AGENT_REQUEST, etc.)
            metadata: Additional metadata about the event
            call_data: Data about the request/call (if applicable)
            result_data: Data about the response/result (if applicable)
            status_data: Data about the agent status (if applicable)
            request_info: Request information containing client ID
        """
        try:
            # Check if monitoring is set up
            if not hasattr(self, 'unified_event_writer') or not self.unified_event_writer:
                logger.debug(f"Unified event writer not initialized, skipping event: {event_type}")
                return
                
            if not hasattr(self, 'unified_event_type') or not self.unified_event_type:
                logger.debug(f"Unified event type not initialized, skipping event: {event_type}")
                return
            
            import rti.connextdds as dds
            
            # Publish to unified Event (kind=GENERAL)
            unified_event = dds.DynamicData(self.unified_event_type)
            unified_event["event_id"] = str(uuid.uuid4())
            unified_event["kind"] = 2  # GENERAL
            unified_event["timestamp"] = int(time.time() * 1000)
            unified_event["component_id"] = self.agent_name
            unified_event["severity"] = "INFO"
            # Use enum name for consistency with old MonitoringEvent
            enum_value = EVENT_TYPE_MAP.get(event_type, 0)
            unified_event["message"] = EVENT_TYPE_ENUM_NAMES.get(enum_value, event_type)
            # Pack all monitoring data into payload
            general_payload = {
                "event_type": event_type,
                "entity_type": self.agent_type,
                "entity_id": self.agent_name,
                "metadata": metadata or {},
                "call_data": call_data or {},
                "result_data": result_data or {},
                "status_data": status_data or {}
            }
            unified_event["payload"] = json.dumps(general_payload)
            self.unified_event_writer.write(unified_event)
            self.unified_event_writer.flush()
            logger.debug(f"Published monitoring event to Event: {event_type}")
            
        except Exception as e:
            logger.error(f"Error publishing monitoring event: {str(e)}")
            logger.error(traceback.format_exc())

    def _trace_discovery_status(self, phase: str):
        """
        Enhanced tracing: Discovery status at different phases.
        Available to all monitored agents regardless of LLM backend.
        
        Args:
            phase: Description of the current execution phase
        """
        logger.debug(f"🔍 TRACE: === Discovery Status: {phase} ===")
        available_functions_for_trace = self._get_available_functions()
        logger.debug(f"🔧 TRACE: Available functions: {len(available_functions_for_trace)} functions")
        for name, info in available_functions_for_trace.items():
            logger.debug(f"🔧 TRACE: - {name}: {info.get('description', 'No description')}")
        
        agent_tools_for_trace = self._get_available_agent_tools()
        logger.debug(f"🤝 TRACE: Available agent tools: {len(agent_tools_for_trace)} agent tools")
        for name, info in agent_tools_for_trace.items():
            logger.debug(f"🤝 TRACE: - {name}: {info.get('agent_name', 'Unknown agent')}")
        
        # Add internal tools tracing
        internal_tools_count = len(getattr(self, 'internal_tools_cache', {}))
        logger.debug(f"🛠️ TRACE: Internal tools cache: {internal_tools_count} internal tools")
        if hasattr(self, 'internal_tools_cache'):
            for name, info in self.internal_tools_cache.items():
                func_name = info.get('function_name', name)
                logger.debug(f"🛠️ TRACE: - {name}: {func_name}")
        
        if hasattr(self, 'agent_communication') and self.agent_communication:
            discovered = self.get_discovered_agents()
            logger.debug(f"🌐 TRACE: Raw discovered agents: {len(discovered)}")
            for agent_id, agent_info in discovered.items():
                logger.debug(f"🌐 TRACE: - {agent_id}: {agent_info.get('prefered_name', 'Unknown')}")
        
        logger.debug(f"🔍 TRACE: === End Discovery Status ===")

    def memory_write(self, item, metadata=None):
        self.memory.write(item, metadata)
        if hasattr(self, 'publish_monitoring_event'):
            self.publish_monitoring_event(event_type="memory_write", metadata={"item": item, "metadata": metadata})

    def memory_retrieve(self, query=None, k=5, policy=None):
        result = self.memory.retrieve(query, k, policy)
        if hasattr(self, 'publish_monitoring_event'):
            self.publish_monitoring_event(event_type="memory_retrieve", metadata={"query": query, "k": k, "policy": policy, "result_count": len(result) if result else 0})
        return result

    # The rest of the agent-to-agent communication, ChainEvent, and utility methods remain unchanged.
