#!/usr/bin/env python3
"""
Simple Monitoring Test

This test uses the exact same pattern as the working Genesis Monitor to 
verify that monitoring events are being generated correctly.
"""

import asyncio
import logging
import subprocess
import sys
import time
import threading
import os
from pathlib import Path

import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SimpleMonitoringTest")

class ComponentLifecycleListener(dds.DynamicData.NoOpDataReaderListener):
    """Listener for ComponentLifecycleEvent topic - copied from genesis_monitor.py"""
    
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.logger = logging.getLogger("ComponentLifecycleListener")
        self.logger.setLevel(logging.DEBUG)
    
    def on_data_available(self, reader):
        """Handle received data."""
        try:
            samples = reader.take()
            logger.debug(f"Got {len(samples)} lifecycle samples")
            
            for data, info in samples:
                if data is None or info.state.instance_state != dds.InstanceState.ALIVE:
                    continue
                
                # Map component types and states
                component_types = ["INTERFACE", "PRIMARY_AGENT", "SPECIALIZED_AGENT", "FUNCTION"]
                states = ["JOINING", "DISCOVERING", "READY", "BUSY", "DEGRADED", "OFFLINE"]
                event_categories = ["NODE_DISCOVERY", "EDGE_DISCOVERY", "STATE_CHANGE", "AGENT_INIT", "AGENT_READY", "AGENT_SHUTDOWN", "DDS_ENDPOINT"]
                
                # Convert enum values to integers for indexing
                component_type_idx = int(data["component_type"])
                previous_state_idx = int(data["previous_state"])
                new_state_idx = int(data["new_state"])
                event_category_idx = int(data["event_category"])
                
                # Safely get event category
                event_category = event_categories[event_category_idx] if 0 <= event_category_idx < len(event_categories) else "UNKNOWN"
                
                # Build data dictionary with new format fields
                data_dict = {
                    "event_category": event_category,
                    "component_id": data["component_id"],
                    "component_type": component_types[component_type_idx],
                    "previous_state": states[previous_state_idx],
                    "new_state": states[new_state_idx],
                    "timestamp": data["timestamp"],
                    "source_id": str(data["source_id"]) if data["source_id"] else "",
                    "target_id": str(data["target_id"]) if data["target_id"] else "",
                    "connection_type": str(data["connection_type"]) if data["connection_type"] else "",
                    "chain_id": data["chain_id"],
                    "call_id": data["call_id"],
                    "capabilities": data["capabilities"],
                    "reason": data["reason"]
                }
                
                if self.callback:
                    self.callback(data_dict)
                    
        except Exception as e:
            logger.error(f"Error in ComponentLifecycleListener: {e}")
            import traceback
            traceback.print_exc()

class ChainEventListener(dds.DynamicData.NoOpDataReaderListener):
    """Listener for ChainEvent topic - copied from genesis_monitor.py"""
    
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.logger = logging.getLogger("ChainEventListener")
        self.logger.setLevel(logging.DEBUG)
    
    def on_data_available(self, reader):
        """Handle received data."""
        try:
            samples = reader.take()
            logger.debug(f"Got {len(samples)} chain samples")
            
            for data, info in samples:
                if data is None or info.state.instance_state != dds.InstanceState.ALIVE:
                    continue
                
                data_dict = {
                    "event_type": data["event_type"],
                    "chain_id": data["chain_id"],
                    "source_id": data["source_id"],
                    "target_id": data["target_id"],
                    "function_id": data["function_id"],
                    "timestamp": data["timestamp"],
                    "status": data["status"],
                    "call_id": data["call_id"]
                }
                
                if self.callback:
                    self.callback(data_dict)
                    
        except Exception as e:
            logger.error(f"Error in ChainEventListener: {e}")
            import traceback
            traceback.print_exc()

class SimpleMonitoringTest:
    """Simple monitoring test using the exact Genesis Monitor pattern"""
    
    def __init__(self, domain_id: int = 0):
        self.domain_id = domain_id
        self.lifecycle_events = []
        self.chain_events = []
        self.participant = None
        self.subscriber = None
        self.lifecycle_reader = None
        self.chain_reader = None
        
        # Set up DDS monitoring
        self._setup_monitoring()
    
    def _setup_monitoring(self):
        """Set up DDS monitoring - copied from genesis_monitor.py"""
        try:
            # Create DDS entities
            self.participant = dds.DomainParticipant(self.domain_id)
            self.subscriber = dds.Subscriber(self.participant)
            
            # Get type provider
            provider = dds.QosProvider(get_datamodel_path())
            
            # Set up ComponentLifecycleEvent subscriber
            lifecycle_type = provider.type("genesis_lib", "ComponentLifecycleEvent")
            lifecycle_topic = dds.DynamicData.Topic(
                self.participant,
                "ComponentLifecycleEvent",
                lifecycle_type
            )
            
            # Set up ChainEvent subscriber
            chain_type = provider.type("genesis_lib", "ChainEvent")
            chain_topic = dds.DynamicData.Topic(
                self.participant,
                "ChainEvent",
                chain_type
            )
            
            # Configure reader QoS
            reader_qos = dds.QosProvider.default.datareader_qos
            reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
            reader_qos.history.depth = 1000
            
            # Create readers with listeners
            lifecycle_listener = ComponentLifecycleListener(self._lifecycle_callback)
            self.lifecycle_reader = dds.DynamicData.DataReader(
                subscriber=self.subscriber,
                topic=lifecycle_topic,
                qos=reader_qos,
                listener=lifecycle_listener,
                mask=dds.StatusMask.DATA_AVAILABLE
            )
            
            chain_listener = ChainEventListener(self._chain_callback)
            self.chain_reader = dds.DynamicData.DataReader(
                subscriber=self.subscriber,
                topic=chain_topic,
                qos=reader_qos,
                listener=chain_listener,
                mask=dds.StatusMask.DATA_AVAILABLE
            )
            
            logger.info(f"Monitoring setup complete on domain {self.domain_id}")
            
        except Exception as e:
            logger.error(f"Failed to setup monitoring: {e}")
            raise
    
    def _lifecycle_callback(self, data):
        """Handle lifecycle events"""
        self.lifecycle_events.append(data)
        logger.info(f"📋 Lifecycle Event: {data['event_category']} - {data['component_type']} - {data['component_id']}")
        
        # Show key details
        if 'capabilities' in data and data['capabilities']:
            try:
                import json
                caps = json.loads(data['capabilities'])
                if 'function_name' in caps:
                    logger.info(f"   Function: {caps['function_name']}")
                if 'agent_type' in caps:
                    logger.info(f"   Agent Type: {caps['agent_type']}")
            except:
                pass
    
    def _chain_callback(self, data):
        """Handle chain events"""
        self.chain_events.append(data)
        logger.info(f"⛓️ Chain Event: {data['event_type']} - {data['source_id']} → {data['target_id']}")
    
    def run_test(self, duration_seconds: float = 30.0):
        """Run the monitoring test"""
        logger.info(f"🚀 Starting monitoring test for {duration_seconds} seconds")
        
        # Start a Genesis scenario in background
        self._start_scenario()
        
        # Wait for events
        logger.info(f"⏳ Waiting {duration_seconds} seconds for monitoring events...")
        time.sleep(duration_seconds)
        
        # Analyze results
        return self._analyze_results()
    
    def _start_scenario(self):
        """Start a Genesis scenario to generate monitoring events"""
        try:
            script_dir = Path(__file__).parent.parent / "run_scripts"
            script_path = script_dir / "run_interface_agent_service_test.sh"
            
            if script_path.exists():
                logger.info("🎬 Starting Genesis scenario in background...")
                
                def run_scenario():
                    try:
                        subprocess.run(
                            [str(script_path)],
                            cwd=script_dir,
                            timeout=25.0,
                            capture_output=True
                        )
                    except Exception as e:
                        logger.debug(f"Scenario completed: {e}")
                
                scenario_thread = threading.Thread(target=run_scenario, daemon=True)
                scenario_thread.start()
            else:
                logger.warning("⚠️ Test scenario not found, monitoring empty domain")
                
        except Exception as e:
            logger.error(f"❌ Failed to start scenario: {e}")
    
    def _analyze_results(self):
        """Analyze monitoring results"""
        logger.info("🔍 Analyzing monitoring results...")
        
        lifecycle_count = len(self.lifecycle_events)
        chain_count = len(self.chain_events)
        
        logger.info(f"📊 Results Summary:")
        logger.info(f"  Lifecycle Events: {lifecycle_count}")
        logger.info(f"  Chain Events: {chain_count}")
        
        # Analyze lifecycle events
        if self.lifecycle_events:
            logger.info("📋 Lifecycle Event Breakdown:")
            event_categories = {}
            component_types = {}
            
            for event in self.lifecycle_events:
                category = event.get('event_category', 'Unknown')
                comp_type = event.get('component_type', 'Unknown')
                
                event_categories[category] = event_categories.get(category, 0) + 1
                component_types[comp_type] = component_types.get(comp_type, 0) + 1
            
            for category, count in event_categories.items():
                logger.info(f"  {category}: {count}")
            
            logger.info("🧩 Component Type Breakdown:")
            for comp_type, count in component_types.items():
                logger.info(f"  {comp_type}: {count}")
        
        # Analyze chain events
        if self.chain_events:
            logger.info("⛓️ Chain Event Breakdown:")
            event_types = {}
            
            for event in self.chain_events:
                event_type = event.get('event_type', 'Unknown')
                event_types[event_type] = event_types.get(event_type, 0) + 1
            
            for event_type, count in event_types.items():
                logger.info(f"  {event_type}: {count}")
        
        # Success criteria
        success_criteria = [
            lifecycle_count > 0,  # Should have some lifecycle events
            # chain_count >= 0,     # Chain events are optional
        ]
        
        overall_success = all(success_criteria)
        
        if overall_success:
            logger.info("✅ Monitoring test PASSED")
            logger.info("✅ System is generating monitoring events correctly")
        else:
            logger.error("❌ Monitoring test FAILED")
            logger.error("❌ No monitoring events detected")
        
        return overall_success
    
    def close(self):
        """Clean up resources"""
        try:
            if self.lifecycle_reader:
                self.lifecycle_reader.close()
            if self.chain_reader:
                self.chain_reader.close()
            if self.subscriber:
                self.subscriber.close()
            if self.participant:
                self.participant.close()
        except Exception as e:
            logger.warning(f"⚠️ Cleanup warning: {e}")

def main():
    """Main test runner"""
    logger.info("🚀 Starting Simple Monitoring Test")
    
    # Check environment
    if not os.path.exists("genesis_lib"):
        logger.error("❌ Please run from the project root directory")
        return False
    
    test = SimpleMonitoringTest(domain_id=0)
    
    try:
        success = test.run_test(duration_seconds=30.0)
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
        test.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 