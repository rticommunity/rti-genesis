#!/usr/bin/env python3
"""
Test Enhanced Agent Discovery Methods
This test verifies the new capability-based discovery methods for agent-to-agent communication.

Usage:
Terminal 1: python test_functions/test_enhanced_discovery.py weather
Terminal 2: python test_functions/test_enhanced_discovery.py general
Terminal 3: python test_functions/test_enhanced_discovery.py test
"""

import asyncio
import sys
import os
import time
import logging
import json
from typing import Optional, List, Dict, Any

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
                "precipitation_forecast"
            ],
            "classification_tags": [
                "weather", "temperature", "forecast", "rain", "snow", 
                "storm", "climate", "humidity", "wind", "pressure"
            ],
            "model_info": {
                "type": "api_integration",
                "data_source": "OpenWeatherMap"
            },
            "default_capable": False,
            "performance_metrics": {
                "avg_response_time": 2.5,
                "accuracy_score": 95.0,
                "availability": 99.9
            }
        }
    
    async def process_agent_request(self, request):
        message = request.get('message', '')
        return {
            'message': f"Weather Expert: {message} - Current temperature is 22°C with partly cloudy skies",
            'status': 0,
            'specialization': 'weather'
        }

class FinanceSpecialistAgent(MonitoredAgent):
    """Specialized agent for financial queries"""
    
    def __init__(self):
        super().__init__(
            agent_name="FinanceExpert",
            base_service_name="FinanceService",
            agent_type="SPECIALIZED_AGENT",
            agent_id="finance_specialist",
            description="Specialized financial analysis and market data agent",
            enable_agent_communication=True
        )
    
    def get_agent_capabilities(self):
        """Define finance-specific capabilities"""
        return {
            "agent_type": "specialized",
            "specializations": ["finance", "economics", "trading"],
            "capabilities": [
                "stock_analysis",
                "market_data",
                "portfolio_optimization",
                "risk_assessment"
            ],
            "classification_tags": [
                "finance", "stocks", "trading", "economics", "market", 
                "portfolio", "investment", "risk", "analysis"
            ],
            "model_info": {
                "type": "ai_model",
                "model": "finance-gpt-4"
            },
            "default_capable": False,
            "performance_metrics": {
                "avg_response_time": 1.8,
                "accuracy_score": 92.0,
                "availability": 98.5
            }
        }
    
    async def process_agent_request(self, request):
        message = request.get('message', '')
        return {
            'message': f"Finance Expert: {message} - Current market analysis shows stable trends",
            'status': 0,
            'specialization': 'finance'
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
                "problem_solving"
            ],
            "classification_tags": [
                "general", "assistant", "ai", "help", "question",
                "analysis", "reasoning", "problem", "task"
            ],
            "model_info": {
                "type": "ai_model",
                "model": "claude-3-opus",
                "context_length": 200000
            },
            "default_capable": True,
            "performance_metrics": {
                "avg_response_time": 1.2,
                "accuracy_score": 88.0,
                "availability": 99.5
            }
        }
    
    async def process_agent_request(self, request):
        message = request.get('message', '')
        return {
            'message': f"General Assistant: I can help with {message}",
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

async def run_finance_agent():
    """Run Finance Specialist Agent"""
    print("=== Starting Finance Specialist Agent ===")
    agent = FinanceSpecialistAgent()
    
    print("Finance Agent: Running as finance specialist...")
    print("Finance Agent: Press Ctrl+C to stop")
    
    await agent.run()

async def run_general_agent():
    """Run General Purpose Agent"""
    print("=== Starting General Purpose Agent ===")
    agent = GeneralPurposeAgent()
    
    print("General Agent: Running as general assistant...")
    print("General Agent: Press Ctrl+C to stop")
    
    await agent.run()

async def test_discovery_methods():
    """Test the enhanced discovery methods"""
    print("=== Testing Enhanced Discovery Methods ===")
    
    # Create a test agent with agent communication
    test_agent = GeneralPurposeAgent()
    
    print("🔍 Waiting for other agents to be discovered...")
    await asyncio.sleep(8)  # Wait for agents to discover each other
    
    discovered = test_agent.get_discovered_agents()
    print(f"📊 Total discovered agents: {len(discovered)}")
    
    if len(discovered) == 0:
        print("⚠️  No agents discovered. Make sure other agents are running.")
        return
    
    # Show all discovered agents
    print("\n📋 All Discovered Agents:")
    for agent_id, info in discovered.items():
        print(f"  • {info['name']} ({agent_id})")
        print(f"    Type: {info.get('agent_type', 'unknown')}")
        print(f"    Default Capable: {info.get('default_capable', 'unknown')}")
    
    print("\n🧪 Testing Enhanced Discovery Methods:")
    
    # Test 1: Find agents by capability
    print("\n1. Testing find_agents_by_capability():")
    weather_forecast_agents = test_agent.find_agents_by_capability("weather_forecast")
    print(f"   Agents with 'weather_forecast' capability: {weather_forecast_agents}")
    
    stock_analysis_agents = test_agent.find_agents_by_capability("stock_analysis") 
    print(f"   Agents with 'stock_analysis' capability: {stock_analysis_agents}")
    
    general_assistance_agents = test_agent.find_agents_by_capability("general_assistance")
    print(f"   Agents with 'general_assistance' capability: {general_assistance_agents}")
    
    # Test 2: Find agents by specialization
    print("\n2. Testing find_agents_by_specialization():")
    weather_specialists = test_agent.find_agents_by_specialization("weather")
    print(f"   Weather specialists: {weather_specialists}")
    
    finance_specialists = test_agent.find_agents_by_specialization("finance")
    print(f"   Finance specialists: {finance_specialists}")
    
    reasoning_specialists = test_agent.find_agents_by_specialization("reasoning")
    print(f"   Reasoning specialists: {reasoning_specialists}")
    
    # Test 3: Find general vs specialized agents
    print("\n3. Testing find_general_agents() and find_specialized_agents():")
    general_agents = test_agent.find_general_agents()
    print(f"   General agents (default_capable=True): {general_agents}")
    
    specialized_agents = test_agent.find_specialized_agents()
    print(f"   Specialized agents (default_capable=False): {specialized_agents}")
    
    # Test 4: Find agents by performance metrics
    print("\n4. Testing get_agents_by_performance_metric():")
    fast_agents = test_agent.get_agents_by_performance_metric("avg_response_time", max_value=2.0)
    print(f"   Fast agents (response time ≤ 2.0s): {fast_agents}")
    
    accurate_agents = test_agent.get_agents_by_performance_metric("accuracy_score", min_value=90.0)
    print(f"   Accurate agents (accuracy ≥ 90.0): {accurate_agents}")
    
    # Test 5: Find agents by model type
    print("\n5. Testing get_agents_by_model_type():")
    claude_agents = test_agent.get_agents_by_model_type("claude")
    print(f"   Agents using Claude models: {claude_agents}")
    
    gpt_agents = test_agent.get_agents_by_model_type("gpt")
    print(f"   Agents using GPT models: {gpt_agents}")
    
    # Test 6: Get detailed info by capability
    print("\n6. Testing get_agent_info_by_capability():")
    weather_agent_info = test_agent.get_agent_info_by_capability("weather_forecast")
    print(f"   Weather forecast agents info:")
    for info in weather_agent_info:
        print(f"     • {info['name']}: {info.get('description', 'No description')}")
    
    # Test 7: Test classifier integration (if available)
    print("\n7. Testing get_best_agent_for_request():")
    if hasattr(test_agent, 'agent_classifier') and test_agent.agent_classifier:
        best_for_weather = await test_agent.get_best_agent_for_request("What's the weather forecast?")
        print(f"   Best agent for weather query: {best_for_weather}")
        
        best_for_finance = await test_agent.get_best_agent_for_request("What are the stock prices?")
        print(f"   Best agent for finance query: {best_for_finance}")
    else:
        print("   Agent classifier not available for testing")
    
    print("\n✅ Enhanced Discovery Methods Test Complete!")
    
    # Keep running briefly to see if we can send requests
    print("\n🔗 Testing agent communication...")
    if weather_specialists:
        try:
            response = await test_agent.send_agent_request_monitored(
                target_agent_id=weather_specialists[0],
                message="What's the current weather?",
                timeout_seconds=5.0
            )
            if response:
                print(f"   Weather response: {response.get('message', 'No message')}")
            else:
                print("   No response from weather agent")
        except Exception as e:
            print(f"   Error communicating with weather agent: {e}")
    
    await test_agent.close()

# Note: The get_agents_by_performance_metric method is now properly implemented 
# in the AgentCommunicationMixin and delegated through GenesisAgent

async def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print("Usage: python test_functions/test_enhanced_discovery.py [weather|finance|general|test]")
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    
    try:
        if mode == "weather":
            await run_weather_agent()
        elif mode == "finance":
            await run_finance_agent()
        elif mode == "general":
            await run_general_agent()
        elif mode == "test":
            await test_discovery_methods()
        else:
            print("Invalid mode. Use: weather, finance, general, or test")
            sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{mode.title()} agent shutting down...")
    except Exception as e:
        print(f"Error in {mode} mode: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 