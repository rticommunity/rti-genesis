from __future__ import annotations

import threading
import json
from dataclasses import dataclass
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

    def start(self) -> None:
        config_path = get_datamodel_path()
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

        lifecycle_type = provider.type("genesis_lib", "ComponentLifecycleEvent")
        lifecycle_topic = dds.DynamicData.Topic(self._participant, "ComponentLifecycleEvent", lifecycle_type)

        reader_qos = dds.QosProvider.default.datareader_qos
        reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
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

        # Durable topology readers
        if graph_node_type is not None and graph_edge_type is not None:
            node_topic = dds.DynamicData.Topic(self._participant, "GenesisGraphNode", graph_node_type)
            edge_topic = dds.DynamicData.Topic(self._participant, "GenesisGraphEdge", graph_edge_type)
            durable_qos = dds.QosProvider.default.datareader_qos
            durable_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            durable_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            durable_qos.history.kind = dds.HistoryKind.KEEP_LAST
            durable_qos.history.depth = 1

            class _NodeListener(dds.DynamicData.NoOpDataReaderListener):
                def __init__(self, outer):
                    super().__init__()
                    self._outer = outer
                def on_data_available(self, reader):  # type: ignore[override]
                    try:
                        for data, info in reader.take():
                            if info.valid:
                                node_id = str(data["node_id"])
                                node_type = str(data["node_type"]) or "UNKNOWN"
                                node_state = str(data["node_state"]) or "UNKNOWN"
                                node_name = str(data["node_name"]) or node_id
                                md = str(data["metadata"]) or "{}"
                                try:
                                    caps = json.loads(md)
                                except Exception:
                                    caps = {}
                                self._outer._on_graph_update("node_update", {"node": NodeInfo(node_id, node_type, node_name, node_state, caps)})
                    except Exception:
                        pass

            class _EdgeListener(dds.DynamicData.NoOpDataReaderListener):
                def __init__(self, outer):
                    super().__init__()
                    self._outer = outer
                def on_data_available(self, reader):  # type: ignore[override]
                    try:
                        for data, info in reader.take():
                            if info.valid:
                                src = str(data["source_id"]) or ""
                                tgt = str(data["target_id"]) or ""
                                et = str(data["edge_type"]) or ""
                                md = str(data["metadata"]) or "{}"
                                try:
                                    caps = json.loads(md)
                                except Exception:
                                    caps = {}
                                self._outer._on_graph_update("edge_update", {"edge": EdgeInfo(src, tgt, et, caps)})
                    except Exception:
                        pass

            self._graph_node_reader = dds.DynamicData.DataReader(
                subscriber=self._subscriber,
                topic=node_topic,
                qos=durable_qos,
                listener=_NodeListener(self),
                mask=dds.StatusMask.DATA_AVAILABLE,
            )
            self._graph_edge_reader = dds.DynamicData.DataReader(
                subscriber=self._subscriber,
                topic=edge_topic,
                qos=durable_qos,
                listener=_EdgeListener(self),
                mask=dds.StatusMask.DATA_AVAILABLE,
            )

        # Activity (ChainEvent) - volatile
        try:
            chain_type = provider.type("genesis_lib", "ChainEvent")
            chain_topic = dds.DynamicData.Topic(self._participant, "ChainEvent", chain_type)
            chain_qos = dds.QosProvider.default.datareader_qos
            chain_qos.durability.kind = dds.DurabilityKind.VOLATILE
            chain_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            # Keep all ChainEvent samples to avoid dropping bursts of activity
            chain_qos.history.kind = dds.HistoryKind.KEEP_ALL

            class _ChainListener(dds.DynamicData.NoOpDataReaderListener):
                def __init__(self, cb):
                    super().__init__()
                    self._cb = cb
                def on_data_available(self, reader):  # type: ignore[override]
                    if self._cb is None:
                        return
                    try:
                        for data, info in reader.take():
                            if info.valid:
                                # Build event dict with defensive access for optional fields
                                def _get_opt(key: str) -> str:
                                    try:
                                        val = data[key]
                                        return str(val) if val else ""
                                    except Exception:
                                        return ""
                                def _get_opt_int(key: str) -> int:
                                    try:
                                        val = data[key]
                                        return int(val) if val else 0
                                    except Exception:
                                        return 0

                                evt = {
                                    "chain_id": _get_opt("chain_id"),
                                    "call_id": _get_opt("call_id"),
                                    "source_id": _get_opt("source_id"),
                                    "target_id": _get_opt("target_id"),
                                    # Optional context fields (present in some schemas)
                                    "function_id": _get_opt("function_id"),
                                    "interface_id": _get_opt("interface_id"),
                                    "primary_agent_id": _get_opt("primary_agent_id"),
                                    "specialized_agent_ids": _get_opt("specialized_agent_ids"),
                                    "query_id": _get_opt("query_id"),
                                    "event_type": _get_opt("event_type"),
                                    "status": _get_opt_int("status"),
                                    "timestamp": _get_opt_int("timestamp"),
                                }
                                try:
                                    self._cb(evt)
                                except Exception:
                                    pass
                    except Exception:
                        pass

            if self._on_activity is not None:
                self._chain_reader = dds.DynamicData.DataReader(
                    subscriber=self._subscriber,
                    topic=chain_topic,
                    qos=chain_qos,
                    listener=_ChainListener(self._on_activity),
                    mask=dds.StatusMask.DATA_AVAILABLE,
                )
        except Exception:
            # ChainEvent may not exist yet; ignore
            pass

    def stop(self) -> None:
        try:
            if self._graph_edge_reader:
                self._graph_edge_reader.close()
            if self._graph_node_reader:
                self._graph_node_reader.close()
            if self._lifecycle_reader:
                self._lifecycle_reader.close()
            if self._chain_reader:
                self._chain_reader.close()
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
            self._on_graph_update("edge_update", {
                "edge": EdgeInfo(source_id=src, target_id=tgt, edge_type=etype, metadata=caps)
            })


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
        self._notify(event, payload)

    def _on_activity_event(self, activity: Dict[str, Any]) -> None:
        self._notify_activity(activity)

    # Exports
    def to_networkx(self):
        return self._graph.to_networkx()

    def to_cytoscape(self) -> Dict[str, Any]:
        return self._graph.to_cytoscape()
