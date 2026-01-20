#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
#                                                                                    #
# RTI grants Licensee a license to use, modify, compile, and create derivative       #
# works of the Software. Licensee has the right to distribute object form only       #
# for use with RTI products. The Software is provided "as is", with no warranty      #
# of any type, including any warranty for fitness for any purpose. RTI is under no   #
# obligation to maintain or support the Software. RTI shall not be liable for any    #
# incidental or consequential damages arising out of the use or inability to use     #
# the software.                                                                      #
# ####################################################################################

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
    # De-duplication windows
    import time
    import threading
    last_update_at: dict[str, float] = {}
    last_remove_at: dict[str, float] = {}
    UPDATE_SUPPRESS_MS = float(os.getenv("GENESIS_GRAPH_BRIDGE_UPDATE_SUPPRESS_MS", "500"))
    REMOVE_SUPPRESS_MS = float(os.getenv("GENESIS_GRAPH_BRIDGE_REMOVE_SUPPRESS_MS", "2000"))
    BATCH_MS = float(os.getenv("GENESIS_GRAPH_BRIDGE_BATCH_MS", "0"))  # 0 disables batching

    # Batch buffers (only used if BATCH_MS > 0)
    pending_batch: dict[str, list] = {
        "node_updates": [],
        "edge_updates": [],
        "node_removes": [],
        "edge_removes": [],
    }
    batch_lock = threading.Lock()
    batch_timer: list[Any] = [None]  # single-item list to allow rebinding within closure

    def _flush_batch() -> None:
        nonlocal pending_batch
        try:
            with batch_lock:
                payload = {
                    "node_updates": pending_batch["node_updates"],
                    "edge_updates": pending_batch["edge_updates"],
                    "node_removes": pending_batch["node_removes"],
                    "edge_removes": pending_batch["edge_removes"],
                }
                # reset buffers and timer before emit to avoid race
                pending_batch = {
                    "node_updates": [],
                    "edge_updates": [],
                    "node_removes": [],
                    "edge_removes": [],
                }
                batch_timer[0] = None
            # Emit once per window
            socketio.emit("graph_batch", payload, namespace='/')
        except Exception as e:
            logger.error(f"Error flushing graph batch: {e}")

    def _schedule_batch_flush() -> None:
        if BATCH_MS <= 0:
            return
        if batch_timer[0] is not None:
            return
        try:
            t = threading.Timer(BATCH_MS / 1000.0, _flush_batch)
            batch_timer[0] = t
            t.daemon = True
            t.start()
        except Exception as e:
            logger.error(f"Error scheduling graph batch flush: {e}")

    def _forward(event: str, payload: Any) -> None:
        try:
            payload_json = _jsonable(payload)
            # Incremental event → emit to all clients on default namespace
            now_ms = time.time() * 1000.0

            # Build a stable key for de-dup windows
            key = event
            if event in ("node_update", "node_remove"):
                node = payload_json.get("node") if isinstance(payload_json, dict) else payload_json
                node_id = node and (node.get('node_id') or node.get('id'))
                key = f"{event}:{node_id}"
            elif event in ("edge_update", "edge_remove"):
                edge = payload_json.get("edge") if isinstance(payload_json, dict) else payload_json
                src = edge and (edge.get('source_id') or edge.get('source'))
                tgt = edge and (edge.get('target_id') or edge.get('target'))
                ety = edge and edge.get('edge_type')
                key = f"{event}:{src}->{tgt}:{ety or ''}"

            # Suppress duplicate updates/removals within short windows
            if event.endswith("_update"):
                last = last_update_at.get(key, 0.0)
                if (now_ms - last) < UPDATE_SUPPRESS_MS:
                    logger.debug(f"Suppressing duplicate {event} within {UPDATE_SUPPRESS_MS}ms for {key}")
                    return
                last_update_at[key] = now_ms
            elif event.endswith("_remove"):
                last = last_remove_at.get(key, 0.0)
                if (now_ms - last) < REMOVE_SUPPRESS_MS:
                    logger.debug(f"Suppressing duplicate {event} within {REMOVE_SUPPRESS_MS}ms for {key}")
                    return
                last_remove_at[key] = now_ms

            # Optional batching: if enabled, collect and emit as one 'graph_batch' later
            if BATCH_MS > 0 and event in ("node_update", "edge_update", "node_remove", "edge_remove"):
                try:
                    with batch_lock:
                        if event == "node_update":
                            pending_batch["node_updates"].append(payload_json)
                        elif event == "edge_update":
                            pending_batch["edge_updates"].append(payload_json)
                        elif event == "node_remove":
                            pending_batch["node_removes"].append(payload_json)
                        elif event == "edge_remove":
                            pending_batch["edge_removes"].append(payload_json)
                    _schedule_batch_flush()
                    # Skip individual emit when batching to reduce chatter
                    is_create = False  # creation signal handled by clients upon batch apply
                    # still update seen caches below appropriately
                except Exception as e:
                    logger.error(f"Error batching {event}: {e}")
                # fall through to seen-cache maintenance without emitting
            else:
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
            elif event == "node_remove":
                # Clear seen caches so future re-discovery will count as create
                node_id = payload_json.get('node_id') if isinstance(payload_json, dict) else None
                if node_id and node_id in seen_node_ids:
                    seen_node_ids.discard(node_id)
                logger.info(f"Forwarded node_remove (node_id={node_id}) → clients")
            elif event == "edge_remove":
                edge = payload_json.get("edge") if isinstance(payload_json, dict) else None
                src = edge and edge.get('source_id')
                tgt = edge and edge.get('target_id')
                ety = edge and edge.get('edge_type')
                if src and tgt:
                    edge_key = f"{src}->{tgt}:{ety or ''}"
                    if edge_key in seen_edge_ids:
                        seen_edge_ids.discard(edge_key)
                logger.info(f"Forwarded edge_remove ({src}->{tgt}:{ety}) → clients")
            else:
                logger.debug(f"Forwarded event {event} → clients")

            if is_create and BATCH_MS <= 0:
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
