#!/usr/bin/env python3
"""
Debug script to trace agent-to-tool conversion specifically
"""
import asyncio
import sys
import os

sys.path.append('../..')
from genesis_lib.monitored_interface import MonitoredInterface

class AgentConversionDebugger(MonitoredInterface):
    def __init__(self):
        super().__init__('AgentConversionDebugger', 'OpenAIAgent')

async def debug_agent_conversion():
    """Debug why PersonalAssistant isn't converting agents to tools"""
    
    print("🔧 Debug: Agent-to-Tool Conversion Issue")
    print("=" * 50)
    
    debugger = AgentConversionDebugger()
    
    try:
        # Wait for discovery
        print("🔍 Waiting for agent discovery...")
        await asyncio.sleep(10)
        
        print(f"📊 Interface discovered {len(debugger.available_agents)} agents:")
        for agent_id, info in debugger.available_agents.items():
            print(f"   - {info.get('prefered_name')}: {agent_id}")
        
        # Connect to PersonalAssistant
        success = await debugger.connect_to_agent('OpenAIAgent')
        if not success:
            print("❌ Failed to connect to PersonalAssistant")
            return
        
        print("✅ Connected to PersonalAssistant")
        
        # Now let's send a simple request to trigger agent discovery internally
        print("🧪 Sending simple request to trigger internal agent discovery...")
        
        response = await debugger.send_request({
            "message": "Hello, can you tell me about your available tools?",
            "conversation_id": "debug_tools_test"
        })
        
        if response:
            message = response.get('message', '')
            print(f"📥 Response: {message}")
            
            # Check if response mentions any weather-related capabilities
            if 'weather' in message.lower():
                print("✅ PersonalAssistant mentions weather capabilities - agent conversion working")
            else:
                print("❌ No mention of weather capabilities - agent conversion may be failing")
        else:
            print("❌ No response received")
            
    finally:
        await debugger.close()

if __name__ == "__main__":
    asyncio.run(debug_agent_conversion()) 