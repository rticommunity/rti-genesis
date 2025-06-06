#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from genesis_lib.monitored_interface import MonitoredInterface

async def test_weather_request():
    interface = MonitoredInterface('WeatherTest', 'OpenAIAgent')
    await asyncio.sleep(3)
    
    success = await interface.connect_to_agent('OpenAIAgent')
    if success:
        print('✅ Connected to PersonalAssistant')
        response = await interface.send_request({'message': 'What is the weather in Denver Colorado?'})
        if response:
            print(f'Response: {response.get("message", "No message")[:500]}')
        else:
            print('❌ No response')
    else:
        print('❌ Failed to connect')
    
    await interface.close()

asyncio.run(test_weather_request()) 