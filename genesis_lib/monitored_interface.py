#!/usr/bin/env python3
"""
Genesis Monitored Interface

This module provides the `MonitoredInterface` class that extends `GenesisInterface`
to add comprehensive monitoring capabilities. It enhances the base interface with
event publishing, lifecycle tracking, and performance monitoring through the DDS
infrastructure.

Key responsibilities include:
- Extending GenesisInterface with standardized monitoring capabilities.
- Publishing interface lifecycle events (JOINING, DISCOVERING, READY, etc.).
- Tracking and publishing request/response events.
- Managing component lifecycle events and chain events.
- Providing enhanced monitoring through DDS topics and writers.
- Supporting both legacy and enhanced (V2) monitoring systems.

This class serves as the monitoring-enabled version of the base interface,
allowing interfaces to participate in the Genesis monitoring ecosystem.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import logging
import time
import uuid
import json
import os
from typing import Any, Dict, Optional, Callable, Coroutine
import rti.connextdds as dds
from .interface import GenesisInterface
from genesis_lib.utils import get_datamodel_path
import asyncio
import functools

# Configure logging
logger = logging.getLogger(__name__)

# Event type mapping
EVENT_TYPE_MAP = {
    "INTERFACE_DISCOVERY": 0,  # Legacy discovery event
    "INTERFACE_REQUEST": 1,    # Request event
    "INTERFACE_RESPONSE": 2,   # Response event
    "INTERFACE_STATUS": 3      # Status event
}

def monitor_method(event_type: str):
    """
    Decorator to add monitoring to interface methods.
    
    Args:
        event_type: Type of event to publish (e.g., "INTERFACE_REQUEST", "INTERFACE_RESPONSE")
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Get request data from args or kwargs
            request_data = args[0] if args else kwargs.get('request_data', {})
            
            # Publish request monitoring event
            self.publish_monitoring_event(
                event_type,
                metadata={
                    "interface_name": self.interface_name,
                    "service_name": self.service_name,
                    "provider_id": str(self.app.participant.instance_handle)
                },
                call_data=request_data if event_type == "INTERFACE_REQUEST" else None,
                result_data=request_data if event_type == "INTERFACE_RESPONSE" else None
            )
            
            # Call the original method
            result = await func(self, *args, **kwargs)
            
            # If this was a request and we got a response, publish response event
            if event_type == "INTERFACE_REQUEST" and result:
                self.publish_monitoring_event(
                    "INTERFACE_RESPONSE",
                    metadata={
                        "interface_name": self.interface_name,
                        "service_name": self.service_name,
                        "provider_id": str(self.app.participant.instance_handle)
                    },
                    result_data=result
                )
            
            return result
        return wrapper
    return decorator

class MonitoredInterface(GenesisInterface):
    """
    Base class for interfaces with monitoring capabilities.
    Extends GenesisInterface to add standardized monitoring.
    """
    
    def __init__(self, interface_name: str, service_name: str):
        """
        Initialize the monitored interface.
        
        Args:
            interface_name: Name of the interface
            service_name: Name of the service this interface connects to
        """
        super().__init__(interface_name=interface_name, service_name=service_name)
        
        # Set up monitoring
        self._setup_monitoring()
        
        # --- Callback related state ---
        self.available_agents: Dict[str, Dict[str, Any]] = {}
        self._agent_found_event = asyncio.Event()
        self._connected_agent_id: Optional[str] = None
        # --- End callback related state ---

        # Register internal handlers for discovery/departure
        # These methods are now defined within this class
        self.register_discovery_callback(self._handle_agent_discovered)
        self.register_departure_callback(self._handle_agent_departed)
        
        # Announce interface presence
        self._publish_discovery_event()
        
        logger.debug(f"Monitored interface {interface_name} initialized")
    
    def _setup_monitoring(self):
        """Set up DDS entities for monitoring"""
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

        # Set up enhanced monitoring (V2)
        # Create topics for new monitoring types
        self.component_lifecycle_type = self.type_provider.type("genesis_lib", "ComponentLifecycleEvent")
        self.chain_event_type = self.type_provider.type("genesis_lib", "ChainEvent")
        self.liveliness_type = self.type_provider.type("genesis_lib", "LivelinessUpdate")

        # Create topics
        self.component_lifecycle_topic = dds.DynamicData.Topic(
            self.app.participant,
            "ComponentLifecycleEvent",
            self.component_lifecycle_type
        )
        self.chain_event_topic = dds.DynamicData.Topic(
            self.app.participant,
            "ChainEvent",
            self.chain_event_type
        )
        self.liveliness_topic = dds.DynamicData.Topic(
            self.app.participant,
            "LivelinessUpdate",
            self.liveliness_type
        )

        # Create writers with QoS
        writer_qos = dds.QosProvider.default.datawriter_qos
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE

        # Create writers for each monitoring type
        self.component_lifecycle_writer = dds.DynamicData.DataWriter(
            pub=self.monitoring_publisher,
            topic=self.component_lifecycle_topic,
            qos=writer_qos
        )
        self.chain_event_writer = dds.DynamicData.DataWriter(
            pub=self.monitoring_publisher,
            topic=self.chain_event_topic,
            qos=writer_qos
        )
        self.liveliness_writer = dds.DynamicData.DataWriter(
            pub=self.monitoring_publisher,
            topic=self.liveliness_topic,
            qos=writer_qos
        )
    
    def _publish_discovery_event(self):
        """Publish interface discovery event"""
        interface_id = str(self.app.participant.instance_handle)
        
        # First publish node discovery event for the interface itself
        self.publish_component_lifecycle_event(
            previous_state="DISCOVERING",
            new_state="DISCOVERING",
            reason=f"Component {interface_id} joined domain",
            capabilities=json.dumps({
                "interface_type": "INTERFACE",
                "service": self.service_name,
                "interface_id": interface_id
            }),
            event_category="NODE_DISCOVERY",
            source_id=interface_id,
            target_id="N/A"  # For node discovery of self, target is same as source
        )

        # Publish legacy monitoring event
        self.publish_monitoring_event(
            "INTERFACE_DISCOVERY",
            metadata={
                "interface_name": self.interface_name,
                "service_name": self.service_name,
                "provider_id": interface_id
            },
            status_data={"status": "available", "state": "ready"}
        )

        # Transition to discovering state
        self.publish_component_lifecycle_event(
            previous_state="JOINING",
            new_state="DISCOVERING",
            reason=f"{interface_id} JOINING -> DISCOVERING",
            capabilities=json.dumps({
                "interface_type": "INTERFACE",
                "service": self.service_name,
                "interface_id": interface_id
            }),
            event_category="STATE_CHANGE",
            source_id=interface_id,
            target_id=interface_id  # For state changes, target is self
        )

        # Transition to ready state
        self.publish_component_lifecycle_event(
            previous_state="DISCOVERING",
            new_state="READY",
            reason=f"{interface_id} DISCOVERING -> READY",
            capabilities=json.dumps({
                "interface_type": "INTERFACE",
                "service": self.service_name,
                "interface_id": interface_id
            }),
            event_category="STATE_CHANGE",
            source_id=interface_id,
            target_id=interface_id  # For state changes, target is self
        )
    
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
            event_type: Type of event (INTERFACE_DISCOVERY, INTERFACE_REQUEST, etc.)
            metadata: Additional metadata about the event
            call_data: Data about the request/call (if applicable)
            result_data: Data about the response/result (if applicable)
            status_data: Data about the interface status (if applicable)
            request_info: Request information containing client ID
        """
        try:
            event = dds.DynamicData(self.monitoring_type)
            
            # Set basic fields
            event["event_id"] = str(uuid.uuid4())
            event["timestamp"] = int(time.time() * 1000)
            event["event_type"] = EVENT_TYPE_MAP[event_type]
            event["entity_type"] = 0  # INTERFACE enum value
            event["entity_id"] = self.interface_name
            
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
            logger.debug(f"Published monitoring event: {event_type}")
            
        except Exception as e:
            logger.error(f"Error publishing monitoring event: {str(e)}")
    
    def publish_component_lifecycle_event(self, 
                                       previous_state: str,
                                       new_state: str,
                                       reason: str = "",
                                       capabilities: str = "",
                                       chain_id: str = "",
                                       call_id: str = "",
                                       event_category: str = None,
                                       source_id: str = "",
                                       target_id: str = "",
                                       connection_type: str = None):
        """
        Publish a component lifecycle event for the interface.
        
        Args:
            previous_state: Previous state of the interface (JOINING, DISCOVERING, READY, etc.)
            new_state: New state of the interface
            reason: Reason for the state change
            capabilities: Interface capabilities as JSON string
            chain_id: ID of the chain this event belongs to (if any)
            call_id: Call ID (if any)
            event_category: Category of the event (NODE_DISCOVERY, EDGE_DISCOVERY, STATE_CHANGE)
            source_id: Source ID of the event
            target_id: Target ID of the event
            connection_type: Type of connection for edge discovery events (optional)
        """
        try:
            # Map state strings to enum values
            states = {
                "JOINING": 0,
                "DISCOVERING": 1,
                "READY": 2,
                "BUSY": 3,
                "DEGRADED": 4,
                "OFFLINE": 5
            }
            
            # Map event categories to enum values
            event_categories = {
                "NODE_DISCOVERY": 0,
                "EDGE_DISCOVERY": 1,
                "STATE_CHANGE": 2,
                "AGENT_INIT": 3,
                "AGENT_READY": 4,
                "AGENT_SHUTDOWN": 5,
                "DDS_ENDPOINT": 6
            }
            
            # Get interface ID - this is our component ID
            interface_id = str(self.app.participant.instance_handle)
            
            # Ensure we have a source_id for all events
            if not source_id:
                source_id = interface_id
            
            event = dds.DynamicData(self.component_lifecycle_type)
            event["component_id"] = interface_id
            event["component_type"] = 0  # INTERFACE enum value
            event["previous_state"] = states[previous_state]
            event["new_state"] = states[new_state]
            event["timestamp"] = int(time.time() * 1000)
            event["reason"] = reason
            event["capabilities"] = capabilities
            event["chain_id"] = chain_id
            event["call_id"] = call_id
            
            # Handle event categorization with proper ID requirements
            if event_category:
                event["event_category"] = event_categories[event_category]  # Use direct lookup instead of .get()
                event["source_id"] = source_id
                
                if event_category == "EDGE_DISCOVERY":
                    # For edge events, ensure we have different source and target IDs
                    if not target_id or target_id == source_id:
                        logger.warning("Edge discovery event requires different source and target IDs")
                        return
                    event["target_id"] = target_id
                    event["connection_type"] = connection_type if connection_type else "agent_connection"
                elif event_category == "STATE_CHANGE":
                    # For state changes, both source and target should be the interface ID
                    event["source_id"] = interface_id
                    event["target_id"] = interface_id
                    event["connection_type"] = ""
                else:
                    # For other events, use provided target_id or leave empty
                    event["target_id"] = target_id if target_id else ""
                    event["connection_type"] = ""
            else:
                # Default to state change if no category provided
                event["event_category"] = event_categories["STATE_CHANGE"]
                event["source_id"] = interface_id
                event["target_id"] = interface_id
                event["connection_type"] = ""

            self.component_lifecycle_writer.write(event)
            self.component_lifecycle_writer.flush()
            logger.debug(f"Published component lifecycle event: {previous_state} -> {new_state}")
        except Exception as e:
            logger.error(f"Error publishing component lifecycle event: {e}")
            logger.error(f"Event category was: {event_category}")
    
    # --- Internal Callback Handlers --- 
    async def _handle_agent_discovered(self, agent_info: dict):
        """Internal callback handler for agent discovery."""
        instance_id = agent_info['instance_id']
        prefered_name = agent_info['prefered_name']
        service_name = agent_info['service_name']
        logger.debug(f"<MonitoredInterface Handler> Agent Discovered: {prefered_name} ({service_name}) - ID: {instance_id}")
        self.available_agents[instance_id] = agent_info
        
        # CRITICAL FIX: Publish EDGE_DISCOVERY event for interface-to-agent connection
        interface_id = str(self.app.participant.instance_handle)
        
        # Publish edge discovery event
        self.publish_component_lifecycle_event(
            previous_state="DISCOVERING",
            new_state="DISCOVERING", 
            reason=f"Interface {interface_id} discovered agent {prefered_name} ({instance_id})",
            capabilities=json.dumps({
                "edge_type": "interface_to_agent",
                "interface_name": self.interface_name,
                "agent_name": prefered_name,
                "service_name": service_name,
                "connection_established": True
            }),
            event_category="EDGE_DISCOVERY",
            source_id=interface_id,
            target_id=instance_id,
            connection_type="INTERFACE_TO_AGENT"
        )
        
        logger.debug(f"Published EDGE_DISCOVERY event: Interface {interface_id} -> Agent {instance_id}")
        
        # For this simple test, signal that *an* agent is found
        # A real app might have more complex logic here (e.g., find specific name)
        # Or expose the event/agents list publicly for the app to manage.
        if not self._agent_found_event.is_set():
            logger.debug("<MonitoredInterface Handler> Signaling internal agent found event.")
            self._agent_found_event.set() 

    async def _handle_agent_departed(self, instance_id: str):
        """Internal callback handler for agent departure."""
        if instance_id in self.available_agents:
            departed_agent = self.available_agents.pop(instance_id)
            prefered_name = departed_agent.get('prefered_name', 'N/A')
            logger.debug(f"<MonitoredInterface Handler> Agent Departed: {prefered_name} - ID: {instance_id}")
            # If the departed agent was the one we connected to, handle it
            if instance_id == self._connected_agent_id:
                 logger.warning(f"<MonitoredInterface Handler> Connected agent {prefered_name} departed! Need to handle reconnection or failure.")
                 self._connected_agent_id = None
                 # Consider if requester should be closed here? Or just let send_request fail?
                 # self.requester.close() # This might cause issues if called from callback context
                 # Potentially clear the event if the application logic relies on it
                 # self._agent_found_event.clear() # If we need to wait for a *new* agent
        else:
            logger.warning(f"<MonitoredInterface Handler> Received departure for unknown agent ID: {instance_id}")
    # --- End Internal Callback Handlers ---

    @monitor_method("INTERFACE_REQUEST")
    async def send_request(self, request_data: Dict[str, Any], timeout_seconds: float = 10.0) -> Optional[Dict[str, Any]]:
        """Send request to agent with monitoring"""
        # Check if we are connected before sending
        if not self.requester or not self._connected_agent_id:
            logger.error("❌ MonitoredInterface cannot send request, not connected to an agent.")
            # Check if the agent we thought we were connected to just departed
            if self._connected_agent_id and self._connected_agent_id not in self.available_agents:
                logger.warning("Connection lost as the target agent departed.")
                self._connected_agent_id = None # Ensure state reflects disconnection
            return None
        
        return await super().send_request(request_data, timeout_seconds)
    
    async def close(self):
        """Clean up resources"""
        try:
            # First transition to BUSY state for shutdown
            self.publish_component_lifecycle_event(
                previous_state="READY",
                new_state="BUSY",
                reason=f"Interface {self.interface_name} preparing for shutdown"
            )

            # Add a small delay to ensure events are distinguishable
            await asyncio.sleep(0.1)

            # Then transition to OFFLINE
            self.publish_component_lifecycle_event(
                previous_state="BUSY",
                new_state="OFFLINE",
                reason=f"Interface {self.interface_name} shutting down"
            )

            # Publish legacy offline status
            self.publish_monitoring_event(
                "INTERFACE_STATUS",
                status_data={"status": "offline"},
                metadata={"service": self.service_name}
            )
            
            # Close monitoring resources
            if hasattr(self, 'monitoring_writer'):
                self.monitoring_writer.close()
            if hasattr(self, 'monitoring_publisher'):
                self.monitoring_publisher.close()
            if hasattr(self, 'monitoring_topic'):
                self.monitoring_topic.close()
            if hasattr(self, 'component_lifecycle_writer'):
                self.component_lifecycle_writer.close()
            if hasattr(self, 'chain_event_writer'):
                self.chain_event_writer.close()
            if hasattr(self, 'liveliness_writer'):
                self.liveliness_writer.close()
            
            # Close base class resources
            await super().close()
            
        except Exception as e:
            logger.error(f"Error closing monitored interface: {str(e)}") 