#!/usr/bin/env python3
"""
Test WeatherAgent directly via interface
"""
import asyncio
import sys
import os
sys.path.append('../..')
from genesis_lib.monitored_interface import MonitoredInterface

async def test_weather_direct():
    """Test WeatherAgent directly"""
    
    print("🌤️ Testing WeatherAgent DIRECTLY via interface")
    print("=" * 60)
    
    interface = MonitoredInterface('WeatherTest', 'WeatherService')
    
    try:
        await asyncio.sleep(3)
        
        print(f"🔍 Available agents: {len(interface.available_agents)}")
        for agent_id, info in interface.available_agents.items():
            name = info.get('prefered_name', 'Unknown')
            service = info.get('service_name', 'Unknown')
            print(f"   - {name} ({service})")
        
        # Connect directly to WeatherAgent service
        success = await interface.connect_to_agent('WeatherService')
        if success:
            print('✅ Connected to WeatherAgent')
            print('📤 Sending weather request directly to WeatherAgent...')
            
            response = await interface.send_request({
                'message': 'What is the weather in Denver Colorado?', 
                'conversation_id': 'test123'
            })
            
            if response:
                print(f'✅ Direct WeatherAgent response: {response.get("message", "No message")[:500]}...')
                print(f'📊 Status: {response.get("status", "No status")}')
                return True
            else:
                print('❌ No response from WeatherAgent')
                return False
        else:
            print('❌ Failed to connect to WeatherAgent')
            return False
    
    finally:
        await interface.close()

if __name__ == "__main__":
    success = asyncio.run(test_weather_direct())
    print(f"\n🎯 Direct WeatherAgent test: {'✅ PASSED' if success else '❌ FAILED'}") 