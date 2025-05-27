#!/usr/bin/env python3
"""
Working Monitoring Events Test

This test captures monitoring events from Genesis components without using curses.
It runs a Genesis scenario and verifies that monitoring events are properly generated.
"""

import asyncio
import logging
import subprocess
import sys
import time
import threading
import os
import json
from pathlib import Path
from typing import List, Dict, Any

import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MonitoringEventsTest")

class MonitoringEventCollector:
    """Collects monitoring events from DDS topics without curses interface"""
    
    def __init__(self, domain_id: int = 0):
        self.domain_id = domain_id
        self.lifecycle_events: List[Dict[str, Any]] = []
        self.chain_events: List[Dict[str, Any]] = []
        self.monitoring_active = False
        
        # Set up DDS
        self._setup_dds()
    
    def _setup_dds(self):
        """Set up DDS monitoring"""
        try:
            print(f"🔧 Setting up DDS monitoring on domain {self.domain_id}")
            
            # Create DDS entities
            self.participant = dds.DomainParticipant(self.domain_id)
            self.subscriber = dds.Subscriber(self.participant)
            
            # Get type provider
            provider = dds.QosProvider(get_datamodel_path())
            
            # Set up ComponentLifecycleEvent
            self.lifecycle_type = provider.type("genesis_lib", "ComponentLifecycleEvent")
            self.lifecycle_topic = dds.DynamicData.Topic(
                self.participant, "ComponentLifecycleEvent", self.lifecycle_type
            )
            
            # Set up ChainEvent  
            self.chain_type = provider.type("genesis_lib", "ChainEvent")
            self.chain_topic = dds.DynamicData.Topic(
                self.participant, "ChainEvent", self.chain_type
            )
            
            # Configure reader QoS
            reader_qos = dds.QosProvider.default.datareader_qos
            reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
            reader_qos.history.depth = 1000
            
            # Create readers
            self.lifecycle_reader = dds.DynamicData.DataReader(
                subscriber=self.subscriber,
                topic=self.lifecycle_topic,
                qos=reader_qos
            )
            
            self.chain_reader = dds.DynamicData.DataReader(
                subscriber=self.subscriber,
                topic=self.chain_topic,
                qos=reader_qos
            )
            
            print("✅ DDS monitoring setup complete")
            
        except Exception as e:
            print(f"❌ Failed to setup DDS monitoring: {e}")
            raise
    
    def start_monitoring(self, duration_seconds: float = 30.0):
        """Start monitoring for the specified duration"""
        print(f"🚀 Starting monitoring for {duration_seconds} seconds")
        self.monitoring_active = True
        
        def monitor_thread():
            start_time = time.time()
            while self.monitoring_active and (time.time() - start_time) < duration_seconds:
                try:
                    # Check for lifecycle events
                    lifecycle_samples = self.lifecycle_reader.take()
                    for data, info in lifecycle_samples:
                        if data is not None and info.state.instance_state == dds.InstanceState.ALIVE:
                            self._process_lifecycle_event(data)
                    
                    # Check for chain events
                    chain_samples = self.chain_reader.take()
                    for data, info in chain_samples:
                        if data is not None and info.state.instance_state == dds.InstanceState.ALIVE:
                            self._process_chain_event(data)
                    
                    time.sleep(0.1)  # Small sleep to prevent busy waiting
                    
                except Exception as e:
                    print(f"❌ Error during monitoring: {e}")
            
            print("⏹️ Monitoring thread completed")
        
        # Start monitoring in background thread
        self.monitor_thread = threading.Thread(target=monitor_thread, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring"""
        print("🛑 Stopping monitoring")
        self.monitoring_active = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=5)
    
    def _process_lifecycle_event(self, data):
        """Process ComponentLifecycleEvent"""
        try:
            # Map enum values to strings
            component_types = ["INTERFACE", "PRIMARY_AGENT", "SPECIALIZED_AGENT", "FUNCTION"]
            states = ["JOINING", "DISCOVERING", "READY", "BUSY", "DEGRADED", "OFFLINE"]
            event_categories = ["NODE_DISCOVERY", "EDGE_DISCOVERY", "STATE_CHANGE", "AGENT_INIT", "AGENT_READY", "AGENT_SHUTDOWN", "DDS_ENDPOINT"]
            
            event_data = {
                "type": "lifecycle",
                "component_id": data["component_id"],
                "component_type": component_types[int(data["component_type"])],
                "previous_state": states[int(data["previous_state"])],
                "new_state": states[int(data["new_state"])],
                "event_category": event_categories[int(data["event_category"])],
                "timestamp": int(data["timestamp"]),
                "reason": data["reason"],
                "capabilities": data["capabilities"]
            }
            
            self.lifecycle_events.append(event_data)
            print(f"📋 Lifecycle: {event_data['event_category']} - {event_data['component_type']} - {event_data['component_id']}")
            
        except Exception as e:
            print(f"❌ Error processing lifecycle event: {e}")
    
    def _process_chain_event(self, data):
        """Process ChainEvent"""
        try:
            event_data = {
                "type": "chain",
                "event_type": data["event_type"],
                "chain_id": data["chain_id"],
                "source_id": data["source_id"],
                "target_id": data["target_id"],
                "function_id": data["function_id"],
                "timestamp": int(data["timestamp"]),
                "status": int(data["status"])
            }
            
            self.chain_events.append(event_data)
            print(f"⛓️ Chain: {event_data['event_type']} - {event_data['source_id']} → {event_data['target_id']}")
            
        except Exception as e:
            print(f"❌ Error processing chain event: {e}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of collected events"""
        return {
            "lifecycle_events": len(self.lifecycle_events),
            "chain_events": len(self.chain_events),
            "total_events": len(self.lifecycle_events) + len(self.chain_events),
            "lifecycle_breakdown": self._analyze_lifecycle_events(),
            "chain_breakdown": self._analyze_chain_events()
        }
    
    def _analyze_lifecycle_events(self) -> Dict[str, int]:
        """Analyze lifecycle events by category"""
        breakdown = {}
        for event in self.lifecycle_events:
            category = event.get('event_category', 'Unknown')
            breakdown[category] = breakdown.get(category, 0) + 1
        return breakdown
    
    def _analyze_chain_events(self) -> Dict[str, int]:
        """Analyze chain events by type"""
        breakdown = {}
        for event in self.chain_events:
            event_type = event.get('event_type', 'Unknown')
            breakdown[event_type] = breakdown.get(event_type, 0) + 1
        return breakdown
    
    def close(self):
        """Clean up resources"""
        try:
            self.stop_monitoring()
            if hasattr(self, 'lifecycle_reader'):
                self.lifecycle_reader.close()
            if hasattr(self, 'chain_reader'):
                self.chain_reader.close()
            if hasattr(self, 'subscriber'):
                self.subscriber.close()
            if hasattr(self, 'participant'):
                self.participant.close()
        except Exception as e:
            print(f"⚠️ Warning during cleanup: {e}")

def run_genesis_scenario():
    """Run the Genesis interface-agent-service test scenario"""
    try:
        script_dir = Path(__file__).parent.parent / "run_scripts"
        script_path = script_dir / "run_interface_agent_service_test.sh"
        
        if not script_path.exists():
            print(f"❌ Test scenario script not found: {script_path}")
            return False
        
        print("🎬 Starting Genesis scenario...")
        result = subprocess.run(
            [str(script_path)],
            cwd=script_dir,
            timeout=30.0,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Genesis scenario completed successfully")
            print("📄 Scenario output:")
            for line in result.stdout.split('\n')[-10:]:  # Show last 10 lines
                if line.strip():
                    print(f"   {line}")
            return True
        else:
            print(f"❌ Genesis scenario failed with return code {result.returncode}")
            print(f"Error output: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Genesis scenario timed out")
        return False
    except Exception as e:
        print(f"❌ Error running Genesis scenario: {e}")
        return False

def main():
    """Main test runner"""
    print("🚀 Starting Monitoring Events Test")
    print("=" * 60)
    
    # Check environment
    if not os.path.exists("genesis_lib"):
        print("❌ Please run from the project root directory")
        return False
    
    collector = MonitoringEventCollector(domain_id=0)
    
    try:
        # Start monitoring
        collector.start_monitoring(duration_seconds=35.0)
        
        # Wait a moment for monitoring to initialize
        time.sleep(2)
        
        # Run Genesis scenario
        scenario_success = run_genesis_scenario()
        
        # Wait for monitoring to complete
        print("⏳ Waiting for monitoring to complete...")
        time.sleep(8)
        
        # Stop monitoring and analyze results
        collector.stop_monitoring()
        summary = collector.get_summary()
        
        print("\n" + "=" * 60)
        print("📊 MONITORING RESULTS")
        print("=" * 60)
        print(f"Total Events Captured: {summary['total_events']}")
        print(f"  - Lifecycle Events: {summary['lifecycle_events']}")
        print(f"  - Chain Events: {summary['chain_events']}")
        
        if summary['lifecycle_breakdown']:
            print("\n📋 Lifecycle Event Breakdown:")
            for category, count in summary['lifecycle_breakdown'].items():
                print(f"  {category}: {count}")
        
        if summary['chain_breakdown']:
            print("\n⛓️ Chain Event Breakdown:")
            for event_type, count in summary['chain_breakdown'].items():
                print(f"  {event_type}: {count}")
        
        # Determine success
        success_criteria = [
            scenario_success,  # Genesis scenario must succeed
            summary['total_events'] > 0,  # Must capture some events
        ]
        
        overall_success = all(success_criteria)
        
        print("\n" + "=" * 60)
        if overall_success:
            print("✅ MONITORING TEST PASSED")
            print("✅ Genesis components are publishing monitoring events correctly")
        else:
            print("❌ MONITORING TEST FAILED")
            if not scenario_success:
                print("❌ Genesis scenario failed")
            if summary['total_events'] == 0:
                print("❌ No monitoring events captured")
        
        print("=" * 60)
        return overall_success
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        collector.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 