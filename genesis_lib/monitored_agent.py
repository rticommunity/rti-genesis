#!/usr/bin/env python3
"""
MonitoredAgent Base Class for Genesis Agents (Unified Graph Monitoring)

This module defines the MonitoredAgent class, which extends the GenesisAgent
base class to provide standardized monitoring capabilities for agents operating
within the Genesis network. It now uses the unified GraphMonitor for all node/edge
monitoring events, supporting robust graph-based monitoring and DDS compatibility.

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

from .agent import GenesisAgent
from genesis_lib.generic_function_client import GenericFunctionClient
from genesis_lib.graph_monitoring import (
    GraphMonitor,
    COMPONENT_TYPE,
    STATE,
    EDGE_TYPE,
)

logger = logging.getLogger(__name__)

# Event type mapping for monitoring events
EVENT_TYPE_MAP = {
    "AGENT_DISCOVERY": 0,  # FUNCTION_DISCOVERY enum value
    "AGENT_REQUEST": 1,    # FUNCTION_CALL enum value
    "AGENT_RESPONSE": 2,   # FUNCTION_RESULT enum value
    "AGENT_STATUS": 3      # FUNCTION_STATUS enum value
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
                 agent_type: str = "AGENT", service_instance_tag: Optional[str] = None,
                 agent_id: str = None, description: str = None, domain_id: int = 0,
                 enable_agent_communication: bool = False, memory_adapter=None):
        logger.info(f"🚀 TRACE: MonitoredAgent {agent_name} STARTING initializing with agent_id {agent_id}")

        super().__init__(
            agent_name=agent_name,
            base_service_name=base_service_name,
            service_instance_tag=service_instance_tag,
            agent_id=agent_id,
            enable_agent_communication=enable_agent_communication,
            memory_adapter=memory_adapter
        )
        logger.info(f"✅ TRACE: MonitoredAgent {agent_name} initialized with base class")

        self.agent_type = agent_type
        self.description = description or f"A {agent_type} providing {base_service_name} service"
        self.domain_id = domain_id
        self.monitor = None
        self.subscription = None

        self._initialize_function_client()
        self.function_cache: Dict[str, Dict[str, Any]] = {}

        self.agent_capabilities = {
            "agent_type": agent_type,
            "service": base_service_name,
            "functions": [],
            "supported_tasks": [],
            "prefered_name": self.agent_name,
            "agent_name": self.agent_name,
        }

        # Unified graph monitor
        self.graph = GraphMonitor(self.app.participant)
        
        # Set up monitoring infrastructure
        self._setup_monitoring()

        # Publish agent node (discovery and ready)
        print(f"MonitoredAgent __init__: publishing DISCOVERING and READY for {agent_name} ({self.app.agent_id})")
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
                "reason": f"Agent {agent_name} discovered"
            }
        )
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

        self.current_state = "READY"
        self.last_state_change = datetime.now()
        self.state_history = []
        self.event_correlation = {}

        logger.info(f"✅ TRACE: Monitored agent {agent_name} initialized with type {agent_type}, agent_id={self.app.agent_id}, dds_guid={getattr(self.app, 'dds_guid', None)}")

    def _initialize_function_client(self) -> None:
        if not self.app or not self.app.participant:
            logger.error("Cannot initialize function client: DDS Participant not available.")
            return
    
    def _setup_monitoring(self) -> None:
        """
        Set up monitoring resources and initialize state.
        """
        try:
            from genesis_lib.utils import get_datamodel_path
            import rti.connextdds as dds
            
            # Get types from XML
            config_path = get_datamodel_path()
            self.type_provider = dds.QosProvider(config_path)
            
            # Get monitoring type from XML
            self.monitoring_type = self.type_provider.type("genesis_lib", "MonitoringEvent")
            
            # Create monitoring topic
            self.monitoring_topic = dds.DynamicData.Topic(
                self.app.participant,
                "MonitoringEvent",
                self.monitoring_type
            )
            
            # Create monitoring publisher with QoS
            publisher_qos = dds.QosProvider.default.publisher_qos
            publisher_qos.partition.name = [""]  # Default partition
            self.monitoring_publisher = dds.Publisher(
                participant=self.app.participant,
                qos=publisher_qos
            )
            
            # Create monitoring writer with QoS
            writer_qos = dds.QosProvider.default.datawriter_qos
            writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            self.monitoring_writer = dds.DynamicData.DataWriter(
                pub=self.monitoring_publisher,
                topic=self.monitoring_topic,
                qos=writer_qos
            )

            # Set up enhanced monitoring (ChainEvent)
            self.chain_event_type = self.type_provider.type("genesis_lib", "ChainEvent")
            self.chain_event_topic = dds.DynamicData.Topic(
                self.app.participant,
                "ChainEvent",
                self.chain_event_type
            )
            self.chain_event_writer = dds.DynamicData.DataWriter(
                pub=self.monitoring_publisher,
                topic=self.chain_event_topic,
                qos=writer_qos
            )
            
            logger.debug("Monitoring setup completed successfully")
            
        except Exception as e:
            logger.error(f"Error setting up monitoring: {str(e)}")
            logger.error(traceback.format_exc())
            # Set monitoring attributes to None so the publish methods can handle gracefully
            self.monitoring_writer = None
            self.monitoring_type = None
            self.chain_event_writer = None
            self.chain_event_type = None

    async def process_request(self, request: Any) -> Dict[str, Any]:
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

            result = await self._process_request(request)

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

    def _process_request(self, request: Any) -> Dict[str, Any]:
        raise NotImplementedError("Concrete agents must implement _process_request")

    async def close(self) -> None:
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
        logger.debug(f"Publishing {len(functions)} discovered functions as monitoring events")
        function_requester_guid = None
        if hasattr(self, 'function_client'):
            function_requester_guid = self._get_requester_guid(self.function_client)
            if function_requester_guid:
                self.function_requester_guid = function_requester_guid

        provider_guids = set()
        function_provider_guid = None

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

            # Node for function
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
            # Edge: agent can call function
            self.graph.publish_edge(
                source_id=self.app.agent_id,
                target_id=function_id,
                edge_type=EDGE_TYPE["FUNCTION_CONNECTION"],
                attrs={
                    "edge_type": "agent_function",
                    "function_id": function_id,
                    "function_name": function_name,
                    "reason": f"Agent {self.agent_name} can call function {function_name}"
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
        """Publish chain event for agent-to-agent interactions"""
        if not hasattr(self, "chain_event_writer"):
            return
        import rti.connextdds as dds
        chain_event = dds.DynamicData(self.chain_event_type)
        chain_event["chain_id"] = chain_id
        chain_event["call_id"] = call_id
        chain_event["interface_id"] = str(self.app.participant.instance_handle)
        chain_event["primary_agent_id"] = self.app.agent_id
        chain_event["specialized_agent_ids"] = target_id if target_id != self.app.agent_id else ""
        chain_event["function_id"] = "agent_communication"
        chain_event["query_id"] = call_id
        chain_event["timestamp"] = int(time.time() * 1000)
        chain_event["event_type"] = event_type
        chain_event["source_id"] = source_id
        chain_event["target_id"] = target_id
        chain_event["status"] = status
        self.chain_event_writer.write(chain_event)
        self.chain_event_writer.flush()

    def _publish_llm_call_start(self, chain_id: str, call_id: str, model_identifier: str):
        """Publish a chain event for LLM call start"""
        if not hasattr(self, "chain_event_writer"):
            return
        import rti.connextdds as dds
        chain_event = dds.DynamicData(self.chain_event_type)
        chain_event["chain_id"] = chain_id
        chain_event["call_id"] = call_id
        chain_event["interface_id"] = str(self.app.participant.instance_handle)
        chain_event["primary_agent_id"] = self.app.agent_id
        chain_event["specialized_agent_ids"] = ""
        chain_event["function_id"] = model_identifier
        chain_event["query_id"] = str(uuid.uuid4())
        chain_event["timestamp"] = int(time.time() * 1000)
        chain_event["event_type"] = "LLM_CALL_START"
        chain_event["source_id"] = str(self.app.participant.instance_handle)
        chain_event["target_id"] = "OpenAI"
        chain_event["status"] = 0
        self.chain_event_writer.write(chain_event)
        self.chain_event_writer.flush()

    def _publish_llm_call_complete(self, chain_id: str, call_id: str, model_identifier: str):
        """Publish a chain event for LLM call completion"""
        if not hasattr(self, "chain_event_writer"):
            return
        import rti.connextdds as dds
        chain_event = dds.DynamicData(self.chain_event_type)
        chain_event["chain_id"] = chain_id
        chain_event["call_id"] = call_id
        chain_event["interface_id"] = str(self.app.participant.instance_handle)
        chain_event["primary_agent_id"] = self.app.agent_id
        chain_event["specialized_agent_ids"] = ""
        chain_event["function_id"] = model_identifier
        chain_event["query_id"] = str(uuid.uuid4())
        chain_event["timestamp"] = int(time.time() * 1000)
        chain_event["event_type"] = "LLM_CALL_COMPLETE"
        chain_event["source_id"] = "OpenAI"
        chain_event["target_id"] = str(self.app.participant.instance_handle)
        chain_event["status"] = 0
        self.chain_event_writer.write(chain_event)
        self.chain_event_writer.flush()

    def _publish_classification_result(self, chain_id: str, call_id: str, classified_function_name: str, classified_function_id: str):
        """Publish a chain event for function classification result"""
        if not hasattr(self, "chain_event_writer"):
            return
        import rti.connextdds as dds
        chain_event = dds.DynamicData(self.chain_event_type)
        chain_event["chain_id"] = chain_id
        chain_event["call_id"] = call_id
        chain_event["interface_id"] = str(self.app.participant.instance_handle)
        chain_event["primary_agent_id"] = self.app.agent_id
        chain_event["specialized_agent_ids"] = ""
        chain_event["function_id"] = classified_function_id
        chain_event["query_id"] = str(uuid.uuid4())
        chain_event["timestamp"] = int(time.time() * 1000)
        chain_event["event_type"] = "CLASSIFICATION_RESULT"
        chain_event["source_id"] = str(self.app.participant.instance_handle)
        # Use function UUID for target_id so activity maps to graph function node
        chain_event["target_id"] = classified_function_id
        chain_event["status"] = 0
        self.chain_event_writer.write(chain_event)
        self.chain_event_writer.flush()

    def _publish_function_call_start(self, chain_id: str, call_id: str, function_name: str, function_id: str, target_provider_id: str = None):
        """Publish a chain event for function call start"""
        if not hasattr(self, "chain_event_writer"):
            return
        import rti.connextdds as dds
        chain_event = dds.DynamicData(self.chain_event_type)
        chain_event["chain_id"] = chain_id
        chain_event["call_id"] = call_id
        chain_event["interface_id"] = str(self.app.participant.instance_handle)
        chain_event["primary_agent_id"] = ""
        chain_event["specialized_agent_ids"] = ""
        chain_event["function_id"] = function_id
        chain_event["query_id"] = str(uuid.uuid4())
        chain_event["timestamp"] = int(time.time() * 1000)
        chain_event["event_type"] = "FUNCTION_CALL_START"
        chain_event["source_id"] = str(self.app.participant.instance_handle)
        # Always target the function UUID; provider id can be inferred from topology
        chain_event["target_id"] = function_id
        chain_event["status"] = 0
        self.chain_event_writer.write(chain_event)
        self.chain_event_writer.flush()

        # Additionally, emit an explicit AGENT->SERVICE activation so the agent-service edge pulses in the UI
        if target_provider_id:
            chain_event2 = dds.DynamicData(self.chain_event_type)
            chain_event2["chain_id"] = chain_id
            chain_event2["call_id"] = call_id
            chain_event2["interface_id"] = str(self.app.participant.instance_handle)
            chain_event2["primary_agent_id"] = self.app.agent_id
            chain_event2["specialized_agent_ids"] = ""
            chain_event2["function_id"] = function_id
            chain_event2["query_id"] = str(uuid.uuid4())
            chain_event2["timestamp"] = int(time.time() * 1000)
            chain_event2["event_type"] = "AGENT_TO_SERVICE_START"
            # Use graph node IDs for direct edge mapping
            chain_event2["source_id"] = self.app.agent_id
            chain_event2["target_id"] = target_provider_id
            chain_event2["status"] = 0
            self.chain_event_writer.write(chain_event2)
            self.chain_event_writer.flush()
            try:
                logger.info(
                    f"CHAIN AGENT_TO_SERVICE_START chain={chain_id[:8]} call={call_id[:8]} "
                    f"agent={self.app.agent_id} -> service={target_provider_id} function_id={function_id}"
                )
            except Exception:
                pass
        else:
            try:
                logger.warning(
                    f"CHAIN A2S SKIP (no provider_id) chain={chain_id[:8]} call={call_id[:8]} agent={self.app.agent_id} function_id={function_id}"
                )
            except Exception:
                pass

    def _publish_function_call_complete(self, chain_id: str, call_id: str, function_name: str, function_id: str, source_provider_id: str = None):
        """Publish a chain event for function call completion"""
        if not hasattr(self, "chain_event_writer"):
            return
        import rti.connextdds as dds
        chain_event = dds.DynamicData(self.chain_event_type)
        chain_event["chain_id"] = chain_id
        chain_event["call_id"] = call_id
        chain_event["interface_id"] = str(self.app.participant.instance_handle)
        chain_event["primary_agent_id"] = ""
        chain_event["specialized_agent_ids"] = ""
        chain_event["function_id"] = function_id
        chain_event["query_id"] = str(uuid.uuid4())
        chain_event["timestamp"] = int(time.time() * 1000)
        chain_event["event_type"] = "FUNCTION_CALL_COMPLETE"
        # Use function UUID as the source of the completion to mirror SERVICE->FUNCTION edge direction
        chain_event["source_id"] = function_id
        chain_event["target_id"] = str(self.app.participant.instance_handle)
        chain_event["status"] = 0
        self.chain_event_writer.write(chain_event)
        self.chain_event_writer.flush()
        try:
            logger.info(
                f"CHAIN FUNCTION_CALL_COMPLETE chain={chain_id[:8]} call={call_id[:8]} "
                f"function_id={function_id} service={self.app.participant.instance_handle}"
            )
        except Exception:
            pass

        # Emit explicit SERVICE->AGENT completion event (reply)
        if source_provider_id:
            chain_event2 = dds.DynamicData(self.chain_event_type)
            chain_event2["chain_id"] = chain_id
            chain_event2["call_id"] = call_id
            chain_event2["interface_id"] = str(self.app.participant.instance_handle)
            chain_event2["primary_agent_id"] = self.app.agent_id
            chain_event2["specialized_agent_ids"] = ""
            chain_event2["function_id"] = function_id
            chain_event2["query_id"] = str(uuid.uuid4())
            chain_event2["timestamp"] = int(time.time() * 1000)
            chain_event2["event_type"] = "SERVICE_TO_AGENT_COMPLETE"
            chain_event2["source_id"] = source_provider_id
            chain_event2["target_id"] = self.app.agent_id
            chain_event2["status"] = 0
            self.chain_event_writer.write(chain_event2)
            self.chain_event_writer.flush()
            try:
                logger.info(
                    f"CHAIN SERVICE_TO_AGENT_COMPLETE chain={chain_id[:8]} call={call_id[:8]} "
                    f"service={source_provider_id} -> agent={self.app.agent_id} function_id={function_id}"
                )
            except Exception:
                pass

    async def execute_function_with_monitoring(self,
                                               function_name: str,
                                               function_id: str,
                                               provider_id: str | None,
                                               tool_args: dict,
                                               chain_id: str,
                                               call_id: str):
        """Centralized function execution + ChainEvent emission.

        All subclasses should call this instead of emitting ChainEvents directly.
        """
        # Start events
        self._publish_function_call_start(
            chain_id=chain_id,
            call_id=call_id,
            function_name=function_name,
            function_id=function_id,
            target_provider_id=provider_id,
        )
        # Execute underlying function via subclass implementation
        result = await self._call_function(function_name, **tool_args)
        # Complete events
        self._publish_function_call_complete(
            chain_id=chain_id,
            call_id=call_id,
            function_name=function_name,
            function_id=function_id,
            source_provider_id=provider_id,
        )
        return result

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
        Publish a monitoring event.
        
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
            if not hasattr(self, 'monitoring_writer') or not self.monitoring_writer:
                logger.debug(f"Monitoring writer not initialized, skipping event: {event_type}")
                return
                
            if not hasattr(self, 'monitoring_type') or not self.monitoring_type:
                logger.debug(f"Monitoring type not initialized, skipping event: {event_type}")
                return
            
            import rti.connextdds as dds
            event = dds.DynamicData(self.monitoring_type)
            
            # Set basic fields
            event["event_id"] = str(uuid.uuid4())
            event["timestamp"] = int(time.time() * 1000)
            event["event_type"] = EVENT_TYPE_MAP.get(event_type, 0)
            event["entity_type"] = AGENT_TYPE_MAP.get(self.agent_type, 1)  # Default to PRIMARY_AGENT if type not found
            event["entity_id"] = self.agent_name
            
            # Set optional fields
            if metadata:
                event["metadata"] = json.dumps(metadata)
            if call_data:
                event["call_data"] = json.dumps(call_data)
            if result_data:
                event["result_data"] = json.dumps(result_data)
            if status_data:
                event["status_data"] = json.dumps(status_data)
            
            # Write the event
            self.monitoring_writer.write(event)
            self.monitoring_writer.flush()
            logger.debug(f"Published monitoring event: {event_type}")
            
        except Exception as e:
            logger.error(f"Error publishing monitoring event: {str(e)}")
            logger.error(traceback.format_exc())

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
