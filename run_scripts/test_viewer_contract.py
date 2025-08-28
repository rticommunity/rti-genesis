#!/usr/bin/env python3
"""
Viewer Contract Test (Schema + Back-Compat Gate)

Builds a small in-memory graph using GenesisNetworkGraph, exports viewer JSON
via genesis_lib.viewer_export, validates against the viewer schema, and asserts
expected nodes/edges with no extras. This does not require DDS.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from genesis_lib.graph_state import GenesisNetworkGraph, NodeInfo, EdgeInfo  # type: ignore
from genesis_lib.viewer_export import export_from_cytoscape  # type: ignore


def load_schema() -> Dict[str, Any]:
    schema_path = os.path.join(REPO_ROOT, "docs", "planning", "schemas", "viewer_topology.schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_schema(obj: Dict[str, Any], schema: Dict[str, Any]) -> None:
    try:
        import jsonschema  # type: ignore
    except Exception as e:  # pragma: no cover
        print(f"ERROR: jsonschema not available: {e}")
        sys.exit(2)
    jsonschema.validate(instance=obj, schema=schema)


def build_sample_graph() -> Dict[str, Any]:
    g = GenesisNetworkGraph()
    # One service, two functions, two edges
    service_id = "svc-1"
    g.add_or_update_node(NodeInfo(node_id=service_id, node_type="SERVICE", node_name="CalculatorService", node_state="READY", metadata={}))
    fn_add_id = "fn-add"
    fn_sub_id = "fn-sub"
    g.add_or_update_node(NodeInfo(node_id=fn_add_id, node_type="FUNCTION", node_name="add", node_state="READY", metadata={}))
    g.add_or_update_node(NodeInfo(node_id=fn_sub_id, node_type="FUNCTION", node_name="subtract", node_state="READY", metadata={}))
    g.add_or_update_edge(EdgeInfo(source_id=service_id, target_id=fn_add_id, edge_type="SERVICE_TO_FUNCTION", metadata={}))
    g.add_or_update_edge(EdgeInfo(source_id=service_id, target_id=fn_sub_id, edge_type="SERVICE_TO_FUNCTION", metadata={}))
    return g.to_cytoscape()


def main() -> int:
    schema = load_schema()
    cyto = build_sample_graph()
    viewer = export_from_cytoscape(cyto, version="v1")

    # Schema validation
    validate_schema(viewer, schema)

    # Back-compat gate: assert structure we expect
    nodes = viewer.get("nodes", [])
    edges = viewer.get("edges", [])
    if len(nodes) != 3:
        print(f"ERROR: Expected 3 nodes (1 service + 2 functions); saw {len(nodes)}")
        return 1
    if len(edges) != 2:
        print(f"ERROR: Expected 2 edges (service→function); saw {len(edges)}")
        return 1
    # Ensure required fields present per node/edge
    for n in nodes:
        for k in ("id", "label", "type"):
            if k not in n:
                print(f"ERROR: Node missing required field '{k}': {n}")
                return 1
    for e in edges:
        for k in ("source", "target"):
            if k not in e:
                print(f"ERROR: Edge missing required field '{k}': {e}")
                return 1

    print("✅ Viewer contract test passed (schema + back-compat gate)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

