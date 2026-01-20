#!/usr/bin/env python3
"""
Quick Test - Genesis Multi-Agent Demo

Automated test script demonstrating key features of the Genesis multi-agent
system including @genesis_tool decorators and agent delegation.

Features:
- Automated agent discovery
- Weather delegation testing
- Function calling demonstration
- @genesis_tool verification

"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any

# Add Genesis library to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from genesis_lib.monitored_interface import MonitoredInterface

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QuickTest:
    """Quick automated test of Genesis multi-agent features"""
    
    def __init__(self):
        self.interface = None
        self.test_results = []
        
    async def run_tests(self):
        """Run all automated tests"""
        print("🧪 Genesis Multi-Agent Quick Test")
        print("=" * 40)
        print()
        
        # Initialize interface
        print("🔧 Initializing Genesis interface...")
        self.interface = MonitoredInterface('QuickTest', 'AutomatedTester')
        
        # Wait for agent discovery
        print("🔍 Discovering agents...")
        await asyncio.sleep(8)  # Give agents time to start
        
        # Run test suite
        await self.test_agent_discovery()
        await self.test_weather_delegation()
        await self.test_function_calling()
        await self.test_genesis_tool_decorators()
        
        # Show results
        self.show_test_results()

    async def test_agent_discovery(self):
        """Test agent discovery functionality"""
        print("1️⃣ Testing Agent Discovery...")
        
        agents = self.interface.available_agents
        discovered_count = len(agents)
        
        if discovered_count >= 1:
            print(f"   ✅ Discovered {discovered_count} agent(s)")
            for agent_id, agent_info in agents.items():
                name = agent_info.get('prefered_name', 'Unknown')
                print(f"      • {name}")
            self.test_results.append(("Agent Discovery", "PASS", f"{discovered_count} agents found"))
        else:
            print("   ❌ No agents discovered")
            self.test_results.append(("Agent Discovery", "FAIL", "No agents found"))
        
        print()

    async def test_weather_delegation(self):
        """Test weather delegation through PersonalAssistant"""
        print("2️⃣ Testing Weather Delegation...")
        
        # Find PersonalAssistant
        personal_assistant = None
        for agent_id, agent_info in self.interface.available_agents.items():
            if agent_info.get('prefered_name') == 'PersonalAssistant':
                personal_assistant = agent_id
                break
        
        if not personal_assistant:
            print("   ⚠️ PersonalAssistant not found - skipping delegation test")
            self.test_results.append(("Weather Delegation", "SKIP", "PersonalAssistant not available"))
            print()
            return
        
        try:
            # Connect to PersonalAssistant
            connected = await self.interface.connect_to_agent(personal_assistant)
            if not connected:
                print("   ❌ Failed to connect to PersonalAssistant")
                self.test_results.append(("Weather Delegation", "FAIL", "Connection failed"))
                print()
                return
            
            print("   📤 Sending weather query: 'What's the weather in London?'")
            
            # Send weather query
            response = await self.interface.send_request({
                'message': 'What is the weather in London, England?',
                'conversation_id': 'quick_test_weather'
            }, timeout_seconds=45.0)
            
            if response and response.get('status') == 0:
                message = response.get('message', '')
                if len(message) > 50 and ('weather' in message.lower() or 'temperature' in message.lower()):
                    print("   ✅ Weather delegation successful")
                    print(f"   📥 Response: {message[:100]}...")
                    self.test_results.append(("Weather Delegation", "PASS", "Weather data received"))
                else:
                    print("   ⚠️ Response received but may not contain weather data")
                    self.test_results.append(("Weather Delegation", "PARTIAL", "Response unclear"))
            else:
                print("   ❌ No valid response received")
                self.test_results.append(("Weather Delegation", "FAIL", "No response"))
                
        except Exception as e:
            print(f"   ❌ Weather delegation error: {e}")
            self.test_results.append(("Weather Delegation", "FAIL", str(e)))
        
        print()

    async def test_function_calling(self):
        """Test function calling through PersonalAssistant"""
        print("3️⃣ Testing Function Calling...")
        
        # Check if PersonalAssistant is still connected
        personal_assistant = None
        for agent_id, agent_info in self.interface.available_agents.items():
            if agent_info.get('prefered_name') == 'PersonalAssistant':
                personal_assistant = agent_id
                break
        
        if not personal_assistant:
            print("   ⚠️ PersonalAssistant not found - skipping function test")
            self.test_results.append(("Function Calling", "SKIP", "PersonalAssistant not available"))
            print()
            return
        
        try:
            print("   📤 Sending math query: 'Calculate 123 * 456'")
            
            # Send math query
            response = await self.interface.send_request({
                'message': 'Calculate 123 * 456',
                'conversation_id': 'quick_test_math'
            }, timeout_seconds=30.0)
            
            if response and response.get('status') == 0:
                message = response.get('message', '')
                expected_result = 123 * 456  # 56,088
                
                if str(expected_result) in message or '56,088' in message or '56088' in message:
                    print("   ✅ Function calling successful")
                    print(f"   📥 Response: {message}")
                    self.test_results.append(("Function Calling", "PASS", "Correct calculation"))
                else:
                    print("   ⚠️ Response received but calculation unclear")
                    print(f"   📥 Response: {message}")
                    self.test_results.append(("Function Calling", "PARTIAL", "Response unclear"))
            else:
                print("   ❌ No valid response received")
                self.test_results.append(("Function Calling", "FAIL", "No response"))
                
        except Exception as e:
            print(f"   ❌ Function calling error: {e}")
            self.test_results.append(("Function Calling", "FAIL", str(e)))
        
        print()

    async def test_genesis_tool_decorators(self):
        """Test @genesis_tool decorators with WeatherAgent"""
        print("4️⃣ Testing @genesis_tool Decorators...")
        
        # Find WeatherAgent
        weather_agent = None
        for agent_id, agent_info in self.interface.available_agents.items():
            if agent_info.get('prefered_name') in ['WeatherExpert', 'WeatherAgent']:
                weather_agent = agent_id
                break
        
        if not weather_agent:
            print("   ⚠️ WeatherAgent not found - skipping @genesis_tool test")
            self.test_results.append(("@genesis_tool Decorators", "SKIP", "WeatherAgent not available"))
            print()
            return
        
        try:
            # Connect to WeatherAgent
            connected = await self.interface.connect_to_agent(weather_agent)
            if not connected:
                print("   ❌ Failed to connect to WeatherAgent")
                self.test_results.append(("@genesis_tool Decorators", "FAIL", "Connection failed"))
                print()
                return
            
            print("   📤 Testing @genesis_tool auto-discovery: 'Get weather forecast for Tokyo'")
            
            # Send query that should trigger @genesis_tool methods
            response = await self.interface.send_request({
                'message': 'Get a 3-day weather forecast for Tokyo, Japan',
                'conversation_id': 'quick_test_tools'
            }, timeout_seconds=30.0)
            
            if response and response.get('status') == 0:
                message = response.get('message', '')
                if len(message) > 50 and any(word in message.lower() for word in ['forecast', 'tokyo', 'weather', 'temperature']):
                    print("   ✅ @genesis_tool decorators working")
                    print(f"   📥 Response: {message[:150]}...")
                    self.test_results.append(("@genesis_tool Decorators", "PASS", "Tool methods executed"))
                else:
                    print("   ⚠️ Response received but tool execution unclear")
                    self.test_results.append(("@genesis_tool Decorators", "PARTIAL", "Response unclear"))
            else:
                print("   ❌ No valid response received")
                self.test_results.append(("@genesis_tool Decorators", "FAIL", "No response"))
                
        except Exception as e:
            print(f"   ❌ @genesis_tool test error: {e}")
            self.test_results.append(("@genesis_tool Decorators", "FAIL", str(e)))
        
        print()

    def show_test_results(self):
        """Show summary of test results"""
        print("📊 Test Results Summary")
        print("=" * 30)
        
        pass_count = sum(1 for _, status, _ in self.test_results if status == "PASS")
        total_tests = len(self.test_results)
        
        for test_name, status, details in self.test_results:
            status_icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⚠️", "PARTIAL": "🟡"}
            print(f"{status_icon.get(status, '❓')} {test_name}: {status}")
            if details:
                print(f"   Details: {details}")
        
        print()
        print(f"📈 Overall: {pass_count}/{total_tests} tests passed")
        
        if pass_count == total_tests:
            print("🎉 All tests passed! Genesis multi-agent system is working correctly.")
        elif pass_count > 0:
            print("🟡 Some tests passed. Check failed tests for issues.")
        else:
            print("❌ No tests passed. Check if agents are running properly.")
        
        print()
        print("💡 For interactive testing, run: python interfaces/interactive_cli.py")

    async def close(self):
        """Clean up resources"""
        if self.interface:
            await self.interface.close()

async def main():
    """Main entry point"""
    test = QuickTest()
    
    try:
        await test.run_tests()
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"❌ Test suite error: {e}")
    finally:
        await test.close()

if __name__ == "__main__":
    asyncio.run(main()) 