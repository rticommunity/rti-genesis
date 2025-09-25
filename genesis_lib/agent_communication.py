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
        
        # Agent capability writer for advertising our capabilities
        self.agent_capability_writer = None
        self.agent_capability_topic = None
        self.agent_capability_publisher = None
        self.agent_capability_type = None  # Add this to store the DDS type
        logger.debug("✅ TRACE: capability writer/topic/publisher/type initialized to None")
        
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
            
            # Get AgentCapability type from XML
            logger.debug("📄 TRACE: Getting datamodel path for AgentCapability...")
            config_path = get_datamodel_path()
            logger.debug(f"📄 TRACE: Datamodel path: {config_path}")
            
            logger.debug("🏗️ TRACE: Creating QosProvider for AgentCapability...")
            type_provider = dds.QosProvider(config_path)
            logger.debug("✅ TRACE: QosProvider created")
            
            logger.debug("📥 TRACE: Loading AgentCapability type...")
            agent_capability_type = type_provider.type("genesis_lib", "AgentCapability")
            logger.debug("✅ TRACE: AgentCapability type loaded")
            
            # Find or create topic for AgentCapability
            logger.debug("🔍 TRACE: Finding or creating AgentCapability topic...")
            try:
                # Try to find existing topic first
                logger.debug("🔍 TRACE: Attempting to find existing AgentCapability topic...")
                self.agent_capability_topic = self.app.participant.find_topic("rti/connext/genesis/AgentCapability", dds.Duration.from_seconds(1))
                if self.agent_capability_topic is None:
                    logger.debug("🏗️ TRACE: Existing topic not found, creating new AgentCapability topic...")
                    # Create new topic if not found
                    self.agent_capability_topic = dds.DynamicData.Topic(
                        self.app.participant,
                        "rti/connext/genesis/AgentCapability",
                        agent_capability_type
                    )
                    logger.debug("✅ TRACE: New AgentCapability topic created")
                else:
                    logger.debug("✅ TRACE: Found existing AgentCapability topic")
            except Exception as topic_error:
                logger.debug(f"⚠️ TRACE: find_topic failed ({topic_error}), creating new topic...")
                # If find_topic fails, create new topic
                self.agent_capability_topic = dds.DynamicData.Topic(
                    self.app.participant,
                    "rti/connext/genesis/AgentCapability",
                    agent_capability_type
                )
                logger.debug("✅ TRACE: New AgentCapability topic created after find_topic failure")
            
            topic = self.agent_capability_topic
            logger.debug("✅ TRACE: AgentCapability topic ready")
            
            # Create DataReader for AgentCapability with listener
            logger.debug("🏗️ TRACE: Creating AgentCapabilityListener class...")
            class AgentCapabilityListener(dds.DynamicData.NoOpDataReaderListener):
                def __init__(self, agent_comm_mixin):
                    logger.debug("🚀 TRACE: AgentCapabilityListener.__init__() starting")
                    super().__init__()
                    self.agent_comm_mixin = agent_comm_mixin
                    logger.debug("✅ TRACE: AgentCapabilityListener.__init__() completed")
                
                def on_data_available(self, reader):
                    try:
                        # Check if tracing is enabled before printing
                        enable_tracing = getattr(self.agent_comm_mixin, 'enable_tracing', False)
                        if enable_tracing:
                            print(f"🔔 PRINT: AgentCapabilityListener.on_data_available() called for agent {getattr(self.agent_comm_mixin, 'agent_name', 'Unknown')}")
                        
                        # Get new data samples
                        samples = reader.take()
                        for data, info in samples:
                            # Check if the sample contains valid data that hasn't been read before
                            if info.state.sample_state == dds.SampleState.NOT_READ:
                                if data is None or info.state.instance_state != dds.InstanceState.ALIVE:
                                    continue
                                
                                # Process the agent capability announcement
                                self.agent_comm_mixin._on_agent_capability_received(data)
                            else:
                                continue
                    except Exception as e:
                        if enable_tracing:
                            print(f"💥 PRINT: Error processing agent capability data: {e}")
                        logger.error(f"💥 TRACE: Error processing agent capability data: {e}")
                        import traceback
                        if enable_tracing:
                            print(f"💥 PRINT: Traceback: {traceback.format_exc()}")
                        logger.error(f"💥 TRACE: Traceback: {traceback.format_exc()}")
            
            # Create reader with durable QoS and listener
            logger.debug("🏗️ TRACE: Creating DataReader for AgentCapability with durable QoS...")
            
            # Set up durable QoS for AgentCapability discovery
            reader_qos = dds.QosProvider.default.datareader_qos
            reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
            reader_qos.history.depth = 500
            reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            reader_qos.liveliness.kind = dds.LivelinessKind.AUTOMATIC
            reader_qos.liveliness.lease_duration = dds.Duration(seconds=2)
            
            # Create subscriber and store it for cleanup
            self.agent_capability_subscriber = dds.Subscriber(self.app.participant)
            
            # Create listener first
            logger.debug("🏗️ TRACE: Creating capability listener instance...")
            capability_listener = AgentCapabilityListener(self)
            logger.debug("✅ TRACE: Capability listener instance created")
            
            # Create DataReader with listener using the working pattern from FunctionRegistry
            self.agent_capability_reader = dds.DynamicData.DataReader(
                topic=topic,
                qos=reader_qos,
                listener=capability_listener,
                subscriber=self.agent_capability_subscriber,
                mask=dds.StatusMask.ALL
            )
            logger.debug("✅ TRACE: DataReader created with listener and durable QoS")
            
            logger.info("✅ TRACE: Agent discovery setup completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"💥 TRACE: Failed to set up agent discovery: {e}")
            import traceback
            logger.error(f"💥 TRACE: Traceback: {traceback.format_exc()}")
            return False
    
    def _setup_agent_capability_publishing(self):
        """Set up agent capability publishing for advertising this agent"""
        try:
            logger.info("Setting up agent capability publishing")
            
            # Ensure we have access to the DDS participant
            if not hasattr(self, 'app') or not hasattr(self.app, 'participant'):
                logger.error("Cannot set up agent capability publishing: no DDS participant available")
                return False
            
            # Get AgentCapability type from XML
            config_path = get_datamodel_path()
            type_provider = dds.QosProvider(config_path)
            agent_capability_type = type_provider.type("genesis_lib", "AgentCapability")
            
            # Use existing topic if already created, otherwise find or create it
            if not self.agent_capability_topic:
                try:
                    # Try to find existing topic first
                    self.agent_capability_topic = self.app.participant.find_topic("rti/connext/genesis/AgentCapability", dds.Duration.from_seconds(1))
                    if self.agent_capability_topic is None:
                        # Create new topic if not found
                        self.agent_capability_topic = dds.DynamicData.Topic(
                            self.app.participant,
                            "rti/connext/genesis/AgentCapability",
                            agent_capability_type
                        )
                except:
                    # If find_topic fails, create new topic
                    self.agent_capability_topic = dds.DynamicData.Topic(
                        self.app.participant,
                        "rti/connext/genesis/AgentCapability",
                        agent_capability_type
                    )
            
            # Create DataWriter for AgentCapability with durable QoS
            writer_qos = dds.QosProvider.default.datawriter_qos
            writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            writer_qos.history.kind = dds.HistoryKind.KEEP_LAST
            writer_qos.history.depth = 500
            writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            writer_qos.liveliness.kind = dds.LivelinessKind.AUTOMATIC
            writer_qos.liveliness.lease_duration = dds.Duration(seconds=2)
            
            # Create publisher and store it for cleanup
            self.agent_capability_publisher = dds.Publisher(self.app.participant)
            
            self.agent_capability_writer = dds.DynamicData.DataWriter(
                pub=self.agent_capability_publisher,
                topic=self.agent_capability_topic,
                qos=writer_qos,
                mask=dds.StatusMask.ALL
            )
            
            self.agent_capability_type = agent_capability_type
            
            logger.info("Agent capability publishing setup completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set up agent capability publishing: {e}")
            return False
    
    def publish_agent_capability(self, agent_capabilities: Optional[Dict[str, Any]] = None):
        """
        Publish agent capability to the DDS network.
        This allows other agents to discover this agent and its capabilities.
        """
        print(f"🚀 TRACE: publish_agent_capability() called for agent {self.agent_name}")
        
        try:
            # Get enhanced capabilities from the agent
            print(f"🔍 TRACE: Getting agent capabilities...")
            agent_capabilities = agent_capabilities or self.get_agent_capabilities()
            print(f"🔍 TRACE: Raw agent capabilities from get_agent_capabilities(): {agent_capabilities}")
            
            # Create the capability message with enhanced information
            capability = dds.DynamicData(self.agent_capability_type)
            capability["agent_id"] = self.app.agent_id
            capability["name"] = self.agent_name
            capability["agent_type"] = self.agent_type
            capability["service_name"] = self._get_agent_service_name(self.app.agent_id)
            capability["description"] = self.description
            
            # Enhanced capabilities - convert to list and then serialize as JSON string
            capabilities_list = agent_capabilities.get("capabilities", [])
            if isinstance(capabilities_list, str):
                capabilities_list = [capabilities_list]
            elif not isinstance(capabilities_list, list):
                capabilities_list = []
            
            print(f"🔍 TRACE: Processed capabilities list: {capabilities_list}")
            capability["capabilities"] = json.dumps(capabilities_list)  # Serialize as JSON string
            
            # Enhanced specializations - convert to list and then serialize as JSON string
            specializations_list = agent_capabilities.get("specializations", [])
            if isinstance(specializations_list, str):
                specializations_list = [specializations_list]
            elif not isinstance(specializations_list, list):
                specializations_list = []
            
            print(f"🔍 TRACE: Processed specializations list: {specializations_list}")
            capability["specializations"] = json.dumps(specializations_list)  # Serialize as JSON string
            
            # Enhanced classification tags - convert to list and then serialize as JSON string
            classification_tags_list = agent_capabilities.get("classification_tags", [])
            if isinstance(classification_tags_list, str):
                classification_tags_list = [classification_tags_list]
            elif not isinstance(classification_tags_list, list):
                classification_tags_list = []
            
            print(f"🔍 TRACE: Processed classification_tags list: {classification_tags_list}")
            capability["classification_tags"] = json.dumps(classification_tags_list)  # Serialize as JSON string
            
            # Enhanced model info - serialize as JSON string if not None
            model_info = agent_capabilities.get("model_info", None)
            if model_info is not None:
                capability["model_info"] = json.dumps(model_info)
            else:
                capability["model_info"] = ""
            
            # Enhanced performance metrics - serialize as JSON string if not None
            performance_metrics = agent_capabilities.get("performance_metrics", None)
            if performance_metrics is not None:
                capability["performance_metrics"] = json.dumps(performance_metrics)
            else:
                capability["performance_metrics"] = ""
            
            # Default capable flag
            default_capable = agent_capabilities.get("default_capable", True)
            capability["default_capable"] = 1 if default_capable else 0
            
            # Set timestamp
            capability["last_seen"] = int(time.time() * 1000)
            
            print(f"📊 TRACE: Final DDS capability message being published:")
            print(f"📊 TRACE:   agent_id: {capability['agent_id']}")
            print(f"📊 TRACE:   name: {capability['name']}")
            print(f"📊 TRACE:   agent_type: {capability['agent_type']}")
            print(f"📊 TRACE:   service_name: {capability['service_name']}")
            print(f"📊 TRACE:   description: {capability['description']}")
            print(f"📊 TRACE:   capabilities: {capability['capabilities']}")
            print(f"📊 TRACE:   specializations: {capability['specializations']}")
            print(f"📊 TRACE:   classification_tags: {capability['classification_tags']}")
            print(f"📊 TRACE:   model_info: {capability['model_info']}")
            print(f"📊 TRACE:   performance_metrics: {capability['performance_metrics']}")
            print(f"📊 TRACE:   default_capable: {capability['default_capable']}")
            print(f"📊 TRACE:   last_seen: {capability['last_seen']}")
            
            # Write the capability
            print(f"📡 TRACE: Writing capability to DDS...")
            self.agent_capability_writer.write(capability)
            self.agent_capability_writer.flush()
            print(f"✅ TRACE: Successfully published agent capability for {self.agent_name}")
            
        except Exception as e:
            print(f"❌ TRACE: Error publishing agent capability for {self.agent_name}: {e}")
            print(f"❌ TRACE: Exception details: {traceback.format_exc()}")
            logger.error(f"Error publishing agent capability: {e}")
            logger.error(traceback.format_exc())
    
    def _on_agent_capability_received(self, capability_sample):
        """Handle discovered agent capability announcements"""
        try:
            # Check if tracing is enabled before printing
            enable_tracing = getattr(self, 'enable_tracing', False)
            if enable_tracing:
                print(f"🔔 PRINT: _on_agent_capability_received() called for agent {getattr(self, 'agent_name', 'Unknown')}")
            
            # Extract agent information from the capability sample
            agent_id = capability_sample.get_string("agent_id")
            agent_name = capability_sample.get_string("name")
            agent_type = capability_sample.get_string("agent_type")
            service_name = capability_sample.get_string("service_name")
            description = capability_sample.get_string("description")
            last_seen = capability_sample.get_int64("last_seen")
            
            if enable_tracing:
                print(f"📥 PRINT: Received capability for agent_id: {agent_id}, name: {agent_name}")
            
            # Skip our own announcements
            if hasattr(self, 'app') and agent_id == self.app.agent_id:
                if enable_tracing:
                    print(f"⏭️ PRINT: Skipping own announcement for {agent_id}")
                return
            
            if enable_tracing:
                print(f"✅ PRINT: Processing capability for external agent: {agent_id}")
            
            # Parse enhanced capability fields
            capabilities_str = capability_sample.get_string("capabilities")
            specializations_str = capability_sample.get_string("specializations")
            model_info_str = capability_sample.get_string("model_info")
            classification_tags_str = capability_sample.get_string("classification_tags")
            performance_metrics_str = capability_sample.get_string("performance_metrics")
            default_capable = capability_sample.get_int32("default_capable")
            
            if enable_tracing:
                print(f"🔍 PRINT: Raw capability data from DDS:")
                print(f"🔍 PRINT:   capabilities_str: {capabilities_str}")
                print(f"🔍 PRINT:   specializations_str: {specializations_str}")
                print(f"🔍 PRINT:   classification_tags_str: {classification_tags_str}")
                print(f"🔍 PRINT:   default_capable: {default_capable}")
            
            # Parse JSON fields
            import json
            try:
                capabilities = json.loads(capabilities_str) if capabilities_str else []
                specializations = json.loads(specializations_str) if specializations_str else []
                classification_tags = json.loads(classification_tags_str) if classification_tags_str else []
                model_info = json.loads(model_info_str) if model_info_str else None
                performance_metrics = json.loads(performance_metrics_str) if performance_metrics_str else None
            except json.JSONDecodeError as e:
                if enable_tracing:
                    print(f"⚠️ PRINT: Failed to parse JSON capability fields: {e}")
                logger.warning(f"Failed to parse JSON capability fields: {e}")
                capabilities = []
                specializations = []
                classification_tags = []
                model_info = None
                performance_metrics = None
            
            if enable_tracing:
                print(f"🔍 PRINT: Parsed capability data:")
                print(f"🔍 PRINT:   capabilities: {capabilities}")
                print(f"🔍 PRINT:   specializations: {specializations}")
                print(f"🔍 PRINT:   classification_tags: {classification_tags}")
            
            # Store agent information with enhanced capabilities
            agent_info = {
                "agent_id": agent_id,
                "name": agent_name,
                "agent_type": agent_type,
                "service_name": service_name,
                "description": description,
                "last_seen": last_seen,
                "discovered_at": time.time(),
                # Enhanced capability information
                "capabilities": capabilities,
                "specializations": specializations,
                "classification_tags": classification_tags,
                "model_info": model_info,
                "performance_metrics": performance_metrics,
                "default_capable": bool(default_capable)
            }
            
            if enable_tracing:
                print(f"🔍 PRINT: Final agent_info being stored: {agent_info}")
            
            # Check if this is a new agent or an update
            is_new_agent = agent_id not in self.discovered_agents
            self.discovered_agents[agent_id] = agent_info
            
            if enable_tracing:
                print(f"🔍 PRINT: Stored agent_info in discovered_agents[{agent_id}]")
                print(f"🔍 PRINT: Current discovered_agents keys: {list(self.discovered_agents.keys())}")
            
            if is_new_agent:
                capabilities_summary = f"Capabilities: {capabilities}, Specializations: {specializations}"
                if enable_tracing:
                    print(f"🎉 PRINT: Discovered NEW agent: {agent_name} (ID: {agent_id}, Type: {agent_type}, Service: {service_name})")
                    print(f"📊 PRINT: Agent capabilities: {capabilities_summary}")
                logger.info(f"Discovered new agent: {agent_name} (ID: {agent_id}, Type: {agent_type}, Service: {service_name}) - {capabilities_summary}")
            else:
                if enable_tracing:
                    print(f"🔄 PRINT: Updated agent info: {agent_name} (ID: {agent_id})")
                logger.debug(f"Updated agent info: {agent_name} (ID: {agent_id})")
            
            if enable_tracing:
                print(f"📊 PRINT: Total discovered agents: {len(self.discovered_agents)}")
                logger.debug(f"Total discovered agents: {len(self.discovered_agents)}")
                
        except Exception as e:
            if enable_tracing:
                print(f"💥 PRINT: Error processing agent capability: {e}")
            logger.error(f"Error processing agent capability: {e}")
            import traceback
            if enable_tracing:
                print(f"💥 PRINT: Traceback: {traceback.format_exc()}")
    
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
            agent_service_name = self._get_agent_service_name(self.app.agent_id)
            print(f"🏗️ PRINT: Creating agent RPC service with name: {agent_service_name}")
            logger.info(f"Creating agent RPC service with name: {agent_service_name}")
            
            # Create replier for agent-to-agent communication
            print("🏗️ PRINT: Creating RPC Replier...")
            self.agent_replier = rpc.Replier(
                request_type=self.agent_request_type,
                reply_type=self.agent_reply_type,
                participant=self.app.participant,
                service_name=f"rti/connext/genesis/{agent_service_name}"
            )
            print("✅ PRINT: RPC Replier created successfully")
            
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
        """Set up listener for incoming agent requests (deprecated - now using polling)"""
        # This method is deprecated in favor of the polling approach used in _handle_agent_requests
        # Keep it for backward compatibility but make it a no-op
        logger.info("Agent request listener setup completed (using polling approach)")
        return True
    
    async def _process_agent_request(self, request, info):
        """Process an agent-to-agent request and send reply"""
        try:
            # Check if tracing is enabled before printing
            enable_tracing = getattr(self, 'enable_tracing', False)
            
            # Extract request data
            request_data = {
                "message": request.get_string("message"),
                "conversation_id": request.get_string("conversation_id")
            }
            
            if enable_tracing:
                print(f"📥 PRINT: Extracted request data: {request_data}")
            logger.info(f"Received agent request: {request_data['message']}")
            
            # Process the request using the abstract method
            try:
                if enable_tracing:
                    print(f"🔄 PRINT: About to call process_agent_request() method...")
                response_data = await self.process_agent_request(request_data)
                if enable_tracing:
                    print(f"✅ PRINT: process_agent_request() returned: {response_data}")
            except Exception as e:
                if enable_tracing:
                    print(f"💥 PRINT: Error in process_agent_request(): {e}")
                logger.error(f"Error processing agent request: {e}")
                response_data = {
                    "message": f"Error processing request: {str(e)}",
                    "status": -1,
                    "conversation_id": request_data.get("conversation_id", "")
                }
            
            if enable_tracing:
                print(f"📤 PRINT: About to create reply sample with data: {response_data}")
            
            # Create reply sample
            reply_sample = dds.DynamicData(self.agent_reply_type)
            reply_sample.set_string("message", response_data.get("message", ""))
            reply_sample.set_int32("status", response_data.get("status", 0))
            reply_sample.set_string("conversation_id", response_data.get("conversation_id", ""))
            
            if enable_tracing:
                print(f"📤 PRINT: About to send reply via agent_replier...")
            
            # Send reply
            self.agent_replier.send_reply(reply_sample, info)
            
            if enable_tracing:
                print(f"✅ PRINT: Reply sent successfully: {response_data.get('message', '')}")
            logger.info(f"Sent reply to agent request: {response_data.get('message', '')}")
            
        except Exception as e:
            enable_tracing = getattr(self, 'enable_tracing', False)
            if enable_tracing:
                print(f"💥 PRINT: Error in _process_agent_request(): {e}")
            logger.error(f"Error processing agent request: {e}")
            # Send error reply
            try:
                reply_sample = dds.DynamicData(self.agent_reply_type)
                reply_sample.set_string("message", f"Error processing request: {str(e)}")
                reply_sample.set_int32("status", -1)
                reply_sample.set_string("conversation_id", request_data.get("conversation_id", ""))
                self.agent_replier.send_reply(reply_sample, info)
                if enable_tracing:
                    print(f"✅ PRINT: Error reply sent")
            except Exception as reply_error:
                if enable_tracing:
                    print(f"💥 PRINT: Error sending error reply: {reply_error}")
                logger.error(f"Error sending error reply: {reply_error}")
    
    async def _handle_agent_requests(self):
        """Handle incoming agent requests using polling approach (like GenesisRPCService)"""
        if not self.agent_replier:
            # Only log this occasionally to avoid spam
            return
        
        try:
            # Use the same pattern as GenesisRPCService.run() - receive_requests with timeout
            requests = self.agent_replier.receive_requests(max_wait=dds.Duration(1))  # 1 second timeout
            
            # Check if tracing is enabled before printing
            enable_tracing = getattr(self, 'enable_tracing', False)
            
            if requests and enable_tracing:  # Only print if we have requests AND tracing is enabled
                print(f"🔔 PRINT: _handle_agent_requests() found {len(requests)} requests for agent {getattr(self, 'agent_name', 'Unknown')}")
            
            for request_sample in requests:
                request = request_sample.data
                request_info = request_sample.info
                
                if enable_tracing:
                    print(f"🔄 PRINT: Processing agent request via polling: {request.get_string('message')}")
                logger.debug(f"Processing agent request: {request.get_string('message')}")
                
                try:
                    # Process the request using our async method
                    await self._process_agent_request(request, request_info)
                except Exception as e:
                    if enable_tracing:
                        print(f"💥 PRINT: Error processing agent request in polling: {e}")
                    logger.error(f"Error processing agent request: {e}")
                    # Send error reply
                    try:
                        reply_sample = dds.DynamicData(self.agent_reply_type)
                        reply_sample.set_string("message", f"Error processing request: {str(e)}")
                        reply_sample.set_int32("status", -1)
                        reply_sample.set_string("conversation_id", request.get_string("conversation_id"))
                        self.agent_replier.send_reply(reply_sample, request_info)
                        if enable_tracing:
                            print("✅ PRINT: Error reply sent via polling")
                    except Exception as reply_error:
                        if enable_tracing:
                            print(f"💥 PRINT: Error sending error reply in polling: {reply_error}")
                        logger.error(f"Error sending error reply: {reply_error}")
                        
        except Exception as e:
            # This is normal if no requests are available - don't print anything
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
            
            if not target_service_name:
                # Fallback to generating service name if not stored
                target_service_name = self._get_agent_service_name(target_agent_id)
                logger.warning(f"No service_name in discovered agent info, using fallback: {target_service_name}")
            
            logger.info(f"Creating RPC requester for service: {target_service_name}")
            
            # Create RPC requester
            requester = rpc.Requester(
                request_type=self.agent_request_type,
                reply_type=self.agent_reply_type,
                participant=self.app.participant,
                service_name=f"rti/connext/genesis/{target_service_name}"
            )
            
            # Wait for DDS match with timeout
            logger.debug(f"Waiting for DDS match with agent {target_agent_id} (timeout: {timeout_seconds}s)")
            start_time = time.time()
            
            while True:
                # Check if we have a match
                if requester.matched_replier_count > 0:
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
    
    async def send_agent_request(self, 
                               target_agent_id: str, 
                               message: str, 
                               conversation_id: Optional[str] = None,
                               timeout_seconds: float = 10.0) -> Optional[Dict[str, Any]]:
        """
        Send a request to another agent.
        
        Args:
            target_agent_id: ID of the target agent
            message: Request message
            conversation_id: Optional conversation ID for tracking
            timeout_seconds: Request timeout
            
        Returns:
            Reply data or None if failed
        """
        try:
            logger.info(f"Sending request to agent {target_agent_id}: {message}")
            
            # Ensure connection exists
            if not await self.connect_to_agent(target_agent_id):
                logger.error(f"Failed to connect to agent {target_agent_id}")
                return None
            
            # Get the requester
            requester = self.agent_connections[target_agent_id]
            
            # Generate conversation ID if not provided
            if conversation_id is None:
                conversation_id = str(uuid.uuid4())
            
            # Create AgentAgentRequest
            request_sample = dds.DynamicData(self.agent_request_type)
            request_sample.set_string("message", message)
            request_sample.set_string("conversation_id", conversation_id)
            
            # Send via RPC
            logger.debug(f"Sending RPC request to agent {target_agent_id}")
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
            
            # Parse response
            response_data = {
                "message": reply_sample.get_string("message"),
                "status": reply_sample.get_int32("status"),
                "conversation_id": reply_sample.get_string("conversation_id")
            }
            
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
            
            # Close agent capability subscriber
            if self.agent_capability_subscriber and hasattr(self.agent_capability_subscriber, 'close'):
                self.agent_capability_subscriber.close()
                self.agent_capability_subscriber = None
            
            logger.info("Agent communication closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing agent communication: {e}") 