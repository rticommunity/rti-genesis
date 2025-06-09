#!/usr/bin/env python3
"""
Quick test to get weather in Monument, Colorado using the real weather agent
"""

import os
import asyncio
import sys
sys.path.insert(0, '.')
from examples.weather_agent.real_weather_agent import RealWeatherAgent

async def test_weather():
    print('🌤️ Testing Real Weather Agent for Monument, Colorado...')
    
    # Check API keys
    openweather_key = os.getenv('OPENWEATHERMAP_API_KEY')
    if openweather_key:
        print(f'✅ OpenWeatherMap API key found: {openweather_key[:8]}...')
    else:
        print('⚠️ No OpenWeatherMap API key - will use mock data')
    
    # Create weather agent
    agent = RealWeatherAgent()
    
    # Test weather request
    request = {
        'message': 'What is the weather in Monument, Colorado right now?',
        'conversation_id': 'test_monument_weather'
    }
    
    print(f'📨 Sending request: {request["message"]}')
    
    try:
        response = await agent.process_agent_request(request)
        print(f'🌡️ Weather Response: {response["message"]}')
        
        if 'metadata' in response:
            metadata = response['metadata']
            print(f'📍 Location: {metadata.get("location", "Unknown")}')
            print(f'🔍 Data Source: {metadata.get("data_source", "Unknown")}')
            print(f'⏰ Timestamp: {metadata.get("timestamp", "Unknown")}')
    
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(test_weather()) 