#!/usr/bin/env python3
"""
Test Enhanced Agent Capability Advertisement
This test verifies that agents can advertise rich capability information for classification.

Usage:
Terminal 1: python test_functions/test_enhanced_capabilities.py weather
Terminal 2: python test_functions/test_enhanced_capabilities.py general
"""

import asyncio
import sys
import os
import time
import logging

# Add the parent directory to the path so we can import genesis_lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.monitored_agent import MonitoredAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WeatherSpecialistAgent(MonitoredAgent):
    """Specialized agent for weather-related queries"""
    
    def __init__(self):
        super().__init__(
            agent_name="WeatherExpert",
            base_service_name="WeatherService",
            agent_type="SPECIALIZED_AGENT",
            agent_id="weather_specialist",
            description="Specialized weather forecasting and climate analysis agent",
            enable_agent_communication=True
        )
    
    def get_agent_capabilities(self):
        """Define weather-specific capabilities"""
        return {
            "agent_type": "specialized",
            "specializations": ["weather", "meteorology", "climate"],
            "capabilities": [
                "current_weather",
                "weather_forecast", 
                "weather_alerts",
                "temperature_analysis",
                "precipitation_forecast",
                "historical_weather"
            ],
            "classification_tags": [
                "weather", "temperature", "forecast", "rain", "snow", 
                "storm", "climate", "humidity", "wind", "pressure",
                "sunny", "cloudy", "precipitation", "conditions"
            ],
            "model_info": None,  # Not an LLM-based agent
            "default_capable": False,  # Only handles weather queries
            "performance_metrics": {
                "avg_response_time": "2-3 seconds",
                "accuracy": "Real-time meteorological data",
                "data_sources": ["OpenWeatherMap", "NOAA"]
            }
        }
    
    async def process_agent_request(self, request):
        message = request.get('message', '')
        
        # Simple weather processing simulation
        if any(word in message.lower() for word in ['weather', 'temperature', 'rain', 'sunny', 'forecast']):
            return {
                'message': f"Weather Expert: Based on current meteorological data, {message} - Today will be partly cloudy with a temperature of 22°C",
                'status': 0,
                'specialization': 'weather'
            }
        else:
            return {
                'message': "Weather Expert: I specialize in weather queries. Please ask about weather, temperature, or forecasts.",
                'status': -1,
                'specialization': 'weather'
            }

class GeneralPurposeAgent(MonitoredAgent):
    """General purpose agent that can handle many types of requests"""
    
    def __init__(self):
        super().__init__(
            agent_name="GeneralAssistant",
            base_service_name="GeneralService",
            agent_type="AGENT",
            agent_id="general_assistant",
            description="General purpose AI assistant for various tasks",
            enable_agent_communication=True
        )
    
    def get_agent_capabilities(self):
        """Define general agent capabilities"""
        return {
            "agent_type": "general",
            "specializations": ["general_assistance", "reasoning", "analysis"],
            "capabilities": [
                "general_assistance",
                "question_answering", 
                "text_analysis",
                "reasoning",
                "problem_solving",
                "task_coordination"
            ],
            "classification_tags": [
                "general", "assistant", "ai", "help", "question",
                "analysis", "reasoning", "problem", "task", "coordination"
            ],
            "model_info": {
                "model": "claude-3-opus",
                "context_length": 200000,
                "capabilities": ["text", "code", "analysis"]
            },
            "default_capable": True,  # Can handle any request
            "performance_metrics": {
                "avg_response_time": "1-2 seconds",
                "reasoning_capabilities": "Advanced",
                "knowledge_cutoff": "2024"
            }
        }
    
    async def process_agent_request(self, request):
        message = request.get('message', '')
        
        # Check if this should be routed to a weather specialist
        if any(word in message.lower() for word in ['weather', 'temperature', 'rain', 'forecast']):
            # Try to find weather specialist
            discovered = self.get_discovered_agents()
            weather_agents = [aid for aid, info in discovered.items() 
                            if 'weather' in info.get('specializations', [])]
            
            if weather_agents:
                weather_agent_id = weather_agents[0]
                logger.info(f"Routing weather query to specialist: {weather_agent_id}")
                
                response = await self.send_agent_request_monitored(
                    target_agent_id=weather_agent_id,
                    message=message,
                    timeout_seconds=5.0
                )
                
                if response and response.get('status') == 0:
                    return {
                        'message': f"[Routed to Weather Expert] {response['message']}",
                        'status': 0,
                        'routed_to': weather_agent_id
                    }
        
        # Handle locally
        return {
            'message': f"General Assistant: I can help with {message}. This is a general response demonstrating my capabilities.",
            'status': 0,
            'specialization': 'general'
        }

async def run_weather_agent():
    """Run Weather Specialist Agent"""
    print("=== Starting Weather Specialist Agent ===")
    agent = WeatherSpecialistAgent()
    
    print("Weather Agent: Running as weather specialist...")
    print("Weather Agent: Press Ctrl+C to stop")
    
    await agent.run()

async def run_general_agent():
    """Run General Purpose Agent"""
    print("=== Starting General Purpose Agent ===")
    agent = GeneralPurposeAgent()
    
    # Wait for weather agent to be discoverable
    print("General Agent: Waiting for Weather Agent to be discoverable...")
    weather_found = await agent.wait_for_agent("weather_specialist", timeout_seconds=15)
    
    if weather_found:
        print("✅ General Agent: Found Weather Specialist!")
        
        # Show discovered agents with their capabilities
        discovered = agent.get_discovered_agents()
        for agent_id, info in discovered.items():
            print(f"📊 Discovered: {info['name']} ({agent_id})")
            print(f"   Type: {info['agent_type']}")
            print(f"   Specializations: {info.get('specializations', [])}")
            print(f"   Capabilities: {info.get('capabilities', [])}")
            print(f"   Default Capable: {info.get('default_capable', False)}")
        
        # Test routing weather query to specialist
        try:
            print("\n🌤️ Testing weather query routing...")
            
            response = await agent.process_agent_request({
                'message': 'What is the weather forecast for today?',
                'conversation_id': 'test_weather_routing'
            })
            
            if response:
                print(f"✅ General Agent Response: {response['message']}")
                if 'routed_to' in response:
                    print(f"📡 Successfully routed to: {response['routed_to']}")
                    print("🎉 SUCCESS: Enhanced capability discovery and routing is working!")
                else:
                    print("ℹ️ Handled locally (no routing)")
            else:
                print("❌ General Agent: No response received")
                
        except Exception as e:
            print(f"❌ General Agent: Request failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ General Agent: Could not find Weather Specialist")
        print("Make sure Weather Agent is running in a separate terminal")
    
    print(f"\nGeneral Agent: Final discovered agents: {list(agent.get_discovered_agents().keys())}")
    await agent.close()

async def main():
    """Run agent based on command line argument"""
    
    if len(sys.argv) != 2 or sys.argv[1] not in ['weather', 'general']:
        print("Usage: python test_enhanced_capabilities.py [weather|general]")
        print("\nTo test enhanced capability advertisement:")
        print("1. Terminal 1: python test_enhanced_capabilities.py weather")
        print("2. Terminal 2: python test_enhanced_capabilities.py general")
        print("\nWeather Agent advertises specialized weather capabilities")
        print("General Agent discovers and routes weather queries to Weather Agent")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == 'weather':
        await run_weather_agent()
    elif mode == 'general':
        await run_general_agent()

if __name__ == "__main__":
    asyncio.run(main()) 