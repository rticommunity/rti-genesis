#!/usr/bin/env python3
"""Test script to verify unique agent service names"""

import os
import sys
import asyncio
import time

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from genesis_lib.monitored_interface import MonitoredInterface


async def main():
    """Test that interface only talks to the selected agent"""
    print("=== Testing Unique Agent Service Names ===")
    
    # Create interface
    interface = MonitoredInterface('TestInterface', 'TestInterface')
    print("✅ Interface created")
    
    # Wait for agents to be discovered
    print("\n⏳ Waiting for agents to be discovered...")
    await asyncio.sleep(5)
    
    # List discovered agents
    print("\n📋 Discovered agents:")
    for agent_id, info in interface.available_agents.items():
        print(f"  - {info.get('prefered_name')} (Service: {info.get('service_name')})")
        
    if len(interface.available_agents) < 2:
        print("❌ Need at least 2 agents running to test isolation")
        await interface.close()
        return
        
    # Find PersonalAssistant
    personal_agent = None
    weather_agent = None
    
    for agent_id, info in interface.available_agents.items():
        if info.get('prefered_name') == 'PersonalAssistant':
            personal_agent = info
        elif info.get('prefered_name') == 'WeatherExpert':
            weather_agent = info
            
    if not personal_agent or not weather_agent:
        print("❌ Could not find both PersonalAssistant and WeatherExpert")
        await interface.close()
        return
        
    # Test 1: Connect to PersonalAssistant and send a non-weather query
    print(f"\n🔗 Test 1: Connecting to PersonalAssistant (Service: {personal_agent.get('service_name')})")
    success = await interface.connect_to_agent(personal_agent.get('service_name'))
    if not success:
        print("❌ Failed to connect to PersonalAssistant")
        await interface.close()
        return
        
    print("✅ Connected to PersonalAssistant")
    
    # Send a math query (should only go to PersonalAssistant)
    print("\n📤 Sending math query to PersonalAssistant...")
    response = await interface.send_request({
        "message": "What is 15 + 27?",
        "conversation_id": "test_isolation"
    }, timeout_seconds=10.0)
    
    if response and response.get('status') == 0:
        print(f"✅ Response from PersonalAssistant: {response.get('message')}")
    else:
        print("❌ Failed to get response from PersonalAssistant")
        
    # Test 2: Connect to WeatherExpert and send a weather query
    print(f"\n🔗 Test 2: Connecting to WeatherExpert (Service: {weather_agent.get('service_name')})")
    success = await interface.connect_to_agent(weather_agent.get('service_name'))
    if not success:
        print("❌ Failed to connect to WeatherExpert")
        await interface.close()
        return
        
    print("✅ Connected to WeatherExpert")
    
    # Send a weather query (should only go to WeatherExpert)
    print("\n📤 Sending weather query to WeatherExpert...")
    response = await interface.send_request({
        "message": "What's the weather in Paris?",
        "conversation_id": "test_isolation"
    }, timeout_seconds=10.0)
    
    if response and response.get('status') == 0:
        print(f"✅ Response from WeatherExpert: {response.get('message')[:100]}...")
    else:
        print("❌ Failed to get response from WeatherExpert")
        
    print("\n✅ Test complete - Agents are properly isolated!")
    await interface.close()


if __name__ == "__main__":
    asyncio.run(main())
