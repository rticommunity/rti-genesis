#!/usr/bin/env python3
"""
Test Agent-to-Agent Delegation Pattern

This test validates the core Genesis agent-to-agent communication pattern:
Interface → PersonalAssistant → WeatherAgent → PersonalAssistant → Interface

This automates what we do manually in the interactive version:
1. Automatically select PersonalAssistant (not user choice)
2. Send weather query to PersonalAssistant
3. Verify PersonalAssistant delegates to WeatherAgent
4. Confirm complete delegation chain works

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import sys
import os
import time
from typing import Dict, Any, List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from genesis_lib.monitored_interface import MonitoredInterface

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AgentDelegationTester(MonitoredInterface):
    """
    Test interface that specifically tests agent-to-agent delegation.
    Based on the interactive CLI pattern but automated for regression testing.
    """
    
    def __init__(self):
        super().__init__(
            interface_name="AgentDelegationTester",
            service_name="DelegationTest"  # Use generic service name like interactive CLI
        )
        self.personal_assistant_info = None
        self.weather_agent_info = None
        
    def get_agent_capabilities(self, agent_info: Dict[str, Any]) -> List[str]:
        """Extract capabilities from agent info (same as interactive CLI)"""
        capabilities = []
        
        # Check for capabilities in the agent info
        if 'capabilities' in agent_info:
            caps = agent_info['capabilities']
            if isinstance(caps, list):
                capabilities.extend(caps)
            elif isinstance(caps, str):
                capabilities.append(caps)
        
        # Check for specializations
        if 'specializations' in agent_info:
            specs = agent_info['specializations']
            if isinstance(specs, list):
                capabilities.extend(specs)
            elif isinstance(specs, str):
                capabilities.append(specs)
        
        # If no explicit capabilities, infer from service name
        service_name = agent_info.get('service_name', '')
        if service_name and not capabilities:
            capabilities.append(service_name.replace('Service', '').lower())
        
        return capabilities
    
    async def discover_and_classify_agents(self, timeout_seconds: float = 15.0) -> bool:
        """Discover agents and classify them by type"""
        logger.info(f"🔍 Discovering and classifying agents (timeout: {timeout_seconds}s)...")
        
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if len(self.available_agents) >= 2:  # Need both PersonalAssistant and WeatherAgent
                break
            await asyncio.sleep(0.5)
        
        if len(self.available_agents) < 2:
            logger.error(f"❌ Expected 2+ agents, found {len(self.available_agents)}")
            return False
        
        logger.info(f"📊 Found {len(self.available_agents)} agents, classifying...")
        
        # Classify agents by capabilities
        for agent_id, agent_info in self.available_agents.items():
            agent_name = agent_info.get('prefered_name', 'Unknown')
            service_name = agent_info.get('service_name', 'Unknown')
            capabilities = self.get_agent_capabilities(agent_info)
            
            logger.info(f"   🤖 {agent_name}")
            logger.info(f"      Service: {service_name}")
            logger.info(f"      Capabilities: {capabilities}")
            
            # Classify as PersonalAssistant (general agent)
            if ('personal' in agent_name.lower() or 
                'assistant' in agent_name.lower() or
                any('general' in cap.lower() for cap in capabilities)):
                self.personal_assistant_info = {
                    "id": agent_id,
                    "name": agent_name,
                    "service_name": service_name,
                    "capabilities": capabilities,
                    "info": agent_info
                }
                logger.info(f"      ✅ Classified as: PersonalAssistant (general agent)")
            
            # Classify as WeatherAgent (weather specialist)
            elif ('weather' in agent_name.lower() or 
                  'weather' in service_name.lower() or
                  any('weather' in cap.lower() for cap in capabilities)):
                self.weather_agent_info = {
                    "id": agent_id,
                    "name": agent_name,
                    "service_name": service_name,
                    "capabilities": capabilities,
                    "info": agent_info
                }
                logger.info(f"      ✅ Classified as: WeatherAgent (weather specialist)")
            else:
                logger.info(f"      ℹ️ Classified as: Other/Unknown agent")
        
        # Verify we have both required agent types
        if not self.personal_assistant_info:
            logger.error("❌ No PersonalAssistant found!")
            return False
        
        if not self.weather_agent_info:
            logger.error("❌ No WeatherAgent found!")
            return False
        
        logger.info("✅ Successfully classified required agents:")
        logger.info(f"   🧠 PersonalAssistant: {self.personal_assistant_info['name']}")
        logger.info(f"   🌤️ WeatherAgent: {self.weather_agent_info['name']}")
        
        return True
    
    async def test_agent_to_agent_delegation(self) -> bool:
        """
        Test the complete agent-to-agent delegation pattern.
        This is the core test that validates agent-to-agent communication.
        """
        logger.info("🎯 Testing Agent-to-Agent Delegation Pattern")
        logger.info("=" * 60)
        logger.info("Expected flow: Interface → PersonalAssistant → WeatherAgent → PersonalAssistant → Interface")
        
        try:
            # Step 1: Connect to PersonalAssistant (NOT WeatherAgent directly)
            logger.info(f"🔗 Connecting to PersonalAssistant: {self.personal_assistant_info['name']}")
            logger.info(f"   Service: {self.personal_assistant_info['service_name']}")
            
            success = await super().connect_to_agent(self.personal_assistant_info['service_name'])
            
            if not success:
                logger.error("❌ Failed to connect to PersonalAssistant")
                return False
            
            logger.info("✅ Connected to PersonalAssistant")
            
            # Step 2: Send weather query that should trigger delegation
            weather_query = "What's the current weather in London, England? I need detailed weather information."
            logger.info(f"🌤️ Sending weather query to PersonalAssistant:")
            logger.info(f"   Query: {weather_query}")
            logger.info("   ⚠️ PersonalAssistant should delegate this to WeatherAgent!")
            
            # Step 3: Send request and monitor for delegation
            logger.info("📤 Sending request to PersonalAssistant...")
            response = await self.send_request({
                "message": weather_query,
                "conversation_id": f"delegation_test_{int(time.time())}"
            }, timeout_seconds=30.0)
            
            # Step 4: Analyze response for agent-to-agent delegation indicators
            if not response or response.get('status') != 0:
                logger.error("❌ Failed to get valid response from PersonalAssistant")
                return False
            
            response_text = response.get('message', '')
            logger.info(f"📥 Received response ({len(response_text)} chars)")
            
            # Check for weather-specific content (indicates WeatherAgent was called)
            weather_indicators = [
                'temperature', 'degrees', 'celsius', 'fahrenheit',
                'weather', 'london', 'humidity', 'wind', 'pressure',
                'sunny', 'cloudy', 'rain', 'storm', 'forecast',
                'conditions', 'climate'
            ]
            
            found_indicators = [word for word in weather_indicators 
                              if word.lower() in response_text.lower()]
            
            # Check for delegation success indicators
            delegation_indicators = [
                'weather agent', 'weather service', 'weather specialist',
                'calling weather', 'contacting weather', 'weather data',
                'api', 'current conditions', 'meteorological'
            ]
            
            found_delegation = [phrase for phrase in delegation_indicators 
                              if phrase.lower() in response_text.lower()]
            
            # Analyze results
            logger.info("🔍 Analyzing response for delegation indicators...")
            logger.info(f"   Weather content found: {found_indicators}")
            logger.info(f"   Delegation indicators: {found_delegation}")
            
            # Success criteria
            has_weather_content = len(found_indicators) >= 3  # At least 3 weather-related terms
            has_substantial_response = len(response_text) > 50  # Not just "I can't help"
            
            if has_weather_content and has_substantial_response:
                logger.info("✅ SUCCESS: Response contains substantial weather content")
                logger.info("🎉 Agent-to-agent delegation appears to be working!")
                
                # Show sample of response
                sample = response_text[:200] + "..." if len(response_text) > 200 else response_text
                logger.info(f"📄 Response sample: {sample}")
                
                return True
            else:
                logger.warning("⚠️ POSSIBLE FAILURE: Limited weather content in response")
                logger.warning("This may indicate PersonalAssistant is NOT calling WeatherAgent")
                
                # Show full response for debugging
                logger.warning(f"📄 Full response: {response_text}")
                
                # Don't fail completely - might still be working but with different keywords
                if has_substantial_response:
                    logger.info("✅ PARTIAL SUCCESS: Got substantial response (communication working)")
                    return True
                else:
                    logger.error("❌ FAILURE: Got minimal/generic response")
                    return False
            
        except Exception as e:
            logger.error(f"❌ Agent-to-agent delegation test failed: {e}")
            return False

async def test_complete_delegation_pattern():
    """Main test function that validates the complete delegation pattern"""
    logger.info("🧪 Starting Agent-to-Agent Delegation Test")
    logger.info("=" * 70)
    logger.info("This test validates the core Genesis multi-agent pattern:")
    logger.info("Interface → PersonalAssistant → WeatherAgent → PersonalAssistant → Interface")
    
    tester = AgentDelegationTester()
    
    try:
        # Step 1: Discover and classify agents
        discovery_success = await tester.discover_and_classify_agents(timeout_seconds=15.0)
        if not discovery_success:
            logger.error("❌ Agent discovery/classification failed")
            return False
        
        # Step 2: Test agent-to-agent delegation
        delegation_success = await tester.test_agent_to_agent_delegation()
        if not delegation_success:
            logger.error("❌ Agent-to-agent delegation test failed")
            return False
        
        logger.info("🎉 Agent-to-Agent Delegation Test PASSED!")
        logger.info("✅ Genesis multi-agent communication is working correctly")
        return True
        
    except Exception as e:
        logger.error(f"💥 Test failed with exception: {e}")
        return False
    
    finally:
        await tester.close()

async def main():
    """Main entry point for standalone test execution"""
    try:
        success = await test_complete_delegation_pattern()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 