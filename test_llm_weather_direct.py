#!/usr/bin/env python3
"""
Direct test of LLM Weather Agent to demonstrate natural language processing
"""

import asyncio
import sys
import json
sys.path.append('.')
from genesis_lib.interface import GenesisInterface

async def test_llm_weather_agent():
    """Test the LLM weather agent directly to show natural language processing"""
    
    print("🎯 TESTING: LLM Natural Language Processing in Weather Agent")
    print("=" * 70)
    
    # Create interface to connect to weather agent
    interface = GenesisInterface(
        interface_name="WeatherTestInterface", 
        service_name="WeatherService"
    )
    
    try:
        print("🔌 Connecting to weather agent...")
        success = await interface.connect_to_agent("WeatherService")
        
        if not success:
            print("❌ Could not connect to weather agent")
            return
            
        print("✅ Connected to weather agent!")
        print()
        
        # Test cases showing LLM understanding complex natural language
        test_cases = [
            {
                "input": "What's the weather like in Tokyo right now?",
                "description": "Simple current weather query"
            },
            {
                "input": "Can you tell me if it's going to rain in London tomorrow?",
                "description": "Future weather with specific condition"
            },
            {
                "input": "I'm planning a trip to Paris next week. What should I expect weather-wise?",
                "description": "Conversational planning context"
            },
            {
                "input": "How hot is it in Phoenix today?",
                "description": "Specific temperature inquiry"
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"🧪 TEST {i}: {test_case['description']}")
            print(f"   Input: \"{test_case['input']}\"")
            
            # Send request to weather agent
            request_data = {
                "message": test_case['input'],
                "conversation_id": f"test_{i}"
            }
            
            print("   🤖 LLM Processing...")
            response = await interface.send_request(request_data, timeout_seconds=15.0)
            
            if response:
                print(f"   ✅ LLM Response received:")
                if isinstance(response, dict) and 'message' in response:
                    # Pretty print the message part
                    message = response['message']
                    print(f"      Message: {message[:200]}{'...' if len(message) > 200 else ''}")
                else:
                    print(f"      Full Response: {str(response)[:200]}{'...' if len(str(response)) > 200 else ''}")
                    
                # Check if it looks like real LLM processing (not just error messages)
                response_str = str(response).lower()
                if any(word in response_str for word in ['weather', 'temperature', 'degrees', 'celsius', 'fahrenheit', 'forecast']):
                    print("   🎯 ✅ LLM correctly identified weather-related content!")
                else:
                    print("   ⚠️  Response doesn't appear weather-related")
            else:
                print("   ❌ No response from agent")
            
            print()
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("🧹 Cleaning up...")
        await interface.close()

if __name__ == "__main__":
    asyncio.run(test_llm_weather_agent()) 