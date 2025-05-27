#!/usr/bin/env python3
"""
Simple test: Ask the weather agent directly about Monument, Colorado
"""

import os
import asyncio
import sys
sys.path.insert(0, '.')
from examples.weather_agent.real_weather_agent import RealWeatherAgent

async def simple_weather_test():
    print('🌤️ Simple Weather Test: Monument, Colorado')
    
    # Set working API key
    os.environ['OPENWEATHERMAP_API_KEY'] = "bd5e378503939ddaee76f12ad7a97608"
    
    # Create weather agent
    agent = RealWeatherAgent()
    
    # Simple, direct request
    request = {
        'message': 'weather Monument Colorado',
        'conversation_id': 'simple_test'
    }
    
    print(f'📨 Request: {request["message"]}')
    
    try:
        response = await agent.process_agent_request(request)
        print(f'🌡️ Response: {response["message"]}')
        
    except Exception as e:
        print(f'❌ Error: {e}')
    finally:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(simple_weather_test()) 