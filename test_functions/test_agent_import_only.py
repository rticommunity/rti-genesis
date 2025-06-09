#!/usr/bin/env python3
"""
Minimal test to see where the hang occurs during agent creation.
"""

import sys
import os

print("🚀 PRINT: Starting import test")

# Add the parent directory to the path so we can import genesis_lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

print("🚀 PRINT: About to import MonitoredAgent")

from genesis_lib.monitored_agent import MonitoredAgent

print("✅ PRINT: MonitoredAgent imported successfully")

print("🚀 PRINT: About to create TestAgentB")

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
    
    async def process_request(self, request):
        return {"message": "test", "status": 0}
    
    async def process_agent_request(self, request):
        return {"message": "test", "status": 0}

print("🚀 PRINT: About to instantiate TestAgentB")

try:
    agent_b = TestAgentB()
    print("✅ PRINT: TestAgentB created successfully")
    
    print("🚀 PRINT: About to close agent")
    import asyncio
    asyncio.run(agent_b.close())
    print("✅ PRINT: Agent closed successfully")
    
except Exception as e:
    print(f"💥 PRINT: Error creating agent: {e}")
    import traceback
    print(f"💥 PRINT: Traceback: {traceback.format_exc()}")

print("✅ PRINT: Test completed") 