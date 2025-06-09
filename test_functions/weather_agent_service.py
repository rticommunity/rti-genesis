#!/usr/bin/env python3
"""
WeatherAgent for Multi-Agent Demo V3 - Using @genesis_tool Auto-Discovery

A specialized weather agent that uses the new @genesis_tool decorator
for automatic tool discovery and schema generation, eliminating manual
OpenAI tool schema definition.

Key improvements:
- @genesis_tool decorator automatically generates OpenAI schemas
- No manual tool schema definition required
- Cleaner, simpler code focused on domain logic
- Automatic tool injection into OpenAI client

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
from genesis_lib.decorators import genesis_tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WeatherAgent(OpenAIGenesisAgent):
    """
    Specialized weather agent using automatic tool discovery.
    
    This agent demonstrates the new @genesis_tool decorator functionality:
    - Automatic OpenAI tool schema generation
    - Zero manual schema definition 
    - Focus on domain logic instead of Genesis plumbing
    """
    
    def __init__(self):
        print("🚀 TRACE: WeatherAgent.__init__() starting...")
        
        # Get weather API key first
        self.weather_api_key = os.getenv('OPENWEATHERMAP_API_KEY')
        print(f"🔑 TRACE: Weather API Key: {'✅ Available' if self.weather_api_key else '❌ Missing'}")
        
        # Initialize with weather-specific configuration
        super().__init__(
            model_name="gpt-4o",
            agent_name="WeatherExpert", 
            base_service_name="OpenAIAgent",
            description="Specialized weather agent with automatic tool discovery - provides real weather data and forecasts",
            enable_agent_communication=True,
            enable_tracing=True  # Enable detailed tracing
        )
        
        print(f"✅ TRACE: WeatherAgent initialized with agent_id: {self.app.agent_id}")
        logger.info(f"✅ WeatherAgent initialized")
        logger.info(f"🌤️ Weather API: {'✅ REAL' if self.weather_api_key else '❌ MOCK'}")

    # =============================================================================
    # AUTO-DISCOVERED TOOLS - Genesis automatically converts these to OpenAI tools
    # =============================================================================

    @genesis_tool(description="Get current weather conditions for any location worldwide")
    async def get_current_weather(self, location: str) -> dict:
        """
        Get current weather conditions for a specific location.
        
        Args:
            location: The city and country, e.g. 'London, UK' or 'Denver, Colorado'
            
        Returns:
            Current weather data including temperature, description, humidity, pressure, wind
        """
        logger.info(f"🌤️ Getting current weather for {location}")
        return await self.get_weather_data(location, forecast=False)

    @genesis_tool(description="Get multi-day weather forecast for any location")
    async def get_weather_forecast(self, location: str, days: int = 5) -> dict:
        """
        Get weather forecast for a specific location.
        
        Args:
            location: The city and country, e.g. 'London, UK' or 'Denver, Colorado'
            days: Number of days to forecast (1-7, default: 5)
            
        Returns:
            Weather forecast data for the specified number of days
        """
        logger.info(f"🌤️ Getting {days}-day weather forecast for {location}")
        return await self.get_weather_data(location, forecast=True)

    @genesis_tool(description="Analyze weather conditions and provide clothing/activity recommendations")
    def analyze_weather_conditions(self, location: str, temperature: float, description: str, humidity: int) -> str:
        """
        Analyze weather conditions and provide insights and recommendations.
        
        Args:
            location: The location being analyzed
            temperature: Current temperature in Celsius
            description: Weather description (e.g., 'sunny', 'rainy', 'cloudy')
            humidity: Humidity percentage (0-100)
            
        Returns:
            Human-readable weather analysis and recommendations
        """
        logger.info(f"📊 Analyzing weather conditions for {location}")
        
        analysis = f"Weather analysis for {location}:\n"
        analysis += f"- Temperature: {temperature}°C ({self._temp_category(temperature)})\n"
        analysis += f"- Conditions: {description.title()}\n"
        analysis += f"- Humidity: {humidity}% ({self._humidity_category(humidity)})\n"
        
        # Add recommendations
        recommendations = self._get_weather_recommendations(temperature, description, humidity, 0)
        if recommendations:
            analysis += f"\nRecommendations: {recommendations}"
        
        return analysis

    # =============================================================================
    # DOMAIN LOGIC METHODS (not auto-discovered tools)
    # =============================================================================

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
            "data_source": "Mock data (auto-generated)"
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
                "data_source": "Mock data (auto-generated)"
            }
        
        return base_weather

    # =============================================================================
    # HELPER METHODS for weather analysis
    # =============================================================================

    def _temp_category(self, temp: float) -> str:
        """Categorize temperature"""
        if temp < 0:
            return "freezing"
        elif temp < 10:
            return "cold"
        elif temp < 20:
            return "cool"
        elif temp < 30:
            return "warm"
        else:
            return "hot"

    def _humidity_category(self, humidity: int) -> str:
        """Categorize humidity"""
        if humidity < 30:
            return "dry"
        elif humidity < 60:
            return "comfortable"
        elif humidity < 80:
            return "humid"
        else:
            return "very humid"

    def _wind_category(self, wind_speed: float) -> str:
        """Categorize wind speed"""
        if wind_speed < 5:
            return "calm"
        elif wind_speed < 15:
            return "moderate"
        elif wind_speed < 25:
            return "strong"
        else:
            return "very strong"

    def _get_weather_recommendations(self, temp: float, desc: str, humidity: int, wind: float) -> str:
        """Get weather-based recommendations"""
        recommendations = []
        
        if temp < 5:
            recommendations.append("Dress warmly, wear layers")
        elif temp > 30:
            recommendations.append("Stay hydrated, seek shade")
        
        if "rain" in desc.lower():
            recommendations.append("Bring umbrella or raincoat")
        
        if humidity > 80:
            recommendations.append("Expect muggy conditions")
        
        if wind > 20:
            recommendations.append("Expect windy conditions")
        
        return "; ".join(recommendations) if recommendations else "No special recommendations"

    async def _ensure_functions_discovered(self):
        """
        Override to disable function discovery for WeatherAgent.
        WeatherAgent is specialized and doesn't need external function services.
        """
        print(f"🔧 TRACE: WeatherAgent._ensure_functions_discovered() - SKIPPING (specialized agent)")
        # Do nothing - WeatherAgent doesn't need external functions

async def main():
    """Main entry point for WeatherAgent"""
    logger.info("🌤️ Starting WeatherAgent with automatic tool discovery...")
    
    # Check for API key
    weather_api_key = os.getenv('OPENWEATHERMAP_API_KEY')
    if not weather_api_key:
        logger.warning("⚠️ No OPENWEATHERMAP_API_KEY found - using mock weather data")
        logger.info("💡 To get real weather data, get a free API key from: https://openweathermap.org/api")
    
    # Create and run weather agent
    agent = WeatherAgent()
    
    try:
        logger.info("🚀 WeatherAgent starting...")
        logger.info("🛠️ Auto-discovery will find @genesis_tool decorated methods")
        logger.info("📡 Agent will be discoverable as 'WeatherExpert' service")
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