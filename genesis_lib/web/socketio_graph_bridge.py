"""
Forward GraphService events to a Flask‑SocketIO namespace.

Usage after creating SocketIO and starting GraphService:

    from genesis_lib.web.socketio_graph_bridge import attach_graph_to_socketio
    graph = GraphService(domain_id=0)
    graph.start()
    attach_graph_to_socketio(graph, socketio)
"""
from typing import Any
import logging
import os
from dataclasses import is_dataclass, asdict
from ..graph_state import GraphService

logger = logging.getLogger("socketio_graph_bridge")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
# Allow runtime control of verbosity via env var (default INFO)
_level_name = os.getenv("GENESIS_GRAPH_BRIDGE_LEVEL", "INFO").upper()
logger.setLevel(getattr(logging, _level_name, logging.INFO))


def _jsonable(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def attach_graph_to_socketio(graph: GraphService, socketio: "SocketIO") -> None:  # type: ignore
    # Track known topology so we only signal 'graph_updated' on creations
    seen_node_ids: set[str] = set()
    seen_edge_ids: set[str] = set()

    def _forward(event: str, payload: Any) -> None:
        try:
            payload_json = _jsonable(payload)
            # Incremental event → emit to all clients on default namespace
            socketio.emit(event, payload_json, namespace='/')

            # Determine if this is a CREATE and signal snapshot refresh only in that case
            is_create = False
            if event == "node_update":
                node = payload_json.get("node") if isinstance(payload_json, dict) else None
                node_id = node and node.get('node_id')
                if node_id and node_id not in seen_node_ids:
                    seen_node_ids.add(node_id)
                    is_create = True
                if is_create:
                    logger.info(f"Forwarded node_update (node_id={node_id}, create=True) → clients")
                else:
                    logger.debug(f"Forwarded node_update (node_id={node_id}, create=False) → clients")
            elif event == "edge_update":
                edge = payload_json.get("edge") if isinstance(payload_json, dict) else None
                src = edge and edge.get('source_id')
                tgt = edge and edge.get('target_id')
                ety = edge and edge.get('edge_type')
                if src and tgt:
                    edge_key = f"{src}->{tgt}:{ety or ''}"
                    if edge_key not in seen_edge_ids:
                        seen_edge_ids.add(edge_key)
                        is_create = True
                if is_create:
                    logger.info(f"Forwarded edge_update ({src}->{tgt}:{ety}, create=True) → clients")
                else:
                    logger.debug(f"Forwarded edge_update ({src}->{tgt}:{ety}, create=False) → clients")
            else:
                logger.debug(f"Forwarded event {event} → clients")

            if is_create:
                socketio.emit("graph_updated", {"event": event}, namespace='/')
        except Exception as e:
            logger.error(f"Error forwarding event {event}: {e}")

    graph.subscribe(_forward)

    # Activity overlay
    def _forward_activity(activity: Any) -> None:
        try:
            socketio.emit("activity", _jsonable(activity), namespace='/')
            logger.debug("Forwarded activity event → clients")
        except Exception as e:
            logger.error(f"Error forwarding activity: {e}")

    graph.subscribe_activity(_forward_activity)

    @socketio.on("graph_snapshot")
    def handle_graph_snapshot():
        try:
            cs = graph.to_cytoscape()
            nodes = len(cs.get("elements", {}).get("nodes", []))
            edges = len(cs.get("elements", {}).get("edges", []))
            logger.debug(f"Emitting graph_snapshot (nodes={nodes}, edges={edges})")
            socketio.emit("graph_snapshot", cs, namespace='/')
        except Exception as e:
            logger.error(f"Error emitting snapshot: {e}")
