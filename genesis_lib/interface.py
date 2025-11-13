"""
GenesisInterface - Base Class for All Genesis Interfaces

This module provides the GenesisInterface base class, which establishes the core interface
functionality for communicating with Genesis agents via DDS RPC. It handles agent discovery,
connection establishment, and request/reply communication patterns.

=================================================================================================
ARCHITECTURE OVERVIEW - Understanding the Interface Layer
=================================================================================================

The Genesis architecture has three primary layers:

1. **Interface Layer** (THIS FILE - GenesisInterface):
   - User-facing entry point to the Genesis system
   - Discovers available agents via DDS advertisements
   - Establishes RPC connections to agents
   - Sends requests and receives replies
   - Manages connection lifecycle

2. **Agent Layer** (GenesisAgent → MonitoredAgent → Provider implementations):
   - Processes incoming requests from interfaces
   - Orchestrates LLM calls and tool execution
   - Returns responses to interfaces

3. **Service Layer** (GenesisService):
   - Provides external functions callable by agents
   - Advertises capabilities via DDS
   - Executes function calls via RPC

GenesisInterface sits at the top of this hierarchy, providing the entry point for external
applications to interact with the Genesis agent ecosystem.

DESIGN NOTE: Why the interface uses a thin direct RPC path
==========================================================
Genesis uses one unified DDS data model (GenesisRPCRequest/Reply) everywhere. The interface
path uses a thin, direct rti.rpc + DynamicData setup rather than the higher-level
GenesisRequester/GenesisReplier wrappers to:
- Preserve exact log formats and timings expected by tests/monitoring
- Avoid forcing a function-call envelope on arbitrary chat/control messages
Service function execution benefits from the wrappers; interface/agent messaging stays
intentionally minimal and flexible.

=================================================================================================
INHERITANCE HIERARCHY - How Interface Classes Relate
=================================================================================================

GenesisInterface (THIS FILE - genesis_lib/interface.py)
├─ Core Business Logic:
│  ├─ __init__() - Initialize DDS participant, setup agent discovery
│  ├─ _setup_advertisement_listener() - Configure DDS readers for agent advertisements
│  ├─ connect_to_agent() - Establish RPC connection to specific agent
│  ├─ send_request() - Send request to agent, wait for reply with RPC v2 targeting
│  ├─ close() - Clean up DDS resources
│  ├─ _handle_agent_discovered() - Update state when agents join
│  ├─ _handle_agent_departed() - Update state when agents leave
│  └─ register_discovery_callback() - Register callbacks for agent lifecycle events
│
    ↓ inherits
│
MonitoredInterface (genesis_lib/monitored_interface.py)
└─ Monitoring Decorator Layer (AUTOMATIC - Transparent to Users):
   ├─ Wraps methods with state transitions (READY→BUSY→READY)
   ├─ Publishes graph topology events (nodes, edges)
   ├─ Tracks ChainEvents for distributed tracing
   └─ No business logic - pure observability layer

=================================================================================================
KEY RESPONSIBILITIES - What GenesisInterface Does
=================================================================================================

1. **Agent Discovery** (via DDS Advertisements):
   - Listens for agent advertisements on the unified Advertisement topic
   - Maintains cache of available agents (available_agents dict)
   - Triggers callbacks when agents join/leave
   - Supports content filtering (only AGENT advertisements, not SERVICE/FUNCTION)

2. **RPC Connection Management**:
   - Creates DDS RPC Requester after agent discovery
   - Waits for DDS endpoint matching before declaring connection ready
   - Supports connection timeout and retry logic

3. **Request/Reply Communication** (RPC v2 Protocol):
   - **First Request**: Broadcasts to all agents with matching service_name (empty target_service_guid)
   - **First Reply**: Captures replier_service_guid from response
   - **Subsequent Requests**: Targeted to specific agent via content filtering (locked GUID)
   - **Failover Support**: reset_target=True forces broadcast again
   - Handles timeout, drains multiple replies, returns final reply

4. **State Management**:
   - Tracks available agents in available_agents dictionary
   - Signals agent_found_event when first agent discovered
   - Manages target_agent_guid for RPC v2 targeting
   - Supports service_instance_tag for blue/green deployments

=================================================================================================
RPC V2 PROTOCOL - How Interface→Agent Communication Works
=================================================================================================

The interface uses an optimized broadcast→target pattern for efficient agent communication:

**Initial Request (Broadcast)**:
```
Interface: "I need service 'MathService', broadcast to all"
           target_service_guid = "" (empty = broadcast)
           ↓
Agent 1:   [Receives request, processes, replies with GUID]
Agent 2:   [Receives request, ignores - already handled]
Agent 3:   [Receives request, ignores - already handled]
           ↓
Agent 1:   "Here's your response"
           replier_service_guid = "agent-1-guid-12345"
           ↓
Interface: "Got response from agent-1-guid-12345, locking to this agent"
           self.target_agent_guid = "agent-1-guid-12345"
```

**Subsequent Requests (Targeted)**:
```
Interface: "Send to agent-1-guid-12345 specifically"
           target_service_guid = "agent-1-guid-12345"
           ↓
Agent 1:   [Receives via content filter, processes, replies]
Agent 2:   [Filtered out by DDS - never sees request]
Agent 3:   [Filtered out by DDS - never sees request]
           ↓
Agent 1:   "Here's your response"
           ↓
Interface: [Continues using same agent]
```

**Why This Matters**:
- **Efficiency**: After first request, only target agent processes messages
- **Consistency**: Same agent handles all requests in a conversation
- **Failover**: Can reset target and broadcast again if agent fails

=================================================================================================
AGENT DISCOVERY - How Interfaces Find Agents
=================================================================================================

Discovery uses the unified Advertisement topic pattern:

**Publication (by Agents)**:
```python
# In MonitoredAgent.__init__():
AdvertisementBus.get(participant).publish(
    kind=AGENT,  # Distinguishes from SERVICE/FUNCTION ads
    name="MathAgent",
    service_name="MathService",
    advertisement_id="agent-guid-12345",
    ...
)
```

**Subscription (by Interfaces)**:
```python
# In GenesisInterface._setup_advertisement_listener():
filtered_topic = ContentFilteredTopic(
    advertisement_topic,
    filter="kind = 1"  # AGENT kind only
)
reader = DataReader(filtered_topic, ...)
```

**Content Filtering Benefits**:
- Interface only receives AGENT advertisements (not SERVICE/FUNCTION)
- Reduces network traffic and CPU usage
- Filtering happens at DDS layer (very efficient)

=================================================================================================
STATE MANAGEMENT - Interface Lifecycle
=================================================================================================

Interface lifecycle is simple compared to agents:

1. **INITIALIZATION**:
   - Create DDS participant
   - Setup advertisement reader (agent discovery)
   - Initialize state: available_agents = {}, requester = None

2. **DISCOVERY PHASE** (continuous):
   - Listen for agent advertisements
   - Update available_agents cache
   - Trigger discovery callbacks

3. **CONNECTION**:
   - User calls connect_to_agent(service_name)
   - Create RPC Requester
   - Wait for DDS endpoint match
   - Ready to send requests

4. **REQUEST/REPLY** (repeated):
   - send_request() broadcasts or targets agent
   - Wait for reply with timeout
   - Return response to caller

5. **CLEANUP**:
   - close() shuts down requester and participant
   - All DDS resources released

=================================================================================================
CALLBACK SYSTEM - Extensibility for Monitoring and Custom Logic
=================================================================================================

GenesisInterface provides callback registration for external observers:

**Discovery Callbacks**:
```python
async def on_agent_discovered(agent_info):
    print(f"Found agent: {agent_info['prefered_name']}")
    
interface.register_discovery_callback(on_agent_discovered)
```

**Departure Callbacks**:
```python
async def on_agent_departed(instance_id):
    print(f"Agent {instance_id} left")
    
interface.register_departure_callback(on_agent_departed)
```

**Why Callbacks Matter**:
- **MonitoredInterface** uses callbacks to publish graph topology events
- **User Applications** can use callbacks for custom logging/monitoring
- **Separation of Concerns**: Core logic doesn't know about monitoring

=================================================================================================
QOS CONFIGURATION - All Settings from XML
=================================================================================================

Following Genesis project standards, ALL QoS settings are loaded from XML:

**Advertisement Reader QoS** (from USER_QOS_PROFILES.xml):
- Profile: `cft_Library::cft_Profile`
- Durability: TRANSIENT_LOCAL (get history of existing agents)
- Reliability: RELIABLE (don't miss agent announcements)
- History: KEEP_LAST with depth 500 (plenty of room for many agents)

**Why XML QoS**:
- **Maintainability**: Change QoS without code changes
- **Consistency**: Same QoS across all components
- **Best Practices**: Industry standard for DDS configuration

=================================================================================================
TYPICAL USAGE PATTERN
=================================================================================================

```python
import asyncio
from genesis_lib.monitored_interface import MonitoredInterface

async def main():
    # Create interface
    interface = MonitoredInterface(
        interface_name="ChatInterface",
        service_name="OpenAIChatService",
        domain_id=0
    )
    
    # Wait for agent discovery (automatic via advertisements)
    await asyncio.sleep(2)
    
    # Connect to agent
    connected = await interface.connect_to_agent("OpenAIChatService", timeout_seconds=10.0)
    if not connected:
        print("Failed to connect to agent")
        return
    
    # Send requests (first = broadcast, subsequent = targeted)
    response = await interface.send_request(
        {"message": "What is 2+2?", "conversation_id": "conv-123"},
        timeout_seconds=30.0
    )
    print(f"Agent response: {response['message']}")
    
    # Send follow-up (automatically targeted to same agent)
    response2 = await interface.send_request(
        {"message": "What about 3+3?", "conversation_id": "conv-123"},
        timeout_seconds=30.0
    )
    print(f"Agent response: {response2['message']}")
    
    # Cleanup
    await interface.close()

asyncio.run(main())
```

=================================================================================================
COMPARISON: GenesisInterface vs MonitoredInterface
=================================================================================================

**Use GenesisInterface when**:
- Building lightweight applications without monitoring
- Benchmarking performance (monitoring has overhead)
- Embedded systems with resource constraints

**Use MonitoredInterface when**:
- Production deployments (recommended)
- Need distributed tracing and observability
- Want network topology visualization
- Debugging complex multi-agent interactions

**Key Difference**:
- GenesisInterface: Business logic only
- MonitoredInterface: Business logic + automatic monitoring (via decorator pattern)

Copyright (c) 2025, RTI & Jason Upchurch
"""

import time
import logging
import os
from abc import ABC
from typing import Any, Dict, Optional, List, Callable, Coroutine
import rti.connextdds as dds
import rti.rpc as rpc
from .genesis_app import GenesisApp
import uuid
import json
from genesis_lib.utils import get_datamodel_path
from genesis_lib.advertisement_bus import AdvertisementBus
import asyncio
import traceback

# Get logger
logger = logging.getLogger(__name__)

class RegistrationListener(dds.DynamicData.NoOpDataReaderListener):
    """Listener for registration announcements (legacy)"""
    def __init__(self, 
                 interface, 
                 loop: asyncio.AbstractEventLoop,
                 on_discovered: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None, 
                 on_departed: Optional[Callable[[str], Coroutine[Any, Any, None]]] = None):
        logger.debug("🔧 TRACE: RegistrationListener class init calling now")
        super().__init__()
        self.interface = interface
        self.received_announcements = {}  # Track announcements by instance_id
        self.on_agent_discovered = on_discovered
        self.on_agent_departed = on_departed
        self._loop = loop
        logger.debug("🔧 TRACE: Registration listener initialized with callbacks")
        
    def on_data_available(self, reader):
        """Handle new registration announcements and departures"""
        logger.debug("🔔 TRACE: RegistrationListener.on_data_available called (sync)")
        try:
            samples = reader.read()
            logger.debug(f"📦 TRACE: Read {len(samples)} samples from reader")
            
            for data, info in samples:
                if data is None:
                    logger.warning(f"⚠️ TRACE: Skipping sample - data is None. Instance Handle: {info.instance_handle if info else 'Unknown'}")
                    continue
                    
                instance_id = data.get_string('instance_id')
                if not instance_id:
                    logger.warning(f"⚠️ TRACE: Skipping sample - missing instance_id. Data: {data}")
                    continue

                if info.state.instance_state == dds.InstanceState.ALIVE:
                    if instance_id not in self.received_announcements:
                        service_name = data.get_string('service_name')
                        prefered_name = data.get_string('prefered_name')
                        agent_info = {
                            'message': data.get_string('message'),
                            'prefered_name': prefered_name,
                            'default_capable': data.get_int32('default_capable'),
                            'instance_id': instance_id,
                            'service_name': service_name,
                            'timestamp': time.time()
                        }
                        self.received_announcements[instance_id] = agent_info
                        logger.debug(f"✨ TRACE: Agent DISCOVERED: {prefered_name} ({service_name}) - ID: {instance_id}")
                        if self.on_agent_discovered:
                            # Schedule the async task creation onto the main loop thread
                            self._loop.call_soon_threadsafe(asyncio.create_task, self._run_discovery_callback(agent_info))
                elif info.state.instance_state in [dds.InstanceState.NOT_ALIVE_DISPOSED, dds.InstanceState.NOT_ALIVE_NO_WRITERS]:
                    if instance_id in self.received_announcements:
                        departed_info = self.received_announcements.pop(instance_id)
                        logger.debug(f"👻 TRACE: Agent DEPARTED: {departed_info.get('prefered_name', 'N/A')} - ID: {instance_id} - Reason: {info.state.instance_state}")
                        if self.on_agent_departed:
                            # Schedule the async task creation onto the main loop thread
                            self._loop.call_soon_threadsafe(asyncio.create_task, self._run_departure_callback(instance_id))
        except dds.Error as dds_e:
            logger.error(f"❌ TRACE: DDS Error in on_data_available: {dds_e}")
            logger.error(traceback.format_exc())
        except Exception as e:
            logger.error(f"❌ TRACE: Unexpected error processing registration announcement: {e}")
            logger.error(traceback.format_exc())

    def on_subscription_matched(self, reader, status):
        """Track when registration publishers are discovered"""
        logger.debug(f"🤝 TRACE: Registration subscription matched event. Current count: {status.current_count}")
        # We're not using this for discovery anymore, just logging for debugging

    # --- Helper methods to run async callbacks --- 
    async def _run_discovery_callback(self, agent_info: Dict[str, Any]):
        """Safely run the discovery callback coroutine."""
        try:
            # Check again in case the callback was unset between scheduling and running
            if self.on_agent_discovered: 
                await self.on_agent_discovered(agent_info)
        except Exception as cb_e:
            instance_id = agent_info.get('instance_id', 'UNKNOWN')
            logger.error(f"❌ TRACE: Error executing on_agent_discovered callback task for {instance_id}: {cb_e}")
            logger.error(traceback.format_exc())
            
    async def _run_departure_callback(self, instance_id: str):
        """Safely run the departure callback coroutine."""
        try:
            # Check again
            if self.on_agent_departed:
                await self.on_agent_departed(instance_id)
        except Exception as cb_e:
            logger.error(f"❌ TRACE: Error executing on_agent_departed callback task for {instance_id}: {cb_e}")
            logger.error(traceback.format_exc())
    # --- End helper methods --- 

class GenesisInterface(ABC):
    """
    Base class for all Genesis interfaces.
    
    Provides core functionality for discovering agents, establishing RPC connections,
    and sending requests to Genesis agents via DDS. This class can be used directly
    for lightweight applications or extended by MonitoredInterface for production
    deployments with comprehensive observability.
    """
    def __init__(self, interface_name: str, service_name: str, domain_id: int = 0):
        """
        Initialize a GenesisInterface for communication with Genesis agents.
        
        **Initialization Sequence**:
        1. Create GenesisApp (DDS participant + basic infrastructure)
        2. Initialize state: available_agents dict, agent_found_event
        3. Load DDS types from XML (GenesisRPCRequest/Reply - unified model)
        4. Setup advertisement monitoring (agent discovery via DDS)
        
        **State After Initialization**:
        - DDS participant is active
        - Advertisement reader is listening for agents
        - No RPC requester yet (created later by connect_to_agent)
        - available_agents is empty (populated as agents join)
        
        **Agent Discovery**:
        Discovery happens automatically after initialization. Agents that publish
        advertisements will trigger callbacks registered via register_discovery_callback().
        MonitoredInterface uses these callbacks to publish graph topology events.
        
        Args:
            interface_name: Human-readable name for this interface (e.g., "ChatInterface")
            service_name: Service name to use for RPC topics (e.g., "OpenAIChatService")
            domain_id: DDS domain ID (default: 0)
        
        Raises:
            Exception: If DDS initialization or advertisement setup fails
        """
        self.interface_name = interface_name
        self.service_name = service_name # This is the *interface's* service name, may differ from agent's
        self.app = GenesisApp(preferred_name=interface_name, domain_id=domain_id)
        self.discovered_agent_service_name: Optional[str] = None # To store discovered agent service name
        self.requester: Optional[rpc.Requester] = None # Requester will be created after discovery
        
        # RPC v2: Track targeted agent GUID and service instance tag
        self.target_agent_guid: Optional[str] = None
        self.target_service_instance_tag: Optional[str] = None
        
        # Core interface state: discovered agents cache
        self.available_agents: Dict[str, Dict[str, Any]] = {}
        self._agent_found_event = asyncio.Event()
        
        # Get types from XML (business logic specific - each component loads its own types)
        # GenesisApp provides infrastructure only; Interface needs RPC types for requester
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        # Use unified RPC types for all Genesis communication
        self.request_type = self.type_provider.type("genesis_lib", "GenesisRPCRequest")
        self.reply_type = self.type_provider.type("genesis_lib", "GenesisRPCReply")
        
        # Store member names for later use
        self.reply_members = [member.name for member in self.reply_type.members()]
        
        # Placeholders for callbacks
        # Optional due to two-tier architecture: GenesisInterface (base) can be used standalone,
        # MonitoredInterface (subclass) registers these callbacks for graph topology tracking
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._on_agent_discovered_callback: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None
        self._on_agent_departed_callback: Optional[Callable[[str], Coroutine[Any, Any, None]]] = None
        
        # Set up advertisement-based listener for agent discovery
        self._loop = asyncio.get_running_loop()
        self._setup_advertisement_listener()

    def _setup_advertisement_listener(self):
        """
        Set up advertisement listener for agent discovery.
        
        **What This Method Does**:
        Creates a DDS DataReader for the unified Advertisement topic with content filtering
        to receive only AGENT advertisements (not SERVICE or FUNCTION advertisements).
        
        **QoS Configuration**:
        All QoS settings are loaded from XML (USER_QOS_PROFILES.xml):
        - Profile: cft_Library::cft_Profile
        - Durability: TRANSIENT_LOCAL (late-joiners get history)
        - Reliability: RELIABLE (don't miss advertisements)
        - History: KEEP_LAST with depth 500
        
        **Content Filtering**:
        Uses DDS ContentFilteredTopic to filter at the DDS layer:
        - Filter: "kind = 1" (AGENT kind only)
        - Benefits: Reduced network traffic, CPU efficiency
        
        **Advertisement Listener**:
        The AdvertisementListener class handles incoming agent advertisements:
        - on_data_available: Called when new agent joins
        - Triggers registered discovery callbacks
        - Updates available_agents cache
        - Handles agent departures (NOT_ALIVE states)
        
        **Why This Matters**:
        Agent discovery is the foundation of Genesis. Without this, interfaces
        cannot find agents to communicate with. The content filtering ensures
        interfaces only see relevant advertisements (agents, not services/functions).
        
        Raises:
            Exception: If DDS reader creation or QoS loading fails
        """
        try:
            logger.debug("🔧 TRACE: Setting up advertisement monitoring...")
            
            # Load reader QoS from XML profile - reuse existing type_provider to avoid duplicate load
            # Configuration in genesis_lib/config/USER_QOS_PROFILES.xml
            try:
                reader_qos = self.type_provider.datareader_qos_from_profile("cft_Library::cft_Profile")
                logger.debug("📋 TRACE: Loaded reader QoS from cft_Profile (transient local, reliable, depth 500)")
            except Exception as e:
                # Fallback: try loading USER_QOS_PROFILES separately if not already in type_provider
                logger.warning(f"Failed to load cft_Profile from type_provider, trying separate load: {e}")
                import os
                config_path = get_datamodel_path()
                config_dir = os.path.dirname(config_path)
                user_qos_path = os.path.join(config_dir, "USER_QOS_PROFILES.xml")
                qos_provider = dds.QosProvider(user_qos_path)
                reader_qos = qos_provider.datareader_qos_from_profile("cft_Library::cft_Profile")
                logger.debug("📋 TRACE: Loaded reader QoS from cft_Profile via fallback")
            
            # Resolve advertisement type/topic
            bus = AdvertisementBus.get(self.app.participant)
            ad_type = bus.ad_type
            ad_topic = bus.topic

            # Create advertisement listener that references the interface's callbacks dynamically
            logger.debug("🎯 TRACE: Creating advertisement listener...")
            class AdvertisementListener(dds.DynamicData.NoOpDataReaderListener):
                def __init__(self, iface: "GenesisInterface"):
                    super().__init__()
                    self._iface = iface
                    self.received = {}
                def on_data_available(self, reader):
                    try:
                        logger.info("🔔 INTERFACE: AdvertisementListener.on_data_available() CALLED!")
                        samples = reader.read()
                        logger.info(f"📊 INTERFACE: Got {len(samples)} advertisement samples")
                        for data, info in samples:
                            if data is None:
                                logger.debug("⏭️ INTERFACE: Skipping None data")
                                continue
                            # Content filter ensures only AGENT ads are delivered - no in-code filtering needed
                            agent_id = data.get_string("advertisement_id") or ""
                            if not agent_id:
                                continue
                            if info.state.instance_state == dds.InstanceState.ALIVE:
                                if agent_id not in self.received:
                                    name = data.get_string("name") or ""
                                    service_name = data.get_string("service_name") or ""
                                    agent_info = {
                                        'message': f'Agent {name} advertising',
                                        'prefered_name': name,
                                        'default_capable': 1,
                                        'instance_id': agent_id,
                                        'service_name': service_name,
                                        'timestamp': time.time()
                                    }
                                    self.received[agent_id] = agent_info
                                    # Legacy log format for test compatibility
                                    logger.info(f"Agent DISCOVERED: {name} ({service_name})")
                                    logger.debug(f"✨ TRACE: Agent DISCOVERED via Advertisement: {name} ({service_name}) - ID: {agent_id}")
                                    cb = self._iface._on_agent_discovered_callback
                                    if cb:
                                        # Schedule on the interface's loop
                                        self._iface._loop.call_soon_threadsafe(asyncio.create_task, cb(agent_info))
                            elif info.state.instance_state in [dds.InstanceState.NOT_ALIVE_DISPOSED, dds.InstanceState.NOT_ALIVE_NO_WRITERS]:
                                if agent_id in self.received:
                                    self.received.pop(agent_id, None)
                                    logger.debug(f"👻 TRACE: Agent DEPARTED via Advertisement: ID: {agent_id} - Reason: {info.state.instance_state}")
                                    cb = self._iface._on_agent_departed_callback
                                    if cb:
                                        self._iface._loop.call_soon_threadsafe(asyncio.create_task, cb(agent_id))
                    except Exception as e:
                        logger.error(f"❌ TRACE: Error in AdvertisementListener.on_data_available: {e}")

            # Create content-filtered topic to only receive AGENT advertisements (kind=1)
            # This filters at the DDS layer, not in code - much more efficient!
            logger.debug("🔍 TRACE: Creating content-filtered topic for AGENT advertisements...")
            filtered_topic = dds.DynamicData.ContentFilteredTopic(
                ad_topic,
                "AgentAdvertisementFilter",
                dds.Filter("kind = %0", ["1"])  # AGENT kind enum value
            )
            
            # Create advertisement reader with content filter
            logger.debug("📡 TRACE: Creating advertisement reader with content filter...")
            self.advertisement_reader = dds.DynamicData.DataReader(
                subscriber=self.app.subscriber,
                cft=filtered_topic,  # Use 'cft' parameter for ContentFilteredTopic
                qos=reader_qos,
                listener=AdvertisementListener(self),
                mask=dds.StatusMask.DATA_AVAILABLE
            )
            # Keep a handle to listener for potential future updates
            self.advertisement_listener = self.advertisement_reader.listener
            
            # Legacy AgentCapability fallback removed - now fully consolidated to Advertisement topic

            logger.debug("✅ TRACE: Advertisement monitoring setup complete")
            
        except Exception as e:
            logger.error(f"❌ TRACE: Error setting up advertisement monitoring: {e}")
            logger.error(traceback.format_exc())
            raise

    async def connect_to_agent(self, service_name: str, timeout_seconds: Optional[float] = None) -> bool:
        """
        Create RPC Requester and establish connection to a specific agent service.
        
        **What This Method Does**:
        1. Creates DDS RPC Requester for the specified service
        2. Waits for DDS endpoint matching (agent's Replier must be discovered)
        3. Returns success/failure status
        
        **Connection Process**:
        ```
        Interface: connect_to_agent("MathService")
                   ↓
                   Create Requester on topic "rti/connext/genesis/rpc/MathService"
                   ↓
                   Wait for DDS discovery (Requester finds Replier)
                   ↓
                   matched_replier_count > 0
                   ↓
                   Return True (ready to send requests)
        ```
        
        **RPC Topic Naming**:
        DDS RPC uses a standardized topic naming convention:
        - Request topic: `rti/connext/genesis/rpc/{service_name}_Request`
        - Reply topic: `rti/connext/genesis/rpc/{service_name}_Reply`
        
        **Endpoint Matching**:
        DDS must discover the agent's Replier before the Requester is usable.
        This method polls `matched_replier_count` until > 0 or timeout expires.
        
        **When to Call This**:
        - After agent discovery (wait a bit for advertisements)
        - Before sending any requests
        - Can be called multiple times (closes previous requester)
        
        **Failover Support**:
        If an agent crashes, you can call connect_to_agent() again to find
        a new agent with the same service_name.
        
        Args:
            service_name: Agent service name to connect to (e.g., "OpenAIChatService")
            timeout_seconds: Max time to wait for endpoint match (None = wait forever)
        
        Returns:
            True if connection established, False if timeout or error
        
        Example:
            ```python
            interface = GenesisInterface("MyInterface", "ChatService")
            await asyncio.sleep(2)  # Wait for agent advertisements
            if await interface.connect_to_agent("ChatService", timeout_seconds=10.0):
                print("Connected!")
            else:
                print("Connection failed")
            ```
        """
        if self.requester:
             logger.warning(f"⚠️ TRACE: Requester already exists for service '{self.discovered_agent_service_name}'. Overwriting.")
             self.requester.close()

        logger.debug(f"🔗 TRACE: Attempting to connect to agent service: {service_name}")
        try:
            timeout_label = "∞" if timeout_seconds is None else str(timeout_seconds)
            print(f"[INTERFACE_RPC] bind: service='{service_name}' timeout={timeout_label}s")
        except Exception:
            pass
        try:
            # Create RPC requester using unified RPC v2 naming
            self.requester = rpc.Requester(
                request_type=self.request_type,
                reply_type=self.reply_type,
                participant=self.app.participant,
                service_name=f"rti/connext/genesis/rpc/{service_name}"
            )
            self.discovered_agent_service_name = service_name

            start_time = time.time()
            while self.requester.matched_replier_count == 0:
                if timeout_seconds is not None and (time.time() - start_time > timeout_seconds):
                    logger.error(f"❌ TRACE: Timeout ({timeout_seconds}s) waiting for DDS replier match for service '{service_name}'")
                    try:
                        print(f"[INTERFACE_RPC] bind-timeout: service='{service_name}' repliers=0")
                    except Exception:
                        pass
                    self.requester.close()
                    self.requester = None
                    self.discovered_agent_service_name = None
                    return False
                await asyncio.sleep(0.1)
            
            logger.debug(f"✅ TRACE: RPC Requester created and DDS replier matched for service: {service_name}")
            try:
                print(f"[INTERFACE_RPC] bind-ok: service='{service_name}' repliers={self.requester.matched_replier_count}")
            except Exception:
                pass
            return True
            
        except Exception as req_e:
            logger.error(f"❌ TRACE: Failed to create or match RPC Requester for service '{service_name}': {req_e}")
            logger.error(traceback.format_exc())
            self.requester = None
            self.discovered_agent_service_name = None
            return False

    async def send_request(self, request_data: Dict[str, Any], timeout_seconds: float = 10.0, 
                          target_agent_guid: Optional[str] = None, 
                          service_instance_tag: Optional[str] = None,
                          reset_target: bool = False) -> Optional[Dict[str, Any]]:
        """
        Send request to agent and wait for reply with broadcast + GUID targeting.
        
        RPC Protocol Behavior:
        - First request: Broadcasts to all agents with the service_name (empty target_service_guid)
        - First reply: Captures replier_service_guid and uses it for subsequent targeted requests
        - Subsequent requests: Targeted to specific agent GUID via content filtering
        - reset_target=True: Forces broadcast again (e.g., for failover or reconnection)
        
        Args:
            request_data: Dictionary with request fields (must include 'message', 'conversation_id')
            timeout_seconds: Max wait time for reply
            target_agent_guid: Optional explicit GUID to target (overrides stored target)
            service_instance_tag: Optional tag for migration scenarios (e.g., "production", "v2")
            reset_target: If True, clears stored GUID and broadcasts again
            
        Returns:
            Reply dictionary or None on timeout/error
        """
        if not self.requester:
            logger.error("❌ TRACE: Cannot send request, agent not discovered or requester not created.")
            return None
            
        try:
            # Handle reset_target flag
            if reset_target:
                logger.debug("🔄 Resetting target agent GUID, will broadcast")
                self.target_agent_guid = None
                self.target_service_instance_tag = None
            
            # Determine target GUID: explicit > stored > broadcast (empty)
            effective_target_guid = target_agent_guid or self.target_agent_guid or ""
            effective_service_tag = service_instance_tag or self.target_service_instance_tag or ""
            
            is_broadcast = not effective_target_guid
            
            # Create request with unified RPC fields
            request = dds.DynamicData(self.request_type)
            for key, value in request_data.items():
                request[key] = value
            
            # Set RPC protocol fields
            request["target_service_guid"] = effective_target_guid
            request["service_instance_tag"] = effective_service_tag
                
            # Send request and wait for reply using synchronous API in a thread
            logger.debug(f"Sending {'broadcast' if is_broadcast else 'targeted'} request to service '{self.discovered_agent_service_name}' (target_guid: {effective_target_guid or 'broadcast'}, tag: {effective_service_tag or 'none'}): {request_data}")
            try:
                msg_preview = request_data.get('message') if isinstance(request_data, dict) else str(request_data)
                print(f"[INTERFACE_RPC] send: service='{self.discovered_agent_service_name}' mode={'broadcast' if is_broadcast else 'targeted'} target='{effective_target_guid[:16] if effective_target_guid else 'all'}' msg='{str(msg_preview)[:120]}' timeout={timeout_seconds}s")
            except Exception:
                pass
            
            def _send_request_sync(requester, req, timeout):
                # Ensure the requester is valid before using it
                if requester is None:
                    logger.error("❌ TRACE: _send_request_sync called with None requester.")
                    return None
                try:
                    request_id = requester.send_request(req)
                    # Convert float seconds to int seconds and nanoseconds
                    seconds = int(timeout)
                    nanoseconds = int((timeout - seconds) * 1e9)
                    # First reply (blocking up to full timeout)
                    replies = requester.receive_replies(
                        max_wait=dds.Duration(seconds=seconds, nanoseconds=nanoseconds),
                        min_count=1,
                        related_request_id=request_id
                    )
                    if not replies:
                        try:
                            print(f"[INTERFACE_RPC] recv-timeout: service='{self.discovered_agent_service_name}'")
                        except Exception:
                            pass
                        return None
                    last = replies[0]
                    # Drain additional replies for a short quiet window so we return the final reply
                    quiet_seconds = 1.0
                    while True:
                        try:
                            more = requester.receive_replies(
                                max_wait=dds.Duration(seconds=int(quiet_seconds), nanoseconds=int((quiet_seconds - int(quiet_seconds))*1e9)),
                                min_count=1,
                                related_request_id=request_id
                            )
                            if more:
                                last = more[0]
                                # continue draining until no more within quiet window
                                continue
                            break
                        except Exception:
                            break
                    return last  # (reply, info)
                except Exception as sync_e:
                    logger.error(f"❌ TRACE: Error in _send_request_sync: {sync_e}")
                    logger.error(traceback.format_exc())
                    return None
                
            result = await asyncio.to_thread(_send_request_sync, self.requester, request, timeout_seconds)
            
            if result:
                reply, info = result
                # Convert reply to dict
                reply_dict = {}
                for member in self.reply_members:
                    reply_dict[member] = reply[member]
                
                # RPC v2: Capture replier_service_guid from first successful reply
                replier_guid = reply_dict.get("replier_service_guid", "")
                replier_tag = reply_dict.get("service_instance_tag", "")
                
                if replier_guid and not self.target_agent_guid:
                    logger.info(f"✅ First reply received, locking to agent GUID: {replier_guid}")
                    self.target_agent_guid = replier_guid
                    self.target_service_instance_tag = replier_tag
                    print(f"[INTERFACE_RPC] lock-target: guid='{replier_guid[:16]}...' tag='{replier_tag or 'none'}'")
                    
                logger.debug(f"Received reply from agent: {reply_dict}")
                try:
                    reply_msg = reply_dict.get('message') if isinstance(reply_dict, dict) else str(reply_dict)
                    print(f"[INTERFACE_RPC] recv-ok: service='{self.discovered_agent_service_name}' msg='{str(reply_msg)[:120]}'")
                except Exception:
                    pass
                return reply_dict
            else:
                logger.error("No reply received")
                try:
                    print(f"[INTERFACE_RPC] recv-none: service='{self.discovered_agent_service_name}'")
                except Exception:
                    pass
                return None
            
        except dds.TimeoutError:
            logger.error(f"Timeout waiting for reply after {timeout_seconds} seconds")
            try:
                print(f"[INTERFACE_RPC] recv-timeout-ex: service='{self.discovered_agent_service_name}'")
            except Exception:
                pass
            return None
        except Exception as e:
            logger.error(f"Error sending request: {e}")
            try:
                print(f"[INTERFACE_RPC] send-ex: service='{self.discovered_agent_service_name}' err='{e}'")
            except Exception:
                pass
            return None

    async def close(self):
        """Clean up resources"""
        if hasattr(self, 'requester') and self.requester: # Check if requester exists before closing
            self.requester.close()
        if hasattr(self, 'app'):
            await self.app.close()

    # --- Agent Discovery State Management (Core Functionality) ---
    
    async def _handle_agent_discovered(self, agent_info: dict):
        """
        Core handler for agent discovery - manages interface state.
        
        This is the base implementation that manages discovered agent state.
        Subclasses (like MonitoredInterface) can override to add monitoring
        but should call super() to preserve this core functionality.
        
        Args:
            agent_info: Dict with keys: instance_id, prefered_name, service_name,
                       message, default_capable, timestamp
        """
        instance_id = agent_info['instance_id']
        prefered_name = agent_info.get('prefered_name', 'Unknown')
        service_name = agent_info.get('service_name', 'Unknown')
        
        logger.debug(f"GenesisInterface: Agent discovered: {prefered_name} ({service_name}) - ID: {instance_id}")
        
        # Cache discovered agent
        self.available_agents[instance_id] = agent_info
        
        # Signal that an agent is available (for connect_to_agent waiting)
        if not self._agent_found_event.is_set():
            self._agent_found_event.set()
    
    async def _handle_agent_departed(self, instance_id: str):
        """
        Core handler for agent departure - manages interface state.
        
        This is the base implementation that manages agent state when agents depart.
        Subclasses can override to add monitoring but should call super().
        
        Args:
            instance_id: GUID of the departed agent
        """
        if instance_id in self.available_agents:
            departed_agent = self.available_agents.pop(instance_id)
            prefered_name = departed_agent.get('prefered_name', 'Unknown')
            logger.debug(f"GenesisInterface: Agent departed: {prefered_name} - ID: {instance_id}")
        else:
            logger.warning(f"GenesisInterface: Received departure for unknown agent: {instance_id}")

    # --- Callback Registration Methods ---
    def register_discovery_callback(self, callback: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]):
        """Register a callback to be invoked when an agent is discovered."""
        logger.debug(f"🔧 TRACE: Registering discovery callback: {callback.__name__ if callback else 'None'}")
        self._on_agent_discovered_callback = callback
        # If advertisement listener exists, backfill any already-received agents
        try:
            listener = getattr(self, 'advertisement_listener', None)
            if listener and hasattr(listener, 'received') and isinstance(listener.received, dict):
                for agent_info in list(listener.received.values()):
                    # Schedule callback on the interface loop
                    self._loop.call_soon_threadsafe(asyncio.create_task, callback(agent_info))
        except Exception:
            pass

    def register_departure_callback(self, callback: Callable[[str], Coroutine[Any, Any, None]]):
        """Register a callback to be invoked when an agent departs."""
        logger.debug(f"🔧 TRACE: Registering departure callback: {callback.__name__ if callback else 'None'}")
        self._on_agent_departed_callback = callback
        # If listener already exists, update its callback directly
        if hasattr(self, 'registration_listener') and self.registration_listener:
            self.registration_listener.on_agent_departed = callback
    # --- End New Callback Registration Methods --- 
