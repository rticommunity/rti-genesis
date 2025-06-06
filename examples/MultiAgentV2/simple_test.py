#!/usr/bin/env python3
"""
Simple test to directly test PersonalAssistant with detailed tracing
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from genesis_lib.monitored_interface import MonitoredInterface

async def simple_test():
    """Simple test with just discovery and a basic request"""
    
    print("🧪 Simple PersonalAssistant Test")
    print("=" * 40)
    
    interface = MonitoredInterface(
        interface_name="SimpleTest",
        service_name="OpenAIAgent"
    )
    
    try:
        print("⏰ Waiting 3 seconds for agent startup...")
        await asyncio.sleep(3)
        
        # Check if any agents are available
        print(f"🔍 Available agents: {len(interface.available_agents)}")
        for agent_id, agent_info in interface.available_agents.items():
            name = agent_info.get('prefered_name', 'Unknown')
            print(f"   - {name} ({agent_id})")
        
        if not interface.available_agents:
            print("❌ No agents found!")
            return
        
        # Connect to first PersonalAssistant
        personal_assistant_id = None
        for agent_id, agent_info in interface.available_agents.items():
            if agent_info.get('prefered_name') == 'PersonalAssistant':
                personal_assistant_id = agent_id
                break
        
        if not personal_assistant_id:
            print("❌ PersonalAssistant not found!")
            return
        
        agent_info = interface.available_agents[personal_assistant_id]
        service_name = agent_info.get('service_name', 'OpenAIAgent')
        
        print(f"🔗 Connecting to PersonalAssistant service: {service_name}")
        connected = await interface.connect_to_agent(service_name)
        
        if not connected:
            print("❌ Connection failed!")
            return
        
        print("✅ Connected! Sending simple test request...")
        
        # Send a simple test request
        request = {
            "message": "Hello, can you help me with something?",
            "conversation_id": "simple_test"
        }
        
        print(f"📤 Sending: {request['message']}")
        print("\n" + "="*50)
        print("TRACING OUTPUT FROM PERSONALASSISTANT:")
        print("="*50)
        
        response = await interface.send_request(request, timeout_seconds=20.0)
        
        print("="*50)
        print("END TRACING OUTPUT")
        print("="*50 + "\n")
        
        if response:
            print(f"✅ Response: {response.get('message', 'No message')}")
            print(f"📊 Status: {response.get('status', 'No status')}")
        else:
            print("❌ No response received")
        
    finally:
        await interface.close()

if __name__ == "__main__":
    asyncio.run(simple_test()) 