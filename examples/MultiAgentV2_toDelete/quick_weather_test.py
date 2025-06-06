#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from genesis_lib.monitored_interface import MonitoredInterface

async def test():
    interface = MonitoredInterface('WeatherTest', 'OpenAIAgent')
    await asyncio.sleep(5)
    
    print(f'Found {len(interface.available_agents)} agents via interface')
    
    connected = await interface.connect_to_agent('OpenAIAgent')
    if connected:
        print('✅ Connected to PersonalAssistant')
        print('📤 Sending weather request...')
        response = await interface.send_request({'message': 'What is the weather in Denver Colorado?'})
        if response:
            print(f'📥 Response: {response.get("message", "No message")[:200]}...')
            print(f'📊 Status: {response.get("status", "No status")}')
        else:
            print('❌ No response received')
    else:
        print('❌ Failed to connect')
    
    await interface.close()

if __name__ == "__main__":
    asyncio.run(test()) 