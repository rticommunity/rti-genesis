#!/usr/bin/env python3
"""
Genesis Monitored Interface (Unified Graph Monitoring)

This module provides the `MonitoredInterface` class that extends `GenesisInterface`
to add comprehensive monitoring capabilities. It now uses the unified GraphMonitor
for all node/edge monitoring events, supporting robust graph-based monitoring and DDS compatibility.

Copyright (c) 2025, RTI & Jason Upchurch
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

    def __init__(self, interface_name: str, service_name: str):
        super().__init__(interface_name=interface_name, service_name=service_name)
        self.graph = GraphMonitor(self.app.participant)
        self.available_agents: Dict[str, Dict[str, Any]] = {}
        self._agent_found_event = asyncio.Event()
        self._connected_agent_id: Optional[str] = None
        self._last_complete_event: Optional[asyncio.Event] = None
        # Unified monitoring event writer for ChainEvents
        self._unified_event_writer = None
        try:
            import rti.connextdds as dds  # type: ignore
            from genesis_lib.utils import get_datamodel_path  # type: ignore
            provider = dds.QosProvider(get_datamodel_path())
            
            # Create unified monitoring event writer (Event)
            # Use process-wide registry to share topics
            from genesis_lib.graph_monitoring import _TOPIC_REGISTRY
            
            writer_qos = dds.QosProvider.default.datawriter_qos
            writer_qos.durability.kind = dds.DurabilityKind.VOLATILE
            writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            
            unified_type = provider.type("genesis_lib", "MonitoringEventUnified")
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
                pub=dds.Publisher(self.app.participant), topic=unified_topic, qos=writer_qos
            )
            # Prepare a reader for InterfaceAgentReply so we can align COMPLETE with the final reply
            self._reply_type = provider.type("genesis_lib", "InterfaceAgentReply")
            self._reply_topic = dds.DynamicData.Topic(self.app.participant, "OpenAIAgentReply", self._reply_type)
            reader_qos = dds.QosProvider.default.datareader_qos
            reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
            reader_qos.history.depth = 256
            # Async event-driven reply listener (no polling)
            self._reply_event = asyncio.Event()
            self._last_reply_time = 0.0

            class _ReplyListener(dds.DynamicData.NoOpDataReaderListener):
                def __init__(self, outer, loop: asyncio.AbstractEventLoop):
                    super().__init__()
                    self._outer = outer
                    self._loop = loop
                def on_data_available(self, reader):
                    try:
                        samples = reader.read()
                        if samples:
                            self._outer._last_reply_time = time.time()
                            # signal on the main loop
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
            logger.info("MonitoredInterface: Event ChainEvent monitoring setup successful")
        except Exception as e:
            # Chain overlay is optional; continue without it if DDS setup fails
            logger.warning(f"MonitoredInterface: Event setup FAILED: {e}")
            import traceback
            traceback.print_exc()
            self._unified_event_writer = None
            self._reply_reader = None

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
    async def connect_to_agent(self, service_name: str, timeout_seconds: Optional[float] = None) -> bool:
        """Override to remember the connected agent GUID for ChainEvent target_id."""
        ok = await super().connect_to_agent(service_name, timeout_seconds=timeout_seconds)
        if ok:
            # Try to resolve the chosen agent's instance_id by service_name or name
            try:
                for aid, info in self.available_agents.items():
                    if info.get('service_name') == service_name or info.get('prefered_name') == service_name:
                        self._connected_agent_id = aid
                        break
            except Exception:
                pass
        return ok


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
        # Emit ChainEvent start to Event (optional)
        # Prepare completion event for strict sequencing
        try:
            self._last_complete_event = asyncio.Event()
        except Exception:
            self._last_complete_event = None
        
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

        # Wait for the final reply (GenesisInterface drains any extra replies briefly)
        result = await super().send_request(request_data, timeout_seconds)

        # Emit ChainEvent complete to Event (optional) at the precise return point
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

        # NOTE: Removed quiet-window wait to avoid masking timing issues; COMPLETE now reflects
        # the actual emission point tied to reply return. Further alignment will be done by
        # correlating with final reply events instead of timers.

        # Signal completion event for strict sequencing even if ChainEvent emission failed
        try:
            if self._last_complete_event is not None:
                self._last_complete_event.set()
        except Exception:
            pass

        return result

    async def _await_reply_quiet_event(self, total_window_seconds: float = 10.0, quiet_seconds: float = 2.0) -> None:
        """Wait until no OpenAIAgentReply arrives for 'quiet_seconds', bounded by 'total_window_seconds'."""
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
                # Quiet period elapsed
                break
            except Exception:
                break

    async def wait_last_complete(self, timeout_seconds: float = 5.0) -> bool:
        """Wait for the most recent request's completion signal (from ChainEvent COMPLETE).

        Returns True if observed before timeout, else False.
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
