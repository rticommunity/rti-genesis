#!/usr/bin/env python3
"""
Working test for agent-to-agent communication.
This test runs one agent per process. Use separate terminals to test communication.

Usage:
Terminal 1: python test_working_communication.py b
Terminal 2: python test_working_communication.py a
"""

import asyncio
import sys
import os
import time

# Add the parent directory to the path so we can import genesis_lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.monitored_agent import MonitoredAgent

class CommunicationAgentA(MonitoredAgent):
    def __init__(self):
        super().__init__(
            agent_name="CommunicationAgentA",
            base_service_name="CommServiceA",
            agent_type="AGENT",
            enable_agent_communication=True
        )
    
    async def process_agent_request(self, request):
        return {'message': f"Agent A processed: {request['message']}", 'status': 0}

class CommunicationAgentB(MonitoredAgent):
    def __init__(self):
        super().__init__(
            agent_name="CommunicationAgentB",
            base_service_name="CommServiceB",
            agent_type="SPECIALIZED_AGENT",
            agent_id="comm_agent_b",
            enable_agent_communication=True
        )
    
    async def process_agent_request(self, request):
        return {'message': f"Agent B processed: {request['message']}", 'status': 0}

async def run_agent_b():
    """Run Agent B as responder"""
    print("=== Starting Agent B (Responder) ===")
    agent = CommunicationAgentB()
    
    print("Agent B: Running as responder, waiting for requests...")
    print("Agent B: Press Ctrl+C to stop")
    print("Agent B: Starting main agent loop with request polling...")
    
    # Use the agent's main run() method which includes request polling
    await agent.run()

async def run_agent_a():
    """Run Agent A as requester"""
    print("=== Starting Agent A (Requester) ===")
    agent = CommunicationAgentA()
    
    # Wait for Agent B to be discoverable
    print("Agent A: Waiting for Agent B to be discoverable...")
    agent_b_found = await agent.wait_for_agent("comm_agent_b", timeout_seconds=15)
    
    if agent_b_found:
        print("✅ Agent A: Found Agent B!")
        
        # Attempt communication
        try:
            print("Agent A: Sending request to Agent B...")
            response = await agent.send_agent_request(
                target_agent_id="comm_agent_b",
                message="Hello from Agent A!",
                timeout_seconds=5.0
            )
            
            if response:
                print(f"✅ Agent A: Received response: {response}")
                print("🎉 SUCCESS: Agent-to-agent communication is working!")
            else:
                print("❌ Agent A: No response received")
                
        except Exception as e:
            print(f"❌ Agent A: Communication failed: {e}")
    else:
        print("❌ Agent A: Could not find Agent B")
        print("Make sure Agent B is running in a separate terminal")
    
    discovered = agent.get_discovered_agents()
    print(f"Agent A: Final discovered agents: {list(discovered.keys())}")
    
    await agent.close()

async def main():
    """Run one agent based on command line argument"""
    
    if len(sys.argv) != 2 or sys.argv[1] not in ['a', 'b']:
        print("Usage: python test_working_communication.py [a|b]")
        print("\nTo test agent-to-agent communication:")
        print("1. Terminal 1: python test_working_communication.py b")
        print("2. Terminal 2: python test_working_communication.py a")
        print("\nAgent B runs as responder, Agent A will discover and send a message to B")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == 'b':
        await run_agent_b()
    elif mode == 'a':
        await run_agent_a()

if __name__ == "__main__":
    asyncio.run(main()) 