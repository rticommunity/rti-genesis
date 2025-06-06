#!/usr/bin/env python3
"""
Test Agent-to-Agent Discovery

This script tests whether PersonalAssistant is discovering WeatherAgent
as an available tool in its agent cache.
"""

import asyncio
import logging
import sys
import os
import time

# Add the project root to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from genesis_lib.monitored_interface import MonitoredInterface

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_agent_discovery():
    """Test if agents are discovering each other"""
    
    # Create interface to connect to PersonalAssistant
    interface = MonitoredInterface(interface_name="AgentDiscoveryTester", service_name="OpenAIAgent")
    
    try:
        logger.info("🔍 Waiting for agent discovery...")
        await asyncio.sleep(5)
        
        logger.info(f"📊 Interface discovered {len(interface.available_agents)} agents:")
        
        personal_assistant_id = None
        weather_agent_id = None
        
        for agent_id, agent_info in interface.available_agents.items():
            agent_name = agent_info.get('prefered_name', 'Unknown')
            service_name = agent_info.get('service_name', 'Unknown')
            
            logger.info(f"  🤖 {agent_name} ({service_name}) - {agent_id[:12]}...")
            
            if 'personal' in agent_name.lower():
                personal_assistant_id = agent_id
            elif 'weather' in agent_name.lower() or 'weather' in service_name.lower():
                weather_agent_id = agent_id
        
        if not personal_assistant_id:
            logger.error("❌ PersonalAssistant not found!")
            return False
            
        if not weather_agent_id:
            logger.error("❌ WeatherAgent not found!")
            return False
        
        logger.info("✅ Both agents found by interface")
        
        # Now test if PersonalAssistant can discover and call WeatherAgent
        logger.info("🔗 Connecting to PersonalAssistant...")
        success = await interface.connect_to_agent("OpenAIAgent")
        
        if not success:
            logger.error("❌ Failed to connect to PersonalAssistant")
            return False
        
        logger.info("✅ Connected to PersonalAssistant")
        
        # Test 1: Simple weather query that should trigger agent-to-agent call
        logger.info("🌤️ Testing weather query: 'What's the weather in Denver?'")
        
        response = await interface.send_request({
            "message": "What's the weather in Denver?",
            "conversation_id": f"test_weather_{int(time.time())}"
        })
        
        if not response or response.get('status') != 0:
            logger.error("❌ Failed to get response from PersonalAssistant")
            return False
        
        response_text = response.get('message', '')
        logger.info(f"📥 Response: {response_text[:200]}{'...' if len(response_text) > 200 else ''}")
        
        # Check if response contains weather-specific info (indicating agent-to-agent call worked)
        weather_indicators = [
            'temperature', 'degrees', 'weather', 'sunny', 'cloudy', 'rain',
            'humidity', 'wind', 'pressure', 'forecast'
        ]
        
        found_indicators = [word for word in weather_indicators if word.lower() in response_text.lower()]
        
        if found_indicators:
            logger.info(f"✅ Weather data found in response: {found_indicators}")
            logger.info("🎉 Agent-to-agent communication appears to be working!")
            return True
        else:
            logger.warning("⚠️ No weather data in response - agent-to-agent communication may not be working")
            logger.warning("Response suggests PersonalAssistant is not calling WeatherAgent")
            return False
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False
    
    finally:
        await interface.close()

async def main():
    """Main test function"""
    logger.info("🧪 Testing Agent-to-Agent Discovery and Communication")
    logger.info("=" * 60)
    
    success = await test_agent_discovery()
    
    if success:
        logger.info("🎉 Agent-to-Agent test PASSED!")
        return 0
    else:
        logger.error("❌ Agent-to-Agent test FAILED!")
        logger.error("PersonalAssistant is NOT discovering or calling WeatherAgent")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 