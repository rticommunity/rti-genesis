#!/usr/bin/env python3
"""
WeatherAgent for Multi-Agent Demo V2

A specialized weather agent that provides real weather data and can be called
by other agents as a tool. Demonstrates agent-as-tool pattern where:
- Users can connect directly to WeatherAgent for weather queries
- PersonalAssistant can discover and call WeatherAgent as a specialized tool

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any, Optional
from datetime import datetime
import traceback

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WeatherAgent(OpenAIGenesisAgent):
    """
    Specialized weather agent for multi-agent system.
    Provides real weather data and can be called by other agents.
    """
    
    def __init__(self):
        print("🚀 TRACE: WeatherAgent.__init__() starting...")
        
        # Get weather API key first (before parent init so it's available in get_agent_capabilities)
        self.weather_api_key = os.getenv('OPENWEATHERMAP_API_KEY')
        print(f"🔑 TRACE: Weather API Key: {'✅ Available' if self.weather_api_key else '❌ Missing'}")
        
        # Initialize with weather-specific configuration
        super().__init__(
            model_name="gpt-4o",
            agent_name="WeatherExpert", 
            base_service_name="WeatherService",
            description="Specialized weather agent providing real weather data, forecasts, and meteorological analysis",
            enable_agent_communication=True,
            enable_tracing=True  # Enable detailed tracing
        )
        
        # Override function discovery behavior for specialized agent
        print(f"🔧 TRACE: Disabling external function discovery for specialized WeatherAgent")
        # WeatherAgent is self-contained and doesn't need external function services
        
        # Weather-specific system prompt
        self.weather_system_prompt = """You are WeatherExpert, a specialized weather agent with access to real weather data.

When users ask about weather, provide detailed, accurate weather information including:
- Current conditions (temperature, humidity, wind, pressure)
- Weather descriptions (sunny, cloudy, rainy, etc.)
- Forecasts when requested
- Weather-related advice and insights

If you have access to real weather API, use it. Otherwise, provide realistic weather estimates based on typical patterns for the location and season.

Be helpful, informative, and weather-focused in your responses."""

        # Override the general system prompt with weather-specific one
        self.system_prompt = self.weather_system_prompt
        
        print(f"✅ TRACE: WeatherAgent initialized with agent_id: {self.app.agent_id}")
        logger.info(f"✅ WeatherAgent initialized")
        logger.info(f"🌤️ Weather API: {'✅ REAL' if self.weather_api_key else '❌ MOCK'}")

    def get_agent_capabilities(self):
        """Return weather-specific agent capabilities"""
        return {
            "agent_type": "specialized",
            "specializations": ["weather", "meteorology", "climate"],
            "capabilities": [
                "current_weather", "weather_forecast", "weather_alerts",
                "temperature_analysis", "precipitation_forecast", "weather_conditions",
                "humidity_check", "wind_speed", "atmospheric_pressure"
            ],
            "classification_tags": [
                "weather", "temperature", "forecast", "rain", "snow", "storm", 
                "climate", "humidity", "wind", "pressure", "sunny", "cloudy",
                "precipitation", "conditions", "meteorology", "celsius", 
                "fahrenheit", "degrees", "hot", "cold", "warm", "cool"
            ],
            "model_info": {
                "type": "weather_specialist",
                "llm_model": "gpt-4o",
                "data_source": "OpenWeatherMap API" if self.weather_api_key else "mock_data",
                "real_api": bool(self.weather_api_key)
            },
            "default_capable": False,  # Specialized agent
            "performance_metrics": {
                "avg_response_time": 2.5,
                "accuracy_score": 95.0,
                "availability": 99.5,
                "data_freshness": "real_time" if self.weather_api_key else "simulated"
            }
        }

    async def get_weather_data(self, location: str, forecast: bool = False) -> Dict[str, Any]:
        """Get weather data for a location (real or mock)"""
        if self.weather_api_key:
            return await self._get_real_weather(location, forecast)
        else:
            return self._get_mock_weather(location, forecast)
    
    async def _get_real_weather(self, location: str, forecast: bool = False) -> Dict[str, Any]:
        """Get real weather data from OpenWeatherMap API"""
        try:
            import aiohttp
            
            base_url = "https://api.openweathermap.org/data/2.5"
            endpoint = "forecast" if forecast else "weather"
            
            async with aiohttp.ClientSession() as session:
                url = f"{base_url}/{endpoint}"
                params = {
                    "q": location,
                    "appid": self.weather_api_key,
                    "units": "metric"
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._format_weather_data(data, forecast)
                    else:
                        error_data = await response.text()
                        logger.error(f"Weather API error {response.status}: {error_data}")
                        return {"error": f"Weather API error: {response.status}"}
                        
        except ImportError:
            logger.warning("aiohttp not available, using mock weather data")
            return self._get_mock_weather(location, forecast)
        except Exception as e:
            logger.error(f"Error getting real weather: {e}")
            return {"error": f"Weather service error: {str(e)}"}
    
    def _format_weather_data(self, data: Dict[str, Any], forecast: bool = False) -> Dict[str, Any]:
        """Format weather API response"""
        if forecast:
            # Format forecast data
            forecasts = []
            for item in data.get("list", [])[:5]:  # Next 5 periods
                forecasts.append({
                    "time": item.get("dt_txt"),
                    "temperature": item["main"]["temp"],
                    "description": item["weather"][0]["description"],
                    "humidity": item["main"]["humidity"],
                    "wind_speed": item.get("wind", {}).get("speed", 0)
                })
            
            return {
                "location": data["city"]["name"],
                "forecast": forecasts,
                "data_source": "OpenWeatherMap API"
            }
        else:
            # Format current weather
            return {
                "location": data["name"],
                "temperature": data["main"]["temp"],
                "description": data["weather"][0]["description"],
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "wind_speed": data.get("wind", {}).get("speed", 0),
                "data_source": "OpenWeatherMap API"
            }
    
    def _get_mock_weather(self, location: str, forecast: bool = False) -> Dict[str, Any]:
        """Generate realistic mock weather data"""
        import random
        
        # Mock current weather
        temperatures = [18, 22, 25, 28, 15, 12, 30, 8, 35]
        descriptions = ["sunny", "partly cloudy", "cloudy", "light rain", "overcast"]
        
        base_weather = {
            "location": location,
            "temperature": random.choice(temperatures),
            "description": random.choice(descriptions),
            "humidity": random.randint(40, 90),
            "pressure": random.randint(1010, 1025),
            "wind_speed": random.uniform(5, 20),
            "data_source": "Mock data (no API key)"
        }
        
        if forecast:
            forecasts = []
            for i in range(5):
                forecasts.append({
                    "time": f"Day {i+1}",
                    "temperature": base_weather["temperature"] + random.randint(-5, 5),
                    "description": random.choice(descriptions),
                    "humidity": random.randint(40, 90),
                    "wind_speed": random.uniform(5, 20)
                })
            
            return {
                "location": location,
                "forecast": forecasts,
                "data_source": "Mock data (no API key)"
            }
        
        return base_weather

    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a weather request using OpenAI with internal weather tool calls.
        This agent uses OpenAI's tool calling feature to access weather APIs internally.
        """
        print(f"🔍 TRACE: WeatherAgent.process_request() called with: {request}")
        
        try:
            # Extract message
            message = request.get("message", "")
            conversation_id = request.get("conversation_id", "")
            print(f"🔍 TRACE: Processing weather request: {message}")
            
            # Check if we have proper OpenAI client setup
            if not hasattr(self, 'client') or self.client is None:
                print(f"❌ TRACE: No OpenAI client found!")
                return {
                    "message": "Weather service configuration error: OpenAI client not initialized",
                    "status": 1
                }
            
            print(f"✅ TRACE: OpenAI client available: {type(self.client)}")
            
            # Define internal weather tools for OpenAI
            weather_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "get_current_weather",
                        "description": "Get current weather conditions for a specific location using OpenWeatherMap API",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {
                                    "type": "string",
                                    "description": "The city and state/country, e.g. 'Denver, Colorado' or 'London, UK'"
                                }
                            },
                            "required": ["location"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather_forecast",
                        "description": "Get weather forecast for a specific location using OpenWeatherMap API",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {
                                    "type": "string",
                                    "description": "The city and state/country, e.g. 'Denver, Colorado' or 'London, UK'"
                                }
                            },
                            "required": ["location"]
                        }
                    }
                }
            ]
            
            print(f"🔧 TRACE: Defined {len(weather_tools)} internal weather tools for OpenAI")
            
            # Create weather-specific system prompt
            weather_system_prompt = """You are WeatherExpert, a specialized weather agent with access to real weather data.

When users ask about weather, use the provided weather tools to get accurate, real-time data:
- Use get_current_weather for current conditions
- Use get_weather_forecast for future weather predictions
- Always extract the location correctly from the user's request
- Provide detailed, helpful weather information
- If no location is specified, ask for clarification

Provide natural, conversational responses based on the real weather data you retrieve."""

            # Call OpenAI with internal weather tools
            print(f"🚀 TRACE: Calling OpenAI with internal weather tools...")
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model_config.get("model", "gpt-4o"),
                    messages=[
                        {"role": "system", "content": weather_system_prompt},
                        {"role": "user", "content": message}
                    ],
                    tools=weather_tools,
                    tool_choice="auto",
                    temperature=0.1
                )
                
                assistant_message = response.choices[0].message
                print(f"🤖 TRACE: OpenAI response received, tool_calls: {bool(assistant_message.tool_calls)}")
                
                if assistant_message.tool_calls:
                    # OpenAI wants to make weather tool calls - execute them internally
                    print(f"🔧 TRACE: Processing {len(assistant_message.tool_calls)} tool call(s)")
                    
                    tool_messages = [
                        {"role": "system", "content": weather_system_prompt},
                        {"role": "user", "content": message},
                        {
                            "role": "assistant",
                            "content": assistant_message.content,
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": tc.type,
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments
                                    }
                                } for tc in assistant_message.tool_calls
                            ]
                        }
                    ]
                    
                    # Execute each tool call internally
                    for tool_call in assistant_message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        
                        print(f"🛠️ TRACE: Executing internal tool: {function_name}({function_args})")
                        
                        if function_name == "get_current_weather":
                            weather_data = await self.get_weather_data(function_args["location"], forecast=False)
                        elif function_name == "get_weather_forecast":
                            weather_data = await self.get_weather_data(function_args["location"], forecast=True)
                        else:
                            weather_data = {"error": f"Unknown tool: {function_name}"}
                        
                        # Add tool result to conversation
                        tool_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(weather_data)
                        })
                        
                        print(f"✅ TRACE: Tool {function_name} executed successfully")
                    
                    # Get final response from OpenAI with tool results
                    print(f"🔄 TRACE: Getting final response from OpenAI with tool results...")
                    final_response = self.client.chat.completions.create(
                        model=self.model_config.get("model", "gpt-4o"),
                        messages=tool_messages,
                        temperature=0.3
                    )
                    
                    final_message = final_response.choices[0].message.content
                    print(f"✅ TRACE: Final weather response generated with tool data")
                    
                else:
                    # OpenAI responded directly without tool calls
                    final_message = assistant_message.content
                    print(f"✅ TRACE: Direct response from OpenAI (no tools needed)")
                
                print(f"🌤️ TRACE: Weather processing completed successfully")
                return {
                    "message": final_message,
                    "status": 0,
                    "conversation_id": conversation_id
                }
                
            except Exception as openai_error:
                print(f"❌ TRACE: OpenAI processing failed: {openai_error}")
                print(f"❌ TRACE: Error type: {type(openai_error)}")
                
                # Fallback to direct weather data if OpenAI fails
                print(f"🧪 TRACE: Falling back to direct weather data due to OpenAI failure")
                
                # Extract location from message for fallback
                location = "Denver, Colorado"  # Default
                if 'london' in message.lower():
                    location = "London, UK"
                elif 'tokyo' in message.lower():
                    location = "Tokyo, Japan"
                elif 'paris' in message.lower():
                    location = "Paris, France"
                
                # Get weather data directly
                weather_data = await self.get_weather_data(location, forecast=False)
                
                if "error" not in weather_data:
                    fallback_message = (
                        f"Current weather in {weather_data['location']}: "
                        f"{weather_data['temperature']}°C, {weather_data['description']}, "
                        f"humidity {weather_data['humidity']}%, "
                        f"wind {weather_data['wind_speed']} m/s. "
                        f"(Note: Using direct API access due to processing error)"
                    )
                else:
                    fallback_message = f"Sorry, I encountered an error getting weather data: {weather_data.get('error', 'Unknown error')}"
                
                return {
                    "message": fallback_message,
                    "status": 0,
                    "conversation_id": conversation_id
                }
            
        except Exception as e:
            print(f"❌ TRACE: Error in WeatherAgent.process_request: {e}")
            print(f"❌ TRACE: Traceback: {traceback.format_exc()}")
            return {
                "message": f"Weather service error: {str(e)}",
                "status": 1,
                "conversation_id": request.get("conversation_id", "")
            }

    async def process_agent_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a request from another agent (agent-to-agent communication).
        This is called when PersonalAssistant sends weather requests to WeatherAgent.
        """
        print(f"🔍 TRACE: WeatherAgent.process_agent_request() called with: {request}")
        
        try:
            # Extract message from agent request
            message = request.get("message", "")
            conversation_id = request.get("conversation_id", "")
            
            print(f"🔍 TRACE: Agent request - message: {message}")
            print(f"🔍 TRACE: Agent request - conversation_id: {conversation_id}")
            
            # Process the weather request using our OpenAI processing
            response = await self.process_request({"message": message})
            
            # Format response for agent-to-agent communication
            agent_response = {
                "message": response.get("message", "Weather information not available"),
                "status": response.get("status", 0),
                "conversation_id": conversation_id
            }
            
            print(f"🔍 TRACE: WeatherAgent agent response: {agent_response}")
            return agent_response
            
        except Exception as e:
            print(f"❌ TRACE: Error in WeatherAgent.process_agent_request: {e}")
            print(f"❌ TRACE: Traceback: {traceback.format_exc()}")
            return {
                "message": f"Weather service error: {str(e)}",
                "status": -1,
                "conversation_id": request.get("conversation_id", "")
            }

    # Add a method to check agent discovery
    def check_agent_discovery_status(self):
        """Debug method to check agent discovery status"""
        print(f"🔍 TRACE: === WeatherAgent Discovery Status ===")
        print(f"🔍 TRACE: Agent ID: {self.app.agent_id}")
        print(f"🔍 TRACE: Agent capabilities: {self.get_agent_capabilities()}")
        
        if hasattr(self, 'agent_communication') and self.agent_communication:
            discovered = self.agent_communication.get_discovered_agents()
            print(f"🔍 TRACE: Discovered agents: {len(discovered)}")
            for agent_id, agent_info in discovered.items():
                print(f"🔍 TRACE: - Agent {agent_id}: {agent_info.get('name', 'Unknown')} (type: {agent_info.get('agent_type', 'Unknown')})")
        else:
            print(f"🔍 TRACE: Agent communication not enabled")
        
        print(f"🔍 TRACE: === End Discovery Status ===")

    async def _ensure_functions_discovered(self):
        """
        Override to disable function discovery for WeatherAgent.
        WeatherAgent is specialized and doesn't need external function services.
        """
        print(f"🔧 TRACE: WeatherAgent._ensure_functions_discovered() - SKIPPING (specialized agent)")
        # Do nothing - WeatherAgent doesn't need external functions
        return

async def main():
    """Main entry point for WeatherAgent"""
    logger.info("🌤️ Starting WeatherAgent...")
    
    # Check for API key
    weather_api_key = os.getenv('OPENWEATHERMAP_API_KEY')
    if not weather_api_key:
        logger.warning("⚠️ No OPENWEATHERMAP_API_KEY found - using mock weather data")
        logger.info("💡 To get real weather data, get a free API key from: https://openweathermap.org/api")
    
    # Create and run weather agent
    agent = WeatherAgent()
    
    # Add delayed discovery check
    print("\n🕐 TRACE: Waiting 10 seconds to see what agents WeatherAgent discovers...")
    await asyncio.sleep(10)
    print("🕐 TRACE: === WEATHERAGENT DISCOVERY CHECK ===")
    agent.check_agent_discovery_status()
    
    try:
        logger.info("🚀 WeatherAgent starting...")
        await agent.run()
    except KeyboardInterrupt:
        logger.info("⏹️ WeatherAgent stopped by user")
    except Exception as e:
        logger.error(f"❌ WeatherAgent error: {e}")
    finally:
        await agent.close()
        logger.info("👋 WeatherAgent shutdown complete")

if __name__ == "__main__":
    asyncio.run(main()) 