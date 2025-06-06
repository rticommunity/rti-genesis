#!/usr/bin/env python3
"""
Test Internal Tool Execution

This script specifically tests whether @genesis_tool decorated methods
are being called by OpenAI during request processing.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import os
import sys

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
from genesis_lib.decorators import genesis_tool

# Configure logging to capture debug messages
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ToolTestAgent(OpenAIGenesisAgent):
    """Agent for testing internal tool execution"""
    
    def __init__(self):
        super().__init__(
            model_name="gpt-4o",
            agent_name="ToolTestAgent",
            description="Agent for testing internal tool execution",
            enable_tracing=True,
            enable_agent_communication=False  # Disable to focus on internal tools
        )
        self.tool_call_log = []  # Track which tools are called

    @genesis_tool(description="Calculate the sum of two numbers")
    def calculate_sum(self, num1: int, num2: int) -> int:
        """
        Calculate the sum of two numbers.
        
        Args:
            num1: First number
            num2: Second number
            
        Returns:
            The sum of the two numbers
        """
        result = num1 + num2
        self.tool_call_log.append(f"calculate_sum({num1}, {num2}) = {result}")
        print(f"🧮 TOOL CALLED: calculate_sum({num1}, {num2}) = {result}")
        return result

    @genesis_tool(description="Get weather forecast for a city")
    async def get_weather_forecast(self, city: str) -> dict:
        """
        Get weather forecast for a specific city.
        
        Args:
            city: Name of the city
            
        Returns:
            Weather forecast data
        """
        forecast = {
            "city": city,
            "temperature": 22,
            "condition": "sunny",
            "humidity": 60,
            "wind_speed": 10
        }
        self.tool_call_log.append(f"get_weather_forecast({city})")
        print(f"🌤️ TOOL CALLED: get_weather_forecast({city})")
        return forecast

    @genesis_tool(description="Convert text to uppercase")
    def make_uppercase(self, text: str) -> str:
        """
        Convert text to uppercase.
        
        Args:
            text: Text to convert
            
        Returns:
            Uppercase version of the text
        """
        result = text.upper()
        self.tool_call_log.append(f"make_uppercase('{text}') = '{result}'")
        print(f"📝 TOOL CALLED: make_uppercase('{text}') = '{result}'")
        return result

async def test_internal_tool_execution():
    """Test that internal tools are actually executed by OpenAI"""
    print("🧪 Testing Internal Tool Execution")
    print("=" * 50)
    
    agent = ToolTestAgent()
    
    try:
        # Ensure internal tools are discovered
        await agent._ensure_internal_tools_discovered()
        print(f"✅ Discovered {len(agent.internal_tools_cache)} internal tools")
        
        # Test 1: Math calculation
        print("\n📤 Test 1: Math calculation")
        request1 = {"message": "What is 25 plus 17?"}
        print(f"Request: {request1['message']}")
        
        response1 = await agent.process_request(request1)
        print(f"Response: {response1.get('message', 'No response')}")
        print(f"Tool calls: {agent.tool_call_log}")
        
        # Reset log
        agent.tool_call_log = []
        
        # Test 2: Weather request
        print("\n📤 Test 2: Weather request")
        request2 = {"message": "What's the weather forecast for Paris?"}
        print(f"Request: {request2['message']}")
        
        response2 = await agent.process_request(request2)
        print(f"Response: {response2.get('message', 'No response')}")
        print(f"Tool calls: {agent.tool_call_log}")
        
        # Reset log
        agent.tool_call_log = []
        
        # Test 3: Text manipulation
        print("\n📤 Test 3: Text manipulation")
        request3 = {"message": "Convert 'hello world' to uppercase"}
        print(f"Request: {request3['message']}")
        
        response3 = await agent.process_request(request3)
        print(f"Response: {response3.get('message', 'No response')}")
        print(f"Tool calls: {agent.tool_call_log}")
        
        print("\n🎯 Test Summary:")
        print("If internal tools are working correctly, you should see:")
        print("1. 'TOOL CALLED:' messages during processing")
        print("2. Tool calls logged in the tool_call_log")
        print("3. OpenAI responses that reference the tool results")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await agent.close()

if __name__ == "__main__":
    success = asyncio.run(test_internal_tool_execution())
    sys.exit(0 if success else 1) 