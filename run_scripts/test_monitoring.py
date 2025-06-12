#!/usr/bin/env python3
"""
Test script for monitoring functionality.
Verifies that agent and function monitoring events are being published correctly.
"""

import argparse
import logging
import sys
import time
import os
import json
from datetime import datetime
import threading
import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path
import re
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class MonitoringTest:
    def __init__(self, domain_id=0):
        """Initialize the monitoring test."""
        self.domain_id = domain_id
        self.events = []
        self.events_lock = threading.Lock()
        self.expected_events = set()
        self.expected_events_lock = threading.Lock()
        self.test_complete = False
        self.quit_flag = False
        
        # Initialize logger
        self.logger = logging.getLogger("MonitoringTest")
        self.logger.setLevel(logging.DEBUG)
        
        # Create DDS entities
        self.logger.info(f"Initializing DDS on domain {domain_id}")
        participant_qos = dds.QosProvider.default.participant_qos
        self.participant = dds.DomainParticipant(domain_id, participant_qos)
        
        # Create subscriber with appropriate QoS
        subscriber_qos = dds.QosProvider.default.subscriber_qos
        subscriber_qos.partition.name = [""]  # Default partition
        self.subscriber = dds.Subscriber(self.participant, subscriber_qos)
        
        # Get type provider
        self.logger.info("Loading types from datamodel.xml")
        provider = dds.QosProvider(get_datamodel_path())
        
        # Set up ComponentLifecycleEvent subscriber
        self.logger.info("Creating ComponentLifecycleEvent topic")
        self.lifecycle_type = provider.type("genesis_lib", "ComponentLifecycleEvent")
        self.lifecycle_topic = dds.DynamicData.Topic(
            self.participant,
            "ComponentLifecycleEvent",
            self.lifecycle_type
        )
        
        # Set up ChainEvent subscriber
        self.logger.info("Creating ChainEvent topic")
        self.chain_type = provider.type("genesis_lib", "ChainEvent")
        self.chain_topic = dds.DynamicData.Topic(
            self.participant,
            "ChainEvent",
            self.chain_type
        )
        
        # Configure reader QoS
        reader_qos = dds.QosProvider.default.datareader_qos
        reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
        reader_qos.history.depth = 1000
        
        # Set up subscription matching listener
        self.subscription_listener = self._setup_subscription_listener()
        
        # Create readers with listeners
        self.lifecycle_listener = self.ComponentLifecycleListener(self)
        self.lifecycle_reader = dds.DynamicData.DataReader(
            subscriber=self.subscriber,
            topic=self.lifecycle_topic,
            qos=reader_qos,
            listener=self.lifecycle_listener,
            mask=dds.StatusMask.DATA_AVAILABLE | dds.StatusMask.SUBSCRIPTION_MATCHED
        )
        
        self.chain_listener = self.ChainEventListener(self)
        self.chain_reader = dds.DynamicData.DataReader(
            subscriber=self.subscriber,
            topic=self.chain_topic,
            qos=reader_qos,
            listener=self.chain_listener,
            mask=dds.StatusMask.DATA_AVAILABLE | dds.StatusMask.SUBSCRIPTION_MATCHED
        )
        
        # Set up expected events
        self._setup_expected_events()
        
        self.logger.info("Monitoring test initialization complete")
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.expected_events = {
            'calculator_service_1_discovery',
            'calculator_service_1_ready',
            'calculator_service_2_discovery',
            'calculator_service_2_ready',
            'calculator_service_3_discovery',
            'calculator_service_3_ready',
            'agent_discovery',
            'agent_ready',
            'function_discovery',
            'function_call_start',
            'function_call_complete'
        }
        self.discovered_services = set()
        self.log_lines = []  # Initialize log_lines to track service discovery order
    
    def _setup_subscription_listener(self):
        """Set up subscription matching listener."""
        class SubscriptionMatchListener(dds.DynamicData.NoOpDataReaderListener):
            def __init__(self, test_instance):
                super().__init__()
                self.test_instance = test_instance

            def on_subscription_matched(self, reader, status):
                # Only log matches for ComponentLifecycleEvent topic
                if reader.topic_name == "ComponentLifecycleEvent":
                    current_count = status.current_count
                    total_count = status.total_count
                    self.test_instance.logger.info(f"Subscription match update for {reader.topic_name}:")
                    self.test_instance.logger.info(f"  Current matched publications: {current_count}")
                    self.test_instance.logger.info(f"  Total cumulative matches: {total_count}")

        return SubscriptionMatchListener(self)
    
    class ComponentLifecycleListener(dds.DynamicData.NoOpDataReaderListener):
        def __init__(self, test_instance):
            super().__init__()
            self.test_instance = test_instance
            self.logger = logging.getLogger("ComponentLifecycleListener")
            self.logger.setLevel(logging.DEBUG)
        
        def on_data_available(self, reader):
            """Handle received data."""
            try:
                samples = reader.take()
                self.logger.debug(f"Got {len(samples)} samples")
                
                for data, info in samples:
                    if data is None or info.state.instance_state != dds.InstanceState.ALIVE:
                        continue
                    
                    self.logger.debug(f"\nRAW DDS DATA:")
                    self.logger.debug(f"Capabilities: {data['capabilities']}")
                    self.logger.debug(f"Reason: {data['reason']}")
                    
                    # Map component types and states
                    component_types = ["INTERFACE", "PRIMARY_AGENT", "SPECIALIZED_AGENT", "FUNCTION", "SERVICE"]
                    states = ["JOINING", "DISCOVERING", "READY", "BUSY", "DEGRADED", "OFFLINE"]
                    event_categories = ["NODE_DISCOVERY", "EDGE_DISCOVERY", "STATE_CHANGE", "AGENT_INIT", "AGENT_READY", "AGENT_SHUTDOWN", "DDS_ENDPOINT"]
                    
                    # Convert enum values to integers for indexing
                    component_type_idx = int(data["component_type"])
                    previous_state_idx = int(data["previous_state"])
                    new_state_idx = int(data["new_state"])
                    event_category_idx = int(data["event_category"])
                    
                    # Safely get event category
                    event_category = event_categories[event_category_idx] if 0 <= event_category_idx < len(event_categories) else "UNKNOWN"
                    
                    # Build data dictionary
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
                    
                    self.test_instance._lifecycle_callback(data_dict)
                    
            except Exception as e:
                self.logger.error(f"Error in ComponentLifecycleListener: {e}")
                traceback.print_exc(file=sys.stderr)
    
    class ChainEventListener(dds.DynamicData.NoOpDataReaderListener):
        def __init__(self, test_instance):
            super().__init__()
            self.test_instance = test_instance
            self.logger = logging.getLogger("ChainEventListener")
            self.logger.setLevel(logging.DEBUG)
        
        def on_data_available(self, reader):
            """Handle received data."""
            try:
                samples = reader.take()
                self.logger.debug(f"Got {len(samples)} samples")
                
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
                    
                    self.test_instance._chain_callback(data_dict)
                    
            except Exception as e:
                self.logger.error(f"Error in ChainEventListener: {e}")
                traceback.print_exc(file=sys.stderr)
    
    def _setup_expected_events(self):
        """Set up the expected events we should see."""
        with self.expected_events_lock:
            # Agent discovery events
            self.expected_events.add("agent_discovery")
            self.expected_events.add("agent_ready")
            
            # Calculator service discovery events
            for i in range(1, 4):
                self.expected_events.add(f"calculator_service_{i}_discovery")
                self.expected_events.add(f"calculator_service_{i}_ready")
            
            # Function discovery events
            self.expected_events.add("function_discovery")
            
            # Function call events
            self.expected_events.add("function_call_start")
            self.expected_events.add("function_call_complete")
    
    def _lifecycle_callback(self, data):
        """Handle received lifecycle events."""
        try:
            with self.events_lock:
                self.events.append(("lifecycle", data))
                self._check_expected_event(data)
                
        except Exception as e:
            self.logger.error(f"Error processing lifecycle event: {e}")
    
    def _chain_callback(self, data):
        """Handle received chain events."""
        try:
            with self.events_lock:
                self.events.append(("chain", data))
                self._check_expected_event(data)
                
        except Exception as e:
            self.logger.error(f"Error processing chain event: {e}")
    
    def _check_expected_event(self, event_data):
        """Check if the event matches any expected events and remove them from the list."""
        try:
            # Extract data from the event
            capabilities = event_data.get("capabilities", {})
            reason = event_data.get("reason", "")
            
            # Convert capabilities to dict if it's a string list
            if isinstance(capabilities, list):
                capabilities = {"capabilities": capabilities}
            
            self.logger.debug(f"\nRAW DDS DATA:")
            self.logger.debug(f"Capabilities: {capabilities}")
            self.logger.debug(f"Reason: {reason}")
            
            # Check for calculator service discovery
            if "Function app" in reason and "CalculatorService" in reason and "discovered" in reason:
                # Count which services we've found
                discovered_count = len([svc for svc in self.discovered_services if svc.startswith("CalculatorService")])
                service_number = discovered_count + 1
                
                if service_number <= 3:
                    service_key = f"CalculatorService_{service_number}"
                    self.discovered_services.add(service_key)
                    event_name = f"calculator_service_{service_number}_discovery"
                    if event_name in self.expected_events:
                        self.logger.info(f"✅ Found calculator service {service_number} discovery event")
                        self.expected_events.remove(event_name)
                    
            # Check for calculator service ready state
            if "All CalculatorService functions published and ready for calls" in reason:
                # Find the next available ready event to match
                for i in range(1, 4):
                    event_name = f"calculator_service_{i}_ready"
                    if event_name in self.expected_events:
                        self.logger.info(f"✅ Found calculator service {i} ready event")
                        self.expected_events.remove(event_name)
                        break
                    
            # Check for agent discovery
            if "TestAgent" in reason and "discovered" in reason:
                if "agent_discovery" in self.expected_events:
                    self.logger.info("✅ Found agent discovery event")
                    self.expected_events.remove("agent_discovery")
                
            # Check for agent ready state
            if "TestAgent" in reason and "ready for requests" in reason:
                if "agent_ready" in self.expected_events:
                    self.logger.info("✅ Found agent ready event")
                    self.expected_events.remove("agent_ready")
                
            # Check for function discovery
            if "Function 'add'" in reason and "available" in reason:
                if "function_discovery" in self.expected_events:
                    self.logger.info("✅ Found add function discovery event")
                    self.expected_events.remove("function_discovery")
                
            # Check for function call start
            if "Processing function call: add" in reason:
                if "function_call_start" in self.expected_events:
                    self.logger.info("✅ Found function call start event")
                    self.expected_events.remove("function_call_start")
                
            # Check for function call completion
            if "Completed function call: add" in reason:
                if "function_call_complete" in self.expected_events:
                    self.logger.info("✅ Found function call complete event")
                    self.expected_events.remove("function_call_complete")
                
            self.logger.debug(f"Remaining expected events: {self.expected_events}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error checking event: {str(e)}")
            return False

    def run_test(self):
        """Run the monitoring test."""
        try:
            self.logger.info("Starting monitoring test...")
            
            # Set initial timeout
            timeout = time.time() + 60  # 60 second timeout
            
            # Wait for all expected events
            while self.expected_events and time.time() < timeout:
                # Check if we've received all events
                if not self.expected_events:
                    break
                
                # Log remaining events every 5 seconds
                if int(time.time()) % 5 == 0:
                    self.logger.debug(f"Remaining expected events: {self.expected_events}")
                
                time.sleep(0.1)  # Small sleep to prevent busy waiting
            
            # Check if we got all events
            if not self.expected_events:
                self.logger.info("All expected events received successfully!")
            else:
                self.logger.error(f"❌ Test timed out waiting for events: {self.expected_events}")
                
            # Print test summary
            self._print_test_summary()
            
            return len(self.expected_events) == 0
            
        except Exception as e:
            self.logger.error(f"Error during test execution: {e}")
            traceback.print_exc()
            return False
        finally:
            self.logger.info("Cleaning up DDS resources...")
            try:
                self.close()
                self.logger.info("Cleanup completed successfully")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")

    def _print_test_summary(self):
        """Print a summary of the test results."""
        with self.events_lock:
            total_events = len(self.events)
            lifecycle_events = sum(1 for e in self.events if e[0] == "lifecycle")
            chain_events = sum(1 for e in self.events if e[0] == "chain")
            
            self.logger.info("\nTest Summary:")
            self.logger.info("=============")
            self.logger.info(f"Total events received: {total_events}")
            self.logger.info(f"Lifecycle events: {lifecycle_events}")
            self.logger.info(f"Chain events: {chain_events}")
            self.logger.info(f"Missing events: {len(self.expected_events)}")
            self.logger.info("=============")

    def close(self):
        """Clean up resources."""
        self.logger.info("Cleaning up DDS resources...")
        try:
            # Helper function to safely close a DDS entity
            def safe_close(entity, entity_name):
                try:
                    if hasattr(self, entity) and getattr(self, entity) is not None:
                        if not getattr(self, entity).closed:
                            getattr(self, entity).close()
                except Exception as e:
                    # Log at debug level since this is expected cleanup behavior
                    self.logger.debug(f"Note: {entity_name} was already closed or had cleanup error: {e}")

            # Close readers first
            safe_close('lifecycle_reader', 'lifecycle reader')
            safe_close('chain_reader', 'chain reader')
            
            # Then close topics
            safe_close('lifecycle_topic', 'lifecycle topic')
            safe_close('chain_topic', 'chain topic')
            
            # Then subscriber
            safe_close('subscriber', 'subscriber')
            
            # Finally close participant
            safe_close('participant', 'participant')
            
            self.logger.info("Cleanup completed successfully")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            traceback.print_exc()

def main():
    """Main entry point for the monitoring test."""
    parser = argparse.ArgumentParser(description="Test monitoring functionality")
    parser.add_argument("--domain", type=int, default=0, help="DDS domain ID")
    parser.add_argument("--timeout", type=int, default=60, help="Test timeout in seconds")
    args = parser.parse_args()
    
    test = MonitoringTest(domain_id=args.domain)
    try:
        success = test.run_test()
        sys.exit(0 if success else 1)
    finally:
        test.close()

if __name__ == "__main__":
    main() 