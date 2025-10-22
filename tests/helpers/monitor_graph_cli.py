#!/usr/bin/env python3
"""
Simple CLI tool to monitor the Genesis graph in real-time.
Shows nodes and edges as they're discovered via DDS.

Usage:
    python tests/helpers/monitor_graph_cli.py [--domain DOMAIN_ID] [--interval SECONDS]
"""
import sys
import os
import time
import argparse
from collections import defaultdict

# Ensure genesis_lib is importable
sys.path.insert(0, os.path.abspath("."))

from genesis_lib.graph_state import GraphService


def format_node(node_data):
    """Format node info for display"""
    node_id = node_data.get('node_id', 'unknown')[:16]
    node_type = node_data.get('type', 'unknown')
    node_name = node_data.get('label', 'unknown')
    node_state = node_data.get('state', 'unknown')
    return f"{node_name:20} | {node_type:15} | {node_state:12} | {node_id}..."


def format_edge(edge_data):
    """Format edge info for display"""
    source = edge_data.get('source_id', 'unknown')[:16]
    target = edge_data.get('target_id', 'unknown')[:16]
    edge_type = edge_data.get('edge_type', 'unknown')
    return f"{source}... -> {target}... : {edge_type}"


def main():
    parser = argparse.ArgumentParser(description="Monitor Genesis graph topology in real-time")
    parser.add_argument("-d", "--domain", type=int, default=0, help="DDS domain ID (default: 0)")
    parser.add_argument("-i", "--interval", type=float, default=2.0, help="Update interval in seconds (default: 2.0)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed events")
    args = parser.parse_args()

    print("=" * 80)
    print(f"Genesis Graph Monitor (Domain {args.domain})")
    print("=" * 80)
    print()

    # Track state for change detection
    node_count = 0
    edge_count = 0
    node_types = defaultdict(int)
    edge_types = defaultdict(int)
    last_nodes = set()
    last_edges = set()

    # Create and start graph service
    graph = GraphService(domain_id=args.domain)
    
    # Subscribe to events for verbose mode
    if args.verbose:
        def on_event(event_type, payload):
            if event_type == "node_update":
                node = payload.get('node')
                if node:
                    node_id = node.node_id
                    print(f"📍 NODE: {format_node({'node_id': node_id, 'type': node.type, 'label': node.label, 'state': node.state})}")
            elif event_type == "edge_update":
                edge = payload.get('edge')
                if edge:
                    print(f"🔗 EDGE: {format_edge({'source_id': edge.source_id, 'target_id': edge.target_id, 'edge_type': edge.edge_type})}")
            elif event_type == "node_remove":
                node_id = payload.get('node_id', 'unknown')[:16]
                print(f"❌ NODE REMOVED: {node_id}...")
            elif event_type == "edge_remove":
                edge = payload.get('edge', {})
                src = edge.get('source_id', 'unknown')[:16]
                tgt = edge.get('target_id', 'unknown')[:16]
                etype = edge.get('edge_type', 'unknown')
                print(f"❌ EDGE REMOVED: {src}... -> {tgt}... : {etype}")
        
        def on_activity(activity):
            """Called when chain events (request/reply) are received"""
            event_type = activity.get('event_type', 'UNKNOWN')
            source = activity.get('source_id', 'unknown')[:16]
            target = activity.get('target_id', 'unknown')[:16]
            chain_id = activity.get('chain_id', 'unknown')[:8]
            print(f"⚡ CHAIN EVENT: {event_type:30} | {source}... -> {target}... | chain:{chain_id}...")
        
        graph.subscribe(on_event)
        graph.subscribe_activity(on_activity)
    
    graph.start()

    try:
        print("⏳ Waiting for graph data...")
        print()
        
        while True:
            time.sleep(args.interval)
            
            # Get current graph state
            cyto_data = graph.to_cytoscape()
            elements = cyto_data.get('elements', {})
            nodes = elements.get('nodes', [])
            edges = elements.get('edges', [])
            
            # Compute stats
            current_node_count = len(nodes)
            current_edge_count = len(edges)
            current_node_types = defaultdict(int)
            current_edge_types = defaultdict(int)
            current_nodes = set()
            current_edges = set()
            
            for node in nodes:
                data = node.get('data', {})
                node_type = data.get('type', 'unknown')
                current_node_types[node_type] += 1
                current_nodes.add(data.get('id', ''))
            
            for edge in edges:
                data = edge.get('data', {})
                edge_type = data.get('type', 'unknown')
                current_edge_types[edge_type] += 1
                src = data.get('source', '')
                tgt = data.get('target', '')
                current_edges.add(f"{src}->{tgt}:{edge_type}")
            
            # Detect changes
            nodes_changed = (current_node_count != node_count) or (current_nodes != last_nodes)
            edges_changed = (current_edge_count != edge_count) or (current_edges != last_edges)
            
            if nodes_changed or edges_changed or args.verbose:
                os.system('clear' if os.name != 'nt' else 'cls')
                
                print("=" * 80)
                print(f"Genesis Graph Monitor (Domain {args.domain}) - {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print("=" * 80)
                print()
                
                # Summary
                print(f"📊 SUMMARY:")
                print(f"   Total Nodes: {current_node_count:3d}")
                print(f"   Total Edges: {current_edge_count:3d}")
                print()
                
                # Node breakdown
                if current_node_types:
                    print(f"📍 NODES BY TYPE:")
                    for ntype, count in sorted(current_node_types.items()):
                        print(f"   {ntype:20} : {count:3d}")
                    print()
                
                # Edge breakdown
                if current_edge_types:
                    print(f"🔗 EDGES BY TYPE:")
                    for etype, count in sorted(current_edge_types.items()):
                        print(f"   {etype:30} : {count:3d}")
                    print()
                
                # Recent nodes (last 10)
                if nodes and not args.verbose:
                    print(f"📍 RECENT NODES (showing last 10):")
                    print(f"   {'Name':<20} | {'Type':<15} | {'State':<12} | ID")
                    print(f"   {'-'*19} | {'-'*14} | {'-'*11} | {'-'*19}")
                    for node in nodes[-10:]:
                        data = node.get('data', {})
                        print(f"   {format_node(data)}")
                    print()
                
                # Recent edges (last 10)
                if edges and not args.verbose:
                    print(f"🔗 RECENT EDGES (showing last 10):")
                    for edge in edges[-10:]:
                        data = edge.get('data', {})
                        print(f"   {format_edge(data)}")
                    print()
                
                # Change indicators
                if nodes_changed:
                    new_nodes = current_nodes - last_nodes
                    removed_nodes = last_nodes - current_nodes
                    if new_nodes:
                        print(f"✨ {len(new_nodes)} new node(s) detected")
                    if removed_nodes:
                        print(f"❌ {len(removed_nodes)} node(s) removed")
                
                if edges_changed:
                    new_edges = current_edges - last_edges
                    removed_edges = last_edges - current_edges
                    if new_edges:
                        print(f"✨ {len(new_edges)} new edge(s) detected")
                    if removed_edges:
                        print(f"❌ {len(removed_edges)} edge(s) removed")
                
                print()
                print(f"{'⏱️  Refreshing every ' + str(args.interval) + 's (Ctrl+C to exit)':^80}")
            
            # Update tracking variables
            node_count = current_node_count
            edge_count = current_edge_count
            node_types = current_node_types
            edge_types = current_edge_types
            last_nodes = current_nodes
            last_edges = current_edges
            
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down monitor...")
    finally:
        graph.stop()
        print("✅ Monitor stopped.")


if __name__ == "__main__":
    main()


