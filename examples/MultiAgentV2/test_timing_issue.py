#!/usr/bin/env python3
"""
Test timing issue in agent-to-agent communication
"""
import asyncio
import sys
import os
sys.path.append('../..')
from genesis_lib.monitored_interface import MonitoredInterface

async def test_timing():
    interface = MonitoredInterface('TimingTest', 'TimingTest')
    
    print('🔍 Waiting for initial discovery...')
    await asyncio.sleep(10)
    print(f'📊 Found {len(interface.available_agents)} agents')
    
    # Connect to PersonalAssistant
    success = await interface.connect_to_agent('OpenAIAgent')
    if success:
        print('✅ Connected to PersonalAssistant')
        
        # Wait additional time for agent tool setup
        print('⏳ Waiting extra time for agent tool setup...')
        await asyncio.sleep(20)  # Wait longer than automated test
        
        response = await interface.send_request({'message': 'What is the weather in London?'})
        if response:
            message = response.get('message', '')
            print(f'📥 Response: {message[:200]}')
            
            # Check for weather indicators
            weather_words = ['temperature', 'degrees', 'humidity', 'pressure', 'cloudy', 'sunny']
            found = [w for w in weather_words if w.lower() in message.lower()]
            print(f'🔍 Weather indicators found: {found}')
        else:
            print('❌ No response')
    else:
        print('❌ Failed to connect')
    
    await interface.close()

if __name__ == "__main__":
    asyncio.run(test_timing()) 