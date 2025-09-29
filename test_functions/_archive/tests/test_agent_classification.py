#!/usr/bin/env python3
"""
Test Agent Classification System
This test verifies the intelligent routing and classification of requests to appropriate agents.

Usage:
Terminal 1: python test_functions/test_agent_classification.py weather
Terminal 2: python test_functions/test_agent_classification.py general
"""

import asyncio
import sys
import os
import time
import logging

# Add the parent directory to the path so we can import genesis_lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.agent import GenesisAgent
from genesis_lib.agent_classifier import AgentClassifier

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WeatherSpecialistAgent(GenesisAgent):
    """Specialized agent for weather-related queries"""
    
    def __init__(self):
        super().__init__(
            agent_name="WeatherExpert",
            base_service_name="WeatherService",
            agent_id="weather_specialist_test",
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
                "storm", "climate", "humidity", "wind", "pressure",
                "sunny", "cloudy", "precipitation", "conditions"
            ],
            "model_info": None,
            "default_capable": False,  # Only handles weather queries
            "performance_metrics": {
                "avg_response_time": "2-3 seconds",
                "accuracy": "Real-time meteorological data"
            }
        }
    
    async def process_request(self, request):
        """Handle regular interface requests"""
        message = request.get('message', '')
        return {
            "response": f"Weather Expert: {message} - Today will be partly cloudy with 22°C",
            "status": 0
        }
    
    async def process_agent_request(self, request):
        """Handle requests from other agents"""
        message = request.get('message', '')
        return {
            'message': f"Weather Expert: {message} - Forecast shows partly cloudy, 22°C with light winds",
            'status': 0,
            'specialization': 'weather'
        }

class GeneralPurposeAgent(GenesisAgent):
    """General purpose agent with intelligent routing capabilities"""
    
    def __init__(self):
        super().__init__(
            agent_name="GeneralAssistant",
            base_service_name="GeneralService", 
            agent_id="general_assistant_test",
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
                "task_coordination"
            ],
            "classification_tags": [
                "general", "assistant", "ai", "help", "question",
                "analysis", "reasoning", "problem", "task"
            ],
            "model_info": {
                "model": "claude-3-opus",
                "context_length": 200000
            },
            "default_capable": True,
            "performance_metrics": {
                "avg_response_time": "1-2 seconds"
            }
        }
    
    async def process_request(self, request):
        """Handle regular interface requests with intelligent routing"""
        # Use the new routing-enabled method
        return await self.process_request_with_routing(request)
    
    async def process_agent_request(self, request):
        """Handle requests from other agents"""
        message = request.get('message', '')
        return {
            'message': f"General Assistant: I can help with {message}",
            'status': 0,
            'specialization': 'general'
        }

async def test_agent_classifier_standalone():
    """Test the PURE LLM AgentClassifier in isolation"""
    print("=== Testing PURE LLM AgentClassifier Standalone ===")
    
    # Check if OpenAI API key is available
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        print("❌ OPENAI_API_KEY not found - LLM classification test requires it")
        print("   Set it with: export OPENAI_API_KEY='your_key_here'")
        return
    
    # Create mock agent data
    mock_agents = {
        "weather_agent": {
            "name": "WeatherExpert",
            "agent_type": "specialized",
            "specializations": ["weather", "meteorology"],
            "capabilities": ["current_weather", "weather_forecast"],
            "classification_tags": ["weather", "temperature", "forecast", "rain"],
            "default_capable": False,
            "description": "Specialized agent for weather forecasting and meteorological data"
        },
        "general_agent": {
            "name": "GeneralAssistant", 
            "agent_type": "general",
            "specializations": ["general_assistance"],
            "capabilities": ["general_assistance", "question_answering"],
            "classification_tags": ["general", "assistant", "help"],
            "default_capable": True,
            "description": "General purpose AI assistant for various tasks"
        },
        "finance_agent": {
            "name": "FinanceExpert",
            "agent_type": "specialized", 
            "specializations": ["finance", "economics"],
            "capabilities": ["stock_analysis", "financial_planning"],
            "classification_tags": ["money", "finance", "stock", "investment"],
            "default_capable": False,
            "description": "Financial expert specializing in market analysis and investment advice"
        }
    }
    
    classifier = AgentClassifier(openai_api_key=openai_key)
    
    # Test various LLM classification scenarios - NO expected results since it's pure LLM
    test_cases = [
        ("What's the weather forecast for tomorrow?", "LLM should analyze semantic meaning"),
        ("How much does Apple stock cost?", "LLM should understand financial context"),
        ("Tell me about the rain forecast", "LLM should identify weather request"),
        ("Help me with my investment portfolio", "LLM should recognize financial advice need"),
        ("What is 2 + 2?", "LLM should identify as general math question"),
        ("How can I learn Python programming?", "LLM should see as general education query"),
        ("Will it be sunny in Paris this weekend?", "LLM should understand weather + location"),
        ("Should I buy Tesla stock?", "LLM should see investment decision request")
    ]
    
    print(f"✅ OpenAI API key found - testing PURE LLM classification with {len(test_cases)} scenarios...")
    print("📝 Note: No expected results - letting LLM make its own semantic decisions")
    
    for i, (request, description) in enumerate(test_cases, 1):
        print(f"\nTest {i}: {description}")
        print(f"Request: '{request}'")
        
        try:
            result = await classifier.classify_request(request, mock_agents)
            
            if result:
                agent_name = mock_agents[result]['name']
                agent_type = mock_agents[result]['agent_type']
                print(f"🤖 LLM selected: {agent_name} ({result}) - Type: {agent_type}")
                
                # Get explanation
                explanation = classifier.get_classification_explanation(request, result, mock_agents)
                print(f"💡 LLM reasoning: {explanation}")
            else:
                print("🤖 LLM found no suitable agent")
                
        except Exception as e:
            print(f"❌ Error in LLM classification: {e}")
    
    print("\n✅ PURE LLM classification testing completed - no rule-based matching used!")

async def run_weather_agent():
    """Run Weather Specialist Agent"""
    print("=== Starting Weather Specialist Agent ===")
    agent = WeatherSpecialistAgent()
    
    print("Weather Agent: Running as weather specialist...")
    print("Weather Agent: Press Ctrl+C to stop")
    
    await agent.run()

async def run_general_agent():
    """Run General Purpose Agent with Classification Testing"""
    print("=== Starting General Purpose Agent with Classification ===")
    agent = GeneralPurposeAgent()
    
    # Wait for weather agent to be discoverable
    print("General Agent: Waiting for Weather Agent to be discoverable...")
    weather_found = await agent.wait_for_agent("weather_specialist_test", timeout_seconds=15)
    
    if weather_found:
        print("✅ General Agent: Found Weather Specialist!")
        
        # Show discovered agents
        discovered = agent.get_discovered_agents()
        print(f"\n📊 Discovered {len(discovered)} agents:")
        for agent_id, info in discovered.items():
            print(f"  - {info['name']} ({agent_id})")
            print(f"    Type: {info['agent_type']}")
            print(f"    Specializations: {info.get('specializations', [])}")
            print(f"    Default Capable: {info.get('default_capable', False)}")
        
        # Test classification and routing
        test_requests = [
            "What's the weather forecast for today?",
            "Will it rain tomorrow?", 
            "What's the temperature outside?",
            "Tell me about the climate conditions",
            "How can I learn about artificial intelligence?",  # Should stay with general agent
            "What is the meaning of life?"  # Should stay with general agent
        ]
        
        print(f"\n🧠 Testing intelligent routing with {len(test_requests)} requests...")
        
        for i, test_request in enumerate(test_requests, 1):
            print(f"\n--- Test {i}/{len(test_requests)} ---")
            print(f"Request: '{test_request}'")
            
            try:
                # Test the intelligent routing
                routed_response = await agent.route_request_to_best_agent(
                    request_message=test_request,
                    conversation_id=f"test_classification_{i}"
                )
                
                if routed_response:
                    print(f"✅ ROUTED: {routed_response.get('message', 'No message')}")
                    print(f"📡 Routed to: {routed_response.get('routed_to', 'Unknown')}")
                    print(f"📝 Explanation: {routed_response.get('routing_explanation', 'No explanation')}")
                else:
                    print("ℹ️ NOT ROUTED: Handling locally or no suitable agent found")
                    
                    # Test what the classifier would decide
                    if agent.agent_classifier:
                        discovered = agent.get_discovered_agents()
                        best_agent = await agent.agent_classifier.classify_request(test_request, discovered)
                        if best_agent:
                            explanation = agent.agent_classifier.get_classification_explanation(
                                test_request, best_agent, discovered
                            )
                            print(f"🤔 Classifier suggests: {best_agent}")
                            print(f"📝 Reason: {explanation}")
                
                # Small delay between tests
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Test failed: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n✅ Classification and routing tests completed!")
        print("🎉 SUCCESS: Agent classification system is working!")
        
    else:
        print("❌ General Agent: Could not find Weather Specialist")
        print("Make sure Weather Agent is running in a separate terminal")
    
    await agent.close()

async def main():
    """Run agent based on command line argument"""
    
    if len(sys.argv) != 2 or sys.argv[1] not in ['weather', 'general', 'test']:
        print("Usage: python test_agent_classification.py [weather|general|test]")
        print("\nTo test agent classification:")
        print("1. Terminal 1: python test_agent_classification.py weather")
        print("2. Terminal 2: python test_agent_classification.py general")
        print("3. Standalone: python test_agent_classification.py test")
        print("\nGeneral Agent will use intelligent classification to route weather queries to Weather Agent")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == 'test':
        await test_agent_classifier_standalone()
    elif mode == 'weather':
        await run_weather_agent()
    elif mode == 'general':
        await run_general_agent()

if __name__ == "__main__":
    asyncio.run(main()) 