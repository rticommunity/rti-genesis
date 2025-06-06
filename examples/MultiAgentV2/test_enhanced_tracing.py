#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.append('../../')
from genesis_lib.monitored_interface import MonitoredInterface

async def test():
    interface = MonitoredInterface('WeatherTest', 'OpenAIAgent')
    await asyncio.sleep(3)
    
    connected = await interface.connect_to_agent('OpenAIAgent')
    if connected:
        print('✅ Connected to PersonalAssistant')
        print('📤 Sending weather request with enhanced tracing...')
        response = await interface.send_request({'message': 'What is the weather in Denver Colorado? I need detailed weather information.'})
        if response:
            print(f'📥 Response: {response.get("message", "No message")[:200]}...')
        else:
            print('❌ No response')
    else:
        print('❌ Failed to connect')
    
    await interface.close()

if __name__ == "__main__":
    asyncio.run(test()) 