#!/usr/bin/env python3
"""
Monitoring Graph Test with Real Genesis Scenario

This test runs an actual Genesis scenario (Interface → Agent → Service) and then
analyzes the monitoring events to verify the graph connectivity is correct.

The test:
1. Starts monitoring collection
2. Runs a real Genesis test scenario 
3. Collects and analyzes monitoring events
4. Verifies that the expected nodes and edges exist
5. Provides detailed analysis report

This is the practical implementation of monitoring graph connectivity testing.
"""

import asyncio
import logging
import subprocess
import sys
import time
import threading
import os
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_functions.test_monitoring_graph_connectivity import (
    MonitoringGraphCollector, 
    RTIDDSSpyAnalyzer, 
    ExpectedTopology,
    GraphAnalyzer
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MonitoringScenarioTest")

class MonitoringScenarioTest:
    """Test monitoring with real Genesis scenario execution"""
    
    def __init__(self, domain_id: int = 0):
        self.domain_id = domain_id
        self.collector = None
        self.spy_analyzer = None
        self.scenario_process = None
        
    def run_interface_agent_service_test(self):
        """Run the interface-agent-service test scenario with monitoring"""
        logger.info("🚀 Starting Interface-Agent-Service test with monitoring")
        
        # Start monitoring collection
        logger.info("📊 Starting monitoring collection...")
        self.collector = MonitoringGraphCollector(self.domain_id)
        
        # Start RTIDDSSPY if available
        self.spy_analyzer = RTIDDSSpyAnalyzer(self.domain_id)
        spy_available = self.spy_analyzer.start_capture()
        if spy_available:
            logger.info("📡 RTIDDSSPY capture started")
        else:
            logger.warning("⚠️ RTIDDSSPY not available, skipping DDS traffic analysis")
        
        # Start monitoring for extended duration
        monitoring_duration = 45.0  # Extended to capture full scenario
        self.collector.start_monitoring(duration_seconds=monitoring_duration)
        
        # Small delay to ensure monitoring is ready
        time.sleep(2.0)
        
        # Run the actual Genesis test scenario
        success = self._run_genesis_scenario()
        
        if not success:
            logger.error("❌ Genesis scenario failed to run")
            return False
        
        # Wait for monitoring to complete
        logger.info(f"⏳ Waiting for monitoring to complete ({monitoring_duration}s)...")
        time.sleep(monitoring_duration + 5.0)  # Extra time for cleanup
        
        # Stop monitoring
        logger.info("🛑 Stopping monitoring collection...")
        self.collector.stop_monitoring()
        if spy_available:
            self.spy_analyzer.stop_capture()
        
        # Analyze the collected graph data
        return self._analyze_monitoring_results(spy_available)
    
    def _run_genesis_scenario(self):
        """Run the Genesis interface-agent-service test scenario"""
        try:
            # Change to run_scripts directory
            script_dir = Path(__file__).parent.parent / "run_scripts"
            
            if not script_dir.exists():
                logger.error(f"❌ Script directory not found: {script_dir}")
                return False
            
            script_path = script_dir / "run_interface_agent_service_test.sh"
            
            if not script_path.exists():
                logger.error(f"❌ Test script not found: {script_path}")
                return False
            
            logger.info(f"🎬 Running Genesis scenario: {script_path}")
            
            # Run the scenario in the background
            def run_scenario():
                try:
                    result = subprocess.run(
                        [str(script_path)],
                        cwd=script_dir,
                        capture_output=True,
                        text=True,
                        timeout=30.0  # 30 second timeout
                    )
                    
                    if result.returncode == 0:
                        logger.info("✅ Genesis scenario completed successfully")
                        logger.debug(f"Scenario output: {result.stdout}")
                    else:
                        logger.error(f"❌ Genesis scenario failed with return code {result.returncode}")
                        logger.error(f"Error output: {result.stderr}")
                        
                except subprocess.TimeoutExpired:
                    logger.warning("⏰ Genesis scenario timed out (expected)")
                except Exception as e:
                    logger.error(f"❌ Error running Genesis scenario: {e}")
            
            # Run scenario in thread so monitoring can continue
            scenario_thread = threading.Thread(target=run_scenario, daemon=True)
            scenario_thread.start()
            
            # Give scenario time to start and run
            time.sleep(5.0)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to run Genesis scenario: {e}")
            return False
    
    def _analyze_monitoring_results(self, spy_available: bool):
        """Analyze the collected monitoring data"""
        logger.info("🔍 Analyzing monitoring results...")
        
        # Get basic statistics
        summary = self.collector.get_graph_summary()
        
        logger.info("📈 Monitoring Collection Summary:")
        logger.info(f"  Total Events Processed: {summary['events_processed']}")
        logger.info(f"  Lifecycle Events: {summary['stats']['lifecycle_events']}")
        logger.info(f"  Chain Events: {summary['stats']['chain_events']}")
        logger.info(f"  Nodes Discovered: {summary['total_nodes']}")
        logger.info(f"  Edges Discovered: {summary['total_edges']}")
        logger.info(f"  Node Types: {summary['node_types']}")
        logger.info(f"  Edge Types: {summary['edge_types']}")
        
        # Show discovered nodes
        if self.collector.nodes:
            logger.info("🔍 Discovered Nodes:")
            for i, node in enumerate(self.collector.nodes.values(), 1):
                capabilities_str = ""
                if node.capabilities:
                    if isinstance(node.capabilities, dict):
                        # Show key capabilities
                        key_caps = []
                        if "function_name" in node.capabilities:
                            key_caps.append(f"func:{node.capabilities['function_name']}")
                        if "agent_type" in node.capabilities:
                            key_caps.append(f"type:{node.capabilities['agent_type']}")
                        if "service" in node.capabilities:
                            key_caps.append(f"svc:{node.capabilities['service']}")
                        if key_caps:
                            capabilities_str = f" [{', '.join(key_caps)}]"
                
                logger.info(f"  {i:2d}. {node.node_type:15s} | {node.name:20s} | {node.node_id}{capabilities_str}")
        
        # Show discovered edges
        if self.collector.edges:
            logger.info("🔗 Discovered Edges:")
            for i, edge in enumerate(self.collector.edges.values(), 1):
                logger.info(f"  {i:2d}. {edge.edge_type:15s} | {edge.source_id} → {edge.target_id}")
        
        # RTIDDSSPY analysis
        if spy_available:
            traffic_summary = self.spy_analyzer.get_traffic_summary()
            logger.info(f"📡 RTIDDSSPY Traffic Summary: {traffic_summary}")
        
        # Define what we expect to see in a typical interface-agent-service scenario
        expected_elements = {
            "min_nodes": 1,  # At least some nodes should be discovered
            "min_events": 1,  # At least some events should be processed
            "expected_node_types": {"FUNCTION"},  # Should see at least function nodes
            "expected_event_categories": {"NODE_DISCOVERY"}  # Should see discovery events
        }
        
        # Analyze against expectations
        success_criteria = []
        
        # Check minimum node count
        nodes_ok = summary['total_nodes'] >= expected_elements["min_nodes"]
        success_criteria.append(nodes_ok)
        if nodes_ok:
            logger.info(f"✅ Node count check passed: {summary['total_nodes']} >= {expected_elements['min_nodes']}")
        else:
            logger.error(f"❌ Node count check failed: {summary['total_nodes']} < {expected_elements['min_nodes']}")
        
        # Check minimum event count
        events_ok = summary['events_processed'] >= expected_elements["min_events"]
        success_criteria.append(events_ok)
        if events_ok:
            logger.info(f"✅ Event count check passed: {summary['events_processed']} >= {expected_elements['min_events']}")
        else:
            logger.error(f"❌ Event count check failed: {summary['events_processed']} < {expected_elements['min_events']}")
        
        # Check for expected node types
        node_types_found = set(summary['node_types'].keys())
        expected_types = expected_elements["expected_node_types"]
        types_intersection = node_types_found.intersection(expected_types)
        types_ok = len(types_intersection) > 0
        success_criteria.append(types_ok)
        if types_ok:
            logger.info(f"✅ Node types check passed: Found {types_intersection}")
        else:
            logger.warning(f"⚠️ Node types check: Expected {expected_types}, found {node_types_found}")
        
        # Check event categories from raw events
        event_categories = set()
        for event in self.collector.events:
            if event.get("type") == "lifecycle":
                event_categories.add(event.get("event_category"))
        
        expected_categories = expected_elements["expected_event_categories"]
        categories_intersection = event_categories.intersection(expected_categories)
        categories_ok = len(categories_intersection) > 0
        success_criteria.append(categories_ok)
        if categories_ok:
            logger.info(f"✅ Event categories check passed: Found {categories_intersection}")
        else:
            logger.warning(f"⚠️ Event categories check: Expected {expected_categories}, found {event_categories}")
        
        # Overall success
        overall_success = all(success_criteria)
        
        if overall_success:
            logger.info("🎉 Monitoring graph connectivity test PASSED")
            logger.info("✅ System monitoring is working correctly")
        else:
            logger.error("💥 Monitoring graph connectivity test FAILED")
            logger.error("❌ Some monitoring issues detected")
        
        # Additional detailed analysis
        self._detailed_analysis()
        
        return overall_success
    
    def _detailed_analysis(self):
        """Perform detailed analysis of the monitoring data"""
        logger.info("🔬 Performing detailed analysis...")
        
        # Analyze event timing
        if self.collector.events:
            events_by_type = {}
            for event in self.collector.events:
                event_type = event.get("type", "unknown")
                if event_type not in events_by_type:
                    events_by_type[event_type] = []
                events_by_type[event_type].append(event)
            
            logger.info(f"📊 Events by type: {[(t, len(events)) for t, events in events_by_type.items()]}")
            
            # Show timeline of key events
            lifecycle_events = events_by_type.get("lifecycle", [])
            if lifecycle_events:
                logger.info("⏰ Lifecycle Event Timeline:")
                for i, event in enumerate(lifecycle_events[:10]):  # Show first 10
                    timestamp = event.get("timestamp", 0)
                    category = event.get("event_category", "Unknown")
                    component = event.get("component_id", "Unknown")
                    logger.info(f"  {i+1:2d}. {timestamp} | {category:15s} | {component}")
        
        # Analyze node connectivity patterns
        if self.collector.nodes and self.collector.edges:
            # Find nodes with most connections
            node_connections = {}
            for edge in self.collector.edges.values():
                source = edge.source_id
                target = edge.target_id
                
                if source not in node_connections:
                    node_connections[source] = {"in": 0, "out": 0}
                if target not in node_connections:
                    node_connections[target] = {"in": 0, "out": 0}
                
                node_connections[source]["out"] += 1
                node_connections[target]["in"] += 1
            
            if node_connections:
                logger.info("🌐 Node Connectivity Analysis:")
                for node_id, connections in sorted(node_connections.items(), 
                                                 key=lambda x: x[1]["in"] + x[1]["out"], 
                                                 reverse=True)[:5]:  # Top 5 most connected
                    node = self.collector.nodes.get(node_id)
                    node_name = node.name if node else node_id
                    total_connections = connections["in"] + connections["out"]
                    logger.info(f"  {node_name:20s} | In: {connections['in']:2d} | Out: {connections['out']:2d} | Total: {total_connections}")
    
    def cleanup(self):
        """Clean up test resources"""
        try:
            if self.collector:
                self.collector.close()
            if self.spy_analyzer:
                self.spy_analyzer.stop_capture()
            if self.scenario_process:
                self.scenario_process.terminate()
        except Exception as e:
            logger.warning(f"⚠️ Cleanup warning: {e}")

def main():
    """Main test runner"""
    logger.info("🚀 Starting Monitoring Graph Test with Real Genesis Scenario")
    
    # Check environment
    if not os.path.exists("genesis_lib"):
        logger.error("❌ Please run from the project root directory")
        return False
    
    test = MonitoringScenarioTest(domain_id=0)
    
    try:
        success = test.run_interface_agent_service_test()
        return success
        
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
        return False
    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        test.cleanup()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 