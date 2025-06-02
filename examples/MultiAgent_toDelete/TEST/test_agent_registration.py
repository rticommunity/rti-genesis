#!/usr/bin/env python3
"""
Agent Registration Test

This test verifies that agents are actually publishing their registration
announcements on the GenesisRegistration DDS topic.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import os
import sys
import subprocess
import time
import logging
from typing import List, Dict, Any, Optional

# Add project paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class RegistrationMonitor:
    """Monitor for agent registration announcements."""
    
    def __init__(self):
        self.registrations_received = {}
        self.participant = None
        self.reader = None
        
    async def start_monitoring(self):
        """Start monitoring for registration announcements."""
        print("🔍 Starting registration monitoring...")
        
        # Create DDS participant
        self.participant = dds.DomainParticipant(0)
        
        # Get types from XML
        config_path = get_datamodel_path()
        type_provider = dds.QosProvider(config_path)
        registration_type = type_provider.type("genesis_lib", "GenesisRegistration")
        
        # Create topic
        topic = dds.DynamicData.Topic(
            self.participant,
            "GenesisRegistration",
            registration_type
        )
        
        # Create subscriber
        subscriber = dds.Subscriber(self.participant)
        
        # Configure reader QoS to match what agents use
        reader_qos = dds.QosProvider.default.datareader_qos
        reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
        reader_qos.history.depth = 500
        reader_qos.liveliness.kind = dds.LivelinessKind.AUTOMATIC
        reader_qos.liveliness.lease_duration = dds.Duration(seconds=2)
        
        # Create reader
        self.reader = dds.DynamicData.DataReader(
            subscriber=subscriber,
            topic=topic,
            qos=reader_qos
        )
        
        print("✅ Registration monitoring started")
        
    async def check_for_registrations(self, duration: float = 10.0):
        """Check for registration announcements for a given duration."""
        print(f"👂 Listening for registrations for {duration} seconds...")
        
        start_time = time.time()
        last_check = start_time
        
        while time.time() - start_time < duration:
            try:
                # Check for new data
                samples = self.reader.read()
                
                for data, info in samples:
                    if data is None:
                        continue
                        
                    instance_id = data.get_string('instance_id')
                    prefered_name = data.get_string('prefered_name')
                    service_name = data.get_string('service_name')
                    message = data.get_string('message')
                    
                    if info.state.instance_state == dds.InstanceState.ALIVE:
                        if instance_id not in self.registrations_received:
                            self.registrations_received[instance_id] = {
                                'prefered_name': prefered_name,
                                'service_name': service_name,
                                'message': message,
                                'instance_id': instance_id,
                                'timestamp': time.time()
                            }
                            print(f"📋 REGISTRATION RECEIVED:")
                            print(f"   Agent: {prefered_name}")
                            print(f"   Service: {service_name}")
                            print(f"   ID: {instance_id}")
                            print(f"   Message: {message}")
                            print()
                    
            except Exception as e:
                if "No data" not in str(e):
                    logger.error(f"Error reading registrations: {e}")
            
            # Print status every 2 seconds
            if time.time() - last_check >= 2.0:
                elapsed = time.time() - start_time
                print(f"⏳ Monitoring... ({elapsed:.1f}/{duration}s) - {len(self.registrations_received)} registrations received")
                last_check = time.time()
            
            await asyncio.sleep(0.1)
        
        print(f"🏁 Monitoring complete. Total registrations received: {len(self.registrations_received)}")
        return self.registrations_received
    
    def close(self):
        """Clean up resources."""
        if self.reader:
            self.reader.close()
        if self.participant:
            self.participant.close()

async def test_agent_registration():
    """Test that agents actually publish registration announcements."""
    print("\n" + "="*80)
    print("🧪 AGENT REGISTRATION TEST")
    print("="*80)
    
    # Start monitoring
    monitor = RegistrationMonitor()
    await monitor.start_monitoring()
    
    # Start PersonalAssistant in subprocess
    print("\n🚀 Starting PersonalAssistant agent...")
    script_path = os.path.join(os.path.dirname(__file__), '..', 'agents', 'general', 'personal_assistant.py')
    
    process = subprocess.Popen(
        [sys.executable, script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy()
    )
    
    print(f"   ✅ PersonalAssistant started (PID: {process.pid})")
    
    try:
        # Monitor for registrations
        registrations = await monitor.check_for_registrations(15.0)
        
        # Analyze results
        print("\n📊 RESULTS:")
        
        if not registrations:
            print("❌ NO REGISTRATIONS RECEIVED!")
            print("   This indicates the agent is not publishing registrations properly.")
            return False
        
        # Look for PersonalAssistant specifically
        personal_assistant_found = False
        for reg_id, reg_info in registrations.items():
            if (reg_info['prefered_name'] == 'PersonalAssistant' or 
                reg_info['service_name'] == 'PersonalAssistanceService'):
                print(f"✅ PersonalAssistant registration found!")
                print(f"   Name: {reg_info['prefered_name']}")
                print(f"   Service: {reg_info['service_name']}")
                print(f"   ID: {reg_info['instance_id']}")
                personal_assistant_found = True
                break
        
        if not personal_assistant_found:
            print("❌ PersonalAssistant registration NOT found!")
            print(f"   Expected: prefered_name='PersonalAssistant' OR service_name='PersonalAssistanceService'")
            print("   Found registrations:")
            for reg_id, reg_info in registrations.items():
                print(f"     - {reg_info['prefered_name']} ({reg_info['service_name']})")
            return False
        
        print("✅ Agent registration test PASSED!")
        return True
        
    finally:
        # Clean up
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        monitor.close()

async def main():
    """Main test runner."""
    success = await test_agent_registration()
    return 0 if success else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        sys.exit(1) 