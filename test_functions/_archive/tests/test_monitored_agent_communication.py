#!/usr/bin/env python3
"""
Test MonitoredAgent agent-to-agent communication with monitoring.
This test verifies that agent communication events are properly monitored.

Usage:
Terminal 1: python test_functions/test_monitored_agent_communication.py b
Terminal 2: python test_functions/test_monitored_agent_communication.py a
"""

import asyncio
import sys
import os
import time
import logging

# Add the parent directory to the path so we can import genesis_lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.monitored_agent import MonitoredAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MonitoredCommunicationAgentA(MonitoredAgent):
    def __init__(self):
        super().__init__(
            agent_name="MonitoredAgentA",
            base_service_name="MonitoredServiceA",
            agent_type="AGENT",
            enable_agent_communication=True
        )
    
    async def process_agent_request(self, request):
        return {'message': f"Monitored Agent A processed: {request['message']}", 'status': 0}

class MonitoredCommunicationAgentB(MonitoredAgent):
    def __init__(self):
        super().__init__(
            agent_name="MonitoredAgentB",
            base_service_name="MonitoredServiceB",
            agent_type="SPECIALIZED_AGENT",
            agent_id="monitored_agent_b",
            enable_agent_communication=True
        )
    
    async def process_agent_request(self, request):
        return {'message': f"Monitored Agent B processed: {request['message']}", 'status': 0}

async def run_monitored_agent_b():
    """Run Monitored Agent B as responder"""
    print("=== Starting Monitored Agent B (Responder) ===")
    agent = MonitoredCommunicationAgentB()
    
    print("Monitored Agent B: Running as responder with monitoring...")
    print("Monitored Agent B: Press Ctrl+C to stop")
    
    # Use the agent's main run() method
    await agent.run()

async def run_monitored_agent_a():
    """Run Monitored Agent A as requester"""
    print("=== Starting Monitored Agent A (Requester) ===")
    agent = MonitoredCommunicationAgentA()
    
    # Wait for Agent B to be discoverable
    print("Monitored Agent A: Waiting for Monitored Agent B to be discoverable...")
    agent_b_found = await agent.wait_for_agent("monitored_agent_b", timeout_seconds=15)
    
    if agent_b_found:
        print("✅ Monitored Agent A: Found Monitored Agent B!")
        
        # Test monitored communication
        try:
            print("Monitored Agent A: Sending monitored request to Agent B...")
            
            # Use the monitored version which publishes events
            response = await agent.send_agent_request_monitored(
                target_agent_id="monitored_agent_b",
                message="Hello from Monitored Agent A with monitoring!",
                timeout_seconds=5.0
            )
            
            if response:
                print(f"✅ Monitored Agent A: Received monitored response: {response}")
                print("🎉 SUCCESS: Monitored agent-to-agent communication is working!")
                print("📊 Monitoring events should have been published for this interaction")
            else:
                print("❌ Monitored Agent A: No response received")
                
        except Exception as e:
            print(f"❌ Monitored Agent A: Communication failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ Monitored Agent A: Could not find Monitored Agent B")
        print("Make sure Monitored Agent B is running in a separate terminal")
    
    discovered = agent.get_discovered_agents()
    print(f"Monitored Agent A: Final discovered agents: {list(discovered.keys())}")
    
    await agent.close()

async def main():
    """Run one agent based on command line argument"""
    
    if len(sys.argv) != 2 or sys.argv[1] not in ['a', 'b']:
        print("Usage: python test_monitored_agent_communication.py [a|b]")
        print("\nTo test monitored agent-to-agent communication:")
        print("1. Terminal 1: python test_monitored_agent_communication.py b")
        print("2. Terminal 2: python test_monitored_agent_communication.py a")
        print("\nMonitored Agent B runs as responder, Monitored Agent A will discover and send a monitored message to B")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == 'b':
        await run_monitored_agent_b()
    elif mode == 'a':
        await run_monitored_agent_a()

if __name__ == "__main__":
    asyncio.run(main()) 