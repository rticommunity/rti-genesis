from __future__ import annotations

import threading
import json
from dataclasses import dataclass
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import rti.connextdds as dds
from .utils import get_datamodel_path

try:
    import networkx as nx  # type: ignore
except Exception:  # pragma: no cover
    nx = None


@dataclass
class NodeInfo:
    node_id: str
    node_type: str
    node_name: str
    node_state: str
    metadata: Dict[str, Any]


@dataclass
class EdgeInfo:
    source_id: str
    target_id: str
    edge_type: str
    metadata: Dict[str, Any]


class GenesisNetworkGraph:
    """Thread-safe in-memory graph of the Genesis network."""

    def __init__(self) -> None:
        self._nodes: Dict[str, NodeInfo] = {}
        self._edges: Dict[Tuple[str, str, str], EdgeInfo] = {}
        self._lock = threading.RLock()

    def add_or_update_node(self, node: NodeInfo) -> None:
        with self._lock:
            self._nodes[node.node_id] = node

    def add_or_update_edge(self, edge: EdgeInfo) -> None:
        with self._lock:
            key = (edge.source_id, edge.target_id, edge.edge_type)
            self._edges[key] = edge

    def remove_node(self, node_id: str) -> None:
        with self._lock:
            self._nodes.pop(node_id, None)
            self._edges = {k: v for k, v in self._edges.items() if node_id not in (k[0], k[1])}

    def remove_edge(self, source_id: str, target_id: str, edge_type: Optional[str] = None) -> None:
        with self._lock:
            if edge_type is None:
                self._edges = {k: v for k, v in self._edges.items() if not (k[0] == source_id and k[1] == target_id)}
            else:
                self._edges.pop((source_id, target_id, edge_type), None)

    def to_networkx(self):
        if nx is None:  # pragma: no cover
            return None
        with self._lock:
            G = nx.DiGraph()
            for node in self._nodes.values():
                G.add_node(node.node_id, **{
                    "node_type": node.node_type,
                    "node_name": node.node_name,
                    "node_state": node.node_state,
                    "metadata": node.metadata,
                })
            for edge in self._edges.values():
                G.add_edge(edge.source_id, edge.target_id, **{
                    "edge_type": edge.edge_type,
                    "metadata": edge.metadata,
                })
            return G

    def to_cytoscape(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "elements": {
                    "nodes": [
                        {"data": {"id": n.node_id, "label": n.node_name, "type": n.node_type, "state": n.node_state}}
                        for n in self._nodes.values()
                    ],
                    "edges": [
                        {"data": {"id": f"{e.source_id}->{e.target_id}:{e.edge_type}", "source": e.source_id, "target": e.target_id, "type": e.edge_type}}
                        for e in self._edges.values()
                    ],
                }
            }


class _LifecycleListener(dds.DynamicData.NoOpDataReaderListener):
    def __init__(self, on_event: Callable[[Dict[str, Any]], None]) -> None:
        super().__init__()
        self._on_event = on_event

    def on_data_available(self, reader) -> None:  # type: ignore[override]
        try:
            for sample in reader.take():
                if sample.info.valid:
                    data = sample.data
                    self._on_event({
                        "component_id": str(data["component_id"]) if data["component_id"] else "",
                        "component_type": int(data["component_type"]),
                        "previous_state": int(data["previous_state"]),
                        "new_state": int(data["new_state"]),
                        "timestamp": int(data["timestamp"]),
                        "reason": str(data["reason"]) if data["reason"] else "",
                        "capabilities": str(data["capabilities"]) if data["capabilities"] else "",
                        "event_category": int(data["event_category"]),
                        "source_id": str(data["source_id"]) if data["source_id"] else "",
                        "target_id": str(data["target_id"]) if data["target_id"] else "",
                        "connection_type": str(data["connection_type"]) if data["connection_type"] else "",
                    })
        except Exception:
            # Avoid raising in DDS callback
            pass


class GraphSubscriber:
    """DDS subscriber focused on ComponentLifecycleEvent for topology graph."""

    # Mappings for enums
    _COMPONENT_TYPES = ["INTERFACE", "PRIMARY_AGENT", "SPECIALIZED_AGENT", "FUNCTION", "SERVICE"]
    _STATES = ["JOINING", "DISCOVERING", "READY", "BUSY", "DEGRADED", "OFFLINE"]
    _EVENT_CATEGORIES = ["NODE_DISCOVERY", "EDGE_DISCOVERY", "STATE_CHANGE", "AGENT_INIT", "AGENT_READY", "AGENT_SHUTDOWN", "DDS_ENDPOINT"]

    def __init__(self, domain_id: int, on_graph_update: Callable[[str, Dict[str, Any]], None], on_activity: Optional[Callable[[Dict[str, Any]], None]] = None):
        self._domain_id = domain_id
        self._on_graph_update = on_graph_update
        self._on_activity = on_activity
        self._participant: Optional[dds.DomainParticipant] = None
        self._subscriber: Optional[dds.Subscriber] = None
        self._lifecycle_reader: Optional[dds.DynamicData.DataReader] = None
        self._graph_node_reader = None
        self._graph_edge_reader = None
        self._chain_reader = None
        # V2 unified topic readers
        self._topology_v2_reader = None
        self._event_v2_chain_reader = None
        # Track instance handles to ids for removal on NOT_ALIVE states
        self._node_handle_to_id: Dict[Any, str] = {}
        self._edge_handle_to_key: Dict[Any, Tuple[str, str, str]] = {}
        # Built-in topic aids: map publication handle → participant key, and participant key → set of node_ids
        self._pub_handle_to_participant: Dict[Any, str] = {}
        self._participant_to_nodes: Dict[str, set[str]] = {}
        # Logger
        self._logger = logging.getLogger("genesis.graph_state")
        if not self._logger.handlers:
            level_name = os.getenv("GENESIS_GRAPH_STATE_LEVEL", "DEBUG").upper()
            self._logger.setLevel(getattr(logging, level_name, logging.INFO))
            sh = logging.StreamHandler()
            sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] graph_state: %(message)s"))
            self._logger.addHandler(sh)
            try:
                log_dir = os.path.join("logs")
                os.makedirs(log_dir, exist_ok=True)
                fh = logging.FileHandler(os.path.join(log_dir, "graph_state.log"), mode='w')
                fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] graph_state: %(message)s"))
                self._logger.addHandler(fh)
            except Exception:
                # If file handler fails, continue with stream only
                pass

    def start(self) -> None:
        config_path = get_datamodel_path()
        self._logger.info(f"Starting GraphSubscriber on domain {self._domain_id}")
        self._participant = dds.DomainParticipant(self._domain_id)
        self._subscriber = dds.Subscriber(self._participant)
        provider = dds.QosProvider(config_path)

        # Prefer durable GenesisGraphNode/Edge if available
        try:
            graph_node_type = provider.type("genesis_lib", "GenesisGraphNode")
            graph_edge_type = provider.type("genesis_lib", "GenesisGraphEdge")
        except Exception:
            graph_node_type = None
            graph_edge_type = None
        if graph_node_type is None or graph_edge_type is None:
            self._logger.warning("Durable GenesisGraphNode/Edge types not found; removals rely on lifecycle or may be delayed")
        else:
            self._logger.info("Durable topology readers enabled (GenesisGraphNode/Edge)")

        lifecycle_type = provider.type("genesis_lib", "ComponentLifecycleEvent")
        lifecycle_topic = dds.DynamicData.Topic(self._participant, "rti/connext/genesis/monitoring/ComponentLifecycleEvent", lifecycle_type)

        reader_qos = dds.QosProvider.default.datareader_qos
        # Lifecycle is transient activity; subscribe VOLATILE
        reader_qos.durability.kind = dds.DurabilityKind.VOLATILE
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.history.kind = dds.HistoryKind.KEEP_ALL

        listener = _LifecycleListener(self._handle_lifecycle_event)
        self._lifecycle_reader = dds.DynamicData.DataReader(
            subscriber=self._subscriber,
            topic=lifecycle_topic,
            qos=reader_qos,
            listener=listener,
            mask=dds.StatusMask.DATA_AVAILABLE,
        )
        self._logger.info("Lifecycle reader started (ComponentLifecycleEvent)")

        # ==============================================================
        # UNIFIED MONITORING TOPICS (GraphTopology, Event)
        # ==============================================================
        self._logger.info("Using unified monitoring topics (GraphTopology, Event)")
        self._setup_v2_topology_reader(provider)
        self._setup_v2_event_reader(provider)

        # Built-in topics to detect ungraceful participant loss
        try:
            builtin_sub = self._participant.builtin_subscriber  # type: ignore[attr-defined]

            class _BuiltInParticipantListener(dds.ParticipantBuiltinTopicData.DataReaderListener):  # type: ignore[attr-defined]
                def __init__(self, outer):
                    super().__init__()
                    self._outer = outer
                def on_data_available(self, reader):  # type: ignore[override]
                    try:
                        for sample in reader.take():
                            info = sample.info
                            if not getattr(info, 'valid_data', False):
                                st = getattr(info, 'instance_state', None)
                                if st in (dds.InstanceState.NOT_ALIVE_NO_WRITERS, dds.InstanceState.NOT_ALIVE_DISPOSED):
                                    # Attempt to get participant key from the instance handle via data if present
                                    part_key = ''
                                    try:
                                        if sample.data is not None:
                                            part_key = str(getattr(sample.data, 'key', ''))
                                    except Exception:
                                        part_key = ''
                                    # Fallback: stringify instance handle
                                    if not part_key:
                                        try:
                                            part_key = str(getattr(info, 'instance_handle', ''))
                                        except Exception:
                                            part_key = ''
                                    try:
                                        self._outer._logger.info(f"participant_lost state={st} key={part_key}")
                                    except Exception:
                                        pass
                                    if part_key:
                                        # Remove all nodes mapped to this participant
                                        try:
                                            node_ids = list(self._outer._participant_to_nodes.get(part_key, set()))
                                            for nid in node_ids:
                                                self._outer._on_graph_event("node_remove", {"node_id": nid})
                                            self._outer._participant_to_nodes.pop(part_key, None)
                                        except Exception:
                                            pass
                    except Exception:
                        pass

            class _BuiltInPublicationListener(dds.PublicationBuiltinTopicData.DataReaderListener):  # type: ignore[attr-defined]
                def __init__(self, outer):
                    super().__init__()
                    self._outer = outer
                def on_data_available(self, reader):  # type: ignore[override]
                    try:
                        for sample in reader.take():
                            info = sample.info
                            data = sample.data
                            try:
                                pub_h = getattr(info, 'instance_handle', None)
                                part_key = str(getattr(data, 'participant_key', ''))
                                if pub_h is not None and part_key:
                                    self._outer._pub_handle_to_participant[pub_h] = part_key
                            except Exception:
                                pass
                    except Exception:
                        pass

            try:
                p_reader = dds.ParticipantBuiltinTopicData.DataReader(builtin_sub)  # type: ignore[attr-defined]
                p_reader.bind_listener(_BuiltInParticipantListener(self), dds.StatusMask.DATA_AVAILABLE)
                self._logger.info("Built-in Participant reader started")
            except Exception:
                self._logger.debug("Built-in Participant reader unavailable")
            try:
                pub_reader = dds.PublicationBuiltinTopicData.DataReader(builtin_sub)  # type: ignore[attr-defined]
                pub_reader.bind_listener(_BuiltInPublicationListener(self), dds.StatusMask.DATA_AVAILABLE)
                self._logger.info("Built-in Publication reader started")
            except Exception:
                self._logger.debug("Built-in Publication reader unavailable")
        except Exception:
            self._logger.debug("Built-in subscriber not available")

    def _setup_v2_topology_reader(self, provider: dds.QosProvider) -> None:
        """Set up GraphTopology reader for unified node and edge data."""
        try:
            topology_type = provider.type("genesis_lib", "GraphTopology")
            topology_topic = dds.DynamicData.Topic(
                self._participant, 
                "rti/connext/genesis/monitoring/GraphTopology", 
                topology_type
            )
            
            # Durable QoS for topology
            durable_qos = dds.QosProvider.default.datareader_qos
            durable_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            durable_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            durable_qos.history.kind = dds.HistoryKind.KEEP_ALL
            
            class _TopologyV2Listener(dds.DynamicData.NoOpDataReaderListener):
                def __init__(self, outer):
                    super().__init__()
                    self._outer = outer
                
                def on_data_available(self, reader):  # type: ignore[override]
                    try:
                        for data, info in reader.take():
                            if info.valid:
                                kind = int(data["kind"]) if data["kind"] is not None else -1
                                element_id = str(data["element_id"]) or ""
                                metadata_json = str(data["metadata"]) or "{}"
                                
                                try:
                                    metadata = json.loads(metadata_json)
                                except Exception:
                                    metadata = {}
                                
                                if kind == 0:  # NODE
                                    # Extract node fields from metadata
                                    node_id = element_id
                                    node_type = metadata.get("node_type", "UNKNOWN")
                                    node_name = metadata.get("node_name", node_id)
                                    node_state = metadata.get("node_state", "UNKNOWN")
                                    caps = metadata.get("capabilities", {})
                                    
                                    # Track handle for removals
                                    try:
                                        self._outer._node_handle_to_id[info.instance_handle] = node_id
                                    except Exception:
                                        pass
                                    
                                    self._outer._logger.debug(f"V2_node_update {node_id} type={node_type} state={node_state}")
                                    self._outer._on_graph_update("node_update", {
                                        "node": NodeInfo(node_id, node_type, node_name, node_state, caps)
                                    })
                                
                                elif kind == 1:  # EDGE
                                    # element_id format: "source|target|edge_type"
                                    parts = element_id.split("|")
                                    if len(parts) == 3:
                                        source_id, target_id, edge_type = parts
                                        edge_metadata = metadata.get("edge_metadata", {})
                                        
                                        # Track handle for removals
                                        try:
                                            self._outer._edge_handle_to_key[info.instance_handle] = (source_id, target_id, edge_type)
                                        except Exception:
                                            pass
                                        
                                        self._outer._logger.debug(f"V2_edge_update {source_id}->{target_id}:{edge_type}")
                                        self._outer._on_graph_update("edge_update", {
                                            "edge": EdgeInfo(source_id, target_id, edge_type, edge_metadata)
                                        })
                            else:
                                # Handle NOT_ALIVE for removals
                                try:
                                    st = info.state.instance_state
                                except Exception:
                                    st = None
                                
                                if st in (dds.InstanceState.NOT_ALIVE_DISPOSED, dds.InstanceState.NOT_ALIVE_NO_WRITERS):
                                    # Try node removal first
                                    node_id = self._outer._node_handle_to_id.pop(info.instance_handle, "")
                                    if node_id:
                                        self._outer._logger.info(f"V2_node_remove due to {st}: id={node_id}")
                                        self._outer._on_graph_update("node_remove", {"node_id": node_id})
                                    else:
                                        # Try edge removal
                                        edge_key = self._outer._edge_handle_to_key.pop(info.instance_handle, None)
                                        if edge_key is not None:
                                            src, tgt, et = edge_key
                                            self._outer._logger.info(f"V2_edge_remove due to {st}: {src}->{tgt}:{et}")
                                            self._outer._on_graph_update("edge_remove", {
                                                "edge": {"source_id": src, "target_id": tgt, "edge_type": et}
                                            })
                    except Exception as e:
                        self._outer._logger.error(f"Error in V2 topology listener: {e}")
            
            self._topology_v2_reader = dds.DynamicData.DataReader(
                subscriber=self._subscriber,
                topic=topology_topic,
                qos=durable_qos,
                listener=_TopologyV2Listener(self),
                mask=dds.StatusMask.DATA_AVAILABLE,
            )
            self._logger.info("✅ GraphTopology reader started (durable, unified node+edge)")
        except Exception as e:
            self._logger.warning(f"Failed to set up GraphTopology reader: {e}")

    def _setup_v2_event_reader(self, provider: dds.QosProvider) -> None:
        """Set up Event reader with content filtering for CHAIN events."""
        if self._on_activity is None:
            self._logger.debug("Skipping Event reader (no activity callback)")
            return
        
        try:
            event_type = provider.type("genesis_lib", "MonitoringEventUnified")
            event_topic = dds.DynamicData.Topic(
                self._participant,
                "rti/connext/genesis/monitoring/Event",
                event_type
            )
            
            # Content filter for CHAIN events only (kind = 0)
            filtered_topic = dds.DynamicData.ContentFilteredTopic(
                event_topic,
                "Event_ChainFilter",
                dds.Filter("kind = %0", ["0"])  # CHAIN kind
            )
            
            # Volatile QoS for events
            event_qos = dds.QosProvider.default.datareader_qos
            event_qos.durability.kind = dds.DurabilityKind.VOLATILE
            event_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            event_qos.history.kind = dds.HistoryKind.KEEP_ALL
            
            class _EventChainListener(dds.DynamicData.NoOpDataReaderListener):
                def __init__(self, cb):
                    super().__init__()
                    self._cb = cb
                
                def on_data_available(self, reader):  # type: ignore[override]
                    try:
                        for data, info in reader.take():
                            if info.valid:
                                # Parse payload JSON for chain event fields
                                payload_json = str(data["payload"]) or "{}"
                                try:
                                    payload = json.loads(payload_json)
                                except Exception:
                                    payload = {}
                                
                                # Build chain event dict matching old ChainEvent format
                                evt = {
                                    "chain_id": payload.get("chain_id", ""),
                                    "call_id": payload.get("call_id", ""),
                                    "source_id": payload.get("source_id", ""),
                                    "target_id": payload.get("target_id", ""),
                                    "function_id": payload.get("function_id", ""),
                                    "interface_id": payload.get("interface_id", ""),
                                    "primary_agent_id": payload.get("primary_agent_id", ""),
                                    "specialized_agent_ids": payload.get("specialized_agent_ids", ""),
                                    "query_id": payload.get("query_id", ""),
                                    "event_type": payload.get("event_type", ""),
                                    "status": payload.get("status", 0),
                                    "timestamp": payload.get("timestamp", 0),
                                }
                                
                                try:
                                    self._cb(evt)
                                except Exception:
                                    pass
                    except Exception:
                        pass
            
            self._event_v2_chain_reader = dds.DynamicData.DataReader(
                subscriber=self._subscriber,
                cft=filtered_topic,  # Use content-filtered topic
                qos=event_qos,
                listener=_EventChainListener(self._on_activity),
                mask=dds.StatusMask.DATA_AVAILABLE,
            )
            self._logger.info("✅ Event CHAIN reader started (volatile, content-filtered for kind=CHAIN)")
        except Exception as e:
            self._logger.warning(f"Failed to set up Event reader: {e}")

    def stop(self) -> None:
        try:
            self._logger.info("Stopping GraphSubscriber")
            if self._graph_edge_reader:
                self._graph_edge_reader.close()
            if self._graph_node_reader:
                self._graph_node_reader.close()
            if self._lifecycle_reader:
                self._lifecycle_reader.close()
            if self._chain_reader:
                self._chain_reader.close()
            # Close V2 readers if present
            if self._topology_v2_reader:
                self._topology_v2_reader.close()
            if self._event_v2_chain_reader:
                self._event_v2_chain_reader.close()
            if self._subscriber:
                self._subscriber.close()
            if self._participant:
                self._participant.close()
        finally:
            self._lifecycle_reader = None
            self._subscriber = None
            self._participant = None
            self._graph_edge_reader = None
            self._graph_node_reader = None
            self._chain_reader = None

    def _select_node_name(self, ctype: str, node_id: str, caps: Dict[str, Any]) -> str:
        if ctype == "FUNCTION":
            return caps.get("function_name") or caps.get("name") or f"FUNCTION_{node_id[:8]}"
        if ctype in ("PRIMARY_AGENT", "SPECIALIZED_AGENT"):
            return caps.get("prefered_name") or caps.get("agent_name") or caps.get("name") or f"Agent_{node_id[:8]}"
        if ctype == "INTERFACE":
            return caps.get("interface_name") or caps.get("prefered_name") or caps.get("service") or f"Interface_{node_id[:8]}"
        if ctype == "SERVICE":
            return caps.get("service_name") or caps.get("service") or f"Service_{node_id[:8]}"
        return f"{ctype}_{node_id[:8]}"

    def _handle_lifecycle_event(self, evt: Dict[str, Any]) -> None:
        cat_idx = evt.get("event_category", -1)
        category = self._EVENT_CATEGORIES[cat_idx] if 0 <= cat_idx < len(self._EVENT_CATEGORIES) else "UNKNOWN"

        if category == "NODE_DISCOVERY":
            ctype_idx = evt.get("component_type", -1)
            ctype = self._COMPONENT_TYPES[ctype_idx] if 0 <= ctype_idx < len(self._COMPONENT_TYPES) else "UNKNOWN"
            node_id = evt.get("component_id", "")
            try:
                caps = json.loads(evt.get("capabilities") or "{}")
            except Exception:
                caps = {}
            node_name = self._select_node_name(ctype, node_id, caps)
            state_idx = evt.get("new_state", 0)
            state = self._STATES[state_idx] if 0 <= state_idx < len(self._STATES) else "UNKNOWN"
            try:
                self._logger.debug(f"lifecycle NODE_DISCOVERY id={node_id} type={ctype} state={state} name=\"{node_name}\"")
            except Exception:
                pass
            self._on_graph_update("node_update", {
                "node": NodeInfo(node_id=node_id, node_type=ctype, node_name=node_name, node_state=state, metadata=caps)
            })

        elif category == "EDGE_DISCOVERY":
            src = evt.get("source_id", "")
            tgt = evt.get("target_id", "")
            etype = evt.get("connection_type", "")
            try:
                caps = json.loads(evt.get("capabilities") or "{}")
            except Exception:
                caps = {}
            try:
                self._logger.debug(f"lifecycle EDGE_DISCOVERY {src}->{tgt}:{etype}")
            except Exception:
                pass
            self._on_graph_update("edge_update", {
                "edge": EdgeInfo(source_id=src, target_id=tgt, edge_type=etype, metadata=caps)
            })

        elif category == "STATE_CHANGE":
            # Forward node update and synthesize activity for interface request start/complete
            node_id = evt.get("component_id", "")
            ctype_idx = evt.get("component_type", -1)
            ctype = self._COMPONENT_TYPES[ctype_idx] if 0 <= ctype_idx < len(self._COMPONENT_TYPES) else "UNKNOWN"
            state_idx = evt.get("new_state", 0)
            state = self._STATES[state_idx] if 0 <= state_idx < len(self._STATES) else "UNKNOWN"
            reason = evt.get("reason", "") or ""
            try:
                caps = json.loads(evt.get("capabilities") or "{}")
            except Exception:
                caps = {}
            # Emit node update for state change
            node_name = self._select_node_name(ctype, node_id, caps)
            self._on_graph_update("node_update", {
                "node": NodeInfo(node_id=node_id, node_type=ctype, node_name=node_name, node_state=state, metadata=caps)
            })
            # Synthesize INTERFACE_* activities so the viewer can pulse/log interface requests
            try:
                if self._on_activity is not None and ctype == "INTERFACE":
                    evt_ts = int(evt.get("timestamp", 0))
                    src = node_id
                    tgt = evt.get("target_id", "") or caps.get("target_id", "")
                    if state == "BUSY" and reason.lower().startswith("interface request"):
                        self._on_activity({
                            "event_type": "INTERFACE_REQUEST_START",
                            "source_id": src,
                            "target_id": tgt,
                            "status": 0,
                            "timestamp": evt_ts,
                        })
                    elif state == "READY" and ("response" in reason.lower() or reason.lower().startswith("interface response")):
                        self._on_activity({
                            "event_type": "INTERFACE_REQUEST_COMPLETE",
                            "source_id": src,
                            "target_id": tgt,
                            "status": 0,
                            "timestamp": evt_ts,
                        })
            except Exception:
                pass


class GraphService:
    """Public façade: manages subscriber and graph, provides exports and change listeners."""

    def __init__(self, domain_id: int = 0) -> None:
        self._graph = GenesisNetworkGraph()
        self._listeners: List[Callable[[str, Dict[str, Any]], None]] = []
        self._activity_listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._subscriber = GraphSubscriber(domain_id, self._on_graph_event, self._on_activity_event)

    # Lifecycle
    def start(self) -> None:
        self._subscriber.start()

    def stop(self) -> None:
        self._subscriber.stop()

    # Subscriptions for UI bridges
    def subscribe(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        self._listeners.append(callback)

    def subscribe_activity(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._activity_listeners.append(callback)

    def _notify(self, event: str, payload: Dict[str, Any]) -> None:
        for cb in list(self._listeners):
            try:
                cb(event, payload)
            except Exception:
                pass

    def _notify_activity(self, activity: Dict[str, Any]) -> None:
        for cb in list(self._activity_listeners):
            try:
                cb(activity)
            except Exception:
                pass

    # Internal handler from DDS subscriber → update graph → notify listeners
    def _on_graph_event(self, event: str, payload: Dict[str, Any]) -> None:
        if event == "node_update":
            node: NodeInfo = payload["node"]
            self._graph.add_or_update_node(node)
        elif event == "edge_update":
            edge: EdgeInfo = payload["edge"]
            self._graph.add_or_update_edge(edge)
        elif event == "node_remove":
            node_id = payload.get("node_id") or payload.get("node", {}).get("node_id")
            if node_id:
                self._graph.remove_node(str(node_id))
        elif event == "edge_remove":
            e = payload.get("edge") or payload
            src = e.get("source_id")
            tgt = e.get("target_id")
            ety = e.get("edge_type")
            if src and tgt:
                self._graph.remove_edge(str(src), str(tgt), str(ety) if ety is not None else None)
        self._notify(event, payload)

    def _on_activity_event(self, activity: Dict[str, Any]) -> None:
        self._notify_activity(activity)

    # Exports
    def to_networkx(self):
        return self._graph.to_networkx()

    def to_cytoscape(self) -> Dict[str, Any]:
        return self._graph.to_cytoscape()
