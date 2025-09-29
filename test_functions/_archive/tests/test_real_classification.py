#!/usr/bin/env python3
"""
Test Real LLM Classification and Weather Agent

This test verifies that:
1. Real LLM classification works with GPT-4o-mini
2. Real weather agent provides actual weather data
3. Agent-to-agent communication works with real services
4. Classification routes requests to appropriate specialized agents

Usage:
    export OPENAI_API_KEY="your_openai_key_here"
    export OPENWEATHERMAP_API_KEY="your_weather_key_here"  # Optional
    
    Terminal 1: python test_functions/test_real_classification.py weather
    Terminal 2: python test_functions/test_real_classification.py general
    Terminal 3: python test_functions/test_real_classification.py test
"""

import asyncio
import sys
import os
import time
import logging

# Add the parent directory to the path so we can import genesis_lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.monitored_agent import MonitoredAgent

# Add examples path for real weather agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'examples', 'weather_agent'))
from real_weather_agent import RealWeatherAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealGeneralAgent(MonitoredAgent):
    """
    Real general purpose agent with LLM classification for routing
    """
    
    def __init__(self):
        super().__init__(
            agent_name="RealGeneralAssistant",
            base_service_name="RealGeneralService",
            agent_type="AGENT",
            agent_id="real_general_assistant",
            description="Real general purpose AI assistant with LLM-based agent routing",
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
                "agent_routing"
            ],
            "classification_tags": [
                "general", "assistant", "ai", "help", "question",
                "analysis", "reasoning", "problem", "task", "routing"
            ],
            "model_info": {
                "type": "ai_model",
                "model": "claude-3-opus",
                "context_length": 200000,
                "routing_model": "gpt-4o-mini"
            },
            "default_capable": True,
            "performance_metrics": {
                "avg_response_time": 1.2,
                "accuracy_score": 88.0,
                "availability": 99.5
            }
        }
    
    async def process_agent_request(self, request):
        """Process requests with intelligent routing to specialized agents"""
        message = request.get('message', '')
        conversation_id = request.get('conversation_id', '')
        
        print(f"🔍 General Agent received request: {message}")
        
        # First try to route to a specialized agent using LLM classification
        if self.agent_classifier and self.agent_communication:
            discovered_agents = self.get_discovered_agents()
            print(f"📊 Found {len(discovered_agents)} discovered agents")
            
            if discovered_agents:
                try:
                    # Use LLM classifier to find the best agent
                    best_agent_id = await self.agent_classifier.classify_request(
                        message, discovered_agents
                    )
                    
                    if best_agent_id and best_agent_id != self.app.agent_id:
                        print(f"🎯 LLM Classification result: routing to {best_agent_id}")
                        
                        # Get explanation for the routing decision
                        explanation = self.agent_classifier.get_classification_explanation(
                            message, best_agent_id, discovered_agents
                        )
                        print(f"💡 Routing explanation: {explanation}")
                        
                        # Route the request to the specialized agent
                        response = await self.send_agent_request(
                            target_agent_id=best_agent_id,
                            message=message,
                            conversation_id=conversation_id,
                            timeout_seconds=15.0
                        )
                        
                        if response and response.get('status') == 0:
                            # Add routing metadata to response
                            routed_message = f"[Routed to {discovered_agents[best_agent_id]['name']}] {response['message']}"
                            print(f"✅ Successfully routed request, got response: {routed_message[:100]}...")
                            
                            return {
                                'message': routed_message,
                                'status': 0,
                                'conversation_id': conversation_id,
                                'routed_to': best_agent_id,
                                'routing_explanation': explanation
                            }
                        else:
                            print(f"❌ Failed to get response from routed agent {best_agent_id}")
                    else:
                        print(f"🏠 LLM Classification result: handle locally (best_agent: {best_agent_id})")
                        
                except Exception as e:
                    print(f"💥 Error in LLM classification: {e}")
                    logger.error(f"Error in LLM classification: {e}")
        
        # Handle locally if no routing or if routing failed
        print("🏠 Handling request locally")
        return {
            'message': f"General Assistant (local): I can help with {message}",
            'status': 0,
            'conversation_id': conversation_id
        }

async def run_weather_agent():
    """Run Real Weather Agent"""
    print("=== Starting Real Weather Agent ===")
    
    # Check API keys
    weather_key = os.getenv('OPENWEATHERMAP_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')
    
    print(f"🔑 OpenWeatherMap API: {'✅ Available' if weather_key else '⚠️  Not set (using mock data)'}")
    print(f"🔑 OpenAI API: {'✅ Available' if openai_key else '❌ Not set (LLM classification disabled)'}")
    
    agent = RealWeatherAgent()
    
    print("🌤️  Real Weather Agent: Running...")
    print("Press Ctrl+C to stop")
    
    await agent.run()

async def run_general_agent():
    """Run Real General Agent with LLM Classification"""
    print("=== Starting Real General Agent ===")
    
    # Check API keys
    openai_key = os.getenv('OPENAI_API_KEY')
    
    print(f"🔑 OpenAI API: {'✅ Available' if openai_key else '❌ Not set (LLM classification disabled)'}")
    
    agent = RealGeneralAgent()
    
    print("🤖 Real General Agent: Running with LLM classification...")
    print("Press Ctrl+C to stop")
    
    await agent.run()

async def test_real_classification():
    """Test real LLM classification and agent communication"""
    print("=== Testing Real LLM Classification ===")
    
    # Check API keys
    openai_key = os.getenv('OPENAI_API_KEY')
    weather_key = os.getenv('OPENWEATHERMAP_API_KEY')
    
    print(f"🔑 OpenAI API: {'✅ Available' if openai_key else '❌ Not set'}")
    print(f"🔑 OpenWeatherMap API: {'✅ Available' if weather_key else '⚠️  Not set'}")
    
    if not openai_key:
        print("❌ OPENAI_API_KEY is required for this test")
        print("   Set it with: export OPENAI_API_KEY='your_key_here'")
        return
    
    print("\n🚀 Creating test agent...")
    test_agent = RealGeneralAgent()
    
    print("🔍 Waiting for other agents to be discovered...")
    await asyncio.sleep(10)  # Wait for agents to discover each other
    
    discovered = test_agent.get_discovered_agents()
    print(f"📊 Total discovered agents: {len(discovered)}")
    
    if len(discovered) == 0:
        print("⚠️  No agents discovered. Make sure weather and general agents are running.")
        print("   Run them in separate terminals first:")
        print("   Terminal 1: python test_functions/test_real_classification.py weather")
        print("   Terminal 2: python test_functions/test_real_classification.py general")
        return
    
    # Show discovered agents
    print("\n📋 Discovered Agents:")
    for agent_id, info in discovered.items():
        agent_type = info.get('agent_type', 'unknown')
        name = info.get('name', agent_id)
        specializations = info.get('specializations', [])
        print(f"  • {name} ({agent_id})")
        print(f"    Type: {agent_type}")
        print(f"    Specializations: {specializations}")
    
    print("\n🧪 Testing Real LLM Classification:")
    
    # Test cases for LLM classification
    test_requests = [
        ("What's the weather in New York?", "Should route to weather agent"),
        ("Tell me the weather forecast for London", "Should route to weather agent"),
        ("Is it going to rain in Paris tomorrow?", "Should route to weather agent"),
        ("What's the temperature in Tokyo?", "Should route to weather agent"),
        ("Can you help me with a math problem?", "Should handle locally or route to general agent"),
        ("What is the capital of France?", "Should handle locally or route to general agent"),
        ("How do I cook pasta?", "Should handle locally or route to general agent"),
    ]
    
    for i, (request, expected) in enumerate(test_requests, 1):
        print(f"\n{i}. Testing: '{request}'")
        print(f"   Expected: {expected}")
        
        try:
            # Test LLM classification directly
            if test_agent.agent_classifier:
                best_agent_id = await test_agent.agent_classifier.classify_request(
                    request, discovered
                )
                
                if best_agent_id:
                    agent_name = discovered[best_agent_id]['name']
                    agent_type = discovered[best_agent_id].get('agent_type', 'unknown')
                    specializations = discovered[best_agent_id].get('specializations', [])
                    
                    explanation = test_agent.agent_classifier.get_classification_explanation(
                        request, best_agent_id, discovered
                    )
                    
                    print(f"   ✅ LLM selected: {agent_name} ({agent_type})")
                    print(f"   📝 Specializations: {specializations}")
                    print(f"   💡 Explanation: {explanation}")
                    
                    # Test actual agent-to-agent communication
                    if best_agent_id != test_agent.app.agent_id:
                        print(f"   🔗 Testing communication with {agent_name}...")
                        response = await test_agent.send_agent_request(
                            target_agent_id=best_agent_id,
                            message=request,
                            timeout_seconds=15.0
                        )
                        
                        if response and response.get('status') == 0:
                            response_msg = response.get('message', '')
                            print(f"   ✅ Response: {response_msg[:150]}{'...' if len(response_msg) > 150 else ''}")
                            
                            # Check if weather agent provided real or mock data
                            if 'weather' in request.lower() and 'metadata' in response:
                                data_source = response['metadata'].get('data_source', 'unknown')
                                print(f"   📊 Data source: {data_source}")
                        else:
                            print(f"   ❌ Communication failed: {response}")
                    else:
                        print(f"   🏠 Would handle locally")
                        
                else:
                    print(f"   ❌ LLM classification returned no agent")
            else:
                print(f"   ❌ Agent classifier not available")
                
        except Exception as e:
            print(f"   💥 Error: {e}")
    
    print("\n✅ Real LLM Classification Test Complete!")
    
    await test_agent.close()

async def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print("Usage: python test_functions/test_real_classification.py [weather|general|test]")
        print("\nAPI Keys required:")
        print("  OPENAI_API_KEY - For LLM classification (required)")
        print("  OPENWEATHERMAP_API_KEY - For real weather data (optional, will use mock data)")
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    
    try:
        if mode == "weather":
            await run_weather_agent()
        elif mode == "general":
            await run_general_agent()
        elif mode == "test":
            await test_real_classification()
        else:
            print("Invalid mode. Use: weather, general, or test")
            sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{mode.title()} agent shutting down...")
    except Exception as e:
        print(f"Error in {mode} mode: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 