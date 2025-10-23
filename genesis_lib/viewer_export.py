#!/usr/bin/env python3
# Copyright (c) 2025, RTI & Jason Upchurch

"""
Viewer Topology Export Adapter

Converts Genesis graph outputs (e.g., GraphService/GenesisNetworkGraph
cytoscape dict) into a stable JSON contract for the orbital viewer.

This keeps the library responsible for the data contract and enables
schema validation without having to load any JS.
"""
from __future__ import annotations

from typing import Any, Dict, List
import time


def export_from_cytoscape(cytoscape: Dict[str, Any], *, version: str = "v1") -> Dict[str, Any]:
    """Map a cytoscape-style dict (from GraphService/GenesisNetworkGraph) to viewer schema.

    Expected cytoscape shape:
    {"elements": {"nodes": [{"data": {"id", "label", "type", "state"}}],
                   "edges": [{"data": {"source", "target", "type"}}]}}

    Returns a dict matching docs/planning/schemas/viewer_topology.schema.json.
    """
    elems = (cytoscape or {}).get("elements", {})
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    for n in elems.get("nodes", []):
        d = n.get("data", {}) if isinstance(n, dict) else {}
        node_id = d.get("id")
        label = d.get("label") or d.get("name") or str(node_id)
        node_type = d.get("type") or d.get("node_type")
        state = d.get("state") or d.get("node_state")
        nodes.append({
            "id": str(node_id) if node_id is not None else "",
            "label": str(label) if label is not None else "",
            "type": str(node_type) if node_type is not None else "UNKNOWN",
            "status": str(state) if state is not None else "",
            "metadata": {},
        })

    for e in elems.get("edges", []):
        d = e.get("data", {}) if isinstance(e, dict) else {}
        src = d.get("source")
        tgt = d.get("target")
        etype = d.get("type") or d.get("edge_type") or ""
        edges.append({
            "source": str(src) if src is not None else "",
            "target": str(tgt) if tgt is not None else "",
            "label": str(etype) if etype is not None else "",
            "channel": str(etype) if etype is not None else "",
            "metadata": {},
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": version,
    }

