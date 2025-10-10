from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import networkx as nx  # type: ignore
except Exception:  # pragma: no cover
    nx = None  # Fallback for environments without NetworkX


@dataclass
class NodeInfo:
    node_id: str
    node_type: str
    node_name: str
    node_state: str = "UNKNOWN"
    metadata: Dict[str, Any] = None


@dataclass
class EdgeInfo:
    source_id: str
    target_id: str
    edge_type: str
    metadata: Dict[str, Any] = None


class GenesisNetworkGraph:
    """Minimal, thread-unsafe skeleton for prototyping only."""

    def __init__(self) -> None:
        self._nodes: Dict[str, NodeInfo] = {}
        self._edges: Dict[Tuple[str, str, str], EdgeInfo] = {}

    def add_or_update_node(self, node: NodeInfo) -> None:
        self._nodes[node.node_id] = node

    def add_or_update_edge(self, edge: EdgeInfo) -> None:
        key = (edge.source_id, edge.target_id, edge.edge_type)
        self._edges[key] = edge

    def remove_node(self, node_id: str) -> None:
        self._nodes.pop(node_id, None)
        self._edges = {k: v for k, v in self._edges.items() if node_id not in (k[0], k[1])}

    def remove_edge(self, source_id: str, target_id: str, edge_type: Optional[str] = None) -> None:
        if edge_type is None:
            self._edges = {
                k: v for k, v in self._edges.items()
                if not (k[0] == source_id and k[1] == target_id)
            }
        else:
            self._edges.pop((source_id, target_id, edge_type), None)

    def to_networkx(self):
        if nx is None:  # pragma: no cover
            return None
        G = nx.DiGraph()
        for node in self._nodes.values():
            G.add_node(node.node_id, **{
                "node_type": node.node_type,
                "node_name": node.node_name,
                "node_state": node.node_state,
                "metadata": node.metadata or {},
            })
        for edge in self._edges.values():
            G.add_edge(edge.source_id, edge.target_id, **{
                "edge_type": edge.edge_type,
                "metadata": edge.metadata or {},
            })
        return G

    def to_cytoscape(self) -> Dict[str, Any]:
        return {
            "elements": {
                "nodes": [
                    {"data": {"id": n.node_id, "label": n.node_name, "type": n.node_type}}
                    for n in self._nodes.values()
                ],
                "edges": [
                    {"data": {"id": f"{e.source_id}->{e.target_id}:{e.edge_type}", "source": e.source_id, "target": e.target_id, "type": e.edge_type}}
                    for e in self._edges.values()
                ],
            }
        }


class GraphSubscriber:
    """Placeholder DDS subscriber facade (no DDS code here)."""

    def __init__(self, graph: GenesisNetworkGraph) -> None:
        self._graph = graph

    def start(self) -> None:
        # No-op in skeleton
        return None

    def stop(self) -> None:
        # No-op in skeleton
        return None


class GraphService:
    """High-level façade combining subscriber + graph state."""

    def __init__(self, domain_id: int = 0) -> None:
        self._graph = GenesisNetworkGraph()
        self._subscriber = GraphSubscriber(self._graph)
        self._listeners: List[Callable[[str, Dict[str, Any]], None]] = []

    def start(self) -> None:
        self._subscriber.start()

    def stop(self) -> None:
        self._subscriber.stop()

    def subscribe(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        self._listeners.append(callback)

    def _notify(self, event: str, payload: Dict[str, Any]) -> None:
        for cb in list(self._listeners):
            try:
                cb(event, payload)
            except Exception:
                # ignore listener failures in skeleton
                pass

    # Prototyping helpers to simulate updates without DDS
    def add_node(self, node: NodeInfo) -> None:
        self._graph.add_or_update_node(node)
        self._notify("node_update", {"action": "add", "node": node.__dict__})

    def add_edge(self, edge: EdgeInfo) -> None:
        self._graph.add_or_update_edge(edge)
        self._notify("edge_update", {"action": "add", "edge": edge.__dict__})

    # Exports
    def to_networkx(self):
        return self._graph.to_networkx()

    def to_cytoscape(self) -> Dict[str, Any]:
        return self._graph.to_cytoscape()
