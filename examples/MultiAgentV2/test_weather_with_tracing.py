#!/usr/bin/env python3
"""
Test script to verify weather agent discovery and agent-to-agent communication
"""

import asyncio
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from genesis_lib.monitored_interface import MonitoredInterface

class WeatherTestInterface(MonitoredInterface):
    """Test interface with agent discovery and connection methods"""
    
    def __init__(self):
        super().__init__(
            interface_name="WeatherTestInterface",
            service_name="OpenAIAgent"  # Connect to PersonalAssistant service
        )
        self.connected_agent_id = None
    
    async def wait_for_agent_discovery(self, timeout_seconds: float = 15.0) -> bool:
        """Wait for PersonalAssistant to be discovered"""
        print(f"🔍 Waiting for agent discovery (timeout: {timeout_seconds}s)...")
        
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if self.available_agents:
                agent_count = len(self.available_agents)
                print(f"✅ Found {agent_count} available agent(s):")
                for agent_id, agent_info in self.available_agents.items():
                    name = agent_info.get('prefered_name', 'Unknown')
                    service = agent_info.get('service_name', 'Unknown')
                    print(f"   - {name} ({service}) - ID: {agent_id}")
                return True
            
            await asyncio.sleep(0.5)
        
        print(f"❌ No agents found within {timeout_seconds} seconds")
        return False
    
    async def connect_to_agent(self) -> bool:
        """Connect to PersonalAssistant specifically"""
        if not self.available_agents:
            print("❌ No agents available for connection")
            return False
        
        # Find PersonalAssistant specifically
        personal_assistant_id = None
        for agent_id, agent_info in self.available_agents.items():
            name = agent_info.get('prefered_name', 'Unknown')
            if name == 'PersonalAssistant':
                personal_assistant_id = agent_id
                break
        
        if not personal_assistant_id:
            print("❌ PersonalAssistant not found in available agents")
            return False
        
        agent_info = self.available_agents[personal_assistant_id]
        
        try:
            name = agent_info.get('prefered_name', 'Unknown')
            service_name = agent_info.get('service_name', 'OpenAIAgent')
            
            print(f"🔗 Connecting specifically to PersonalAssistant: {name} ({personal_assistant_id})")
            print(f"   Service name: {service_name}")
            
            # Use Genesis built-in connection method with the EXACT service name from discovery
            success = await super().connect_to_agent(service_name)
            
            if success:
                print(f"✅ Successfully connected to PersonalAssistant: {name}")
                self.connected_agent_id = personal_assistant_id
                self._connected_agent_id = personal_assistant_id  # Also set internal tracking
                return True
            else:
                print(f"❌ Failed to connect to PersonalAssistant: {name}")
                return False
                
        except Exception as e:
            print(f"❌ Error connecting to PersonalAssistant {personal_assistant_id}: {e}")
            return False

async def test_weather_request():
    """Test weather request that should trigger agent-to-agent communication"""
    
    print("🧪 Starting Weather Request Test with Agent-to-Agent Communication")
    print("=" * 70)
    
    # Create interface with discovery methods
    interface = WeatherTestInterface()
    
    try:
        # Wait for agent discovery
        print("🔍 Waiting for PersonalAssistant discovery...")
        found = await interface.wait_for_agent_discovery(timeout_seconds=15.0)
        
        if not found:
            print("❌ PersonalAssistant not found!")
            return
        
        print("✅ PersonalAssistant discovered, connecting...")
        
        # Connect to PersonalAssistant
        connected = await interface.connect_to_agent()
        if not connected:
            print("❌ Failed to connect to PersonalAssistant!")
            return
        
        print("✅ Connected to PersonalAssistant")
        print()
        
        # Test weather request that should trigger delegation to WeatherAgent
        print("🌤️ Testing weather request (should delegate to WeatherAgent)...")
        
        weather_request = {
            "message": "What is the current weather in Denver, Colorado? I need detailed weather information.",
            "conversation_id": "weather_test_001"
        }
        
        print(f"📤 Sending: {weather_request['message']}")
        print()
        print("🔍 EXPECTED BEHAVIOR:")
        print("  1. PersonalAssistant should discover WeatherAgent in agent cache")
        print("  2. PersonalAssistant should create agent tools based on weather capabilities")
        print("  3. OpenAI should see weather-related tools available")
        print("  4. OpenAI should call WeatherAgent for weather query")
        print("  5. WeatherAgent should process weather request")
        print("  6. PersonalAssistant should return weather data")
        print()
        print("🔍 MONITORING AGENT COMMUNICATION...")
        print("-" * 50)
        
        # Send request with detailed timeout
        response = await interface.send_request(weather_request, timeout_seconds=30.0)
        
        print("-" * 50)
        print("🔍 RESPONSE ANALYSIS:")
        
        if response and response.get('status') == 0:
            message = response.get('message', '')
            print(f"✅ Response received (status: {response.get('status')})")
            print(f"📝 Message length: {len(message)} characters")
            
            # Check if response contains weather content
            weather_indicators = ['weather', 'temperature', 'denver', 'colorado', 'humidity', 'wind', 'pressure']
            weather_content = [word for word in weather_indicators if word.lower() in message.lower()]
            
            if weather_content:
                print(f"🌤️ Weather content detected: {weather_content}")
                print("✅ LIKELY SUCCESS: Response contains weather-related content")
            else:
                print("❌ LIKELY FAILURE: No weather content detected")
                print("💡 This suggests PersonalAssistant didn't call WeatherAgent")
            
            # Check for agent-to-agent communication indicators
            if 'weather agent' in message.lower() or 'weather service' in message.lower():
                print("🤝 Agent delegation detected in response")
            
            print()
            print(f"📄 Full Response: {message}")
            
        else:
            print(f"❌ Request failed!")
            print(f"📝 Response: {response}")
        
    finally:
        await interface.close()
        print()
        print("🧪 Test completed")

if __name__ == "__main__":
    asyncio.run(test_weather_request()) 