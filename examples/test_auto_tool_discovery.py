#!/usr/bin/env python3
"""
Test Auto Tool Discovery

This script tests the new @genesis_tool decorator functionality
by creating an agent, discovering its tools, and making a direct request
to demonstrate automatic tool injection and execution.

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

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestAutoToolAgent(OpenAIGenesisAgent):
    """
    Test agent for demonstrating automatic tool discovery.
    """
    
    def __init__(self):
        super().__init__(
            model_name="gpt-4o",
            agent_name="TestAutoToolAgent",
            description="Test agent for auto tool discovery",
            enable_tracing=True  # Enable for debugging
        )
        print("✅ TestAutoToolAgent initialized")

    @genesis_tool(description="Add two numbers together")
    def add_numbers(self, a: int, b: int) -> int:
        """
        Add two numbers and return the result.
        
        Args:
            a: First number to add
            b: Second number to add
        
        Returns:
            The sum of a and b
        """
        print(f"🧮 Adding {a} + {b}")
        return a + b

    @genesis_tool(description="Get weather information for a location")
    async def get_weather(self, location: str) -> dict:
        """
        Get mock weather information for a location.
        
        Args:
            location: The city name
        
        Returns:
            Weather data dictionary
        """
        print(f"🌤️ Getting weather for {location}")
        return {
            "location": location,
            "temperature": 22,
            "description": "sunny",
            "humidity": 65
        }

    @genesis_tool(description="Analyze text and return word count")
    def analyze_text(self, text: str) -> dict:
        """
        Analyze text and return statistics.
        
        Args:
            text: Text to analyze
        
        Returns:
            Analysis results
        """
        print(f"📝 Analyzing text: {text[:50]}...")
        words = text.split()
        return {
            "word_count": len(words),
            "character_count": len(text),
            "first_word": words[0] if words else "",
            "last_word": words[-1] if words else ""
        }

async def test_auto_tool_discovery():
    """Test the automatic tool discovery functionality"""
    print("🧪 Testing Automatic Tool Discovery")
    print("=" * 50)
    
    # Create test agent
    agent = TestAutoToolAgent()
    
    try:
        # Test internal tool discovery
        print("\n🔍 Testing internal tool discovery...")
        await agent._ensure_internal_tools_discovered()
        
        # Check if tools were discovered
        if hasattr(agent, 'internal_tools_cache'):
            print(f"✅ Found {len(agent.internal_tools_cache)} internal tools:")
            for tool_name, tool_info in agent.internal_tools_cache.items():
                print(f"   • {tool_name}: {tool_info['metadata'].get('description', 'No description')}")
        else:
            print("❌ No internal tools cache found")
            return False
        
        # Test schema generation
        print("\n🛠️ Testing schema generation...")
        schemas = agent._get_internal_tool_schemas_for_openai()
        print(f"✅ Generated {len(schemas)} OpenAI tool schemas:")
        for schema in schemas:
            tool_name = schema.get('function', {}).get('name', 'Unknown')
            print(f"   • {tool_name}")
        
        # Test a simple request that should use internal tools
        print("\n📤 Testing request processing with internal tools...")
        test_request = {
            "message": "Add 15 and 27 together"
        }
        
        print(f"Sending request: {test_request['message']}")
        response = await agent.process_request(test_request)
        
        print(f"✅ Response received:")
        print(f"   Status: {response.get('status', 'Unknown')}")
        print(f"   Message: {response.get('message', 'No message')}")
        
        # Test another request
        print("\n📤 Testing another request...")
        test_request2 = {
            "message": "What's the weather like in Tokyo?"
        }
        
        print(f"Sending request: {test_request2['message']}")
        response2 = await agent.process_request(test_request2)
        
        print(f"✅ Response received:")
        print(f"   Status: {response2.get('status', 'Unknown')}")
        print(f"   Message: {response2.get('message', 'No message')}")
        
        print("\n🎉 Auto tool discovery test completed successfully!")
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
    success = await test_auto_tool_discovery()
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 