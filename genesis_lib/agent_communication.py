"""
Agent-to-Agent Communication Module

This module provides the AgentCommunicationMixin class that enables agent-to-agent
communication capabilities in Genesis. It can be mixed into GenesisAgent or 
MonitoredAgent to add agent discovery, connection management, and RPC communication
between agents.

Key Features:
- Agent discovery through unified Advertisement topic (kind=AGENT)
- Dynamic RPC connection management
- Agent-to-agent request/reply handling
- Connection pooling and cleanup

Copyright (c) 2025, RTI & Jason Upchurch
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

class AgentCommunicationMixin:
    """
    Mixin class that provides agent-to-agent communication capabilities.
    This can be mixed into GenesisAgent or MonitoredAgent.
    """
    
    def __init__(self):
        """Initialize agent communication capabilities"""
        logger.info("🚀 TRACE: AgentCommunicationMixin.__init__() starting")
        
        # Store active agent connections (agent_id -> rpc.Requester)
        self.agent_connections: Dict[str, rpc.Requester] = {}
        logger.debug("✅ TRACE: agent_connections dict initialized")
        
        # Store discovered agents (agent_id -> agent_info)
        self.discovered_agents: Dict[str, Dict[str, Any]] = {}
        logger.debug("✅ TRACE: discovered_agents dict initialized")
        
        # Agent discovery callbacks (similar to function discovery callbacks)
        self.agent_discovery_callbacks: List = []
        logger.debug("✅ TRACE: agent_discovery_callbacks list initialized")
        
        # Unified advertisement writer/reader for all discovery
        self.advertisement_writer = None
        self.advertisement_reader = None
        self.advertisement_topic = None
        self.advertisement_type = None
        logger.debug("✅ TRACE: Advertisement writer/reader/topic/type initialized to None")
        
        # Initialize agent-to-agent RPC types
        self.agent_request_type = None
        self.agent_reply_type = None
        logger.debug("✅ TRACE: RPC types initialized to None")
        
        # Agent RPC replier for receiving requests from other agents
        self.agent_replier = None
        logger.debug("✅ TRACE: agent_replier initialized to None")
        
        # Flag to track if agent communication is enabled
        self._agent_communication_enabled = False
        logger.debug("✅ TRACE: agent_communication_enabled flag set to False")
        
        # Agent capability reader for discovering other agents
        self.agent_capability_reader = None
        self.agent_capability_subscriber = None
        logger.debug("✅ TRACE: agent_capability_reader and subscriber initialized to None")
        
        logger.info("✅ TRACE: AgentCommunicationMixin.__init__() completed successfully")
    
    def _initialize_agent_rpc_types(self):
        """Load AgentAgentRequest and AgentAgentReply types from XML"""
        try:
            logger.info("🚀 TRACE: _initialize_agent_rpc_types() starting")
            
            # Get types from XML
            logger.debug("📄 TRACE: Getting datamodel path...")
            config_path = get_datamodel_path()
            logger.debug(f"📄 TRACE: Datamodel path: {config_path}")
            
            logger.debug("🏗️ TRACE: Creating QosProvider...")
            type_provider = dds.QosProvider(config_path)
            logger.debug("✅ TRACE: QosProvider created successfully")
            
            # Load agent-to-agent communication types
            logger.debug("📥 TRACE: Loading AgentAgentRequest type...")
            self.agent_request_type = type_provider.type("genesis_lib", "AgentAgentRequest")
            logger.debug("✅ TRACE: AgentAgentRequest type loaded")
            
            logger.debug("📥 TRACE: Loading AgentAgentReply type...")
            self.agent_reply_type = type_provider.type("genesis_lib", "AgentAgentReply")
            logger.debug("✅ TRACE: AgentAgentReply type loaded")
            
            logger.info("✅ TRACE: Successfully loaded AgentAgentRequest and AgentAgentReply types")
            return True
            
        except Exception as e:
            logger.error(f"💥 TRACE: Failed to load agent-to-agent RPC types: {e}")
            import traceback
            logger.error(f"💥 TRACE: Traceback: {traceback.format_exc()}")
            return False
    
    def _get_agent_service_name(self, agent_id: str) -> str:
        """Generate RPC service name for an agent.

        With RPC v2, all instances of the same service type share unified topics.
        This returns the base service name, not unique per-instance names.
        Individual instances are targeted via their replier_guid, not separate topic names.
        """
        try:
            if hasattr(self, 'rpc_service_name') and self.rpc_service_name:
                return self.rpc_service_name
            if hasattr(self, 'base_service_name') and hasattr(self, 'app'):
                return self.base_service_name
        except Exception:
            pass
        return f"AgentService_{agent_id}"
    
    def get_discovered_agents(self) -> Dict[str, Dict[str, Any]]:
        """Return dictionary of discovered agents"""
        return self.discovered_agents.copy()
    
    def add_agent_discovery_callback(self, callback):
        """
        Register a callback to be called when a new agent is discovered.
        Callback will receive agent_info dict as parameter.
        
        Args:
            callback: Function to call when agent discovered, signature: callback(agent_info)
        """
        if callback not in self.agent_discovery_callbacks:
            self.agent_discovery_callbacks.append(callback)
            logger.debug(f"Registered agent discovery callback: {callback}")
    
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
            logger.info("🚀 TRACE: _setup_agent_discovery() starting")
            
            # Ensure we have access to the DDS participant
            logger.debug("🔍 TRACE: Checking for DDS participant...")
            if not hasattr(self, 'app') or not hasattr(self.app, 'participant'):
                logger.error("💥 TRACE: Cannot set up agent discovery: no DDS participant available")
                return False
            logger.debug("✅ TRACE: DDS participant available")
            
            # AgentCapability topic removed - now using unified Advertisement topic for agent discovery
            logger.debug("✅ TRACE: Agent discovery will use unified Advertisement topic (AGENT kind)")
            
            # Set up unified advertisement reader to populate discovered_agents via shared AdvertisementBus
            try:
                print("🏗️ PRINT: Setting up unified advertisement reader...")
                logger.info("🏗️ TRACE: Setting up unified advertisement reader...")
                
                # Get datamodel path for type provider
                config_path = get_datamodel_path()
                provider = dds.QosProvider(config_path)
                self.advertisement_type = provider.type("genesis_lib", "GenesisAdvertisement")
                # Use AdvertisementBus to get the shared topic (avoids duplicate creation)
                print("🔍 PRINT: Getting AdvertisementBus...")
                logger.info("🔍 TRACE: Getting AdvertisementBus...")
                bus = AdvertisementBus.get(self.app.participant)
                ad_topic = bus.topic
                print(f"✅ PRINT: Got advertisement topic: {ad_topic.name}")
                print(f"🔍 PRINT: Topic object id: {id(ad_topic)}, Writer topic id: {id(bus.writer.topic)}")
                print(f"🔍 PRINT: Same topic object? {ad_topic is bus.writer.topic}")
                logger.info(f"✅ TRACE: Got advertisement topic: {ad_topic.name}")
                
                class _AdvertisementListener(dds.DynamicData.NoOpDataReaderListener):
                    def __init__(self, outer):
                        super().__init__()
                        self._outer = outer
                    def on_data_available(self, reader):
                        # ALWAYS print to verify callback is invoked
                        print(f"🔔🔔🔔 PRINT: _AdvertisementListener.on_data_available() CALLED!")
                        try:
                            enable_tracing = getattr(self._outer, 'enable_tracing', False)
                            if enable_tracing:
                                print(f"🔔 PRINT: _AdvertisementListener.on_data_available() called for agent {getattr(self._outer, 'agent_name', 'Unknown')}")
                            logger.info(f"🔔 TRACE: _AdvertisementListener.on_data_available() called")
                            
                            samples = reader.take()  # Use take() to consume samples
                            print(f"📊 PRINT: Got {len(samples)} advertisement samples")
                            logger.info(f"📊 TRACE: Got {len(samples)} advertisement samples")
                            for data, info in samples:
                                print(f"🔍 PRINT: Sample state={info.state.sample_state}, instance_state={info.state.instance_state}")
                                if info.state.sample_state == dds.SampleState.NOT_READ and info.state.instance_state == dds.InstanceState.ALIVE:
                                    if enable_tracing:
                                        print(f"📨 PRINT: Processing advertisement sample...")
                                    print(f"📨 PRINT: Processing valid advertisement sample...")
                                    logger.info("📨 TRACE: Processing advertisement sample...")
                                    self._outer._on_agent_advertisement_received(data)
                                else:
                                    print(f"⏭️ PRINT: Skipping sample (already read or not alive)")
                        except Exception as e:
                            # NEVER silently swallow exceptions - log them!
                            logger.error(f"💥 ERROR: _AdvertisementListener failed to process advertisement: {e}")
                            logger.error(f"💥 ERROR: Traceback: {traceback.format_exc()}")
                            if enable_tracing:
                                print(f"💥 PRINT: _AdvertisementListener error: {e}")
                                print(f"💥 PRINT: Traceback: {traceback.format_exc()}")
                
                print("🏗️ PRINT: Creating advertisement listener instance...")
                logger.info("🏗️ TRACE: Creating advertisement listener instance...")
                ad_listener = _AdvertisementListener(self)
                print("🏗️ PRINT: Creating content-filtered topic for AGENT advertisements...")
                logger.info("🏗️ TRACE: Creating content-filtered topic for AGENT advertisements...")
                
                # Create content-filtered topic to only receive AGENT advertisements (kind=1)
                # This filters at DDS layer - much more efficient than in-code filtering!
                filtered_topic = dds.DynamicData.ContentFilteredTopic(
                    ad_topic,
                    f"AgentDiscoveryFilter_{self.agent_name}",  # Unique name per agent
                    dds.Filter("kind = %0", ["1"])  # AGENT kind enum value
                )
                
                print("🏗️ PRINT: Creating advertisement DataReader with content filter...")
                logger.info("🏗️ TRACE: Creating advertisement DataReader with content filter...")
                
                # Create reader with EXACTLY the same QoS pattern as AdvertisementBus writer
                # Match advertisement_bus.py lines 44-48 exactly
                ad_reader_qos = dds.QosProvider.default.datareader_qos
                ad_reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
                ad_reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
                ad_reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
                ad_reader_qos.history.depth = 500
                print(f"📊 PRINT: Reader QoS: durability={ad_reader_qos.durability.kind}, reliability={ad_reader_qos.reliability.kind}, history_depth={ad_reader_qos.history.depth}")
                
                # CRITICAL: Set listener BEFORE creating reader to receive TRANSIENT_LOCAL historical data
                print("🏗️ PRINT: Creating DataReader with listener and content filter attached from creation...")
                self.advertisement_reader = dds.DynamicData.DataReader(
                    self.app.participant,
                    filtered_topic,  # Use content-filtered topic instead of base topic
                    ad_reader_qos,
                    ad_listener,  # Attach listener during creation, not after!
                    dds.StatusMask.DATA_AVAILABLE  # Listen for data available events
                )
                print("✅ PRINT: Unified advertisement reader created successfully!")
                logger.info("✅ TRACE: Unified advertisement reader created via AdvertisementBus")
            except Exception as e:
                print(f"💥 PRINT: Unified advertisement reader failed: {e}")
                logger.error(f"💥 ERROR: Unified advertisement reader failed: {e}")
                logger.error(f"💥 ERROR: Traceback: {traceback.format_exc()}")
            
            logger.info("✅ TRACE: Agent discovery setup completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"💥 TRACE: Failed to set up agent discovery: {e}")
            import traceback
            logger.error(f"💥 TRACE: Traceback: {traceback.format_exc()}")
            return False

    def _on_agent_advertisement_received(self, ad_sample):
        """Handle discovered unified agent advertisement"""
        print(f"🎯 PRINT: _on_agent_advertisement_received() called")
        try:
            # Content filter ensures only AGENT ads are delivered - no in-code filtering needed
            agent_id = ad_sample.get_string("advertisement_id") or ""
            name = ad_sample.get_string("name") or ""
            description = ad_sample.get_string("description") or ""
            service_name = ad_sample.get_string("service_name") or ""
            print(f"🔍 PRINT: Advertisement: agent_id={agent_id}, name={name}, service={service_name}")
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
            # Skip our own
            if hasattr(self, 'app') and agent_id == self.app.agent_id:
                print(f"⏭️ PRINT: Skipping own advertisement (agent_id={agent_id})")
                return
            agent_info = {
                "agent_id": agent_id,
                "name": name,
                "agent_type": agent_type,
                "service_name": service_name,
                "description": description,
                "last_seen": last_seen,
                "discovered_at": time.time(),
                "capabilities": capabilities,
                "specializations": specializations,
                "classification_tags": classification_tags,
                "model_info": model_info,
                "performance_metrics": performance_metrics,
                "default_capable": default_capable,
            }
            is_new_agent = agent_id not in self.discovered_agents
            self.discovered_agents[agent_id] = agent_info
            print(f"📝 PRINT: Added to discovered_agents: {name} (new={is_new_agent}), total agents: {len(self.discovered_agents)}")
            if is_new_agent:
                print(f"🎉 PRINT: Discovered new agent via Advertisement: {name} ({agent_id}) service={service_name}")
                logger.info(f"Discovered new agent via Advertisement: {name} ({agent_id}) service={service_name}")
                
                # Call agent discovery callbacks (for monitoring/graph topology)
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
        print(f"🚀 TRACE: publish_agent_capability() called for agent {self.agent_name}")
        
        try:
            # Get enhanced capabilities from the agent
            print(f"🔍 TRACE: Getting agent capabilities...")
            agent_capabilities = agent_capabilities or self.get_agent_capabilities()
            print(f"🔍 TRACE: Raw agent capabilities from get_agent_capabilities(): {agent_capabilities}")
            
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
            print("📡 PRINT: Publishing to unified Advertisement topic...")
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
            
            print(f"📡 PRINT: Writing advertisement for {self.agent_name} (service={ad['service_name']})...")
            self.advertisement_writer.write(ad)
            self.advertisement_writer.flush()
            print("✅ PRINT: Successfully published GenesisAdvertisement(kind=AGENT)")
            logger.debug("Published GenesisAdvertisement(kind=AGENT)")
            
        except Exception as e:
            print(f"❌ TRACE: Error publishing agent capability for {self.agent_name}: {e}")
            print(f"❌ TRACE: Exception details: {traceback.format_exc()}")
            logger.error(f"Error publishing agent capability: {e}")
            logger.error(traceback.format_exc())
    
    # _on_agent_capability_received() removed - now using _on_agent_advertisement_received() for unified discovery
    
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
    
    # Enhanced Discovery Methods for Step 3.5
    
    def find_agents_by_capability(self, capability: str) -> List[str]:
        """
        Find agents that advertise a specific capability.
        
        Args:
            capability: The specific capability to search for
            
        Returns:
            List of agent IDs that have the specified capability
        """
        matching_agents = []
        for agent_id, agent_info in self.discovered_agents.items():
            capabilities = agent_info.get('capabilities', [])
            if isinstance(capabilities, str):
                try:
                    capabilities = json.loads(capabilities) if capabilities else []
                except (json.JSONDecodeError, TypeError):
                    capabilities = []
            
            if capability in capabilities:
                matching_agents.append(agent_id)
        
        return matching_agents
    
    def find_agents_by_specialization(self, domain: str) -> List[str]:
        """
        Find agents with expertise in a specific domain.
        
        Args:
            domain: The specialization domain to search for (e.g., "weather", "finance")
            
        Returns:
            List of agent IDs with the specified specialization
        """
        matching_agents = []
        for agent_id, agent_info in self.discovered_agents.items():
            specializations = agent_info.get('specializations', [])
            if isinstance(specializations, str):
                try:
                    specializations = json.loads(specializations) if specializations else []
                except (json.JSONDecodeError, TypeError):
                    specializations = []
            
            if domain.lower() in [spec.lower() for spec in specializations]:
                matching_agents.append(agent_id)
        
        return matching_agents
    
    def find_general_agents(self) -> List[str]:
        """
        Find agents that can handle general requests (default_capable = True).
        
        Returns:
            List of agent IDs that can handle general requests
        """
        general_agents = []
        for agent_id, agent_info in self.discovered_agents.items():
            default_capable = agent_info.get('default_capable', False)
            if isinstance(default_capable, str):
                default_capable = default_capable.lower() == 'true'
            elif isinstance(default_capable, int):
                default_capable = bool(default_capable)
            
            if default_capable:
                general_agents.append(agent_id)
        
        return general_agents
    
    def find_specialized_agents(self) -> List[str]:
        """
        Find agents that are specialized (not default_capable).
        
        Returns:
            List of agent IDs that are specialized agents
        """
        specialized_agents = []
        for agent_id, agent_info in self.discovered_agents.items():
            default_capable = agent_info.get('default_capable', False)
            if isinstance(default_capable, str):
                default_capable = default_capable.lower() == 'true'
            elif isinstance(default_capable, int):
                default_capable = bool(default_capable)
            
            if not default_capable:
                specialized_agents.append(agent_id)
        
        return specialized_agents
    
    async def get_best_agent_for_request(self, request: str) -> Optional[str]:
        """
        Use the classifier to find the best agent for a specific request.
        
        Args:
            request: The request text to classify
            
        Returns:
            Agent ID of the best agent, or None if no suitable agent found
        """
        if not hasattr(self, 'agent_classifier') or not self.agent_classifier:
            logger.warning("No agent classifier available for get_best_agent_for_request")
            return None
        
        try:
            best_agent = await self.agent_classifier.classify_request(
                request, 
                self.discovered_agents
            )
            return best_agent
        except Exception as e:
            logger.error(f"Error classifying request for best agent: {e}")
            return None
    
    def get_agents_by_performance_metric(self, metric_name: str, min_value: Optional[float] = None, max_value: Optional[float] = None) -> List[str]:
        """
        Find agents based on performance metrics.
        
        Args:
            metric_name: Name of the performance metric to check
            min_value: Minimum value for the metric (optional)
            max_value: Maximum value for the metric (optional)
            
        Returns:
            List of agent IDs that meet the performance criteria
        """
        matching_agents = []
        for agent_id, agent_info in self.discovered_agents.items():
            performance_metrics = agent_info.get('performance_metrics', {})
            if isinstance(performance_metrics, str):
                try:
                    performance_metrics = json.loads(performance_metrics) if performance_metrics else {}
                except (json.JSONDecodeError, TypeError):
                    performance_metrics = {}
            
            if metric_name in performance_metrics:
                if min_value is None and max_value is None:
                    matching_agents.append(agent_id)
                else:
                    try:
                        metric_value = float(performance_metrics[metric_name])
                        
                        # Check min_value constraint
                        if min_value is not None and metric_value < min_value:
                            continue
                            
                        # Check max_value constraint  
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
        
        Args:
            capability: The capability to search for
            
        Returns:
            List of agent info dictionaries for agents with the capability
        """
        matching_agents = []
        for agent_id, agent_info in self.discovered_agents.items():
            capabilities = agent_info.get('capabilities', [])
            if isinstance(capabilities, str):
                try:
                    capabilities = json.loads(capabilities) if capabilities else []
                except (json.JSONDecodeError, TypeError):
                    capabilities = []
            
            if capability in capabilities:
                matching_agents.append(agent_info)
        
        return matching_agents
    
    def get_agents_by_model_type(self, model_type: str) -> List[str]:
        """
        Find agents using a specific model type (useful for AI agents).
        
        Args:
            model_type: The model type to search for (e.g., "claude-3-opus", "gpt-4")
            
        Returns:
            List of agent IDs using the specified model type
        """
        matching_agents = []
        for agent_id, agent_info in self.discovered_agents.items():
            model_info = agent_info.get('model_info', {})
            if isinstance(model_info, str):
                try:
                    model_info = json.loads(model_info) if model_info else {}
                except (json.JSONDecodeError, TypeError):
                    model_info = {}
            
            if isinstance(model_info, dict):
                agent_model = model_info.get('model', '')
                if model_type.lower() in agent_model.lower():
                    matching_agents.append(agent_id)
        
        return matching_agents
    
    def _setup_agent_rpc_service(self):
        """Set up RPC service for receiving requests from other agents"""
        try:
            print(f"🚀 PRINT: _setup_agent_rpc_service() starting for agent {getattr(self, 'agent_name', 'Unknown')}")
            logger.info("Setting up agent RPC service for receiving agent requests")
            
            # Ensure we have access to the DDS participant and agent ID
            if not hasattr(self, 'app') or not hasattr(self.app, 'participant'):
                print("💥 PRINT: Cannot set up agent RPC service: no DDS participant available")
                logger.error("Cannot set up agent RPC service: no DDS participant available")
                return False
            
            if not hasattr(self.app, 'agent_id'):
                print("💥 PRINT: Cannot set up agent RPC service: no agent_id available")
                logger.error("Cannot set up agent RPC service: no agent_id available")
                return False
            
            # Ensure RPC types are loaded
            if not self.agent_request_type or not self.agent_reply_type:
                print("💥 PRINT: Cannot set up agent RPC service: RPC types not loaded")
                logger.error("Cannot set up agent RPC service: RPC types not loaded")
                return False
            
            # Generate unique service name for this agent
            # CRITICAL: Agent-to-agent RPC must use a DIFFERENT service name than Interface-to-Agent RPC
            # to avoid service name collisions. Append "_AgentRPC" to distinguish them.
            base_agent_service_name = self._get_agent_service_name(self.app.agent_id)
            agent_service_name = f"{base_agent_service_name}_AgentRPC"
            print(f"🏗️ PRINT: Creating agent RPC service with name: {agent_service_name}")
            logger.info(f"Creating agent RPC service with name: {agent_service_name}")
            
            # Create replier for agent-to-agent communication
            print("🏗️ PRINT: Creating RPC Replier...")
            # Create agent replier using unified RPC v2 naming
            self.agent_replier = rpc.Replier(
                request_type=self.agent_request_type,
                reply_type=self.agent_reply_type,
                participant=self.app.participant,
                service_name=f"rti/connext/genesis/rpc/{agent_service_name}"
            )
            print("✅ PRINT: RPC Replier created successfully")
            
            # RPC v2: Store replier GUID for content filtering
            from genesis_lib.utils.guid_utils import format_guid
            self.agent_replier_guid = format_guid(self.agent_replier.reply_datawriter.instance_handle)
            logger.info(f"Agent-to-agent replier GUID: {self.agent_replier_guid}")
            
            # Set up listener for incoming requests
            print("🏗️ PRINT: Setting up agent request listener...")
            if self._setup_agent_request_listener():
                print(f"✅ PRINT: Agent RPC service '{agent_service_name}' created successfully with listener")
                logger.info(f"Agent RPC service '{agent_service_name}' created successfully with listener")
                return True
            else:
                print("💥 PRINT: Failed to set up agent request listener")
                logger.error("Failed to set up agent request listener")
                return False
            
        except Exception as e:
            print(f"💥 PRINT: Failed to set up agent RPC service: {e}")
            logger.error(f"Failed to set up agent RPC service: {e}")
            import traceback
            print(f"💥 PRINT: Traceback: {traceback.format_exc()}")
            return False
    
    def _setup_agent_request_listener(self):
        """Set up listener for incoming agent requests using DDS callbacks"""
        try:
            print("🏗️ PRINT: Setting up agent-to-agent request listener...")
            
            # Create listener class for agent-to-agent RPC requests
            class AgentRequestListener(dds.DynamicData.DataReaderListener):
                def __init__(self, outer):
                    super().__init__()
                    self._outer = outer
                    
                def on_data_available(self, reader):
                    # ALWAYS print to verify callback is invoked
                    agent_name = getattr(self._outer, 'agent_name', 'Unknown')
                    print(f"🔔🔔🔔 PRINT: AgentRequestListener.on_data_available() CALLED for {agent_name}!")
                    logger.info(f"AgentRequestListener.on_data_available() CALLED for {agent_name}")
                    
                    try:
                        # Get all available samples using the replier's take_requests method
                        samples = self._outer.agent_replier.take_requests()
                        print(f"📊 PRINT: AgentRequestListener got {len(samples)} agent request samples")
                        
                        for request, info in samples:
                            if request is None or info.state.instance_state != dds.InstanceState.ALIVE:
                                print(f"⏭️ PRINT: Skipping invalid agent request sample")
                                continue
                            
                            # RPC v2: Content filtering based on target_service_guid
                            # Extract target_service_guid from request if present
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
                                    logger.debug(f"⏭️ Skipping agent request targeted to different agent (target: {target_guid}, us: {our_guid})")
                                    continue
                                    
                                if not tag_matches:
                                    logger.debug(f"⏭️ Skipping agent request with non-matching service_instance_tag")
                                    continue
                                    
                                logger.debug(f"✅ Processing agent request ({'broadcast' if is_broadcast else 'targeted'}, tag: {service_tag or 'none'})")
                                
                            except Exception as e:
                                # If fields don't exist, fall back to processing (backward compat)
                                logger.warning(f"Could not read RPC v2 fields from agent request, processing anyway: {e}")
                            
                            print(f"📨 PRINT: Processing agent request sample...")
                            print(f"🔧 PRINT: Step 1 - Entering try block...")
                            # CRITICAL: DDS callbacks run in a different thread than the asyncio event loop
                            # Use run_coroutine_threadsafe to schedule the async task in the correct event loop
                            # The wrapper's parent_agent has the event loop
                            try:
                                print(f"🔧 PRINT: Step 2 - Inside try, about to call run_coroutine_threadsafe...")
                                print(f"🔧 PRINT: Loop = {self._outer.parent_agent.loop}")
                                print(f"🔧 PRINT: Loop running = {self._outer.parent_agent.loop.is_running()}")
                                future = asyncio.run_coroutine_threadsafe(
                                    self._outer._process_agent_request(request, info),
                                    self._outer.parent_agent.loop
                                )
                                print(f"✅ PRINT: run_coroutine_threadsafe returned future: {future}")
                            except Exception as schedule_error:
                                print(f"💥 PRINT: Error scheduling agent request processing: {schedule_error}")
                                logger.error(f"Error scheduling agent request processing: {schedule_error}")
                                logger.error(traceback.format_exc())
                    except Exception as e:
                        print(f"💥 PRINT: Error in AgentRequestListener.on_data_available: {e}")
                        logger.error(f"Error in AgentRequestListener.on_data_available: {e}")
                        logger.error(traceback.format_exc())
            
            # Create and attach the listener
            self.agent_request_listener = AgentRequestListener(self)
            # Attach listener to the replier's request DataReader (not the replier itself)
            mask = dds.StatusMask.DATA_AVAILABLE
            self.agent_replier.request_datareader.set_listener(self.agent_request_listener, mask)
            
            print("✅ PRINT: Agent-to-agent request listener attached successfully")
            logger.info("Agent-to-agent request listener setup completed (using callback approach)")
            return True
            
        except Exception as e:
            print(f"💥 PRINT: Failed to set up agent request listener: {e}")
            logger.error(f"Failed to set up agent request listener: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def _process_agent_request(self, request, info):
        """Process an agent-to-agent request and send reply"""
        # ALWAYS print at start to verify this method is being called
        agent_name = getattr(self, 'agent_name', 'Unknown')
        print(f"🚀🚀🚀 PRINT: _process_agent_request() STARTED for {agent_name}!")
        logger.info(f"_process_agent_request() STARTED for {agent_name}")
        
        try:
            # Check if tracing is enabled before printing
            enable_tracing = getattr(self, 'enable_tracing', False)
            
            # Extract request data including RPC v2 fields
            print(f"📥 PRINT: Extracting request data...")
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
            
            print(f"📥 PRINT: Extracted request data: {request_data}")
            
            if enable_tracing:
                print(f"📥 PRINT: Trace mode - Extracted request data: {request_data}")
            logger.info(f"Received agent request: {request_data['message']}")
            
            # Process the request using the abstract method
            print(f"🔄 PRINT: About to call process_agent_request() method...", flush=True)
            try:
                response_data = await self.process_agent_request(request_data)
                print(f"✅ PRINT: process_agent_request() returned: {response_data}", flush=True)
            except Exception as e:
                print(f"💥 PRINT: Error in process_agent_request(): {e}", flush=True)
                logger.error(f"Error processing agent request: {e}")
                logger.error(traceback.format_exc())
                response_data = {
                    "message": f"Error processing request: {str(e)}",
                    "status": -1,
                    "conversation_id": request_data.get("conversation_id", "")
                }
            
            print(f"📤 PRINT: About to create reply sample with data: {response_data}", flush=True)
            
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
            
            print(f"📤 PRINT: About to send reply via agent_replier...", flush=True)
            
            # Send reply
            self.agent_replier.send_reply(reply_sample, info)
            
            print(f"✅ PRINT: Agent-to-agent reply sent successfully! Message length: {len(str(message))}", flush=True)
            logger.info(f"Sent reply to agent request: {response_data.get('message', '')}")
            
        except Exception as e:
            enable_tracing = getattr(self, 'enable_tracing', False)
            if enable_tracing:
                print(f"💥 PRINT: Error in _process_agent_request(): {e}")
            logger.error(f"Error processing agent request: {e}")
            # Send error reply with RPC v2 fields
            try:
                reply_sample = dds.DynamicData(self.agent_reply_type)
                reply_sample.set_string("message", f"Error processing request: {str(e)}")
                reply_sample.set_int32("status", -1)
                reply_sample.set_string("conversation_id", request_data.get("conversation_id", ""))
                reply_sample.set_string("replier_service_guid", self.agent_replier_guid)  # RPC v2
                reply_sample.set_string("service_instance_tag", "")  # RPC v2
                self.agent_replier.send_reply(reply_sample, info)
                if enable_tracing:
                    print(f"✅ PRINT: Error reply sent")
            except Exception as reply_error:
                if enable_tracing:
                    print(f"💥 PRINT: Error sending error reply: {reply_error}")
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
        
        Args:
            target_agent_id: ID of the target agent
            timeout_seconds: Connection timeout
            
        Returns:
            True if connection successful, False otherwise
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
            agent_info = self.discovered_agents[target_agent_id]
            target_service_name = agent_info.get("service_name")
            print(f"🔍 PRINT: target_agent_id={target_agent_id}, agent_info={agent_info}")
            print(f"🔍 PRINT: target_service_name from agent_info: {target_service_name}")
            
            if not target_service_name:
                # Fallback to generating service name if not stored
                target_service_name = self._get_agent_service_name(target_agent_id)
                print(f"⚠️ PRINT: No service_name in discovered agent info, using fallback: {target_service_name}")
                logger.warning(f"No service_name in discovered agent info, using fallback: {target_service_name}")
            
            # CRITICAL: Agent-to-agent RPC must use "_AgentRPC" suffix to distinguish from Interface-to-Agent RPC
            agent_to_agent_service_name = f"{target_service_name}_AgentRPC"
            print(f"🚀 PRINT: Creating RPC requester for agent-to-agent service: {agent_to_agent_service_name}")
            logger.info(f"Creating RPC requester for agent-to-agent service: {agent_to_agent_service_name}")
            
            # Create RPC requester using unified RPC v2 naming
            requester = rpc.Requester(
                request_type=self.agent_request_type,
                reply_type=self.agent_reply_type,
                participant=self.app.participant,
                service_name=f"rti/connext/genesis/rpc/{agent_to_agent_service_name}"
            )
            
            # Wait for DDS match with timeout
            print(f"⏳ PRINT: Waiting for DDS match with agent {target_agent_id} (timeout: {timeout_seconds}s)")
            logger.debug(f"Waiting for DDS match with agent {target_agent_id} (timeout: {timeout_seconds}s)")
            start_time = time.time()
            
            while True:
                # Check if we have a match
                matched_count = requester.matched_replier_count
                if matched_count > 0:
                    print(f"✅ PRINT: Successfully connected to agent {target_agent_id} (matched repliers: {matched_count})")
                    logger.info(f"Successfully connected to agent {target_agent_id}")
                    self.agent_connections[target_agent_id] = requester
                    return True
                
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed >= timeout_seconds:
                    print(f"⏰ PRINT: Timeout connecting to agent {target_agent_id} after {timeout_seconds}s (matched: {matched_count})")
                    logger.warning(f"Timeout connecting to agent {target_agent_id} after {timeout_seconds}s")
                    requester.close()
                    return False
                
                # Log progress every second
                if int(elapsed) > int(elapsed - 0.1) and int(elapsed) % 1 == 0:
                    print(f"⏳ PRINT: Still waiting for match... elapsed={int(elapsed)}s, matched={matched_count}")
                
                # Wait a bit before checking again
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error connecting to agent {target_agent_id}: {e}")
            return False
    
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
            print(f"🚀 PRINT: send_agent_request() called for target {target_agent_id}")
            logger.info(f"Sending request to agent {target_agent_id}: {message}")
            
            # Ensure connection exists
            print(f"🔗 PRINT: Calling connect_to_agent({target_agent_id}, timeout={timeout_seconds})...")
            if not await self.connect_to_agent(target_agent_id, timeout_seconds=timeout_seconds):
                print(f"❌ PRINT: Failed to connect to agent {target_agent_id}")
                logger.error(f"Failed to connect to agent {target_agent_id}")
                return None
            print(f"✅ PRINT: Connected to agent {target_agent_id}")
            
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
            
            # Create AgentAgentRequest with RPC v2 fields
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
                    logger.info(f"✅ First reply from agent {target_agent_id}, locking to GUID: {replier_guid}")
                    self.agent_target_guids[target_agent_id] = replier_guid
            except:
                pass
            
            logger.info(f"Received reply from agent {target_agent_id}: {response_data['message']}")
            return response_data
            
        except Exception as e:
            logger.error(f"Error sending request to agent {target_agent_id}: {e}")
            return None
    
    def _cleanup_agent_connection(self, agent_id: str):
        """Clean up connection to a specific agent"""
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
            
            # Close agent capability publisher
            if self.agent_capability_publisher and hasattr(self.agent_capability_publisher, 'close'):
                self.agent_capability_publisher.close()
                self.agent_capability_publisher = None
            
            # Close agent capability reader
            if self.agent_capability_reader and hasattr(self.agent_capability_reader, 'close'):
                self.agent_capability_reader.close()
                self.agent_capability_reader = None
            # Close unified advertisement reader
            if self.advertisement_reader and hasattr(self.advertisement_reader, 'close'):
                try:
                    self.advertisement_reader.close()
                except Exception:
                    pass
                self.advertisement_reader = None
            
            # Close agent capability subscriber
            if self.agent_capability_subscriber and hasattr(self.agent_capability_subscriber, 'close'):
                self.agent_capability_subscriber.close()
                self.agent_capability_subscriber = None
            # Close advertisement writer/topic
            if self.advertisement_writer and hasattr(self.advertisement_writer, 'close'):
                try:
                    self.advertisement_writer.close()
                except Exception:
                    pass
                self.advertisement_writer = None
            if self.advertisement_topic and hasattr(self.advertisement_topic, 'close'):
                try:
                    self.advertisement_topic.close()
                except Exception:
                    pass
                self.advertisement_topic = None
            
            logger.info("Agent communication closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing agent communication: {e}") 
