#!/usr/bin/env python3
"""
Unified Graph Monitoring Helper for Genesis

Provides a single interface for publishing node and edge events
to DDS (ComponentLifecycleEvent), with optional legacy MonitoringEvent
support for backward compatibility.

- publish_node: emits NODE_DISCOVERY for agents, interfaces, services, functions
- publish_edge: emits EDGE_DISCOVERY for connections (DDS, agent, function, etc.)

DDS setup is handled as a singleton per process.
Enums/constants are shared for all monitoring users.

Legacy MonitoringEvent emission is controlled by GENESIS_MON_LEGACY=1.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import os
import time
import uuid
import json
import threading
import logging
import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path

logger = logging.getLogger("graph_monitoring")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Enum constants for component types
COMPONENT_TYPE = {
    "INTERFACE": 0,
    "AGENT_PRIMARY": 1,
    "AGENT_SPECIALIZED": 2,
    "FUNCTION": 3,
    "SERVICE": 4
}

# Enum constants for states
STATE = {
    "JOINING": 0,
    "DISCOVERING": 1,
    "READY": 2,
    "BUSY": 3,
    "DEGRADED": 4,
    "OFFLINE": 5
}

# Enum constants for event categories
EVENT_CATEGORY = {
    "NODE_DISCOVERY": 0,
    "EDGE_DISCOVERY": 1,
    "STATE_CHANGE": 2,
    "AGENT_INIT": 3,
    "AGENT_READY": 4,
    "AGENT_SHUTDOWN": 5,
    "DDS_ENDPOINT": 6
}

# Enum constants for edge types
EDGE_TYPE = {
    "DDS_ENDPOINT": "DDS_ENDPOINT",
    "AGENT_COMMUNICATION": "AGENT_COMMUNICATION",
    "FUNCTION_CONNECTION": "FUNCTION_CONNECTION",
    "INTERFACE_TO_AGENT": "INTERFACE_TO_AGENT",
    "SERVICE_TO_FUNCTION": "SERVICE_TO_FUNCTION",
    "EXPLICIT_CONNECTION": "EXPLICIT_CONNECTION"
}

# Singleton DDS setup
class _DDSWriters:
    _instances = {}
    _lock = threading.Lock()

    def __init__(self, participant):
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        self.participant = participant
        self.publisher = dds.Publisher(self.participant)
        # Topics
        self.component_lifecycle_type = self.type_provider.type("genesis_lib", "ComponentLifecycleEvent")
        self.component_lifecycle_topic = dds.DynamicData.Topic(
            self.participant, "rti/connext/genesis/monitoring/ComponentLifecycleEvent", self.component_lifecycle_type
        )
        # Writers
        writer_qos = dds.QosProvider.default.datawriter_qos
        # Lifecycle is an event stream: make it VOLATILE (no history backfill)
        writer_qos.durability.kind = dds.DurabilityKind.VOLATILE
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        self.component_lifecycle_writer = dds.DynamicData.DataWriter(
            pub=self.publisher,
            topic=self.component_lifecycle_topic,
            qos=writer_qos
        )
        # Durable Graph topology writers (node/edge)
        self.graph_node_type = self.type_provider.type("genesis_lib", "GenesisGraphNode")
        self.graph_edge_type = self.type_provider.type("genesis_lib", "GenesisGraphEdge")
        self.graph_node_topic = dds.DynamicData.Topic(self.participant, "rti/connext/genesis/monitoring/GenesisGraphNode", self.graph_node_type)
        self.graph_edge_topic = dds.DynamicData.Topic(self.participant, "rti/connext/genesis/monitoring/GenesisGraphEdge", self.graph_edge_type)
        durable_qos = dds.QosProvider.default.datawriter_qos
        durable_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        durable_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        durable_qos.history.kind = dds.HistoryKind.KEEP_LAST
        durable_qos.history.depth = 1
        self.graph_node_writer = dds.DynamicData.DataWriter(pub=self.publisher, topic=self.graph_node_topic, qos=durable_qos)
        self.graph_edge_writer = dds.DynamicData.DataWriter(pub=self.publisher, topic=self.graph_edge_topic, qos=durable_qos)
        
        # NEW UNIFIED MONITORING TOPICS (Phase 2: Dual-publishing)
        # GraphTopology (durable) - consolidates GenesisGraphNode + GenesisGraphEdge
        self.graph_topology_type = self.type_provider.type("genesis_lib", "GraphTopology")
        try:
            self.graph_topology_topic = dds.DynamicData.Topic(
                self.participant, "rti/connext/genesis/monitoring/GraphTopology", self.graph_topology_type
            )
        except Exception:
            # Topic already exists, find it
            self.graph_topology_topic = dds.Topic.find(
                self.participant, "rti/connext/genesis/monitoring/GraphTopology"
            )
        self.graph_topology_writer = dds.DynamicData.DataWriter(
            pub=self.publisher, topic=self.graph_topology_topic, qos=durable_qos
        )
        
        # MonitoringEventUnified (volatile) - consolidates ChainEvent + ComponentLifecycleEvent + MonitoringEvent
        self.monitoring_event_unified_type = self.type_provider.type("genesis_lib", "MonitoringEventUnified")
        try:
            self.monitoring_event_unified_topic = dds.DynamicData.Topic(
                self.participant, "rti/connext/genesis/monitoring/Event", self.monitoring_event_unified_type
            )
        except Exception:
            # Topic already exists, find it
            self.monitoring_event_unified_topic = dds.Topic.find(
                self.participant, "rti/connext/genesis/monitoring/Event"
            )
        volatile_qos = dds.QosProvider.default.datawriter_qos
        volatile_qos.durability.kind = dds.DurabilityKind.VOLATILE
        volatile_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        self.monitoring_event_unified_writer = dds.DynamicData.DataWriter(
            pub=self.publisher, topic=self.monitoring_event_unified_topic, qos=volatile_qos
        )
        
        # Optional legacy MonitoringEvent
        self.legacy_enabled = os.environ.get("GENESIS_MON_LEGACY", "0") == "1"
        if self.legacy_enabled:
            self.monitoring_type = self.type_provider.type("genesis_lib", "MonitoringEvent")
            self.monitoring_topic = dds.DynamicData.Topic(
                self.participant, "rti/connext/genesis/monitoring/MonitoringEvent", self.monitoring_type
            )
            self.monitoring_writer = dds.DynamicData.DataWriter(
                pub=self.publisher,
                topic=self.monitoring_topic,
                qos=writer_qos
            )

    @classmethod
    def get(cls, participant):
        with cls._lock:
            key = id(participant)
            if key not in cls._instances:
                cls._instances[key] = _DDSWriters(participant)
            return cls._instances[key]

class GraphMonitor:
    def __init__(self, participant):
        self.dds = _DDSWriters.get(participant)

    def _derive_node_name(self, component_type: int, attrs: dict | None, component_id: str) -> str:
        attrs = attrs or {}
        try:
            ct_str = [k for k, v in COMPONENT_TYPE.items() if v == int(component_type)][0]
        except Exception:
            ct_str = "UNKNOWN"
        if ct_str == "SERVICE":
            return attrs.get("service_name") or attrs.get("service") or attrs.get("prefered_name") or f"Service_{component_id[:8]}"
        if ct_str in ("AGENT_PRIMARY", "AGENT_SPECIALIZED"):
            return attrs.get("prefered_name") or attrs.get("agent_name") or attrs.get("name") or f"Agent_{component_id[:8]}"
        if ct_str == "INTERFACE":
            return attrs.get("interface_name") or attrs.get("prefered_name") or attrs.get("service") or f"Interface_{component_id[:8]}"
        if ct_str == "FUNCTION":
            return attrs.get("function_name") or attrs.get("name") or f"Function_{component_id[:8]}"
        return attrs.get("name") or component_id

    def publish_node(self, component_id, component_type, state, attrs=None):
        """
        Publish a node (agent, interface, service, function) to the graph.
        component_id: str (GUID or UUID)
        component_type: int (see COMPONENT_TYPE)
        state: int (see STATE)
        attrs: dict (arbitrary metadata)
        """
        event = dds.DynamicData(self.dds.component_lifecycle_type)
        # Set all fields in the exact order as in the IDL
        event["component_id"] = component_id
        event["component_type"] = int(component_type)
        event["previous_state"] = int(state)
        event["new_state"] = int(state)
        event["timestamp"] = int(time.time() * 1000)
        event["reason"] = attrs.get("reason", "") if attrs else ""
        event["capabilities"] = json.dumps(attrs) if attrs else ""
        event["chain_id"] = ""
        event["call_id"] = ""
        event["event_category"] = int(EVENT_CATEGORY["NODE_DISCOVERY"])
        event["source_id"] = component_id
        event["target_id"] = component_id
        event["connection_type"] = ""
        self.dds.component_lifecycle_writer.write(event)
        self.dds.component_lifecycle_writer.flush()
        logger.info(f"GraphMonitor: Published NODE {component_id} type={component_type} state={state}")
        print(f"GraphMonitor: Published NODE {component_id} type={component_type} state={state}")

        # Durable node update
        node = dds.DynamicData(self.dds.graph_node_type)
        node["node_id"] = component_id
        # Map integer to string for node_type/state in durable topic
        node_type_str = "UNKNOWN"
        try:
            node_type_str = [k for k, v in COMPONENT_TYPE.items() if v == int(component_type)][0]
        except Exception:
            pass
        state_str = "UNKNOWN"
        try:
            state_str = [k for k, v in STATE.items() if v == int(state)][0]
        except Exception:
            pass
        node["node_type"] = node_type_str
        node["node_state"] = state_str
        node["node_name"] = self._derive_node_name(component_type, attrs, component_id)
        node["metadata"] = json.dumps(attrs or {})
        node["timestamp"] = int(time.time() * 1000)
        self.dds.graph_node_writer.write(node)

        # NEW: Publish to unified GraphTopology topic (kind=NODE)
        topology = dds.DynamicData(self.dds.graph_topology_type)
        topology["element_id"] = component_id
        topology["kind"] = 0  # NODE
        topology["timestamp"] = int(time.time() * 1000)
        topology["component_name"] = self._derive_node_name(component_type, attrs, component_id)
        topology["component_type"] = node_type_str
        topology["state"] = state_str
        # Pack node metadata into JSON payload
        node_payload = {
            "node_type": node_type_str,
            "node_state": state_str,
            "capabilities": attrs or {}
        }
        topology["metadata"] = json.dumps(node_payload)
        self.dds.graph_topology_writer.write(topology)
        logger.debug(f"GraphMonitor: Published unified GraphTopology NODE {component_id}")

        # NEW: Publish to unified MonitoringEventUnified topic (kind=LIFECYCLE)
        unified_event = dds.DynamicData(self.dds.monitoring_event_unified_type)
        unified_event["event_id"] = str(uuid.uuid4())
        unified_event["kind"] = 1  # LIFECYCLE
        unified_event["timestamp"] = int(time.time() * 1000)
        unified_event["component_id"] = component_id
        unified_event["severity"] = "INFO"
        unified_event["message"] = f"Node {node_type_str} {state_str}"
        # Pack lifecycle data into payload
        lifecycle_payload = {
            "previous_state": state_str,
            "new_state": state_str,
            "reason": attrs.get("reason", "") if attrs else "",
            "capabilities": attrs or {},
            "component_type": node_type_str
        }
        unified_event["payload"] = json.dumps(lifecycle_payload)
        self.dds.monitoring_event_unified_writer.write(unified_event)

        # Optionally emit legacy MonitoringEvent
        if self.dds.legacy_enabled:
            self._publish_legacy_monitoring_event(component_id, component_type, state, attrs)

    def publish_edge(self, source_id, target_id, edge_type, attrs=None, component_type=None):
        """
        Publish an edge (connection) between two nodes.
        source_id: str (GUID or UUID)
        target_id: str (GUID or UUID)
        edge_type: str (see EDGE_TYPE)
        attrs: dict (arbitrary metadata)
        component_type: int (see COMPONENT_TYPE) - type of the source node (REQUIRED)
        """
        if component_type is None:
            # Default to INTERFACE if not specified, but this should be set by caller
            component_type = COMPONENT_TYPE["INTERFACE"]
        event = dds.DynamicData(self.dds.component_lifecycle_type)
        # Set all fields in the exact order as in the IDL
        event["component_id"] = source_id
        event["component_type"] = int(component_type)
        event["previous_state"] = int(STATE["DISCOVERING"])
        event["new_state"] = int(STATE["DISCOVERING"])
        event["timestamp"] = int(time.time() * 1000)
        event["reason"] = attrs.get("reason", "") if attrs else ""
        event["capabilities"] = json.dumps(attrs) if attrs else ""
        event["chain_id"] = ""
        event["call_id"] = ""
        event["event_category"] = int(EVENT_CATEGORY["EDGE_DISCOVERY"])
        event["source_id"] = source_id
        event["target_id"] = target_id
        event["connection_type"] = edge_type
        self.dds.component_lifecycle_writer.write(event)
        self.dds.component_lifecycle_writer.flush()
        logger.info(f"GraphMonitor: Published EDGE {source_id} -> {target_id} type={edge_type}")
        print(f"GraphMonitor: Published EDGE {source_id} -> {target_id} type={edge_type}")

        # Durable edge update
        edge = dds.DynamicData(self.dds.graph_edge_type)
        edge["source_id"] = source_id
        edge["target_id"] = target_id
        edge["edge_type"] = edge_type
        edge["metadata"] = json.dumps(attrs or {})
        edge["timestamp"] = int(time.time() * 1000)
        self.dds.graph_edge_writer.write(edge)

        # NEW: Publish to unified GraphTopology topic (kind=EDGE)
        topology = dds.DynamicData(self.dds.graph_topology_type)
        # Use compound ID for edges: source_id|target_id|edge_type
        edge_id = f"{source_id}|{target_id}|{edge_type}"
        topology["element_id"] = edge_id
        topology["kind"] = 1  # EDGE
        topology["timestamp"] = int(time.time() * 1000)
        topology["component_name"] = f"{source_id[:8]}→{target_id[:8]}"
        topology["component_type"] = edge_type
        topology["state"] = "ACTIVE"
        # Pack edge metadata into JSON payload
        edge_payload = {
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": edge_type,
            "attributes": attrs or {}
        }
        topology["metadata"] = json.dumps(edge_payload)
        self.dds.graph_topology_writer.write(topology)
        logger.debug(f"GraphMonitor: Published unified GraphTopology EDGE {source_id} -> {target_id}")

        # NEW: Publish to unified MonitoringEventUnified topic (kind=LIFECYCLE for edge discovery)
        unified_event = dds.DynamicData(self.dds.monitoring_event_unified_type)
        unified_event["event_id"] = str(uuid.uuid4())
        unified_event["kind"] = 1  # LIFECYCLE (edge discovery is a lifecycle event)
        unified_event["timestamp"] = int(time.time() * 1000)
        unified_event["component_id"] = source_id
        unified_event["severity"] = "INFO"
        unified_event["message"] = f"Edge {edge_type}: {source_id[:8]} -> {target_id[:8]}"
        # Pack edge discovery data into payload
        edge_event_payload = {
            "event_category": "EDGE_DISCOVERY",
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": edge_type,
            "attributes": attrs or {}
        }
        unified_event["payload"] = json.dumps(edge_event_payload)
        self.dds.monitoring_event_unified_writer.write(unified_event)

        # Optionally emit legacy MonitoringEvent
        if self.dds.legacy_enabled:
            self._publish_legacy_monitoring_event(source_id, -1, STATE["DISCOVERING"], attrs, edge=True, target_id=target_id, edge_type=edge_type)

    def _publish_legacy_monitoring_event(self, entity_id, entity_type, state, attrs, edge=False, target_id=None, edge_type=None):
        """
        Optionally publish a legacy MonitoringEvent for backward compatibility.
        """
        if not hasattr(self.dds, "monitoring_writer"):
            return
        event = dds.DynamicData(self.dds.monitoring_type)
        event["event_id"] = str(uuid.uuid4())
        event["timestamp"] = int(time.time() * 1000)
        event["event_type"] = 0 if not edge else 1  # 0=node, 1=edge
        event["entity_type"] = entity_type
        event["entity_id"] = entity_id
        if attrs:
            event["metadata"] = json.dumps(attrs)
        if edge and target_id:
            event["call_data"] = json.dumps({"target_id": target_id, "edge_type": edge_type})
        self.dds.monitoring_writer.write(event)
        logger.debug(f"GraphMonitor: Published legacy MonitoringEvent for {'EDGE' if edge else 'NODE'} {entity_id}")

# Export enums for import convenience
__all__ = [
    "GraphMonitor",
    "COMPONENT_TYPE",
    "STATE",
    "EVENT_CATEGORY",
    "EDGE_TYPE"
]
