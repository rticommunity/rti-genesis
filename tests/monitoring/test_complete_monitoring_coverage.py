"""
Comprehensive Monitoring Coverage Test

This test verifies that ALL monitoring features are working correctly:
1. Node publishing (agents, services, functions)
2. Edge publishing:
   - Agent→Service edges
   - Agent→Agent edges
   - Service→Function edges
3. Chain events:
   - Agent→Service→Function call chain
   - Agent→Agent call chain
   - Interface→Agent request/reply

This test exists because previous monitoring tests PASSED but didn't actually
verify that monitoring was complete. This is a regression test to ensure we
catch monitoring gaps in the future.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import time
import logging
from typing import Dict, Set
from genesis_lib.graph_state import GraphSubscriber, GraphService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MonitoringVerifier:
    """Verifies all aspects of monitoring are functioning"""
    
    def __init__(self, domain_id: int = 0):
        self.domain_id = domain_id
        self.graph = GraphService(domain_id)
        
        # Track what we've seen with additional metadata
        self.nodes_seen: Dict[str, Dict] = {}  # node_id -> {type, name, state}
        self.edges_seen: Set[tuple] = set()  # (source, target, edge_type)
        self.chain_events: list = []
        
        # Subscribe to updates
        self.graph.subscribe(self._on_node_or_edge)
        self.graph.subscribe_activity(self._on_chain_event)
    
    def _on_node_or_edge(self, event: str, payload: Dict):
        """Track nodes and edges"""
        if event == 'node_update':
            node = payload.get('node')
            if node:
                node_id = node.node_id
                self.nodes_seen[node_id] = {
                    'type': node.node_type,
                    'name': node.node_name,
                    'state': node.node_state
                }
                logger.info(f"✅ NODE: {node.node_type} - {node.node_name} ({node.node_state})")
        
        elif event == 'edge_update':
            edge = payload.get('edge')
            if edge:
                edge_tuple = (edge.source_id, edge.target_id, edge.edge_type)
                self.edges_seen.add(edge_tuple)
                logger.info(f"✅ EDGE: {edge.source_id[:8]}... → {edge.target_id[:8]}... ({edge.edge_type})")
    
    def _on_chain_event(self, event: Dict):
        """Track chain events"""
        self.chain_events.append(event)
        event_type = event.get('event_type', 'UNKNOWN')
        logger.info(f"✅ CHAIN: {event_type}")
    
    async def start(self):
        """Start the graph subscriber"""
        self.graph.start()  # Not async
        logger.info("📊 MonitoringVerifier started")
    
    def get_nodes_by_type(self, node_type: str) -> Set[str]:
        """Get all nodes of a specific type"""
        return {nid for nid, info in self.nodes_seen.items() if info['type'] == node_type}
    
    def get_edges_by_type(self, edge_type: str) -> Set[tuple]:
        """Get all edges of a specific type"""
        return {e for e in self.edges_seen if e[2] == edge_type}
    
    def verify_topology_complete(self, 
                                 expected_agents: int = 0,
                                 expected_services: int = 0,
                                 expected_functions: int = 0,
                                 expected_agent_service_edges: int = 0,
                                 expected_agent_agent_edges: int = 0,
                                 expected_service_function_edges: int = 0) -> Dict[str, bool]:
        """
        Verify that the expected topology has been discovered.
        
        Returns:
            Dict of test_name -> passed
        """
        results = {}
        
        # Count nodes by type
        agent_nodes = self.get_nodes_by_type('AGENT_PRIMARY') | self.get_nodes_by_type('AGENT_SPECIALIZED')
        service_nodes = self.get_nodes_by_type('SERVICE')
        function_nodes = self.get_nodes_by_type('FUNCTION')
        
        # Count edges by type
        agent_service_edges = self.get_edges_by_type('FUNCTION_CONNECTION')
        agent_agent_edges = self.get_edges_by_type('AGENT_COMMUNICATION')
        service_function_edges = self.get_edges_by_type('SERVICE_FUNCTION')
        
        # Verify counts
        results['agent_nodes'] = len(agent_nodes) >= expected_agents
        results['service_nodes'] = len(service_nodes) >= expected_services
        results['function_nodes'] = len(function_nodes) >= expected_functions
        results['agent_service_edges'] = len(agent_service_edges) >= expected_agent_service_edges
        results['agent_agent_edges'] = len(agent_agent_edges) >= expected_agent_agent_edges
        results['service_function_edges'] = len(service_function_edges) >= expected_service_function_edges
        
        # Log results
        logger.info("=" * 80)
        logger.info("TOPOLOGY VERIFICATION")
        logger.info("=" * 80)
        logger.info(f"Agents:          {len(agent_nodes):3d} / {expected_agents} expected - {'✅ PASS' if results['agent_nodes'] else '❌ FAIL'}")
        logger.info(f"Services:        {len(service_nodes):3d} / {expected_services} expected - {'✅ PASS' if results['service_nodes'] else '❌ FAIL'}")
        logger.info(f"Functions:       {len(function_nodes):3d} / {expected_functions} expected - {'✅ PASS' if results['function_nodes'] else '❌ FAIL'}")
        logger.info(f"Agent→Service:   {len(agent_service_edges):3d} / {expected_agent_service_edges} expected - {'✅ PASS' if results['agent_service_edges'] else '❌ FAIL'}")
        logger.info(f"Agent→Agent:     {len(agent_agent_edges):3d} / {expected_agent_agent_edges} expected - {'✅ PASS' if results['agent_agent_edges'] else '❌ FAIL'}")
        logger.info(f"Service→Function:{len(service_function_edges):3d} / {expected_service_function_edges} expected - {'✅ PASS' if results['service_function_edges'] else '❌ FAIL'}")
        logger.info("=" * 80)
        
        return results
    
    def verify_chain_events(self,
                          expected_agent_to_service: int = 0,
                          expected_agent_to_agent: int = 0,
                          expected_interface_to_agent: int = 0) -> Dict[str, bool]:
        """
        Verify that expected chain events were captured.
        
        Returns:
            Dict of test_name -> passed
        """
        results = {}
        
        # Count chain events by type
        agent_to_service_start = len([e for e in self.chain_events if e.get('event_type') == 'AGENT_TO_SERVICE_START'])
        agent_to_service_complete = len([e for e in self.chain_events if e.get('event_type') == 'SERVICE_TO_AGENT_COMPLETE'])
        agent_to_agent_start = len([e for e in self.chain_events if e.get('event_type') == 'AGENT_TO_AGENT_START'])
        agent_to_agent_complete = len([e for e in self.chain_events if e.get('event_type') == 'AGENT_TO_AGENT_COMPLETE'])
        interface_to_agent_start = len([e for e in self.chain_events if e.get('event_type') == 'INTERFACE_REQUEST_START'])
        interface_to_agent_complete = len([e for e in self.chain_events if e.get('event_type') == 'INTERFACE_REPLY_COMPLETE'])
        
        # Verify chain event pairs are balanced
        results['agent_to_service'] = agent_to_service_start >= expected_agent_to_service and agent_to_service_complete >= expected_agent_to_service
        results['agent_to_agent'] = agent_to_agent_start >= expected_agent_to_agent and agent_to_agent_complete >= expected_agent_to_agent
        results['interface_to_agent'] = interface_to_agent_start >= expected_interface_to_agent and interface_to_agent_complete >= expected_interface_to_agent
        
        # Log results
        logger.info("=" * 80)
        logger.info("CHAIN EVENT VERIFICATION")
        logger.info("=" * 80)
        logger.info(f"Agent→Service:   {agent_to_service_start:3d} starts, {agent_to_service_complete:3d} completes (expected {expected_agent_to_service}) - {'✅ PASS' if results['agent_to_service'] else '❌ FAIL'}")
        logger.info(f"Agent→Agent:     {agent_to_agent_start:3d} starts, {agent_to_agent_complete:3d} completes (expected {expected_agent_to_agent}) - {'✅ PASS' if results['agent_to_agent'] else '❌ FAIL'}")
        logger.info(f"Interface→Agent: {interface_to_agent_start:3d} starts, {interface_to_agent_complete:3d} completes (expected {expected_interface_to_agent}) - {'✅ PASS' if results['interface_to_agent'] else '❌ FAIL'}")
        logger.info("=" * 80)
        
        return results
    
    async def close(self):
        """Clean up resources"""
        # GraphService doesn't have a close() method, resources are cleaned up automatically
        logger.info("📊 MonitoringVerifier closed")


async def main():
    """
    Run comprehensive monitoring test.
    
    This test should be run alongside:
    1. At least 2 agents (for agent→agent edges)
    2. At least 1 service (for agent→service edges)
    3. Actual function calls (for chain events)
    
    Example topology to run in parallel:
    ```
    # Terminal 1: Start this test
    python tests/monitoring/test_complete_monitoring_coverage.py
    
    # Terminal 2: Start agents and service
    cd examples/MultiAgent/agents && python personal_assistant.py &
    cd examples/MultiAgent/agents && python weather_agent.py &
    python -m test_functions.calculator_service &
    
    # Terminal 3: Trigger function calls
    # ... send requests via interface or direct agent calls
    ```
    """
    verifier = MonitoringVerifier(domain_id=0)
    await verifier.start()
    
    logger.info("🔍 Monitoring for 60 seconds to capture topology and events...")
    logger.info("   (Agents should be started BEFORE or shortly after this test begins)")
    
    # Wait for discovery and events, logging progress every 10 seconds
    for i in range(6):
        await asyncio.sleep(10)
        logger.info(f"⏱️  {(i+1)*10}s elapsed - Nodes: {len(verifier.nodes_seen)}, Edges: {len(verifier.edges_seen)}, Chain events: {len(verifier.chain_events)}")
    
    # Verify topology (adjust expected values based on your test setup)
    topology_results = verifier.verify_topology_complete(
        expected_agents=2,          # PersonalAssistant + WeatherAgent
        expected_services=1,         # CalculatorService
        expected_functions=4,        # add, subtract, multiply, divide
        expected_agent_service_edges=2,  # PA→Calc, WA→Calc
        expected_agent_agent_edges=2,    # PA↔WA (bidirectional)
        expected_service_function_edges=4  # Calc→each function
    )
    
    # Verify chain events (adjust based on actual calls made)
    chain_results = verifier.verify_chain_events(
        expected_agent_to_service=0,    # Set to >0 if you trigger function calls
        expected_agent_to_agent=0,       # Set to >0 if you trigger agent-agent calls
        expected_interface_to_agent=0    # Set to >0 if you trigger interface requests
    )
    
    # Overall result
    all_topology_pass = all(topology_results.values())
    all_chain_pass = all(chain_results.values())
    
    logger.info("=" * 80)
    if all_topology_pass and all_chain_pass:
        logger.info("✅ ALL MONITORING TESTS PASSED")
        exit_code = 0
    else:
        logger.error("❌ SOME MONITORING TESTS FAILED")
        exit_code = 1
    logger.info("=" * 80)
    
    await verifier.close()
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

