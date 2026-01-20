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
Agent-to-Agent Communication Module

This module provides the AgentCommunicationMixin class that enables agent-to-agent
communication capabilities in Genesis. It can be mixed into GenesisAgent or 
MonitoredAgent to add agent discovery, connection management, and RPC communication
between agents.

=================================================================================================
WHAT IS AGENTCOMMUNICATIONMIXIN?
=================================================================================================

AgentCommunicationMixin is a Python mixin class that adds agent-to-agent communication
capabilities to Genesis agents. It provides three core features:

1. **Agent Discovery**: Passive discovery of other agents via DDS advertisements
2. **Connection Management**: Dynamic creation and caching of RPC connections
3. **Request/Reply Communication**: Send requests to discovered agents and receive replies

When mixed into GenesisAgent (via MonitoredAgent), agents gain the ability to:
- Discover other agents on the network automatically
- Query discovered agents by capability, specialization, or other criteria
- Connect to and communicate with other agents via RPC
- Delegate tasks to specialized agents (agent-as-tool pattern)

=================================================================================================
ARCHITECTURE OVERVIEW - How AgentCommunicationMixin Fits Into Genesis
=================================================================================================

Genesis Agent Inheritance Hierarchy:

    GenesisAgent (genesis_agent.py)
    ├─ Core business logic: request processing, tool orchestration, memory
    ├─ Abstract methods for LLM providers
    └─ Optional: AgentCommunicationMixin (THIS FILE) [mixed in if enable_agent_communication=True]
        ↓
    MonitoredAgent (monitored_agent.py)
    ├─ Adds monitoring wrapper around all methods
    ├─ Wraps _call_agent() to publish AGENT_TO_AGENT_START/COMPLETE events
    └─ Inherits agent communication capabilities if enabled
        ↓
    OpenAIGenesisAgent (openai_genesis_agent.py)
    └─ Implements LLM provider methods (OpenAI API)

**THE MIXIN PATTERN**:
AgentCommunicationMixin is OPTIONAL and only included when enable_agent_communication=True.
This keeps agent communication orthogonal to:
- LLM provider implementation (OpenAI vs Anthropic vs ...)
- Monitoring concerns (handled by MonitoredAgent wrapper)
- Core agent logic (request processing, memory, tools)

**EXAMPLE: Creating an Agent WITH Communication**:
```python
from genesis_lib import OpenAIGenesisAgent

agent = OpenAIGenesisAgent(
    agent_name="PersonalAssistant",
    base_service_name="OpenAIChatService",
    enable_agent_communication=True,  # ← Mixes in AgentCommunicationMixin
    ...
)
# Agent can now discover and delegate to other agents
```

**EXAMPLE: Creating an Agent WITHOUT Communication**:
```python
agent = OpenAIGenesisAgent(
    agent_name="SimpleAgent",
    base_service_name="OpenAIChatService",
    enable_agent_communication=False,  # ← No agent communication (default)
    ...
)
# Agent operates independently, cannot discover or call other agents
```

=================================================================================================
THE THREE PHASES - Discovery, Connection, Communication
=================================================================================================

Agent-to-agent interaction follows a three-phase lifecycle:

**PHASE 1: DISCOVERY (Passive - Automatic)**
    When: Starts immediately after initialization
    How: DDS listener continuously receives agent advertisements
    Data: Agent metadata (capabilities, specializations, service_name, agent_id)
    Storage: self.discovered_agents Dict[agent_id -> agent_info]
    
    Example Flow:
    1. WeatherAgent publishes advertisement to "rti/connext/genesis/Advertisement" topic
    2. PersonalAssistant's DDS listener receives advertisement (content-filtered for kind=AGENT)
    3. _on_agent_advertisement_received() parses data, stores in discovered_agents
    4. Discovery callbacks are invoked (e.g., MonitoredAgent publishes graph topology edge)

**PHASE 2: CONNECTION (Active - On-Demand)**
    When: First time you want to communicate with a specific agent
    How: Create RPC Requester for the agent's "_AgentRPC" service
    Data: RPC connection (cached in self.agent_connections)
    
    Example Flow:
    1. PersonalAssistant calls: await connect_to_agent("weather-agent-uuid")
    2. Lookup agent in discovered_agents to get service_name
    3. Create RPC Requester for "WeatherService_AgentRPC"
    4. Wait for DDS DataReader/DataWriter matching
    5. Cache requester in self.agent_connections for reuse

**PHASE 3: COMMUNICATION (Active - Repeated)**
    When: Every time you want to send a request to a connected agent
    How: Use cached RPC Requester to send GenesisRPCRequest, await GenesisRPCReply
    Data: Request/reply messages with conversation_id for tracking
    
    Example Flow (GUID-based RPC targeting):
    1. PersonalAssistant calls: response = await send_agent_request(agent_id, "What's the weather?")
    2. First request: Broadcast (empty target_service_guid field)
    3. WeatherAgent replies, includes replier_service_guid in response
    4. PersonalAssistant captures and stores the GUID
    5. Subsequent requests: Targeted (target_service_guid = captured GUID)
    6. Benefits: Session affinity, canary deployments, A/B testing

**KEY INSIGHT**: Discovery is continuous and passive. Connection and communication are 
on-demand and active. This design minimizes resource usage while maintaining fresh 
discovery data.

=================================================================================================
RPC v2 ARCHITECTURE - Broadcast First, Then Lock to GUID
=================================================================================================

Genesis uses "RPC v2" for agent-to-agent communication, which solves a critical problem:
How do you route requests to the correct service instance when multiple instances exist?

**THE PROBLEM**:
In a distributed system, you might have:
- 3 instances of WeatherService running (production, canary, v2-migration)
- All using the same service name: "WeatherService_AgentRPC"
- All listening on the same DDS topics
- How do you ensure Agent A always talks to the same instance?

**NAIVE SOLUTION (Fails)**:
Use service instance names like "WeatherService_AgentRPC_instance1"
- Breaks discovery (how do you know which instances exist?)
- Requires manual coordination (what if instance1 crashes?)
- Can't do canary deployments or gradual rollouts

**RPC v2 SOLUTION (Works)**:
First request broadcasts, reply captures GUID, subsequent requests target that GUID.

**DETAILED FLOW**:
```
Request 1 (Broadcast):
    GenesisRPCRequest {
        message: "What's the weather in London?",
        conversation_id: "conv-123",
        target_service_guid: "",  ← EMPTY = broadcast to all
        service_instance_tag: ""
    }
    → All WeatherService instances receive this
    → First to reply wins

Reply 1 (GUID Capture):
    GenesisRPCReply {
        message: "It's 15°C and sunny",
        status: 0,
        conversation_id: "conv-123",
        replier_service_guid: "01abc123..."  ← Instance GUID
    }
    → PersonalAssistant stores: agent_target_guids["weather-agent-uuid"] = "01abc123..."

Request 2+ (Targeted):
    GenesisRPCRequest {
        message: "How about tomorrow?",
        conversation_id: "conv-456",
        target_service_guid: "01abc123...",  ← Targets specific instance
        service_instance_tag: ""
    }
    → Only the instance with GUID "01abc123..." processes this
    → Other instances ignore (content filtering)
```

**BENEFITS**:
- Session Affinity: Subsequent requests go to the same instance (maintains context)
- Service Migration: Can deploy new version, agents gradually lock to new instances
- Canary Deployments: Route 10% of NEW conversations to canary instance
- A/B Testing: Different instances can run different models/configs

**MIGRATION SCENARIO**:
```
1. Deploy WeatherService v2 alongside v1
2. New agent connections: Broadcast first request
   - Some lock to v1, some lock to v2 (50/50 natural split)
3. Monitor metrics for both versions
4. If v2 is good: Wait for v1 connections to drain (no new ones locking to it)
5. Shut down v1 when all active conversations complete
6. 100% traffic on v2 with zero downtime, no connection disruption
```

=================================================================================================
ARCHITECTURAL DECISION: Why Separate Agent-to-Agent vs. Interface-to-Agent Communication?
=================================================================================================

Genesis implements TWO separate communication paths:
1. Interface-to-Agent: Human interfaces → Agents (via GenesisRPCRequest/Reply on Interface topics)
2. Agent-to-Agent: Agents → Other Agents (via GenesisRPCRequest/Reply on Agent topics) [THIS FILE]

Note: As of the unified RPC model, both paths use the same message types (GenesisRPCRequest/Reply)
but with different topic names to maintain separation of concerns and traffic isolation.

DESIGN NOTE: Why not use GenesisRequester/GenesisReplier wrappers here?
The agent↔agent path retains a minimal surface on top of rti.rpc + DynamicData to match the
interface/agent control path characteristics (thin, predictable logging, flexible payloads).
Function-style RPC uses the GenesisRequester/GenesisReplier wrappers for convenience and
consistent function-call behavior (packing params/results, result logs).

WHY NOT A SINGLE COMBINED SYSTEM?

This separation exists for fundamental architectural and technical reasons:

1. DDS CONSTRAINT: Topic Name Uniqueness (Technical Requirement)
   -------------------------------------------------------------
   DDS requires unique service names per participant. A single agent must simultaneously:
   - Accept requests from human interfaces (Interface RPC service)
   - Accept requests from other agents (Agent RPC service with "_AgentRPC" suffix)
   
   Using the same service name would cause:
   - Topic collision errors
   - Inability to distinguish request sources
   - Routing ambiguity (is this from a human or another agent?)
   
   Solution: Separate service names → Requires separate RPC infrastructure

2. DIFFERENT MESSAGE SCHEMAS (Fundamental Design Difference)
   -------------------------------------------------------------
   InterfaceAgentReply:
   - status: int32
   - conversation_id: string
   - NO message field (agent handles response delivery separately)
   
   AgentAgentReply:
   - message: string (8KB)  [CRITICAL DIFFERENCE]
   - status: int32
   - conversation_id: string
   - Agent needs full message content to compose into reasoning
   
   Why different?
   - Interfaces receive full responses through separate channels
   - Agents must embed responses directly into their orchestration flow
   - Merging schemas would bloat one or break the other

3. DIFFERENT MONITORING SEMANTICS (Observability Requirements)
   -------------------------------------------------------------
   Interface-to-Agent:
   - Track: Human interaction patterns, response times, user satisfaction
   - Metrics: Simple request/response tracking
   
   Agent-to-Agent:
   - Track: Orchestration chains, delegation patterns, multi-hop latency
   - Metrics: AGENT_TO_AGENT_START/COMPLETE events, chain_id propagation
   - Enables: Distributed tracing across agent collaboration graphs
   
   Separate paths enable specialized monitoring for each use case

4. INDEPENDENT EVOLUTION (Maintainability)
   -------------------------------------------------------------
   Interface UX concerns (streaming, human feedback, rate limiting) can evolve
   independently from agent orchestration logic (capability routing, chain 
   optimization, autonomous delegation).
   
   Mixed concerns would create coupling between human-facing and AI-facing APIs.

5. DIFFERENT PROCESSING SEMANTICS (Behavioral Difference)
   -------------------------------------------------------------
   While BOTH paths are stateful (maintain memory/conversation state), they differ:
   
   Interface-to-Agent:
   - Single-session conversations with humans
   - Linear request-response pattern
   - conversation_id tracks human sessions
   
   Agent-to-Agent:
   - Multi-session orchestration (Agent A → B, C, D concurrently)
   - Recursive composition (agents orchestrate agents)
   - conversation_id tracks sub-workflows in larger agent chains
   - Enables capability-based routing via AgentClassifier

CONSIDERED ALTERNATIVES:
=======================

Alternative 1: Unified Path with source_type flag
   - Would require merged schemas (loses optimization)
   - Topic collision issues remain unsolved
   - Mixed concerns hurt maintainability
   - Can't independently scale interface vs agent traffic

Alternative 2: Layered approach (agent-agent routes through interface-agent)
   - Loses separate monitoring for agent chains
   - Extra hop adds latency
   - Can't distinguish human requests from agent orchestration
   - Breaks chain event tracking

Current Approach: Separate paths (CHOSEN)
   - Clean separation of concerns
   - Solves DDS constraints
   - Optimized schemas for each use case
   - Independent evolution
   - Specialized monitoring

TRADE-OFFS ACCEPTED:
===================

Cons of this approach:
- ~200-300 lines of similar RPC setup code (duplication)
- Increased cognitive load (two patterns to understand)
- 2x RPC endpoints per agent (resource overhead)
- Must test both paths for feature parity

Mitigation strategies:
- Extract common RPC infrastructure to reduce duplication
- Comprehensive documentation (this comment!)
- Shared processing core where applicable
- Automated testing to ensure consistency

VERDICT: The separate paths are architecturally justified. The alternatives would
create worse problems (topic collisions, mixed concerns, loss of monitoring fidelity)
than they solve. The accepted trade-offs are manageable through better factoring
of shared infrastructure.

Last reviewed: October 2025
Decision ratified by: Architecture review
=================================================================================================

=================================================================================================
WHAT YOU GET FOR FREE - Using AgentCommunicationMixin
=================================================================================================

When you mix AgentCommunicationMixin into your Genesis agent (by setting 
enable_agent_communication=True), you automatically get ALL of these capabilities
without writing any agent communication code:

1. **Automatic Agent Discovery** (Passive Background Process):
   - DDS listener continuously receives agent advertisements
   - Discovered agents stored in self.discovered_agents
   - Discovery callbacks invoked for integration (e.g., graph topology)
   - No manual registration or configuration needed

2. **Rich Query API** (10+ Query Methods):
   - Query by agent type: get_agents_by_type("WeatherAgent")
   - Query by capability: find_agents_by_capability("weather_forecast")
   - Query by specialization: find_agents_by_specialization("finance")
   - Query by model: get_agents_by_model_type("gpt-4")
   - Query by performance: get_agents_by_performance_metric("latency_ms", max_value=100)
   - AI-powered routing: get_best_agent_for_request("What's the weather?")
   - Fuzzy search: search_agents("weather")

3. **Dynamic Connection Management** (Lazy Connection Creation):
   - Connections created on-demand when first needed
   - Automatic connection caching for reuse
   - DDS matching with timeout and retries
   - Graceful cleanup on shutdown

4. **RPC v2 Communication** (Broadcast → GUID Locking):
   - First request broadcasts to all instances
   - Reply captures replier GUID for session affinity
   - Subsequent requests target specific instance
   - Supports canary deployments and A/B testing

5. **Agent-as-Tool Pattern** (Seamless Integration):
   - Discovered agents automatically exposed as tools to LLM
   - LLM can orchestrate agent delegation ("ask the weather agent")
   - Responses integrated back into conversation flow
   - MonitoredAgent publishes AGENT_TO_AGENT events for tracing

**EXAMPLE: Agent Discovers and Delegates to Another Agent**:
```python
# PersonalAssistant (with enable_agent_communication=True)
# 1. WeatherAgent publishes advertisement → PersonalAssistant discovers it automatically
# 2. User asks: "What's the weather in London?"
# 3. LLM sees WeatherAgent as available tool, decides to use it
# 4. PersonalAssistant calls: result = await self._call_agent("weather_agent", message="...")
# 5. _call_agent() uses send_agent_request() from AgentCommunicationMixin
# 6. WeatherAgent processes request, replies with weather data
# 7. PersonalAssistant incorporates result into response to user
```

**WHAT YOU DON'T NEED TO WORRY ABOUT**:
- ❌ Manual agent registration
- ❌ Service discovery configuration
- ❌ RPC connection setup code
- ❌ Request/reply message formatting
- ❌ Connection pooling and cleanup
- ❌ GUID tracking for session affinity

All of this is handled automatically by the mixin!

=================================================================================================
INTEGRATION WITH MONITOREDAGENT - Automatic Observability
=================================================================================================

When AgentCommunicationMixin is used with MonitoredAgent (the normal case), you also get
automatic monitoring and observability for all agent-to-agent interactions:

**MonitoredAgent Automatically Publishes**:
- Graph Topology Edges: Agent A → Agent B connections (via _on_agent_discovered callback)
- Chain Events: AGENT_TO_AGENT_START when sending request
- Chain Events: AGENT_TO_AGENT_COMPLETE when receiving reply
- Distributed Tracing: chain_id propagation across agent calls

**Consumed By**:
- Network visualization UI (shows agent-to-agent connections)
- Monitoring dashboards (tracks agent collaboration patterns)
- Distributed tracing tools (follows requests across agent boundaries)
- Performance monitoring (measures agent-to-agent latency)

**The Integration Point**:
MonitoredAgent._call_agent() wraps AgentCommunicationMixin.send_agent_request():
```python
class MonitoredAgent(GenesisAgent, AgentCommunicationMixin):  # Multiple inheritance
    async def _call_agent(self, agent_tool_name, **kwargs):
        # BEFORE: Publish AGENT_TO_AGENT_START event
        chain_id = uuid.uuid4()
        self._publish_agent_to_agent_start(chain_id, agent_tool_name)
        
        # EXECUTE: Call AgentCommunicationMixin's send_agent_request()
        result = await super()._call_agent(agent_tool_name, **kwargs)
        
        # AFTER: Publish AGENT_TO_AGENT_COMPLETE event
        self._publish_agent_to_agent_complete(chain_id, agent_tool_name)
        return result
```

This is the DECORATOR PATTERN in action - MonitoredAgent adds observability around
AgentCommunicationMixin's core functionality without modifying it.

=================================================================================================

"""

import asyncio
import json
import logging
import time
import traceback
import uuid
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import rti.connextdds as dds
import rti.rpc as rpc
from .utils import get_datamodel_path
from .advertisement_bus import AdvertisementBus

# Get logger
logger = logging.getLogger(__name__)


# ==========================================================================
# MODULE-LEVEL HELPER CLASSES - DDS Listeners for Async Callbacks
# ==========================================================================
# These listener classes are invoked by DDS when data arrives on topics.
# They run in DDS middleware threads, not the main async event loop.
# 
# Pattern: Listener receives data → validates → calls parent method
# ==========================================================================

# Module-level helper class for agent advertisement discovery
class _AgentAdvertisementListener(dds.DynamicData.NoOpDataReaderListener):
    """
    DDS listener for agent advertisement discovery.
    
    Automatically invoked when new agent advertisements arrive on the
    filtered Advertisement topic. Populates the parent's discovered_agents
    dict and invokes discovery callbacks.
    """
    
    def __init__(self, parent_mixin):
        """
        Initialize listener with reference to parent mixin.
        
        Args:
            parent_mixin: AgentCommunicationMixin instance that owns this listener
        """
        super().__init__()
        self._parent = parent_mixin
    
    def on_data_available(self, reader):
        """
        DDS callback invoked when advertisement data arrives.
        
        Processes agent advertisements, updates discovered_agents,
        and invokes discovery callbacks for new agents.
        
        Args:
            reader: DDS DataReader with available samples
        """
        try:
            # Use read() instead of take() to preserve durable advertisement data
            # Advertisements are TRANSIENT_LOCAL - DDS is the source of truth
            samples = reader.read()
            
            for data, info in samples:
                # Only process valid, unread samples
                if (info.state.sample_state != dds.SampleState.NOT_READ or 
                    info.state.instance_state != dds.InstanceState.ALIVE):
                    continue
                
                self._parent._on_agent_advertisement_received(data)
                
        except Exception as e:
            logger.error(f"Error in agent advertisement listener: {e}")
            logger.error(traceback.format_exc())


class _AgentRequestListener(dds.DynamicData.DataReaderListener):
    """
    DDS listener for agent-to-agent RPC requests.
    
    Handles incoming agent requests via DDS callback, performing RPC v2
    content filtering (GUID-based targeting) and scheduling async processing.
    """
    
    def __init__(self, parent_mixin):
        """
        Initialize listener with reference to parent mixin.
        
        Args:
            parent_mixin: AgentCommunicationMixin instance that owns this listener
        """
        super().__init__()
        self._outer = parent_mixin
    
    def on_data_available(self, reader):
        """
        DDS callback invoked when agent request arrives.
        
        Processes RPC v2 content filtering (target_service_guid, service_instance_tag)
        and schedules async processing in the event loop.
        
        Args:
            reader: DDS DataReader with available request samples
        """
        try:
            # Get all available samples using the replier's take_requests method
            samples = self._outer.agent_replier.take_requests()
            
            for request, info in samples:
                if request is None or info.state.instance_state != dds.InstanceState.ALIVE:
                    continue
                
                # RPC v2: Content filtering based on target_service_guid
                try:
                    target_guid = request.get_string("target_service_guid")
                    service_tag = request.get_string("service_instance_tag")
                    
                    # Get our replier GUID (stored during setup)
                    our_guid = getattr(self._outer, 'agent_replier_guid', '')
                    
                    # Check if this is a broadcast (empty target_guid) or targeted to us
                    is_broadcast = not target_guid or target_guid == ""
                    is_targeted_to_us = target_guid == our_guid
                    
                    # Check if service_instance_tag matches (if set)
                    tag_matches = True
                    if service_tag and hasattr(self._outer.parent_agent, 'service_instance_tag'):
                        tag_matches = service_tag == self._outer.parent_agent.service_instance_tag
                    
                    if not is_broadcast and not is_targeted_to_us:
                        continue
                        
                    if not tag_matches:
                        continue
                    
                except Exception as e:
                    # If fields don't exist, fall back to processing (backward compat)
                    logger.debug(f"Could not read RPC v2 fields, processing anyway: {e}")
                
                # CRITICAL: DDS callbacks run in a different thread than the asyncio event loop
                # Use run_coroutine_threadsafe to schedule the async task in the correct event loop
                try:
                    asyncio.run_coroutine_threadsafe(
                        self._outer._process_agent_request(request, info),
                        self._outer.parent_agent.loop
                    )
                except Exception as schedule_error:
                    logger.error(f"Error scheduling agent request processing: {schedule_error}")
                    logger.error(traceback.format_exc())
                    
        except Exception as e:
            logger.error(f"Error in AgentRequestListener.on_data_available: {e}")
            logger.error(traceback.format_exc())


# ==========================================================================
# AGENT COMMUNICATION MIXIN - Main Class
# ==========================================================================

class AgentCommunicationMixin:
    """
    Mixin class that provides agent-to-agent communication capabilities.
    
    This class can be mixed into GenesisAgent to add:
    - Automatic agent discovery via DDS advertisements
    - Dynamic RPC connection management
    - Agent-to-agent request/reply communication
    - Rich query API for discovering agents by capability, specialization, etc.
    
    Usage:
        class GenesisAgent(AgentCommunicationMixin):  # Multiple inheritance
            ...
    
    See module docstring for comprehensive architecture overview.
    """
    
    # ==========================================================================
    # INITIALIZATION & CORE DATA STRUCTURES
    # ==========================================================================
    
    def __init__(self):
        """Initialize agent communication capabilities"""
        # Store active agent connections (agent_id -> rpc.Requester)
        self.agent_connections: Dict[str, rpc.Requester] = {}
        
        # Agent discovery state (DDS is single source of truth - no local cache)
        # DDS reader with TRANSIENT_LOCAL durability maintains history
        self.advertisement_reader = None  # Set during discovery setup
        
        # Agent discovery callbacks (similar to function discovery callbacks)
        self.agent_discovery_callbacks: List = []
        
        # Unified advertisement writer/reader for all discovery
        self.advertisement_writer = None
        self.advertisement_topic = None
        self.advertisement_type = None
        
        # Initialize agent-to-agent RPC types
        self.agent_request_type = None
        self.agent_reply_type = None
        
        # Agent RPC replier for receiving requests from other agents
        self.agent_replier = None
        
        # Flag to track if agent communication is enabled
        self._agent_communication_enabled = False
    
    # ==========================================================================
    # AGENT DISCOVERY SETUP - Passive Background Discovery
    # ==========================================================================
    # Methods for initializing agent discovery infrastructure.
    # Discovery is passive - DDS listeners continuously receive advertisements.
    # DDS (with TRANSIENT_LOCAL) is the single source of truth - no local cache.
    # ==========================================================================
    
    def _initialize_agent_rpc_types(self):
        """
        Load GenesisRPCRequest and GenesisRPCReply types from datamodel XML.
        
        These types define the RPC message schemas for agent-to-agent communication.
        The same types are used for interface-to-agent communication, but on different
        topics to maintain traffic separation. See module docstring for architectural rationale.
        
        Called during agent communication setup to prepare for agent-to-agent RPC.
        
        Returns:
            bool: True if types loaded successfully, False on error
            
        Note:
            Failure to load these types will prevent agent-to-agent communication
            but won't affect interface-to-agent or function calling capabilities.
        """
        try:
            config_path = get_datamodel_path()
            type_provider = dds.QosProvider(config_path)
            
            # Load agent-to-agent communication types from datamodel.xml
            self.agent_request_type = type_provider.type("genesis_lib", "GenesisRPCRequest")
            self.agent_reply_type = type_provider.type("genesis_lib", "GenesisRPCReply")
            
            logger.info("Agent-to-agent RPC types loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load agent-to-agent RPC types: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _get_agent_service_name(self, agent_id: str) -> str:
        """
        Generate RPC service name for an agent.
        
        With RPC v2, all instances of the same service type share unified topics.
        This returns the base service name if available (set during agent initialization),
        otherwise generates a default name from the agent_id.
        
        Args:
            agent_id: Unique identifier for the agent
            
        Returns:
            Service name for RPC topic generation (e.g., "Chat" or "AgentService_<uuid>")
            
        Note:
            Individual instances are targeted via replier_guid, not separate topic names.
            The base_service_name is preferred as it enables topic sharing across agent instances.
        """
        # Prefer base_service_name if set during initialization
        if hasattr(self, 'base_service_name') and self.base_service_name:
            return self.base_service_name
        
        # Fallback: Generate from agent_id for agents without explicit service type
        return f"AgentService_{agent_id}"
    
    # ==========================================================================
    # AGENT DISCOVERY QUERY API - Public Methods for Finding Agents
    # ==========================================================================
    # These methods provide various ways to query discovered agents.
    # All operate by querying DDS directly (single source of truth - no caching).
    # Performance: O(n) scans of DDS reader history.
    #
    # Method Patterns:
    # - get_*() methods: Return List[Dict[str, Any]] (full agent info)
    # - find_*() methods: Return List[str] (agent IDs only)
    # - is_*() methods: Return bool (existence checks)
    # - wait_for_*() methods: Return bool (async wait for condition)
    # ==========================================================================
    
    def get_discovered_agents(self) -> Dict[str, Dict[str, Any]]:
        """
        Get currently available agents by querying DDS reader on-demand.
        
        DDS (with TRANSIENT_LOCAL durability) is the single source of truth.
        No local cache maintained - each access queries DDS directly.
        
        Returns:
            Dictionary mapping agent_id -> agent_info containing:
            - agent_id, name, agent_type, service_name
            - capabilities, specializations, classification_tags
            - model_info, performance_metrics, default_capable
            - last_seen timestamp
            
        Note:
            NOT_ALIVE instances are automatically filtered out by DDS.
            Only currently alive agents are returned.
        """
        if not self.advertisement_reader:
            logger.warning("Advertisement reader not initialized, returning empty dict")
            return {}
        
        agents: Dict[str, Dict[str, Any]] = {}
        
        try:
            # Read all available samples from DDS reader (TRANSIENT_LOCAL history)
            # Use read() instead of take() to preserve samples for future queries
            # DDS automatically filters out NOT_ALIVE instances
            samples = self.advertisement_reader.read()
            
            for sample, info in samples:
                # Skip invalid samples or not-alive instances
                if sample is None or info.state.instance_state != dds.InstanceState.ALIVE:
                    continue
                
                try:
                    # Parse agent advertisement from DDS sample
                    agent_id = sample.get_string("advertisement_id") or ""
                    
                    # Skip our own advertisement
                    if hasattr(self, 'app') and agent_id == self.app.agent_id:
                        continue
                    
                    name = sample.get_string("name") or ""
                    description = sample.get_string("description") or ""
                    service_name = sample.get_string("service_name") or ""
                    last_seen = sample.get_int64("last_seen") if hasattr(sample, 'get_int64') else 0
                    payload_str = sample.get_string("payload") or "{}"
                    
                    try:
                        payload = json.loads(payload_str)
                    except Exception:
                        payload = {}
                    
                    agent_type = payload.get("agent_type", "")
                    capabilities = payload.get("capabilities", [])
                    specializations = payload.get("specializations", [])
                    classification_tags = payload.get("classification_tags", [])
                    model_info = payload.get("model_info")
                    performance_metrics = payload.get("performance_metrics")
                    default_capable = bool(payload.get("default_capable", True))
                    
                    agent_info = {
                        "agent_id": agent_id,
                        "name": name,
                        "agent_type": agent_type,
                        "service_name": service_name,
                        "description": description,
                        "last_seen": last_seen,
                        "capabilities": capabilities,
                        "specializations": specializations,
                        "classification_tags": classification_tags,
                        "model_info": model_info,
                        "performance_metrics": performance_metrics,
                        "default_capable": default_capable,
                    }
                    
                    agents[agent_id] = agent_info
                    
                except Exception as e:
                    logger.warning(f"Failed to parse agent advertisement: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error reading agents from DDS: {e}")
        
        return agents
    
    def add_agent_discovery_callback(self, callback: callable) -> None:
        """
        Register a callback to be invoked when a new agent advertisement is received.
        
        The callback is invoked within the DDS listener thread context when an agent
        advertisement arrives. Keep callbacks lightweight to avoid blocking discovery.
        
        Note: Callback is for notification only - agent data is NOT cached locally.
        To query agents, use get_discovered_agents() which reads from DDS directly.
        
        Args:
            callback: Function with signature callback(agent_info: Dict[str, Any])
                     Will receive the full agent_info dict containing capabilities,
                     specializations, and metadata.
                     
        Example:
            def on_agent_found(agent_info):
                print(f"Found agent: {agent_info['name']}")
                
            agent.add_agent_discovery_callback(on_agent_found)
        """
        if callback not in self.agent_discovery_callbacks:
            self.agent_discovery_callbacks.append(callback)
            logger.debug(f"Registered agent discovery callback: {callback}")
    
    def is_agent_discovered(self, agent_id: str) -> bool:
        """
        Check if a specific agent has been discovered by querying DDS.
        
        Args:
            agent_id: Unique identifier of the agent to check
            
        Returns:
            True if agent is currently alive in DDS, False otherwise
        """
        discovered_agents = self.get_discovered_agents()
        return agent_id in discovered_agents
    
    async def wait_for_agent(self, agent_id: str, timeout_seconds: float = 30.0) -> bool:
        """
        Wait for a specific agent to be discovered via DDS advertisement.
        
        This method uses an event-based approach, waiting for the discovery callback
        to signal agent arrival rather than busy-polling.
        
        Args:
            agent_id: Unique identifier of the agent to wait for
            timeout_seconds: Maximum time to wait before giving up
            
        Returns:
            True if agent was discovered within timeout, False otherwise
            
        Example:
            if await agent.wait_for_agent("weather-agent-uuid", timeout_seconds=10):
                response = await agent.send_agent_request("weather-agent-uuid", "Hello")
        """
        logger.info(f"Waiting for agent {agent_id} (timeout: {timeout_seconds}s)")
        
        # Fast path: already discovered
        if self.is_agent_discovered(agent_id):
            logger.info(f"Agent {agent_id} already discovered")
            return True
        
        # Event-based waiting instead of polling
        discovery_event = asyncio.Event()
        
        def discovery_callback(agent_info: Dict[str, Any]) -> None:
            if agent_info.get('agent_id') == agent_id:
                discovery_event.set()
        
        # Register temporary callback
        self.add_agent_discovery_callback(discovery_callback)
        
        try:
            # Wait with timeout
            await asyncio.wait_for(discovery_event.wait(), timeout=timeout_seconds)
            logger.info(f"Agent {agent_id} discovered successfully")
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for agent {agent_id} after {timeout_seconds}s")
            return False
            
        finally:
            # Clean up callback
            if discovery_callback in self.agent_discovery_callbacks:
                self.agent_discovery_callbacks.remove(discovery_callback)
    
    def _setup_agent_discovery(self):
        """
        Set up agent discovery for agent-to-agent communication.
        
        Creates a DDS DataReader with content filtering to discover other agents
        via the unified Advertisement topic. Only AGENT-kind advertisements are
        received (kind=1), filtered at the DDS layer for efficiency.
        
        Architecture:
            - Uses AdvertisementBus for shared topic access
            - Content-filtered topic: Only receives AGENT advertisements
            - QoS: TRANSIENT_LOCAL durability to receive historical agents
            - Listener callback: Populates self.discovered_agents on discovery
            
        Returns:
            bool: True if discovery setup successful, False on error
            
        Note:
            QoS settings must exactly match AdvertisementBus writer to ensure
            proper matching and historical data delivery.
        """
        try:
            # Validate DDS participant availability
            if not hasattr(self, 'app') or not hasattr(self.app, 'participant'):
                logger.error("Cannot set up agent discovery: no DDS participant available")
                return False
            
            # Set up unified advertisement reader for agent discovery
            if not self._create_advertisement_reader():
                logger.error("Failed to create advertisement reader")
                return False
            
            logger.info("Agent discovery setup completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set up agent discovery: {e}")
            logger.error(traceback.format_exc())
            return False

    def _create_advertisement_reader(self):
        """
        Create DDS DataReader for agent advertisements with content filtering.
        
        Sets up:
            1. Content-filtered topic (only AGENT advertisements, kind=1)
            2. DataReader with TRANSIENT_LOCAL QoS matching writer
            3. Listener callback for automatic agent discovery
            
        Returns:
            bool: True if reader created successfully, False otherwise
        """
        try:
            # Get advertisement type and shared bus
            config_path = get_datamodel_path()
            provider = dds.QosProvider(config_path)
            self.advertisement_type = provider.type("genesis_lib", "GenesisAdvertisement")
            
            bus = AdvertisementBus.get(self.app.participant)
            ad_topic = bus.topic
            
            # Create content-filtered topic for AGENT advertisements only (kind=1)
            # DDS-layer filtering is more efficient than in-code filtering
            filtered_topic = dds.DynamicData.ContentFilteredTopic(
                ad_topic,
                f"AgentDiscoveryFilter_{self.agent_name}",
                dds.Filter("kind = %0", ["1"])  # Filter for AGENT kind enum value
            )
            
            # Configure QoS to match AdvertisementBus writer
            # CRITICAL: Exact QoS match required for proper DDS matching
            ad_reader_qos = dds.QosProvider.default.datareader_qos
            ad_reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            ad_reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            ad_reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
            ad_reader_qos.history.depth = 500
            
            # Create listener for automatic agent discovery
            ad_listener = _AgentAdvertisementListener(self)
            
            # Create reader with listener attached from creation
            # Attaching listener during creation ensures we receive historical data
            self.advertisement_reader = dds.DynamicData.DataReader(
                self.app.participant,
                filtered_topic,
                ad_reader_qos,
                ad_listener,
                dds.StatusMask.DATA_AVAILABLE
            )
            
            logger.info("Advertisement reader created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create advertisement reader: {e}")
            logger.error(traceback.format_exc())
            return False

    def _on_agent_advertisement_received(self, ad_sample):
        """
        Handle discovered unified agent advertisement.
        
        Parses agent advertisement and triggers discovery callbacks for monitoring/topology.
        Does NOT cache data locally - DDS (TRANSIENT_LOCAL) is the single source of truth.
        
        Args:
            ad_sample: DDS DynamicData sample containing agent advertisement
        """
        try:
            # Content filter ensures only AGENT ads are delivered - no in-code filtering needed
            agent_id = ad_sample.get_string("advertisement_id") or ""
            name = ad_sample.get_string("name") or ""
            description = ad_sample.get_string("description") or ""
            service_name = ad_sample.get_string("service_name") or ""
            last_seen = ad_sample.get_int64("last_seen") if hasattr(ad_sample, 'get_int64') else 0
            payload_str = ad_sample.get_string("payload") or "{}"
            
            try:
                payload = json.loads(payload_str)
            except Exception:
                payload = {}
                
            agent_type = payload.get("agent_type", "")
            capabilities = payload.get("capabilities", [])
            specializations = payload.get("specializations", [])
            classification_tags = payload.get("classification_tags", [])
            model_info = payload.get("model_info")
            performance_metrics = payload.get("performance_metrics")
            default_capable = bool(payload.get("default_capable", True))
            
            # Skip our own advertisement
            if hasattr(self, 'app') and agent_id == self.app.agent_id:
                return
            
            # Build agent_info for callback notification
            agent_info = {
                "agent_id": agent_id,
                "name": name,
                "agent_type": agent_type,
                "service_name": service_name,
                "description": description,
                "last_seen": last_seen,
                "capabilities": capabilities,
                "specializations": specializations,
                "classification_tags": classification_tags,
                "model_info": model_info,
                "performance_metrics": performance_metrics,
                "default_capable": default_capable,
            }
            
            logger.info(f"Received agent advertisement: {name} ({agent_id}) service={service_name}")
            
            # Trigger callbacks for monitoring/graph topology
            # No caching - callbacks are for notification only
            for callback in self.agent_discovery_callbacks:
                try:
                    callback(agent_info)
                except Exception as e:
                    logger.error(f"Error in agent discovery callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing agent advertisement: {e}")
    
    def _setup_agent_capability_publishing(self):
        """Set up agent capability publishing for advertising this agent"""
        try:
            logger.info("Setting up agent capability publishing")
            
            # Ensure we have access to the DDS participant
            if not hasattr(self, 'app') or not hasattr(self.app, 'participant'):
                logger.error("Cannot set up agent capability publishing: no DDS participant available")
                return False
            
            # Legacy AgentCapability topic/writer removed - now using unified Advertisement topic
            
            # Get unified advertisement writer via shared bus
            config_path = get_datamodel_path()
            type_provider = dds.QosProvider(config_path)
            try:
                self.advertisement_type = type_provider.type("genesis_lib", "GenesisAdvertisement")
                bus = AdvertisementBus.get(self.app.participant)
                self.advertisement_topic = bus.topic
                self.advertisement_writer = bus.writer
                logger.info("Using unified Advertisement topic for agent capability publishing")
            except Exception as e:
                logger.error(f"Failed to set up unified advertisement writer: {e}")
                return False
            
            logger.info("Agent capability publishing setup completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set up agent capability publishing: {e}")
            return False
    
    def publish_agent_capability(self, agent_capabilities: Optional[Dict[str, Any]] = None):
        """
        Publish agent capability to the unified Advertisement topic.
        This allows other agents to discover this agent and its capabilities.
        """
        try:
            # Get enhanced capabilities from the agent
            agent_capabilities = agent_capabilities or self.get_agent_capabilities()
            
            # Process capabilities lists
            capabilities_list = agent_capabilities.get("capabilities", [])
            if isinstance(capabilities_list, str):
                capabilities_list = [capabilities_list]
            elif not isinstance(capabilities_list, list):
                capabilities_list = []
            
            specializations_list = agent_capabilities.get("specializations", [])
            if isinstance(specializations_list, str):
                specializations_list = [specializations_list]
            elif not isinstance(specializations_list, list):
                specializations_list = []
            
            classification_tags_list = agent_capabilities.get("classification_tags", [])
            if isinstance(classification_tags_list, str):
                classification_tags_list = [classification_tags_list]
            elif not isinstance(classification_tags_list, list):
                classification_tags_list = []
            
            # Publish to unified Advertisement topic
            ad = dds.DynamicData(self.advertisement_type)
            ad["advertisement_id"] = self.app.agent_id
            # AdvertisementKind: FUNCTION=0, AGENT=1, REGISTRATION=2
            ad["kind"] = 1  # AGENT
            ad["name"] = self.agent_name
            ad["description"] = self.description or ""
            ad["provider_id"] = str(self.advertisement_writer.instance_handle)
            ad["service_name"] = self._get_agent_service_name(self.app.agent_id)
            ad["last_seen"] = int(time.time() * 1000)
            
            payload = {
                "agent_type": self.agent_type,
                "capabilities": capabilities_list,
                "specializations": specializations_list,
                "classification_tags": classification_tags_list,
                "model_info": agent_capabilities.get("model_info", {}),
                "performance_metrics": agent_capabilities.get("performance_metrics", {}),
                "default_capable": agent_capabilities.get("default_capable", True),
                "prefered_name": self.agent_name,
            }
            ad["payload"] = json.dumps(payload)
            
            self.advertisement_writer.write(ad)
            self.advertisement_writer.flush()
            logger.debug(f"Published agent capability advertisement for {self.agent_name}")
            
        except Exception as e:
            logger.error(f"Error publishing agent capability for {self.agent_name}: {e}")
            logger.error(traceback.format_exc())
    
    # _on_agent_capability_received() removed - now using _on_agent_advertisement_received() for unified discovery
    
    # ==========================================================================
    # AGENT DISCOVERY AND QUERY METHODS
    # ==========================================================================
    # These methods provide various ways to query discovered agents based on
    # capabilities, specializations, and characteristics.
    # All methods query DDS directly via get_discovered_agents() - no caching.
    #
    # Return type patterns:
    # - get_*()  methods return List[Dict[str, Any]] (full agent info)
    # - find_*() methods return List[str] (agent IDs only)
    # ==========================================================================
    
    def get_agents_by_type(self, agent_type: str) -> List[Dict[str, Any]]:
        """
        Get all discovered agents of a specific type.
        
        Args:
            agent_type: The agent type to filter by (exact match)
            
        Returns:
            List of full agent info dicts for matching agents
            
        Example:
            weather_agents = agent.get_agents_by_type("WeatherAgent")
        """
        discovered_agents = self.get_discovered_agents()
        return [
            agent_info for agent_info in discovered_agents.values()
            if agent_info.get("agent_type") == agent_type
        ]
    
    def search_agents(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Search for agents using fuzzy text matching across multiple fields.
        
        Searches in: agent_type, service_name, description (case-insensitive).
        Use this for human-initiated searches or exploratory queries.
        
        Args:
            search_term: Text to search for (case-insensitive substring match)
            
        Returns:
            List of full agent info dicts for matching agents
            
        Example:
            # Find any agents related to "weather"
            agents = agent.search_agents("weather")
        """
        discovered_agents = self.get_discovered_agents()
        
        if not search_term:
            return list(discovered_agents.values())
        
        search_lower = search_term.lower()
        matching_agents = []
        
        for agent_info in discovered_agents.values():
            if (search_lower in agent_info.get("agent_type", "").lower() or
                search_lower in agent_info.get("service_name", "").lower() or
                search_lower in agent_info.get("description", "").lower()):
                matching_agents.append(agent_info)
        
        return matching_agents
    
    def find_agents_by_capability(self, capability: str) -> List[str]:
        """
        Find agents that advertise a specific capability (exact match).
        
        Searches the 'capabilities' list field in agent advertisements.
        Use this for programmatic routing based on declared capabilities.
        
        Args:
            capability: Exact capability string to match
            
        Returns:
            List of agent IDs that declare this capability
            
        Example:
            # Find agents that can generate images
            image_agents = agent.find_agents_by_capability("image_generation")
        """
        discovered_agents = self.get_discovered_agents()
        matching_agents = []
        
        for agent_id, agent_info in discovered_agents.items():
            capabilities = self._extract_list_field(agent_info, 'capabilities')
            if capability in capabilities:
                matching_agents.append(agent_id)
        
        return matching_agents
    
    def find_agents_by_specialization(self, domain: str) -> List[str]:
        """
        Find agents with expertise in a specific domain (case-insensitive match).
        
        Searches the 'specializations' list field in agent advertisements.
        Use this to find domain experts for specialized tasks.
        
        Args:
            domain: Specialization domain (e.g., "weather", "finance", "medical")
            
        Returns:
            List of agent IDs with matching specialization
            
        Example:
            # Find financial experts
            finance_agents = agent.find_agents_by_specialization("finance")
        """
        discovered_agents = self.get_discovered_agents()
        matching_agents = []
        domain_lower = domain.lower()
        
        for agent_id, agent_info in discovered_agents.items():
            specializations = self._extract_list_field(agent_info, 'specializations')
            if domain_lower in [spec.lower() for spec in specializations]:
                matching_agents.append(agent_id)
        
        return matching_agents
    
    def find_general_agents(self) -> List[str]:
        """
        Find agents that can handle general requests (default_capable = True).
        
        Returns agents that don't require specific domain knowledge.
        Use this for fallback routing when no specialist is available.
        
        Returns:
            List of agent IDs that can handle general requests
            
        Example:
            # Get general-purpose agents for fallback
            general_agents = agent.find_general_agents()
        """
        discovered_agents = self.get_discovered_agents()
        general_agents = []
        
        for agent_id, agent_info in discovered_agents.items():
            default_capable = self._extract_bool_field(agent_info, 'default_capable', default=False)
            if default_capable:
                general_agents.append(agent_id)
        
        return general_agents
    
    def find_specialized_agents(self) -> List[str]:
        """
        Find agents that are specialized (default_capable = False).
        
        Returns agents that focus on specific domains/tasks.
        Use this to find experts before falling back to generalists.
        
        Returns:
            List of agent IDs that are specialized agents
            
        Example:
            # Try specialists first
            specialists = agent.find_specialized_agents()
        """
        discovered_agents = self.get_discovered_agents()
        specialized_agents = []
        
        for agent_id, agent_info in discovered_agents.items():
            default_capable = self._extract_bool_field(agent_info, 'default_capable', default=True)
            if not default_capable:
                specialized_agents.append(agent_id)
        
        return specialized_agents
    
    async def get_best_agent_for_request(self, request: str) -> Optional[str]:
        """
        Use AI classifier to find the best agent for a specific request.
        
        This is the recommended approach for intelligent agent routing.
        Uses semantic understanding of the request to match against agent
        capabilities, specializations, and descriptions.
        
        Requires agent_classifier to be configured during initialization.
        
        Args:
            request: The request text to classify
            
        Returns:
            Agent ID of the best matching agent, or None if:
            - No classifier available
            - No suitable agent found
            - Classification error occurred
            
        Example:
            # Let AI find the best agent
            agent_id = await agent.get_best_agent_for_request(
                "What's the weather in London?"
            )
            if agent_id:
                response = await agent.send_agent_request(agent_id, ...)
        """
        if not hasattr(self, 'agent_classifier') or not self.agent_classifier:
            logger.warning("No agent classifier available for intelligent routing")
            return None
        
        try:
            best_agent = await self.agent_classifier.classify_request(
                request, 
                self.discovered_agents
            )
            return best_agent
        except Exception as e:
            logger.error(f"Error in agent classification: {e}")
            return None
    
    def get_agents_by_performance_metric(self, metric_name: str, 
                                         min_value: Optional[float] = None,
                                         max_value: Optional[float] = None) -> List[str]:
        """
        Find agents based on performance metrics.
        
        Args:
            metric_name: Name of the metric to check (e.g., "latency_ms", "success_rate")
            min_value: Minimum value for the metric (inclusive, optional)
            max_value: Maximum value for the metric (inclusive, optional)
            
        Returns:
            List of agent IDs that meet the performance criteria
            
        Example:
            # Find fast agents
            fast_agents = agent.get_agents_by_performance_metric(
                "latency_ms", 
                max_value=100.0
            )
        """
        matching_agents = []
        for agent_id, agent_info in self.discovered_agents.items():
            performance_metrics = self._extract_dict_field(agent_info, 'performance_metrics')
            
            if metric_name not in performance_metrics:
                continue
            
            try:
                metric_value = float(performance_metrics[metric_name])
                
                # Check constraints
                if min_value is not None and metric_value < min_value:
                    continue
                if max_value is not None and metric_value > max_value:
                    continue
                    
                matching_agents.append(agent_id)
            except (ValueError, TypeError):
                # Skip agents with non-numeric metric values
                continue
        
        return matching_agents
    
    def get_agent_info_by_capability(self, capability: str) -> List[Dict[str, Any]]:
        """
        Get full agent information for agents with a specific capability.
        
        Similar to find_agents_by_capability() but returns full agent info dicts
        instead of just IDs.
        
        Args:
            capability: The capability to search for
            
        Returns:
            List of agent info dicts for agents with the capability
            
        Example:
            # Get detailed info about image generation agents
            image_agents = agent.get_agent_info_by_capability("image_generation")
            for agent in image_agents:
                print(f"{agent['name']}: {agent['description']}")
        """
        matching_agents = []
        for agent_id, agent_info in self.discovered_agents.items():
            capabilities = self._extract_list_field(agent_info, 'capabilities')
            if capability in capabilities:
                matching_agents.append(agent_info)
        
        return matching_agents
    
    def get_agents_by_model_type(self, model_type: str) -> List[str]:
        """
        Find agents using a specific AI model.
        
        Searches the 'model_info.model' field for substring matches.
        Useful for routing based on model capabilities or costs.
        
        Args:
            model_type: Model identifier to search for (e.g., "gpt-4", "claude-3")
            
        Returns:
            List of agent IDs using the specified model type
            
        Example:
            # Find all Claude agents
            claude_agents = agent.get_agents_by_model_type("claude")
        """
        matching_agents = []
        model_lower = model_type.lower()
        
        for agent_id, agent_info in self.discovered_agents.items():
            model_info = self._extract_dict_field(agent_info, 'model_info')
            agent_model = model_info.get('model', '')
            
            if model_lower in agent_model.lower():
                matching_agents.append(agent_id)
        
        return matching_agents
    
    # ==========================================================================
    # HELPER METHODS FOR FIELD EXTRACTION
    # ==========================================================================
    # Centralized defensive parsing to avoid repetition across query methods
    
    def _extract_list_field(self, agent_info: Dict[str, Any], field_name: str) -> List:
        """
        Safely extract a list field from agent info, handling various formats.
        
        Args:
            agent_info: Agent information dictionary
            field_name: Name of the field to extract
            
        Returns:
            List value, or empty list if field missing/invalid
        """
        value = agent_info.get(field_name, [])
        
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            try:
                parsed = json.loads(value) if value else []
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        else:
            return []
    
    def _extract_dict_field(self, agent_info: Dict[str, Any], field_name: str) -> Dict:
        """
        Safely extract a dict field from agent info, handling various formats.
        
        Args:
            agent_info: Agent information dictionary
            field_name: Name of the field to extract
            
        Returns:
            Dict value, or empty dict if field missing/invalid
        """
        value = agent_info.get(field_name, {})
        
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            try:
                parsed = json.loads(value) if value else {}
                return parsed if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, TypeError):
                return {}
        else:
            return {}
    
    def _extract_bool_field(self, agent_info: Dict[str, Any], field_name: str, 
                           default: bool = False) -> bool:
        """
        Safely extract a boolean field from agent info, handling various formats.
        
        Args:
            agent_info: Agent information dictionary
            field_name: Name of the field to extract
            default: Default value if field missing/invalid
            
        Returns:
            Boolean value
        """
        value = agent_info.get(field_name, default)
        
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.lower() == 'true'
        elif isinstance(value, int):
            return bool(value)
        else:
            return default
    
    # ==========================================================================
    # AGENT-TO-AGENT RPC INFRASTRUCTURE
    # ==========================================================================
    # Core RPC setup for receiving and processing agent-to-agent requests.
    # Uses DDS listener callbacks for efficient asynchronous request handling.
    # Separate from interface-to-agent RPC (see architectural decision at top).
    # ==========================================================================
    
    def _setup_agent_rpc_service(self):
        """
        Set up RPC service for receiving requests from other agents.
        
        Creates an RPC Replier with the "_AgentRPC" suffix to distinguish from
        interface-to-agent RPC and prevent service name collisions.
        
        Returns:
            bool: True if setup successful, False otherwise
        """
        try:
            logger.info("Setting up agent RPC service for receiving agent requests")
            
            # Ensure we have access to the DDS participant and agent ID
            if not hasattr(self, 'app') or not hasattr(self.app, 'participant'):
                logger.error("Cannot set up agent RPC service: no DDS participant available")
                return False
            
            if not hasattr(self.app, 'agent_id'):
                logger.error("Cannot set up agent RPC service: no agent_id available")
                return False
            
            # Ensure RPC types are loaded
            if not self.agent_request_type or not self.agent_reply_type:
                logger.error("Cannot set up agent RPC service: RPC types not loaded")
                return False
            
            # Generate unique service name for this agent
            # CRITICAL: Agent-to-agent RPC must use a DIFFERENT service name than Interface-to-Agent RPC
            # to avoid service name collisions. Append "_AgentRPC" to distinguish them.
            base_agent_service_name = self._get_agent_service_name(self.app.agent_id)
            agent_service_name = f"{base_agent_service_name}_AgentRPC"
            logger.info(f"Creating agent RPC service with name: {agent_service_name}")
            
            # Create replier for agent-to-agent communication using unified RPC v2 naming
            self.agent_replier = rpc.Replier(
                request_type=self.agent_request_type,
                reply_type=self.agent_reply_type,
                participant=self.app.participant,
                service_name=f"rti/connext/genesis/rpc/{agent_service_name}"
            )
            
            # RPC v2: Store replier GUID for content filtering
            from genesis_lib.utils.guid_utils import format_guid
            self.agent_replier_guid = format_guid(self.agent_replier.reply_datawriter.instance_handle)
            logger.debug(f"Agent-to-agent replier GUID: {self.agent_replier_guid}")
            
            # Set up listener for incoming requests
            if self._setup_agent_request_listener():
                logger.info(f"Agent RPC service '{agent_service_name}' created successfully")
                return True
            else:
                logger.error("Failed to set up agent request listener")
                return False
            
        except Exception as e:
            logger.error(f"Failed to set up agent RPC service: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _setup_agent_request_listener(self):
        """
        Set up listener for incoming agent requests using DDS callbacks.
        
        Creates and attaches a DataReaderListener to handle agent-to-agent RPC
        requests asynchronously via callbacks rather than polling.
        
        Returns:
            bool: True if listener setup successful, False otherwise
        """
        try:
            # Create listener using module-level helper class
            self.agent_request_listener = _AgentRequestListener(self)
            
            # Attach listener to the replier's request DataReader (not the replier itself)
            mask = dds.StatusMask.DATA_AVAILABLE
            self.agent_replier.request_datareader.set_listener(self.agent_request_listener, mask)
            
            logger.info("Agent-to-agent request listener setup completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set up agent request listener: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def _process_agent_request(self, request, info):
        """
        Process an agent-to-agent request and send reply.
        
        Extracts request data, invokes the abstract process_agent_request method,
        and sends the reply with RPC v2 fields.
        
        Args:
            request: DDS request sample
            info: DDS sample info
        """
        try:
            # Extract request data including RPC v2 fields
            request_data = {
                "message": request.get_string("message"),
                "conversation_id": request.get_string("conversation_id")
            }
            
            # Extract RPC v2 fields for echo back
            try:
                service_tag = request.get_string("service_instance_tag")
                request_data["service_instance_tag"] = service_tag
            except:
                service_tag = ""
            
            logger.debug(f"Received agent request: {request_data['message'][:100]}")
            
            # Process the request using the abstract method
            try:
                response_data = await self.process_agent_request(request_data)
            except Exception as e:
                logger.error(f"Error processing agent request: {e}")
                logger.error(traceback.format_exc())
                response_data = {
                    "message": f"Error processing request: {str(e)}",
                    "status": -1,
                    "conversation_id": request_data.get("conversation_id", "")
                }
            
            # Create reply sample with RPC v2 fields
            reply_sample = dds.DynamicData(self.agent_reply_type)
            # Ensure message is always a string, never None
            message = response_data.get("message") or ""
            reply_sample.set_string("message", str(message) if message else "")
            reply_sample.set_int32("status", response_data.get("status", 0))
            reply_sample.set_string("conversation_id", response_data.get("conversation_id", ""))
            
            # RPC v2: Include our replier_guid for subsequent targeted requests
            reply_sample.set_string("replier_service_guid", self.agent_replier_guid)
            
            # Echo back the service_instance_tag if present in request
            reply_sample.set_string("service_instance_tag", service_tag)
            
            # Send reply
            self.agent_replier.send_reply(reply_sample, info)
            
            logger.debug(f"Sent agent reply ({len(str(message))} chars)")
            
        except Exception as e:
            logger.error(f"Error in _process_agent_request: {e}")
            logger.error(traceback.format_exc())
            # Send error reply with RPC v2 fields
            try:
                reply_sample = dds.DynamicData(self.agent_reply_type)
                reply_sample.set_string("message", f"Error processing request: {str(e)}")
                reply_sample.set_int32("status", -1)
                reply_sample.set_string("conversation_id", request_data.get("conversation_id", ""))
                reply_sample.set_string("replier_service_guid", self.agent_replier_guid)
                reply_sample.set_string("service_instance_tag", "")
                self.agent_replier.send_reply(reply_sample, info)
            except Exception as reply_error:
                logger.error(f"Error sending error reply: {reply_error}")
    
    async def _handle_agent_requests(self):
        """
        DEPRECATED: Agent-to-agent requests are now handled via DDS listener callbacks.
        This method is kept for backward compatibility but is a no-op.
        The actual handling happens in AgentRequestListener.on_data_available().
        """
        # No-op: All agent request handling is done via callbacks now
        pass
    
    async def connect_to_agent(self, target_agent_id: str, timeout_seconds: float = 5.0) -> bool:
        """
        Establish RPC connection to another agent.
        
        Creates an RPC Requester for the target agent and waits for DDS matching.
        Once connected, the requester is cached in self.agent_connections for reuse.
        
        Connection Process:
        1. Check for existing connection (returns immediately if found)
        2. Verify agent is discovered via advertisement
        3. Look up agent's service name from discovered_agents
        4. Create RPC Requester with "_AgentRPC" suffix
        5. Wait for DDS DataReader/DataWriter matching
        6. Cache requester for subsequent send_agent_request() calls
        
        Args:
            target_agent_id: Unique identifier of the agent to connect to
            timeout_seconds: Maximum time to wait for DDS matching (default: 5.0s)
            
        Returns:
            True if connection established successfully, False otherwise
            
        Note:
            Uses "_AgentRPC" suffix on service names to distinguish agent-to-agent
            RPC from interface-to-agent RPC. This prevents DDS topic collisions.
            
        Example:
            # Connect and send request
            if await agent.connect_to_agent("weather-agent-uuid"):
                response = await agent.send_agent_request(
                    "weather-agent-uuid", 
                    "What's the weather?"
                )
        """
        try:
            logger.info(f"Connecting to agent {target_agent_id}")
            
            # Check if we already have a connection
            if target_agent_id in self.agent_connections:
                logger.debug(f"Reusing existing connection to agent {target_agent_id}")
                return True
            
            # Look up target agent in discovered agents
            if not self.is_agent_discovered(target_agent_id):
                logger.warning(f"Agent {target_agent_id} not discovered yet")
                return False
            
            # Ensure RPC types are loaded
            if not self.agent_request_type or not self.agent_reply_type:
                logger.error("Cannot connect to agent: RPC types not loaded")
                return False
            
            # Ensure we have access to the DDS participant
            if not hasattr(self, 'app') or not hasattr(self.app, 'participant'):
                logger.error("Cannot connect to agent: no DDS participant available")
                return False
            
            # Get target agent's service name from discovered agent info
            discovered_agents = self.get_discovered_agents()
            agent_info = discovered_agents.get(target_agent_id, {})
            target_service_name = agent_info.get("service_name")
            
            if not target_service_name:
                # Fallback to generating service name if not stored
                target_service_name = self._get_agent_service_name(target_agent_id)
                logger.warning(f"No service_name in discovered agent info, using fallback: {target_service_name}")
            
            # CRITICAL: Agent-to-agent RPC must use "_AgentRPC" suffix to distinguish from Interface-to-Agent RPC
            agent_to_agent_service_name = f"{target_service_name}_AgentRPC"
            logger.info(f"Creating RPC requester for agent-to-agent service: {agent_to_agent_service_name}")
            
            # Create RPC requester using unified RPC v2 naming
            requester = rpc.Requester(
                request_type=self.agent_request_type,
                reply_type=self.agent_reply_type,
                participant=self.app.participant,
                service_name=f"rti/connext/genesis/rpc/{agent_to_agent_service_name}"
            )
            
            # Wait for DDS match with timeout
            logger.debug(f"Waiting for DDS match with agent {target_agent_id} (timeout: {timeout_seconds}s)")
            start_time = time.time()
            
            while True:
                # Check if we have a match
                matched_count = requester.matched_replier_count
                if matched_count > 0:
                    logger.info(f"Successfully connected to agent {target_agent_id}")
                    self.agent_connections[target_agent_id] = requester
                    return True
                
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed >= timeout_seconds:
                    logger.warning(f"Timeout connecting to agent {target_agent_id} after {timeout_seconds}s")
                    requester.close()
                    return False
                
                # Wait a bit before checking again
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error connecting to agent {target_agent_id}: {e}")
            return False
    
    # ==========================================================================
    # CONNECTION MANAGEMENT AND CLEANUP
    # ==========================================================================
    # Public API for sending requests and managing connections to other agents.
    # Includes cleanup methods for graceful shutdown of agent communication.
    # ==========================================================================
    
    async def send_agent_request(self, 
                               target_agent_id: str, 
                               message: str, 
                               conversation_id: Optional[str] = None,
                               timeout_seconds: float = 10.0,
                               target_agent_guid: Optional[str] = None,
                               service_instance_tag: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Send a request to another agent with RPC v2 broadcast + GUID targeting.
        
        RPC v2 Behavior:
        - First request: Broadcasts to all agents (empty target_service_guid)
        - First reply: Captures replier_service_guid for subsequent targeted requests
        - Subsequent requests: Targeted to specific agent GUID via content filtering
        
        Args:
            target_agent_id: ID of the target agent (for connection management)
            message: Request message
            conversation_id: Optional conversation ID for tracking
            timeout_seconds: Request timeout
            target_agent_guid: Optional explicit GUID to target (overrides stored)
            service_instance_tag: Optional tag for migration scenarios (e.g., "production", "v2")
            
        Returns:
            Reply data or None if failed
        """
        try:
            logger.info(f"Sending request to agent {target_agent_id}: {message}")
            
            # Ensure connection exists
            if not await self.connect_to_agent(target_agent_id, timeout_seconds=timeout_seconds):
                logger.error(f"Failed to connect to agent {target_agent_id}")
                return None
            
            # Get the requester
            requester = self.agent_connections[target_agent_id]
            
            # Generate conversation ID if not provided
            if conversation_id is None:
                conversation_id = str(uuid.uuid4())
            
            # RPC v2: Determine target GUID (explicit > stored > broadcast)
            # Track per-connection target GUIDs
            if not hasattr(self, 'agent_target_guids'):
                self.agent_target_guids = {}
                
            effective_target_guid = target_agent_guid or self.agent_target_guids.get(target_agent_id, "")
            effective_service_tag = service_instance_tag or ""
            is_broadcast = not effective_target_guid
            
            # Create GenesisRPCRequest with unified RPC fields
            request_sample = dds.DynamicData(self.agent_request_type)
            request_sample.set_string("message", message)
            request_sample.set_string("conversation_id", conversation_id)
            request_sample.set_string("target_service_guid", effective_target_guid)
            request_sample.set_string("service_instance_tag", effective_service_tag)
            
            # Send via RPC
            logger.debug(f"Sending {'broadcast' if is_broadcast else 'targeted'} RPC request to agent {target_agent_id} (guid: {effective_target_guid or 'all'})")
            request_id = requester.send_request(request_sample)
            
            # Wait for and receive the reply
            timeout_duration = dds.Duration.from_seconds(timeout_seconds)
            replies = requester.receive_replies(
                max_wait=timeout_duration,
                min_count=1,
                related_request_id=request_id
            )
            
            if not replies:
                logger.warning(f"No reply received from agent {target_agent_id} within {timeout_seconds}s")
                return None
            
            # Process the reply
            reply_sample = replies[0].data
            
            # Parse response with RPC v2 fields
            response_data = {
                "message": reply_sample.get_string("message"),
                "status": reply_sample.get_int32("status"),
                "conversation_id": reply_sample.get_string("conversation_id")
            }
            
            # RPC v2: Capture replier_service_guid from first successful reply
            try:
                replier_guid = reply_sample.get_string("replier_service_guid")
                if replier_guid and target_agent_id not in self.agent_target_guids:
                    logger.info(f"First reply from agent {target_agent_id}, locking to GUID: {replier_guid}")
                    self.agent_target_guids[target_agent_id] = replier_guid
            except:
                pass
            
            logger.info(f"Received reply from agent {target_agent_id}: {response_data['message']}")
            return response_data
            
        except Exception as e:
            logger.error(f"Error sending request to agent {target_agent_id}: {e}")
            return None
    
    def _cleanup_agent_connection(self, agent_id: str):
        """
        Clean up connection to a specific agent.
        
        Closes the RPC Requester and removes it from the connection cache.
        Called when an agent connection is no longer needed or has failed.
        
        Args:
            agent_id: Unique identifier of the agent whose connection to clean up
            
        Note:
            Errors during cleanup are logged but not raised, allowing graceful
            degradation during shutdown or error recovery.
        """
        if agent_id in self.agent_connections:
            try:
                requester = self.agent_connections[agent_id]
                if hasattr(requester, 'close'):
                    requester.close()
                del self.agent_connections[agent_id]
                logger.debug(f"Cleaned up connection to agent {agent_id}")
            except Exception as e:
                logger.warning(f"Error cleaning up connection to agent {agent_id}: {e}")
    
    @abstractmethod
    async def process_agent_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a request from another agent.
        
        This method must be implemented by subclasses to handle agent-to-agent requests.
        It is invoked by _process_agent_request() when an agent request arrives via DDS.
        
        Args:
            request: Dictionary containing the request data:
                - message: str - The request message/prompt
                - conversation_id: str - Conversation ID for tracking
                - service_instance_tag: str - Optional service tag (RPC v2)
            
        Returns:
            Dictionary containing the response data:
                - message: str - The response message (required)
                - status: int - Status code (0 = success, <0 = error)
                - conversation_id: str - Echo back the conversation ID
                
        Note:
            This abstract method is placed here (near cleanup methods) rather than
            at the class top because it's closely related to _process_agent_request()
            which calls it. Placement emphasizes the request processing flow.
        """
        pass
    
    def _cleanup_agent_connections(self):
        """
        Clean up all agent connections.
        
        Iterates through all cached RPC Requesters and closes them.
        Called during agent shutdown via close_agent_communication().
        
        Note:
            Errors closing individual connections are logged but don't stop
            the cleanup process. Ensures all connections are attempted even
            if some fail.
        """
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
        """
        Clean up all agent communication resources.
        
        Comprehensive shutdown method that closes:
        - All active agent RPC connections (requesters)
        - Agent RPC replier (for receiving requests)
        - Advertisement reader (for agent discovery)
        - Advertisement writer/topic (shared via AdvertisementBus)
        
        Called during agent shutdown to ensure graceful cleanup of DDS resources.
        Errors during cleanup are logged but don't interrupt the shutdown process.
        
        Note:
            Advertisement writer/topic are shared resources managed by AdvertisementBus,
            so close() calls may be no-ops depending on the implementation.
        """
        logger.info("Closing agent communication")
        
        try:
            # Clean up all agent connections (RPC requesters)
            self._cleanup_agent_connections()
            
            # Close agent replier (for receiving agent-to-agent requests)
            if self.agent_replier and hasattr(self.agent_replier, 'close'):
                self.agent_replier.close()
                self.agent_replier = None
            
            # Close unified advertisement reader (for agent discovery)
            if self.advertisement_reader and hasattr(self.advertisement_reader, 'close'):
                try:
                    self.advertisement_reader.close()
                except Exception:
                    pass  # Reader may be shared, ignore close errors
                self.advertisement_reader = None
            
            # Close advertisement writer/topic (shared via AdvertisementBus)
            if self.advertisement_writer and hasattr(self.advertisement_writer, 'close'):
                try:
                    self.advertisement_writer.close()
                except Exception:
                    pass  # Shared resource, may already be closed
                self.advertisement_writer = None
                
            if self.advertisement_topic and hasattr(self.advertisement_topic, 'close'):
                try:
                    self.advertisement_topic.close()
                except Exception:
                    pass  # Shared resource, may already be closed
                self.advertisement_topic = None
            
            logger.info("Agent communication closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing agent communication: {e}") 
