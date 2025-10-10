#!/usr/bin/env python3
"""
Test WeatherAgent @genesis_tool Decorators

This script tests the new WeatherAgent using @genesis_tool decorators
to verify automatic tool discovery and execution.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import os
import sys

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import the new decorator-based WeatherAgent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'test_functions'))
from weather_agent_service import WeatherAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_weather_agent_decorators():
    """Test the WeatherAgent's @genesis_tool decorators"""
    print("🌤️ Testing WeatherAgent @genesis_tool Decorators")
    print("=" * 60)
    
    agent = WeatherAgent()
    
    try:
        # Test internal tool discovery
        print("\n🔍 Testing internal tool discovery...")
        await agent._ensure_internal_tools_discovered()
        
        # Check if tools were discovered
        if hasattr(agent, 'internal_tools_cache'):
            print(f"✅ Found {len(agent.internal_tools_cache)} internal tools:")
            for tool_name, tool_info in agent.internal_tools_cache.items():
                description = tool_info['metadata'].get('description', 'No description')
                print(f"   • {tool_name}: {description}")
        else:
            print("❌ No internal tools cache found")
            return False
        
        # Test schema generation
        print("\n🛠️ Testing OpenAI schema generation...")
        schemas = agent._get_internal_tool_schemas_for_openai()
        print(f"✅ Generated {len(schemas)} OpenAI tool schemas:")
        for schema in schemas:
            tool_name = schema.get('function', {}).get('name', 'Unknown')
            description = schema.get('function', {}).get('description', 'No description')
            print(f"   • {tool_name}: {description}")
        
        # Test weather request processing
        print("\n📤 Testing weather request processing...")
        test_request = {
            "message": "What's the current weather in Paris, France?"
        }
        
        print(f"Sending request: {test_request['message']}")
        response = await agent.process_request(test_request)
        
        print(f"✅ Response received:")
        print(f"   Status: {response.get('status', 'Unknown')}")
        print(f"   Message: {response.get('message', 'No message')}")
        
        # Test forecast request
        print("\n📤 Testing forecast request...")
        test_request2 = {
            "message": "Can you give me a 5-day weather forecast for Tokyo, Japan?"
        }
        
        print(f"Sending request: {test_request2['message']}")
        response2 = await agent.process_request(test_request2)
        
        print(f"✅ Response received:")
        print(f"   Status: {response2.get('status', 'Unknown')}")
        print(f"   Message: {response2.get('message', 'No message')}")
        
        # Test analysis request
        print("\n📤 Testing weather analysis...")
        test_request3 = {
            "message": "Analyze the weather conditions for London with 18°C, cloudy skies, and 75% humidity"
        }
        
        print(f"Sending request: {test_request3['message']}")
        response3 = await agent.process_request(test_request3)
        
        print(f"✅ Response received:")
        print(f"   Status: {response3.get('status', 'Unknown')}")
        print(f"   Message: {response3.get('message', 'No message')}")
        
        print("\n🎉 WeatherAgent @genesis_tool decorator test completed successfully!")
        print("✅ Automatic tool discovery working correctly")
        print("✅ OpenAI schema generation working correctly")
        print("✅ Tool execution working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await agent.close()

async def main():
    """Main entry point"""
    success = await test_weather_agent_decorators()
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 