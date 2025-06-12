#!/usr/bin/env python3
"""
Genesis Monitored Interface (Unified Graph Monitoring)

This module provides the `MonitoredInterface` class that extends `GenesisInterface`
to add comprehensive monitoring capabilities. It now uses the unified GraphMonitor
for all node/edge monitoring events, supporting robust graph-based monitoring and DDS compatibility.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import logging
import uuid
import json
from typing import Any, Dict, Optional
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

    def __init__(self, interface_name: str, service_name: str):
        super().__init__(interface_name=interface_name, service_name=service_name)
        self.graph = GraphMonitor(self.app.participant)
        self.available_agents: Dict[str, Dict[str, Any]] = {}
        self._agent_found_event = asyncio.Event()
        self._connected_agent_id: Optional[str] = None

        # Announce interface node (discovery and ready)
        interface_id = str(self.app.participant.instance_handle)
        print(f"MonitoredInterface __init__: publishing DISCOVERING and READY for {self.interface_name} ({interface_id})")
        self.graph.publish_node(
            component_id=interface_id,
            component_type=COMPONENT_TYPE["INTERFACE"],
            state=STATE["DISCOVERING"],
            attrs={
                "interface_type": "INTERFACE",
                "service": self.service_name,
                "interface_id": interface_id,
                "reason": f"Component {interface_id} joined domain"
            }
        )
        self.graph.publish_node(
            component_id=interface_id,
            component_type=COMPONENT_TYPE["INTERFACE"],
            state=STATE["READY"],
            attrs={
                "interface_type": "INTERFACE",
                "service": self.service_name,
                "interface_id": interface_id,
                "reason": f"{interface_id} DISCOVERING -> READY"
            }
        )

        # Register internal handlers for discovery/departure
        self.register_discovery_callback(self._handle_agent_discovered)
        self.register_departure_callback(self._handle_agent_departed)

        logger.debug(f"Monitored interface {interface_name} initialized")

    async def _handle_agent_discovered(self, agent_info: dict):
        instance_id = agent_info['instance_id']
        prefered_name = agent_info['prefered_name']
        service_name = agent_info['service_name']
        logger.debug(f"<MonitoredInterface Handler> Agent Discovered: {prefered_name} ({service_name}) - ID: {instance_id}")
        self.available_agents[instance_id] = agent_info

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

        if not self._agent_found_event.is_set():
            logger.debug("<MonitoredInterface Handler> Signaling internal agent found event.")
            self._agent_found_event.set()

    async def _handle_agent_departed(self, instance_id: str):
        if instance_id in self.available_agents:
            departed_agent = self.available_agents.pop(instance_id)
            prefered_name = departed_agent.get('prefered_name', 'N/A')
            logger.debug(f"<MonitoredInterface Handler> Agent Departed: {prefered_name} - ID: {instance_id}")
            if instance_id == self._connected_agent_id:
                logger.warning(f"<MonitoredInterface Handler> Connected agent {prefered_name} departed! Need to handle reconnection or failure.")
                self._connected_agent_id = None
        else:
            logger.warning(f"<MonitoredInterface Handler> Received departure for unknown agent ID: {instance_id}")

    @monitor_method("INTERFACE_REQUEST")
    async def send_request(self, request_data: Dict[str, Any], timeout_seconds: float = 10.0) -> Optional[Dict[str, Any]]:
        return await super().send_request(request_data, timeout_seconds)

    async def close(self):
        try:
            interface_id = str(self.app.participant.instance_handle)
            print(f"MonitoredInterface.close: publishing OFFLINE for {self.interface_name} ({interface_id})")
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
