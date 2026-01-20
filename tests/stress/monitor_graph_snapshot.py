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
Monitor DDS topology and write a snapshot

This utility monitors the Genesis network topology via DDS and captures
a point-in-time snapshot in Cytoscape JSON format. Useful for:
- Testing graph visualization offline
- Debugging topology issues
- Capturing network state for analysis
- Creating test fixtures
"""
import argparse
import json
import os
import sys
import time
from typing import Dict, Any

# Ensure local package import works when run from repo root
sys.path.append(os.path.abspath("."))

from genesis_lib.graph_state import GraphService  # type: ignore


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor DDS topology and write a snapshot")
    parser.add_argument("--domain", type=int, default=0, help="DDS domain id")
    parser.add_argument("--duration", type=float, default=8.0, help="Monitoring duration in seconds")
    parser.add_argument("--out", type=str, default="graph_snapshot.json", help="Path to write Cytoscape JSON snapshot")
    parser.add_argument("--activity-out", type=str, default="", help="Optional path to write captured ChainEvent activity as JSON list")
    # Formatting controls
    parser.add_argument("--pretty", dest="pretty", action="store_true", default=True, help="Write pretty-printed JSON (default)")
    parser.add_argument("--compact", dest="pretty", action="store_false", help="Write compact JSON (no whitespace)")
    args = parser.parse_args()

    graph = GraphService(domain_id=args.domain)

    counts: Dict[str, int] = {"nodes": 0, "edges": 0, "activities": 0}
    activities: list[Dict[str, Any]] = []

    def on_change(event: str, payload: Dict[str, Any]) -> None:
        if event == "node_update":
            counts["nodes"] += 1
        elif event == "edge_update":
            counts["edges"] += 1

    graph.subscribe(on_change)

    # Capture activity (ChainEvent) if requested
    def on_activity(evt: Dict[str, Any]) -> None:
        counts["activities"] += 1
        activities.append(evt)
    graph.subscribe_activity(on_activity)

    print(f"Monitoring topology for {args.duration} seconds...")
    graph.start()
    try:
        time.sleep(max(0.1, args.duration))
        snapshot = graph.to_cytoscape()
        out_dir = os.path.dirname(args.out)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        with open(args.out, "w") as f:
            if args.pretty:
                json.dump(snapshot, f, indent=2, sort_keys=True)
            else:
                json.dump(snapshot, f, separators=(",", ":"))
        print(f"✅ Snapshot written: {args.out}")
        if args.activity_out:
            try:
                with open(args.activity_out, "w") as af:
                    json.dump(activities, af, indent=2)
                print(f"✅ Activities written: {args.activity_out} (count={counts['activities']})")
            except Exception as e:
                print(f"❌ Failed to write activities: {e}")
        # Print quick summary
        num_nodes = len(snapshot.get("elements", {}).get("nodes", []))
        num_edges = len(snapshot.get("elements", {}).get("edges", []))
        print(f"Summary: nodes={num_nodes} edges={num_edges} (events: nodes={counts['nodes']} edges={counts['edges']} activities={counts['activities']})")
        return 0
    except Exception as e:
        print(f"❌ Monitor error: {e}")
        return 1
    finally:
        graph.stop()


if __name__ == "__main__":
    sys.exit(main())

