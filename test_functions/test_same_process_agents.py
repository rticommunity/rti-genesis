#!/usr/bin/env python3
"""
Test both agents in the same process to see if they can discover each other.
"""

import asyncio
import logging
import sys
import os
import time
from typing import Dict, Any

print("🚀 PRINT: Same process test starting")

# Add the parent directory to the path so we can import genesis_lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.monitored_agent import MonitoredAgent

print("🚀 PRINT: MonitoredAgent imported")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

print("🚀 PRINT: Logging configured")

class TestAgentA(MonitoredAgent):
    def __init__(self):
        print("🚀 PRINT: TestAgentA.__init__() starting")
        super().__init__(
            agent_name="TestAgentA",
            base_service_name="TestServiceA",
            agent_type="AGENT",
            enable_agent_communication=True
        )
        print("✅ PRINT: TestAgentA.__init__() completed")
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {"message": f"Agent A processed: {request.get('message', '')}", "status": 0}
    
    async def process_agent_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {"message": f"Agent A handled agent request: {request.get('message', '')}", "status": 0}

class TestAgentB(MonitoredAgent):
    def __init__(self):
        print("🚀 PRINT: TestAgentB.__init__() starting")
        super().__init__(
            agent_name="TestAgentB",
            base_service_name="TestServiceB",
            agent_type="SPECIALIZED_AGENT",
            agent_id="test_agent_b",
            enable_agent_communication=True
        )
        print("✅ PRINT: TestAgentB.__init__() completed")
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {"message": f"Agent B processed: {request.get('message', '')}", "status": 0}
    
    async def process_agent_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return {"message": f"Agent B handled agent request: {request.get('message', '')}", "status": 0}

async def test_agent_discovery():
    """Test if agents can discover each other in the same process"""
    print("🎬 PRINT: Starting same-process agent discovery test")
    
    # Create both agents
    print("🏗️ PRINT: Creating Agent A...")
    agent_a = TestAgentA()
    print("✅ PRINT: Agent A created")
    
    print("🏗️ PRINT: Creating Agent B...")
    agent_b = TestAgentB()
    print("✅ PRINT: Agent B created")
    
    try:
        # Announce both agents
        print("📢 PRINT: Announcing Agent A...")
        await agent_a.announce_self()
        print("✅ PRINT: Agent A announced")
        
        print("📢 PRINT: Announcing Agent B...")
        await agent_b.announce_self()
        print("✅ PRINT: Agent B announced")
        
        # Wait a bit for discovery
        print("⏳ PRINT: Waiting 3 seconds for discovery...")
        await asyncio.sleep(3)
        
        # Check if they discovered each other
        print("🔍 PRINT: Checking Agent A's discovered agents...")
        discovered_by_a = agent_a.get_discovered_agents()
        print(f"📋 PRINT: Agent A discovered: {list(discovered_by_a.keys())}")
        
        print("🔍 PRINT: Checking Agent B's discovered agents...")
        discovered_by_b = agent_b.get_discovered_agents()
        print(f"📋 PRINT: Agent B discovered: {list(discovered_by_b.keys())}")
        
        # Test communication if they found each other
        if "test_agent_b" in discovered_by_a:
            print("🔗 PRINT: Testing Agent A -> Agent B communication...")
            response = await agent_a.send_agent_request(
                target_agent_id="test_agent_b",
                message="Hello from Agent A",
                timeout_seconds=5.0
            )
            print(f"📥 PRINT: Response from Agent B: {response}")
        else:
            print("❌ PRINT: Agent A did not discover Agent B")
        
        return discovered_by_a, discovered_by_b
        
    finally:
        print("🧹 PRINT: Cleaning up agents...")
        await agent_a.close()
        await agent_b.close()
        print("✅ PRINT: Agents cleaned up")

async def main():
    print("🎬 PRINT: Main function starting")
    try:
        discovered_a, discovered_b = await test_agent_discovery()
        print(f"🎯 PRINT: Test completed. A discovered {len(discovered_a)}, B discovered {len(discovered_b)}")
    except Exception as e:
        print(f"💥 PRINT: Error in test: {e}")
        import traceback
        print(f"💥 PRINT: Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    print("🎬 PRINT: Script starting")
    asyncio.run(main())
    print("✅ PRINT: Script completed") 