#!/usr/bin/env python3
"""
Simple test for agent discovery - start Agent B, wait, then start Agent A.
Agent A should discover Agent B via durable topics.
"""

import asyncio
import sys
import os
import time

# Add the parent directory to the path so we can import genesis_lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.monitored_agent import MonitoredAgent

class SimpleAgentA(MonitoredAgent):
    def __init__(self):
        super().__init__(
            agent_name="SimpleAgentA",
            base_service_name="SimpleServiceA",
            agent_type="AGENT",
            enable_agent_communication=True
        )
    
    async def process_agent_request(self, request):
        return {'message': f"Agent A handled: {request['message']}", 'status': 0}

class SimpleAgentB(MonitoredAgent):
    def __init__(self):
        super().__init__(
            agent_name="SimpleAgentB",
            base_service_name="SimpleServiceB",
            agent_type="SPECIALIZED_AGENT",
            agent_id="simple_agent_b",
            enable_agent_communication=True
        )
    
    async def process_agent_request(self, request):
        return {'message': f"Agent B handled: {request['message']}", 'status': 0}

async def test_discovery():
    """Test discovery by starting agents sequentially"""
    
    if len(sys.argv) != 2 or sys.argv[1] not in ['a', 'b']:
        print("Usage: python test_simple_discovery.py [a|b]")
        sys.exit(1)
    
    agent_type = sys.argv[1]
    
    if agent_type == 'b':
        print("=== Starting Agent B ===")
        agent = SimpleAgentB()
        
        # Publish capability and wait
        print("Publishing Agent B capability...")
        if hasattr(agent, 'agent_communication') and agent.agent_communication:
            agent.agent_communication.publish_agent_capability()
        
        print("Agent B running for 10 seconds...")
        await asyncio.sleep(10)
        print("Agent B shutting down...")
        await agent.close()
        
    else:  # agent_type == 'a'
        print("=== Starting Agent A ===")
        agent = SimpleAgentA()
        
        # Wait a moment for initialization
        await asyncio.sleep(2)
        
        # Check discovered agents
        discovered = agent.get_discovered_agents()
        print(f"Agent A discovered agents: {list(discovered.keys())}")
        print(f"Full discovery data: {discovered}")
        
        if "simple_agent_b" in discovered:
            print("✅ SUCCESS: Agent A discovered Agent B!")
        else:
            print("❌ FAILURE: Agent A did not discover Agent B")
        
        await agent.close()

if __name__ == "__main__":
    asyncio.run(test_discovery()) 