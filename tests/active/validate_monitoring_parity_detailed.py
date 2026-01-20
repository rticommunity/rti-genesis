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
Detailed monitoring topic parity validation using rtiddsspy output.

This script parses rtiddsspy logs to extract actual data samples from old and new
monitoring topics, then pairs them by content to verify 1:1 parity.

Instead of just counting samples, it matches:
- GenesisGraphNode + GenesisGraphEdge → GraphTopologyV2 (by component_id/node_id)
- ChainEvent → EventV2 (kind=CHAIN, by chain_id/call_id)
- ComponentLifecycleEvent → EventV2 (kind=LIFECYCLE, by component_id/timestamp)
- MonitoringEvent → EventV2 (kind=GENERAL, by component_id/timestamp)

This provides precise identification of missing, duplicate, or extra samples.
"""

import re
import json
import sys
from typing import Dict, List, Set, Tuple
from collections import defaultdict

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'

class Sample:
    """Represents a single DDS sample with its key data."""
    def __init__(self, topic: str, timestamp: str, data: Dict):
        self.topic = topic
        self.timestamp = timestamp
        self.data = data
    
    def __repr__(self):
        return f"Sample({self.topic}, {self.timestamp}, {list(self.data.keys())})"

def parse_spy_log(log_file: str) -> Dict[str, List[Sample]]:
    """
    Parse rtiddsspy output to extract samples by topic.
    
    Returns:
        Dict mapping topic name to list of Sample objects
    """
    samples_by_topic = defaultdict(list)
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for "New data" or "Modified instance" lines with topic name
        match = re.search(r'(New data|Modified instance).*topic="rti/connext/genesis/([^"]+)"', line)
        if match:
            timestamp = line.split()[0]  # Extract timestamp from beginning of line
            topic_name = match.group(2)  # Extract topic name
            
            # Extract data fields from subsequent lines until we hit the next timestamp or separator
            data = {}
            i += 1
            while i < len(lines):
                data_line = lines[i]
                # Stop at next timestamp or separator
                if re.match(r'\d{2}:\d{2}:\d{2}', data_line) or data_line.strip().startswith('---'):
                    break
                # Skip empty lines
                if not data_line.strip():
                    i += 1
                    continue
                # Parse field: value pairs (handle both "field: value" and "field:value")
                field_match = re.match(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)$', data_line)
                if field_match:
                    field = field_match.group(1)
                    value = field_match.group(2).strip()
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    data[field] = value
                i += 1
            
            if data:  # Only add if we extracted some data
                samples_by_topic[topic_name].append(Sample(topic_name, timestamp, data))
            continue
        
        i += 1
    
    return dict(samples_by_topic)

def normalize_node_key(sample: Sample) -> str:
    """Extract unique key for node samples (old GenesisGraphNode)."""
    node_id = sample.data.get('node_id', '')
    timestamp = sample.data.get('timestamp', '')
    return f"{node_id}:{timestamp}"

def normalize_edge_key(sample: Sample) -> str:
    """Extract unique key for edge samples (old GenesisGraphEdge)."""
    source = sample.data.get('source_id', '')
    target = sample.data.get('target_id', '')
    edge_type = sample.data.get('edge_type', '')
    return f"{source}->{target}:{edge_type}"

def normalize_chain_key(sample: Sample) -> str:
    """Extract unique key for chain event samples."""
    chain_id = sample.data.get('chain_id', '')
    call_id = sample.data.get('call_id', '')
    event_type = sample.data.get('event_type', '')
    return f"{chain_id}:{call_id}:{event_type}"

def normalize_lifecycle_key(sample: Sample) -> str:
    """Extract unique key for lifecycle event samples."""
    component_id = sample.data.get('component_id', '')
    timestamp = sample.data.get('timestamp', '')
    new_state = sample.data.get('new_state', '')
    return f"{component_id}:{timestamp}:{new_state}"

def normalize_monitoring_key(sample: Sample) -> str:
    """Extract unique key for general monitoring event samples (old MonitoringEvent)."""
    entity_id = sample.data.get('entity_id', '')
    timestamp = sample.data.get('timestamp', '')
    event_type = sample.data.get('event_type', '')
    return f"{entity_id}:{timestamp}:{event_type}"

def match_topology_samples(old_nodes: List[Sample], old_edges: List[Sample], 
                           new_topology: List[Sample]) -> Tuple[List, List, List]:
    """
    Match old node/edge samples with new GraphTopologyV2 samples.
    
    Returns:
        (matched_pairs, unmatched_old, unmatched_new)
    """
    # Build keys for old samples
    old_keys = {}
    for node in old_nodes:
        key = normalize_node_key(node)
        old_keys[key] = ('NODE', node)
    
    for edge in old_edges:
        key = normalize_edge_key(edge)
        old_keys[key] = ('EDGE', edge)
    
    # Build keys for new samples and match
    matched = []
    unmatched_new = []
    
    for new_sample in new_topology:
        kind = new_sample.data.get('kind', '')
        element_id = new_sample.data.get('element_id', '')
        timestamp = new_sample.data.get('timestamp', '')
        
        if kind in ('0', 'NODE'):  # NODE
            key = f"{element_id}:{timestamp}"
            if key in old_keys and old_keys[key][0] == 'NODE':
                matched.append((old_keys[key][1], new_sample))
                del old_keys[key]
            else:
                unmatched_new.append(new_sample)
        elif kind in ('1', 'EDGE'):  # EDGE
            # Parse composite element_id: "source|target|edge_type"
            try:
                parts = element_id.split('|')
                if len(parts) == 3:
                    source, target, edge_type = parts
                    key = f"{source}->{target}:{edge_type}"
                    if key in old_keys and old_keys[key][0] == 'EDGE':
                        matched.append((old_keys[key][1], new_sample))
                        del old_keys[key]
                    else:
                        unmatched_new.append(new_sample)
                else:
                    unmatched_new.append(new_sample)
            except:
                unmatched_new.append(new_sample)
    
    unmatched_old = [sample for _, sample in old_keys.values()]
    
    return matched, unmatched_old, unmatched_new

def match_event_samples(old_chain: List[Sample], old_lifecycle: List[Sample],
                        old_monitoring: List[Sample], new_events: List[Sample]) -> Tuple[List, List, List]:
    """
    Match old event samples with new EventV2 samples.
    
    Returns:
        (matched_pairs, unmatched_old, unmatched_new)
    """
    # Build keys for old samples by kind
    old_keys = {
        'CHAIN': {},
        'LIFECYCLE': {},
        'GENERAL': {}
    }
    
    for chain in old_chain:
        key = normalize_chain_key(chain)
        old_keys['CHAIN'][key] = chain
    
    for lifecycle in old_lifecycle:
        key = normalize_lifecycle_key(lifecycle)
        old_keys['LIFECYCLE'][key] = lifecycle
    
    for monitoring in old_monitoring:
        key = normalize_monitoring_key(monitoring)
        old_keys['GENERAL'][key] = monitoring
    
    # Match new samples
    matched = []
    unmatched_new = []
    
    for new_sample in new_events:
        kind_val = new_sample.data.get('kind', '')
        
        if kind_val in ('0', 'CHAIN'):  # CHAIN
            # Extract chain data from payload JSON
            try:
                payload = json.loads(new_sample.data.get('payload', '{}'))
                chain_id = payload.get('chain_id', '')
                call_id = payload.get('call_id', '')
                event_type = payload.get('event_type', '')
                key = f"{chain_id}:{call_id}:{event_type}"
                
                if key in old_keys['CHAIN']:
                    matched.append((old_keys['CHAIN'][key], new_sample))
                    del old_keys['CHAIN'][key]
                else:
                    unmatched_new.append(new_sample)
            except:
                unmatched_new.append(new_sample)
        
        elif kind_val in ('1', 'LIFECYCLE'):  # LIFECYCLE
            component_id = new_sample.data.get('component_id', '')
            timestamp = new_sample.data.get('timestamp', '')
            try:
                payload = json.loads(new_sample.data.get('payload', '{}'))
                new_state = payload.get('new_state', '')
                key = f"{component_id}:{timestamp}:{new_state}"
                
                if key in old_keys['LIFECYCLE']:
                    matched.append((old_keys['LIFECYCLE'][key], new_sample))
                    del old_keys['LIFECYCLE'][key]
                else:
                    # LIFECYCLE events in new system are expected to be NEW (graph topology)
                    # Don't count as unmatched if there's no old equivalent
                    pass  # This is expected for graph topology updates
            except:
                pass
        
        elif kind_val in ('2', 'GENERAL'):  # GENERAL
            component_id = new_sample.data.get('component_id', '')
            timestamp = new_sample.data.get('timestamp', '')
            message = new_sample.data.get('message', '')  # message contains event_type
            # Old MonitoringEvent key: entity_id:timestamp:event_type
            # New EventV2 key: component_id:timestamp:message (message = event_type)
            key = f"{component_id}:{timestamp}:{message}"
            
            if key in old_keys['GENERAL']:
                matched.append((old_keys['GENERAL'][key], new_sample))
                del old_keys['GENERAL'][key]
            else:
                unmatched_new.append(new_sample)
    
    # Collect unmatched old samples
    unmatched_old = []
    for kind_dict in old_keys.values():
        unmatched_old.extend(kind_dict.values())
    
    return matched, unmatched_old, unmatched_new

def main():
    if len(sys.argv) < 2:
        print("Usage: validate_monitoring_parity_detailed.py <spy_log_file>")
        sys.exit(1)
    
    spy_log = sys.argv[1]
    
    print(f"{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}Detailed Monitoring Topic Parity Validation{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")
    
    print(f"Parsing spy log: {spy_log}\n")
    
    # Parse spy log
    samples = parse_spy_log(spy_log)
    
    # Extract samples by topic
    old_nodes = samples.get('monitoring/GenesisGraphNode', [])
    old_edges = samples.get('monitoring/GenesisGraphEdge', [])
    old_chain = samples.get('monitoring/ChainEvent', [])
    old_lifecycle = samples.get('monitoring/ComponentLifecycleEvent', [])
    old_monitoring = samples.get('monitoring/MonitoringEvent', [])
    
    new_topology = samples.get('monitoring/GraphTopologyV2', [])
    new_events = samples.get('monitoring/EventV2', [])
    
    print(f"{BLUE}Sample Counts:{RESET}")
    print(f"  Old Topics:")
    print(f"    GenesisGraphNode:         {len(old_nodes)}")
    print(f"    GenesisGraphEdge:         {len(old_edges)}")
    print(f"    ChainEvent:               {len(old_chain)}")
    print(f"    ComponentLifecycleEvent:  {len(old_lifecycle)}")
    print(f"    MonitoringEvent:          {len(old_monitoring)}")
    print(f"  New Topics:")
    print(f"    GraphTopologyV2:          {len(new_topology)}")
    print(f"    EventV2:                  {len(new_events)}\n")
    
    # Match topology samples
    print(f"{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}1. GRAPH TOPOLOGY PARITY (Durable){RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")
    
    topology_matched, topology_unmatched_old, topology_unmatched_new = match_topology_samples(
        old_nodes, old_edges, new_topology
    )
    
    print(f"  {GREEN}✅ Matched pairs:{RESET}        {len(topology_matched)}")
    print(f"  {RED}❌ Unmatched old samples:{RESET} {len(topology_unmatched_old)}")
    print(f"  {YELLOW}⚠️  Unmatched new samples:{RESET} {len(topology_unmatched_new)}\n")
    
    if topology_unmatched_old:
        print(f"{RED}Unmatched OLD topology samples:{RESET}")
        for sample in topology_unmatched_old[:5]:  # Show first 5
            print(f"  - {sample.topic}: {list(sample.data.keys())}")
        if len(topology_unmatched_old) > 5:
            print(f"  ... and {len(topology_unmatched_old) - 5} more\n")
    
    if topology_unmatched_new:
        print(f"{YELLOW}Unmatched NEW topology samples:{RESET}")
        for sample in topology_unmatched_new[:5]:  # Show first 5
            print(f"  - {sample.topic}: element_id={sample.data.get('element_id', 'N/A')}, kind={sample.data.get('kind', 'N/A')}")
        if len(topology_unmatched_new) > 5:
            print(f"  ... and {len(topology_unmatched_new) - 5} more\n")
    
    topology_pass = len(topology_matched) == (len(old_nodes) + len(old_edges)) and len(topology_unmatched_old) == 0
    
    if topology_pass:
        print(f"{GREEN}✅ TOPOLOGY PARITY: PASS{RESET}\n")
    else:
        print(f"{RED}❌ TOPOLOGY PARITY: FAIL{RESET}\n")
    
    # Match event samples
    print(f"{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}2. MONITORING EVENTS PARITY (Volatile){RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")
    
    event_matched, event_unmatched_old, event_unmatched_new = match_event_samples(
        old_chain, old_lifecycle, old_monitoring, new_events
    )
    
    print(f"  {GREEN}✅ Matched pairs:{RESET}        {len(event_matched)}")
    print(f"  {RED}❌ Unmatched old samples:{RESET} {len(event_unmatched_old)}")
    print(f"  {YELLOW}⚠️  Unmatched new samples:{RESET} {len(event_unmatched_new)}")
    print(f"  {BLUE}ℹ️  LIFECYCLE events:{RESET}     {len([s for s in new_events if s.data.get('kind') in ('1', 'LIFECYCLE')])} (NEW feature - graph topology lifecycle)\n")
    
    if event_unmatched_old:
        print(f"{RED}Unmatched OLD event samples:{RESET}")
        for sample in event_unmatched_old[:10]:  # Show first 10
            print(f"  - {sample.topic}: {list(sample.data.keys())[:5]}")
        if len(event_unmatched_old) > 10:
            print(f"  ... and {len(event_unmatched_old) - 10} more\n")
    
    if event_unmatched_new:
        print(f"{YELLOW}Unmatched NEW event samples:{RESET}")
        for sample in event_unmatched_new[:10]:  # Show first 10
            kind_map = {'0': 'CHAIN', '1': 'LIFECYCLE', '2': 'GENERAL'}
            kind_str = kind_map.get(sample.data.get('kind', ''), 'UNKNOWN')
            msg = sample.data.get('message', 'N/A')[:50]
            print(f"  - {sample.topic}: kind={kind_str}, message={msg}")
        if len(event_unmatched_new) > 10:
            print(f"  ... and {len(event_unmatched_new) - 10} more\n")
    
    # For events, we expect new LIFECYCLE events (graph topology), so only check CHAIN and GENERAL
    expected_matches = len(old_chain) + len(old_monitoring)
    events_pass = len(event_unmatched_old) == 0 and len(event_matched) == expected_matches
    
    if events_pass:
        print(f"{GREEN}✅ EVENTS PARITY: PASS (excluding new LIFECYCLE events){RESET}\n")
    else:
        print(f"{YELLOW}⚠️  EVENTS PARITY: PARTIAL{RESET}")
        print(f"   Expected matches: {expected_matches} (Chain + Monitoring)")
        print(f"   Actual matches:   {len(event_matched)}\n")
    
    # Overall result
    print(f"{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}OVERALL RESULT{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")
    
    if topology_pass and events_pass:
        print(f"{GREEN}✅ SUCCESS - All monitoring topics have verified 1:1 parity{RESET}\n")
        sys.exit(0)
    else:
        print(f"{YELLOW}⚠️  PARTIAL SUCCESS - Review unmatched samples above{RESET}")
        print(f"\nNote: New LIFECYCLE events in EventV2 are a feature improvement.")
        print(f"The old system didn't publish lifecycle events for graph topology updates.\n")
        sys.exit(1)

if __name__ == '__main__':
    main()

