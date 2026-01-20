#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
#                                                                                    #
# RTI grants Licensee a license to use, modify, compile, and create derivative       #
# works of the Software. Licensee has the right to distribute object form only       #
# for use with RTI products. The Software is provided "as is", with no warranty      #
# of any type, including any warranty for fitness for any purpose. RTI is under no   #
# obligation to maintain or support the Software. RTI shall not be liable for any    #
# incidental or consequential damages arising out of the use or inability to use     #
# the software.                                                                      #
# ####################################################################################

"""
MonitoredInterface - Monitoring Decorator Layer for Genesis Interfaces

This module provides the MonitoredInterface class, which adds automatic monitoring, observability,
and graph topology tracking to all Genesis interfaces. It sits on top of GenesisInterface as a
transparent decorator layer for comprehensive system-wide visibility.

=================================================================================================
ARCHITECTURE OVERVIEW - Understanding the Inheritance Hierarchy
=================================================================================================

GenesisInterface (genesis_lib/interface.py)
├─ Interface-Agnostic Business Logic:
│  ├─ connect_to_agent() - Agent discovery and connection establishment
│  ├─ send_request() - Main request sending flow
│  ├─ Agent discovery callbacks registration
│  ├─ DDS RPC requester setup and management
│  └─ Interface lifecycle management (init, close)
│
    ↓ inherits
│
MonitoredInterface (THIS FILE - genesis_lib/monitored_interface.py)
└─ Monitoring Decorator Layer (AUTOMATIC - Transparent to Users):
   ├─ __init__() - Wraps initialization with monitoring setup
   ├─ send_request() - Wraps with ChainEvent tracking (START/COMPLETE)
   ├─ close() - Wraps with OFFLINE state publishing
   ├─ connect_to_agent() - Wraps to track connected agent ID
   └─ _handle_agent_discovered() - Publishes interface-to-agent edges

=================================================================================================
WHAT YOU GET FOR FREE - Automatic Monitoring Without Writing Code
=================================================================================================

When you create an interface that inherits from MonitoredInterface, you automatically get
ALL of this monitoring without writing any monitoring code:

1. **State Machine Tracking** (via __init__() wrapper):
   - DISCOVERING → Interface initializing and discovering agents
   - READY → Interface idle and ready to send requests
   - BUSY → Interface actively sending/waiting for request
   - OFFLINE → Interface shutting down

2. **Graph Topology Publishing** (via __init__() and discovery callbacks):
   - Interface nodes: Lifecycle events, state transitions
   - Agent nodes: Discovered agents from DDS advertisements
   - Edges: Interface→Agent connections
   - Consumed by: Network visualization UI, topology analyzers

3. **Chain Event Tracking** (via send_request() wrapper):
   - INTERFACE_REQUEST_START event when request is sent
   - INTERFACE_REQUEST_COMPLETE event when reply is received
   - Tracks: chain_id, call_id, interface_id, target_agent_id
   - Consumed by: Distributed tracing, performance monitoring, debugging

4. **Agent Discovery Integration** (via discovery callbacks):
   - Automatic edge creation when agents are discovered
   - Real-time network graph updates as agents join/leave
   - Interface-to-agent relationship tracking

=================================================================================================
THE DECORATOR PATTERN - How MonitoredInterface Wraps GenesisInterface
=================================================================================================

MonitoredInterface uses the DECORATOR PATTERN to add monitoring to existing functionality.
It overrides parent methods to wrap them with monitoring, then calls super() to execute
the original business logic.

Pattern Example (simplified):

    class GenesisInterface:
        async def send_request(self, request_data):
            # Business logic: Send request via DDS RPC
            return result
    
    class MonitoredInterface(GenesisInterface):
        async def send_request(self, request_data):
            # BEFORE: Publish BUSY state + ChainEvent START
            self.graph.publish_node(state=BUSY)
            self._publish_chain_event(type="START")
            
            try:
                # EXECUTE: Call parent's business logic
                result = await super().send_request(request_data)
                
                # AFTER (success): Publish READY state + ChainEvent COMPLETE
                self.graph.publish_node(state=READY)
                self._publish_chain_event(type="COMPLETE")
                return result

Decorated Methods (What Gets Monitoring Automatically):

    1. __init__() - Initialization wrapper
       - Calls super().__init__() to create GenesisInterface
       - Sets up GraphMonitor for topology publishing
       - Publishes DISCOVERING state (discovery starting)
       - Sets up monitoring infrastructure (Event topic writer)
       - Publishes READY state (interface ready for requests)
       - Registers discovery callbacks for agent tracking
       
    2. send_request() - Request sending wrapper
       - Publishes BUSY state before sending
       - Publishes ChainEvent START to Event topic
       - Calls super().send_request() for actual RPC work
       - Publishes ChainEvent COMPLETE after reply received
       - Publishes READY state on success
       
    3. close() - Shutdown wrapper
       - Publishes OFFLINE state before cleanup
       - Calls super().close() for actual cleanup
       
    4. connect_to_agent() - Connection tracking wrapper
       - Calls super().connect_to_agent() for actual connection
       - Tracks connected agent ID for ChainEvent correlation

Helper Methods (Not Decorators - Monitoring-Specific Functionality):

    - _handle_agent_discovered() - Publishes interface→agent edges when agents join
    - _handle_agent_departed() - Tracks agent departures and updates state
    - wait_last_complete() - Utility for waiting on ChainEvent COMPLETE signal
    - _await_reply_quiet_event() - Event-driven reply completion detection

=================================================================================================
TOPIC REGISTRY IMPLEMENTATION DETAIL - Why We Need It
=================================================================================================

Similar to MonitoredAgent, MonitoredInterface uses _TOPIC_REGISTRY to handle DDS topic sharing
when multiple Genesis components (Interface + Agent + Services) run in the same process.

TL;DR: Multiple Genesis components can share a DDS Participant for efficiency. DDS requires
topic names to be unique per participant. The registry prevents "topic already exists" errors
and ensures proper cleanup (delegated to participant.close()).

See detailed architectural note in MonitoredAgent._setup_monitoring() for full explanation.

=================================================================================================
STATE MACHINE - Interface Lifecycle States
=================================================================================================

DISCOVERING → READY → BUSY → READY (normal request flow)
                    ↓
                 OFFLINE (shutdown)

States:
- DISCOVERING: Interface initializing, discovering agents
- READY: Idle, ready to send requests
- BUSY: Sending request and waiting for reply
- OFFLINE: Shutting down

"""

import logging
import time
import uuid
import json
from typing import Any, Dict, Optional
import uuid as _uuid
import asyncio
import functools

from .interface import GenesisInterface
from genesis_lib.graph_monitoring import (
    GraphMonitor,
    COMPONENT_TYPE,
    STATE,
    EDGE_TYPE,
)

logger = logging.getLogger(__name__)

def monitor_method(event_type: str):
    """
    Decorator to add monitoring to interface methods.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            request_data = args[0] if args else kwargs.get('request_data', {})
            # Publish request monitoring event as node update (BUSY)
            self.graph.publish_node(
                component_id=str(self.app.participant.instance_handle),
                component_type=COMPONENT_TYPE["INTERFACE"],
                state=STATE["BUSY"],
                attrs={
                    "interface_name": self.interface_name,
                    "service_name": self.service_name,
                    "provider_id": str(self.app.participant.instance_handle),
                    "reason": f"Interface request: {request_data}"
                }
            )
            result = await func(self, *args, **kwargs)
            # Publish response monitoring event as node update (READY)
            self.graph.publish_node(
                component_id=str(self.app.participant.instance_handle),
                component_type=COMPONENT_TYPE["INTERFACE"],
                state=STATE["READY"],
                attrs={
                    "interface_name": self.interface_name,
                    "service_name": self.service_name,
                    "provider_id": str(self.app.participant.instance_handle),
                    "reason": f"Interface response: {result}"
                }
            )
            return result
        return wrapper
    return decorator

class MonitoredInterface(GenesisInterface):
    """
    Base class for interfaces with monitoring capabilities.
    Extends GenesisInterface to add standardized monitoring.
    """

    def __init__(self, interface_name: str, service_name: str, domain_id: int = 0):
        """
        Initialize a MonitoredInterface with full observability and graph monitoring.
        
        **DECORATOR PATTERN - Monitoring Wrapper**:
        This method wraps GenesisInterface.__init__() to add monitoring infrastructure.
        All DDS communication setup is done by the parent; this just adds monitoring.
        
        **Initialization Sequence**:
        1. Call super().__init__() → creates GenesisInterface with DDS participant
        2. Create GraphMonitor for publishing topology events
        3. Setup monitoring infrastructure (DDS Event topic writer + reply reader)
        4. Publish DISCOVERING state (interface is discovering agents)
        5. Publish READY state (interface is ready to send requests)
        6. Register discovery callbacks for agent tracking
        
        **State Semantics**:
        - DISCOVERING: Interface has active DDS listeners discovering agents
        - READY: Interface can send requests and is waiting for user input
        
        **Topic Registry Pattern**:
        Uses _TOPIC_REGISTRY to share DDS topics across multiple Genesis components
        (Interface + Agent + Services) in the same process. See MonitoredAgent for
        detailed explanation of why this pattern is necessary.
        
        Args:
            interface_name: Human-readable name for the interface (e.g., "ChatInterface")
            service_name: DDS service name for agent RPC topics (e.g., "OpenAIChatService")
            domain_id: DDS domain ID (default 0)
        
        Raises:
            Exception: Re-raises any exception from parent initialization
        """
        # ===== Step 1: Initialize base GenesisInterface =====
        super().__init__(interface_name=interface_name, service_name=service_name, domain_id=domain_id)
        
        # ===== Step 2: Create unified graph monitor =====
        self.graph = GraphMonitor(self.app.participant)
        
        # ===== Step 3: Initialize monitoring-specific state =====
        # Note: available_agents and _agent_found_event are inherited from GenesisInterface
        self._connected_agent_id: Optional[str] = None  # For ChainEvent target_id correlation
        self._last_complete_event: Optional[asyncio.Event] = None  # For strict sequencing
        
        # ===== Step 4: Setup monitoring infrastructure =====
        self._setup_monitoring()
        
        # ===== Step 5: Publish DISCOVERING state =====
        interface_id = str(self.app.participant.instance_handle)
        logger.debug(f"MonitoredInterface __init__: publishing DISCOVERING for {interface_name} ({interface_id})")
        self.graph.publish_node(
            component_id=interface_id,
            component_type=COMPONENT_TYPE["INTERFACE"],
            state=STATE["DISCOVERING"],
            attrs={
                "interface_type": "INTERFACE",
                "service": self.service_name,
                "interface_id": interface_id,
                "reason": f"Interface {interface_name} is discovering agents"
            }
        )
        
        # ===== Step 6: Publish READY state =====
        self.graph.publish_node(
            component_id=interface_id,
            component_type=COMPONENT_TYPE["INTERFACE"],
            state=STATE["READY"],
            attrs={
                "interface_type": "INTERFACE",
                "service": self.service_name,
                "interface_id": interface_id,
                "reason": f"Interface {interface_name} ready for requests"
            }
        )

        # ===== Step 7: Register discovery callbacks =====
        self.register_discovery_callback(self._handle_agent_discovered)
        self.register_departure_callback(self._handle_agent_departed)

        logger.info(f"Monitored interface {interface_name} initialized successfully")

    def _setup_monitoring(self) -> None:
        """
        Set up monitoring resources for publishing interface lifecycle events.
        
        Creates DDS readers/writers for the Event topic (unified monitoring).
        All QoS settings are loaded from XML profiles - no hardcoded QoS values.
        
        **Topic Sharing Pattern**:
        Genesis allows multiple components (e.g., Interface + Agent + Services) to run
        in the same process and share a single DDS Participant. Each component needs to
        publish to the same monitoring topics.
        
        DDS Constraint: Within a single DDS Participant, each topic name must be unique.
        You cannot create the same topic twice, even if it has the same configuration.
        
        Solution: Use a process-wide topic registry keyed by (participant_id, topic_name):
        - First component creates the topic and caches it
        - Subsequent components reuse from registry
        - Simple and efficient for same-process sharing
        
        **QoS Management**:
        All QoS settings are loaded from XML profiles defined in:
        - genesis_lib/config/USER_QOS_PROFILES.xml
        
        Profiles used:
        - VolatileEventsProfile: For Event topic writers (volatile, no historical data)
        - cft_Profile: For reply readers (transient local, keeps recent history)
        
        **Failure Handling**:
        Gracefully handles DDS setup failures by setting monitoring attributes to None,
        allowing the interface to function without monitoring if DDS infrastructure is unavailable.
        
        Raises:
            No exceptions - failures are logged but don't propagate
        """
        self._unified_event_writer = None
        self._reply_reader = None
        
        try:
            import rti.connextdds as dds  # type: ignore
            from genesis_lib.utils import get_datamodel_path  # type: ignore
            from genesis_lib.graph_monitoring import _TOPIC_REGISTRY
            import os
            
            # Load datamodel for types
            datamodel_provider = dds.QosProvider(get_datamodel_path())
            
            # Load QoS profiles using singleton to avoid duplicate registration errors
            from genesis_lib.utils import get_qos_provider
            qos_provider = get_qos_provider()
            
            # ===== Create Event Topic Writer (ChainEvent monitoring) =====
            # Load QoS from XML profile - no hardcoded values
            try:
                writer_qos = qos_provider.datawriter_qos_from_profile(
                    "cft_Library::VolatileEventsProfile"
                )
                logger.debug("Loaded writer QoS from VolatileEventsProfile")
            except Exception as e:
                logger.error(f"Failed to load VolatileEventsProfile from XML: {e}")
                raise
            
            # Get Event type and create/reuse topic via registry
            unified_type = datamodel_provider.type("genesis_lib", "MonitoringEventUnified")
            participant_id = id(self.app.participant)
            event_key = (participant_id, "rti/connext/genesis/monitoring/Event")
            
            if event_key in _TOPIC_REGISTRY:
                unified_topic = _TOPIC_REGISTRY[event_key]
                logger.debug("MonitoredInterface: Reusing Event topic from registry")
            else:
                unified_topic = dds.DynamicData.Topic(
                    self.app.participant, event_key[1], unified_type
                )
                _TOPIC_REGISTRY[event_key] = unified_topic
                logger.debug("MonitoredInterface: Created and registered Event topic")
            
            self._unified_event_type = unified_type
            self._unified_event_writer = dds.DynamicData.DataWriter(
                pub=dds.Publisher(self.app.participant), 
                topic=unified_topic, 
                qos=writer_qos
            )
            
            # ===== Create Reply Reader (for COMPLETE event correlation) =====
            # Load QoS from XML profile - no hardcoded values
            try:
                reader_qos = qos_provider.datareader_qos_from_profile("cft_Library::cft_Profile")
                logger.debug("Loaded reader QoS from cft_Profile")
            except Exception as e:
                logger.error(f"Failed to load cft_Profile from XML: {e}")
                raise
            
            # Setup reply topic and async event-driven listener
            # Use unified RPC v2 types (GenesisRPCReply) instead of legacy InterfaceAgentReply
            self._reply_type = datamodel_provider.type("genesis_lib", "GenesisRPCReply")
            
            # Use unified reply topic name for RPC v2
            # All RPC communication (interface→agent, agent→agent, agent→function) uses this topic
            reply_topic_name = "rti/connext/genesis/rpc/Reply"
            
            self._reply_topic = dds.DynamicData.Topic(
                self.app.participant, 
                reply_topic_name, 
                self._reply_type
            )
            self._reply_event = asyncio.Event()
            self._last_reply_time = 0.0

            class _ReplyListener(dds.DynamicData.NoOpDataReaderListener):
                """Async event-driven listener for reply detection."""
                def __init__(self, outer, loop: asyncio.AbstractEventLoop):
                    super().__init__()
                    self._outer = outer
                    self._loop = loop
                    
                def on_data_available(self, reader):
                    """Called by DDS when new reply data arrives."""
                    try:
                        samples = reader.read()
                        if samples:
                            self._outer._last_reply_time = time.time()
                            # Signal on the main event loop (thread-safe)
                            self._loop.call_soon_threadsafe(self._outer._reply_event.set)
                    except Exception:
                        pass

            self._reply_reader = dds.DynamicData.DataReader(
                subscriber=self.app.subscriber,
                topic=self._reply_topic,
                qos=reader_qos,
                listener=_ReplyListener(self, asyncio.get_running_loop()),
                mask=dds.StatusMask.DATA_AVAILABLE
            )
            
            logger.info("MonitoredInterface: Event monitoring setup successful (all QoS from XML)")
            
        except Exception as e:
            # Monitoring is optional; continue without it if DDS setup fails
            logger.warning(f"MonitoredInterface: Event setup FAILED: {e}")
            import traceback
            traceback.print_exc()
            self._unified_event_writer = None
            self._reply_reader = None



    async def _handle_agent_discovered(self, agent_info: dict):
        """
        Monitoring decorator for agent discovery.
        
        **DECORATOR PATTERN - Monitoring Wrapper**:
        Calls parent implementation (business logic) then adds monitoring.
        
        **Parent (GenesisInterface) Does** (Business Logic):
        - Signals _agent_found_event for connection establishment
        - No caching - DDS (TRANSIENT_LOCAL) is the single source of truth
        
        **This Method Does** (Monitoring Layer):
        - Publishes interface→agent edge to graph topology
        - Logs discovery for monitoring dashboards
        
        **Discovery Integration**:
        This callback bridges DDS discovery (source of truth) with graph monitoring
        (visualization layer). When an agent publishes its advertisement to DDS,
        this callback is triggered automatically.
        
        **Graph Events Published**:
        - Edge from interface to agent (INTERFACE_TO_AGENT type)
        - Includes: interface_name, agent_name, service_name, connection metadata
        - Consumed by: Network topology viewers, monitoring dashboards
        
        Args:
            agent_info: Dict with keys: instance_id, prefered_name, service_name,
                       message, default_capable, timestamp
        """
        # ===== BUSINESS LOGIC: Let parent handle state management =====
        await super()._handle_agent_discovered(agent_info)
        
        # ===== MONITORING: Add observability on top =====
        instance_id = agent_info['instance_id']
        prefered_name = agent_info['prefered_name']
        service_name = agent_info['service_name']
        
        # Backward-compatible log message for tests
        logger.debug(f"<MonitoredInterface Handler> Agent Discovered: {prefered_name} ({service_name}) - ID: {instance_id}")

        interface_id = str(self.app.participant.instance_handle)
        # Publish edge discovery event for interface-to-agent connection
        self.graph.publish_edge(
            source_id=interface_id,
            target_id=instance_id,
            edge_type=EDGE_TYPE["INTERFACE_TO_AGENT"],
            attrs={
                "edge_type": "interface_to_agent",
                "interface_name": self.interface_name,
                "agent_name": prefered_name,
                "service_name": service_name,
                "connection_established": True,
                "reason": f"Interface {interface_id} discovered agent {prefered_name} ({instance_id})"
            },
            component_type=COMPONENT_TYPE["INTERFACE"]
        )
        logger.debug(f"Published EDGE_DISCOVERY event: Interface {interface_id} -> Agent {instance_id}")



    async def connect_to_agent(self, service_name: str, timeout_seconds: Optional[float] = None) -> bool:
        """
        Override to track connected agent ID for ChainEvent correlation.
        
        **DECORATOR PATTERN - Monitoring Wrapper**:
        This method wraps GenesisInterface.connect_to_agent() to remember which
        agent we're connected to. This is critical for ChainEvent target_id tracking.
        
        **What This Method Does** (Monitoring Layer):
        1. Call parent implementation (actual connection logic)
        2. If successful, lookup agent's instance_id by service_name
        3. Store connected agent ID for future ChainEvent emissions
        
        **What the Parent Does** (Business Logic):
        - Waits for agent discovery via DDS advertisements
        - Validates agent exists and is reachable
        - Establishes connection readiness
        
        **Why This Matters**:
        ChainEvent tracking requires knowing the target_id (agent GUID) for proper
        distributed tracing. Without this, we couldn't correlate interface requests
        with agent responses in the monitoring UI.
        
        Args:
            service_name: Name of the agent service to connect to
            timeout_seconds: Optional timeout for connection (None = wait forever)
        
        Returns:
            True if connection successful, False otherwise
        """
        ok = await super().connect_to_agent(service_name, timeout_seconds=timeout_seconds)
        if ok:
            # Try to resolve the chosen agent's instance_id by service_name or name
            try:
                for aid, info in self.available_agents.items():
                    if info.get('service_name') == service_name or info.get('prefered_name') == service_name:
                        self._connected_agent_id = aid
                        logger.debug(f"Connected to agent {service_name} (ID: {aid})")
                        break
            except Exception:
                pass
        return ok



    async def _handle_agent_departed(self, instance_id: str):
        """
        Monitoring decorator for agent departure.
        
        **DECORATOR PATTERN - Monitoring Wrapper**:
        Calls parent implementation (business logic) then adds monitoring.
        
        **Parent (GenesisInterface) Does** (Business Logic):
        - Logs departure event
        - No cache cleanup - DDS automatically filters out NOT_ALIVE instances
        
        **This Method Does** (Monitoring Layer):
        - Checks if departed agent was our connected agent
        - Clears _connected_agent_id if needed (ChainEvent tracking)
        - Logs departure for monitoring dashboards
        
        **Departure Handling**:
        This callback is triggered when DDS detects an agent has gone offline
        (either gracefully or via liveliness timeout).
        
        **Why This Matters**:
        Detecting agent departure allows interfaces to:
        - Update their connection state immediately
        - Display accurate network topology in monitoring UI
        - Trigger reconnection or failover logic
        - Avoid sending requests to dead agents
        
        Args:
            instance_id: GUID of the departed agent
        """
        # ===== BUSINESS LOGIC: Let parent handle state removal =====
        await super()._handle_agent_departed(instance_id)
        
        # ===== MONITORING: Check if this affects our ChainEvent tracking =====
        if instance_id == self._connected_agent_id:
            logger.warning(f"<MonitoredInterface> Connected agent departed: {instance_id}. Connection lost.")
            self._connected_agent_id = None  # Clear ChainEvent target_id




    @monitor_method("INTERFACE_REQUEST")
    async def send_request(self, request_data: Dict[str, Any], timeout_seconds: float = 10.0) -> Optional[Dict[str, Any]]:
        """
        Send request to connected agent with automatic ChainEvent monitoring.
        
        **DECORATOR PATTERN - Monitoring Wrapper**:
        This method is decorated by @monitor_method AND wraps the parent's send_request()
        to add comprehensive distributed tracing via ChainEvent emissions.
        
        **What This Method Does** (Monitoring Layer):
        1. @monitor_method publishes BUSY state before execution
        2. Create completion event for strict sequencing
        3. Publish INTERFACE_REQUEST_START ChainEvent to Event topic
        4. Call parent implementation (actual DDS RPC request)
        5. Publish INTERFACE_REQUEST_COMPLETE ChainEvent to Event topic
        6. @monitor_method publishes READY state after execution
        7. Signal completion event for external coordination
        
        **What the Parent Does** (Business Logic - GenesisInterface.send_request):
        - Validates request data structure
        - Makes actual DDS RPC call to agent
        - Waits for agent reply with timeout
        - Returns agent response
        
        **ChainEvent Flow**:
        ```
        Interface sends request
          ↓
        INTERFACE_REQUEST_START event (this method)
          ↓
        Agent processes request (tracked by MonitoredAgent)
          ↓
        INTERFACE_REQUEST_COMPLETE event (this method)
          ↓
        Interface receives reply
        ```
        
        **Why ChainEvent Matters**:
        ChainEvent tracking enables:
        - Distributed tracing across interface→agent→service→function calls
        - Performance monitoring (latency, bottlenecks)
        - Debugging request flow issues
        - Correlation of logs across multiple components
        
        **Correlation IDs**:
        - chain_id: Unique ID for entire request chain (persists across START/COMPLETE)
        - call_id: Unique ID for this specific request
        - interface_id: GUID of this interface
        - target_id: GUID of connected agent (if known)
        
        Args:
            request_data: Request dictionary with 'message' key and optional metadata
            timeout_seconds: Maximum time to wait for reply (default: 10 seconds)
        
        Returns:
            Response dictionary from agent, or None if timeout/error
        
        Raises:
            Exception: Re-raises any exception from parent after logging
        """
        # Prepare completion event for strict sequencing
        try:
            self._last_complete_event = asyncio.Event()
        except Exception:
            self._last_complete_event = None
        
        # ===== Publish INTERFACE_REQUEST_START ChainEvent =====
        if self._unified_event_writer is not None:
            try:
                import rti.connextdds as dds  # type: ignore
                chain_id = str(_uuid.uuid4())
                call_id = str(_uuid.uuid4())
                
                # Publish to unified Event (kind=CHAIN)
                unified_ev = dds.DynamicData(self._unified_event_type)
                unified_ev["event_id"] = call_id
                unified_ev["kind"] = 0  # CHAIN
                unified_ev["timestamp"] = int(time.time() * 1000)
                unified_ev["component_id"] = str(self.app.participant.instance_handle)
                unified_ev["severity"] = "INFO"
                unified_ev["message"] = "INTERFACE_REQUEST_START"
                # Pack ChainEvent data into payload
                chain_payload = {
                    "chain_id": chain_id,
                    "call_id": call_id,
                    "interface_id": str(self.app.participant.instance_handle),
                    "primary_agent_id": "",
                    "specialized_agent_ids": "",
                    "function_id": "",
                    "query_id": call_id,
                    "event_type": "INTERFACE_REQUEST_START",
                    "source_id": str(self.app.participant.instance_handle),
                    "target_id": self._connected_agent_id or "",
                    "status": 0
                }
                unified_ev["payload"] = json.dumps(chain_payload)
                self._unified_event_writer.write(unified_ev)
                self._unified_event_writer.flush()
                logger.debug("ChainEvent START published to Event")
                
                # Persist IDs for completion correlation
                self._last_chain_id = chain_id
                self._last_call_id = call_id
            except Exception:
                pass

        # ===== Call parent implementation (actual RPC request) =====
        result = await super().send_request(request_data, timeout_seconds)

        # ===== Publish INTERFACE_REQUEST_COMPLETE ChainEvent =====
        if self._unified_event_writer is not None:
            try:
                import rti.connextdds as dds  # type: ignore
                # Reuse IDs from START when available
                chain_id = getattr(self, "_last_chain_id", None) or str(_uuid.uuid4())
                call_id = getattr(self, "_last_call_id", None) or str(_uuid.uuid4())
                
                # Publish to unified Event (kind=CHAIN)
                unified_ev = dds.DynamicData(self._unified_event_type)
                unified_ev["event_id"] = call_id
                unified_ev["kind"] = 0  # CHAIN
                unified_ev["timestamp"] = int(time.time() * 1000)
                unified_ev["component_id"] = self._connected_agent_id or str(self.app.participant.instance_handle)
                unified_ev["severity"] = "INFO"
                unified_ev["message"] = "INTERFACE_REQUEST_COMPLETE"
                # Pack ChainEvent data into payload
                chain_payload = {
                    "chain_id": chain_id,
                    "call_id": call_id,
                    "interface_id": str(self.app.participant.instance_handle),
                    "primary_agent_id": "",
                    "specialized_agent_ids": "",
                    "function_id": "",
                    "query_id": call_id,
                    "event_type": "INTERFACE_REQUEST_COMPLETE",
                    "source_id": self._connected_agent_id or "",
                    "target_id": str(self.app.participant.instance_handle),
                    "status": 0
                }
                unified_ev["payload"] = json.dumps(chain_payload)
                self._unified_event_writer.write(unified_ev)
                self._unified_event_writer.flush()
                logger.debug("ChainEvent COMPLETE published to Event")
                
                # Clear persisted IDs
                try:
                    del self._last_chain_id
                    del self._last_call_id
                except Exception:
                    pass
            except Exception:
                pass

        # Signal completion event for strict sequencing even if ChainEvent emission failed
        try:
            if self._last_complete_event is not None:
                self._last_complete_event.set()
        except Exception:
            pass

        return result



    async def _await_reply_quiet_event(self, total_window_seconds: float = 10.0, quiet_seconds: float = 2.0) -> None:
        """
        Wait until no OpenAIAgentReply arrives for 'quiet_seconds', bounded by 'total_window_seconds'.
        
        **Event-Driven Reply Detection**:
        Uses async event listener to detect reply arrivals instead of polling.
        This method waits for a "quiet period" where no new replies arrive,
        indicating the agent has finished streaming/multi-turn responses.
        
        **Use Case**:
        For streaming responses or multi-turn conversations, the agent may send
        multiple reply messages. This method waits until the stream quiets down
        before proceeding, ensuring we've received the complete response.
        
        **Algorithm**:
        1. Clear any prior events
        2. Wait for new reply or quiet_seconds timeout
        3. If new reply arrives, reset quiet timer and continue
        4. If quiet_seconds passes with no replies, return (stream complete)
        5. If total_window_seconds expires, return regardless (safety timeout)
        
        Args:
            total_window_seconds: Maximum total time to wait (default: 10 seconds)
            quiet_seconds: Quiet period indicating stream completion (default: 2 seconds)
        """
        if not getattr(self, "_reply_reader", None) or not getattr(self, "_reply_event", None):
            return
        deadline = time.time() + total_window_seconds
        # Clear any prior event state
        try:
            self._reply_event.clear()
        except Exception:
            pass
        last_seen = time.time()
        while time.time() < deadline:
            # Wait for a new reply or until quiet_seconds passes
            try:
                timeout = max(0.0, min(quiet_seconds, deadline - time.time()))
                await asyncio.wait_for(self._reply_event.wait(), timeout=timeout)
                # Got a reply; reset event and extend quiet timer
                self._reply_event.clear()
                last_seen = time.time()
                continue
            except asyncio.TimeoutError:
                # Quiet period elapsed - stream complete
                break
            except Exception:
                break

    async def wait_last_complete(self, timeout_seconds: float = 5.0) -> bool:
        """
        Wait for the most recent request's completion signal (from ChainEvent COMPLETE).
        
        **Synchronization Utility**:
        Provides external code a way to wait for ChainEvent COMPLETE emission
        before proceeding. Useful for testing or strict sequencing requirements.
        
        **Use Case**:
        Tests or monitoring tools can call this after send_request() to ensure
        the COMPLETE event has been published to DDS before validating event logs.
        
        **Implementation**:
        Uses an asyncio.Event set by send_request() after publishing COMPLETE.
        This is more reliable than time.sleep() for synchronization.
        
        Args:
            timeout_seconds: Maximum time to wait (default: 5 seconds)
        
        Returns:
            True if completion event observed before timeout, False otherwise
        """
        ev = getattr(self, "_last_complete_event", None)
        if ev is None:
            return False
        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout_seconds)
            return True
        except Exception:
            return False

    async def close(self):
        """
        Gracefully shut down the interface with automatic state notification.
        
        **DECORATOR PATTERN - Monitoring Wrapper**:
        This method wraps GenesisInterface.close() to publish OFFLINE state
        before cleanup, notifying the network that the interface is shutting down.
        
        **Shutdown Sequence**:
        1. Publish OFFLINE state to graph topology
        2. Call parent's close() ← ACTUAL CLEANUP HAPPENS HERE
           - GenesisApp.close() shuts down DDS participant, RPC service, etc.
        
        **Why OFFLINE State Matters**:
        - Notifies network topology that interface is no longer available
        - Allows monitoring systems to update status in real-time
        - Enables clean removal from network graphs/dashboards
        - Prevents routing requests to dead interfaces
        
        **What Gets Cleaned Up** (in parent GenesisApp.close()):
        - DDS Participant (closes all topics, readers, writers)
        - RPC Requester (stops accepting requests)
        - Discovery listeners (cleanup agent monitoring)
        - Monitoring infrastructure (Event writers, reply readers)
        
        Raises:
            Exception: Re-raises any exception from cleanup after logging
        """
        try:
            interface_id = str(self.app.participant.instance_handle)
            logger.debug(f"MonitoredInterface.close: publishing OFFLINE for {self.interface_name} ({interface_id})")
            self.graph.publish_node(
                component_id=interface_id,
                component_type=COMPONENT_TYPE["INTERFACE"],
                state=STATE["OFFLINE"],
                attrs={
                    "interface_type": "INTERFACE",
                    "service": self.service_name,
                    "interface_id": interface_id,
                    "reason": f"Interface {self.interface_name} shutting down"
                }
            )
            await super().close()
        except Exception as e:
            logger.error(f"Error closing monitored interface: {str(e)}")

