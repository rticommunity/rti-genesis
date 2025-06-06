#!/usr/bin/env python3
"""
Auto Tool Weather Agent Example

This example demonstrates the new @genesis_tool decorator functionality
that automatically generates OpenAI tool schemas from type hints and docstrings,
eliminating the need for manual tool schema definition.

Key Features:
- @genesis_tool decorator automatically converts methods to tools
- Type hints automatically generate OpenAI parameter schemas
- Docstrings automatically provide tool descriptions
- Zero manual schema definition required

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import os
import sys

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
from genesis_lib.decorators import genesis_tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutoToolWeatherAgent(OpenAIGenesisAgent):
    """
    Weather agent using automatic tool discovery.
    
    This agent demonstrates how @genesis_tool automatically:
    1. Generates OpenAI tool schemas from type hints
    2. Injects tools into the OpenAI client
    3. Handles tool calling transparently
    
    NO manual tool schema definition required!
    """
    
    def __init__(self):
        super().__init__(
            model_name="gpt-4o",
            agent_name="AutoToolWeatherAgent",
            description="Weather agent with automatic tool discovery",
            enable_tracing=True  # Enable for debugging
        )
        
        # Store API key for weather data
        self.weather_api_key = os.getenv('OPENWEATHERMAP_API_KEY')
        
        logger.info("AutoToolWeatherAgent initialized with automatic tool discovery")

    @genesis_tool(description="Get current weather conditions for any location")
    async def get_current_weather(self, location: str) -> dict:
        """
        Get current weather conditions for a specific location.
        
        Args:
            location: The city and country, e.g. 'London, UK' or 'Denver, Colorado'
        
        Returns:
            Current weather data including temperature, description, humidity
        """
        logger.info(f"🌤️ Getting current weather for {location}")
        
        if self.weather_api_key:
            # Use real weather API
            return await self._get_real_weather(location)
        else:
            # Use mock weather data
            return self._get_mock_weather(location)

    @genesis_tool(description="Get weather forecast for multiple days")
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
        
        # Mock forecast data for demonstration
        return {
            "location": location,
            "forecast_days": days,
            "forecast": [
                {
                    "day": f"Day {i+1}",
                    "temperature": 20 + i,
                    "description": "partly cloudy",
                    "humidity": 60 + i * 2
                }
                for i in range(days)
            ],
            "data_source": "Genesis Auto Tool System"
        }

    @genesis_tool(description="Analyze weather conditions and provide recommendations")
    def analyze_weather_conditions(self, temperature: float, description: str, humidity: int) -> str:
        """
        Analyze weather conditions and provide clothing and activity recommendations.
        
        Args:
            temperature: Current temperature in Celsius
            description: Weather description (e.g., 'sunny', 'rainy', 'cloudy')
            humidity: Humidity percentage (0-100)
        
        Returns:
            Detailed analysis and recommendations
        """
        logger.info(f"📊 Analyzing weather: {temperature}°C, {description}, {humidity}% humidity")
        
        # Generate recommendations based on conditions
        recommendations = []
        
        if temperature < 5:
            recommendations.append("Dress warmly with layers and winter coat")
        elif temperature < 15:
            recommendations.append("Wear a jacket or sweater")
        elif temperature > 25:
            recommendations.append("Light clothing recommended, stay hydrated")
        
        if "rain" in description.lower():
            recommendations.append("Bring umbrella or raincoat")
        
        if humidity > 70:
            recommendations.append("Expect muggy conditions")
        
        analysis = f"Weather Analysis:\n"
        analysis += f"Temperature: {temperature}°C ({self._temp_category(temperature)})\n"
        analysis += f"Conditions: {description.title()}\n"
        analysis += f"Humidity: {humidity}% ({self._humidity_category(humidity)})\n"
        
        if recommendations:
            analysis += f"\nRecommendations:\n" + "\n".join(f"• {rec}" for rec in recommendations)
        
        return analysis

    # =========================================================================
    # Helper methods (not tools)
    # =========================================================================

    async def _get_real_weather(self, location: str) -> dict:
        """Get real weather data from OpenWeatherMap API"""
        try:
            import aiohttp
            
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": location,
                "appid": self.weather_api_key,
                "units": "metric"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "location": data["name"],
                            "temperature": data["main"]["temp"],
                            "description": data["weather"][0]["description"],
                            "humidity": data["main"]["humidity"],
                            "pressure": data["main"]["pressure"],
                            "wind_speed": data.get("wind", {}).get("speed", 0),
                            "data_source": "OpenWeatherMap API"
                        }
                    else:
                        return {"error": f"Weather API error: {response.status}"}
                        
        except ImportError:
            logger.warning("aiohttp not available, using mock weather data")
            return self._get_mock_weather(location)
        except Exception as e:
            logger.error(f"Error getting real weather: {e}")
            return {"error": f"Weather service error: {str(e)}"}

    def _get_mock_weather(self, location: str) -> dict:
        """Generate realistic mock weather data"""
        import random
        
        return {
            "location": location,
            "temperature": random.randint(15, 25),
            "description": random.choice(["sunny", "partly cloudy", "cloudy", "light rain"]),
            "humidity": random.randint(40, 80),
            "pressure": random.randint(1010, 1025),
            "wind_speed": random.uniform(5, 15),
            "data_source": "Mock data (no API key provided)"
        }

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

async def main():
    """Main entry point for AutoToolWeatherAgent"""
    print("🚀 Starting AutoToolWeatherAgent with automatic tool discovery...")
    
    # Check for API key
    weather_api_key = os.getenv('OPENWEATHERMAP_API_KEY')
    if not weather_api_key:
        print("⚠️ No OPENWEATHERMAP_API_KEY found - using mock weather data")
        print("💡 Get a free API key from: https://openweathermap.org/api")
    else:
        print("✅ Weather API key found - using real weather data")
    
    # Create and run weather agent
    agent = AutoToolWeatherAgent()
    
    try:
        print("✅ AutoToolWeatherAgent created, starting RPC service...")
        print("🛠️ Automatic tool discovery will scan for @genesis_tool methods")
        print("📡 Agent will be discoverable as 'AutoToolWeatherAgent' service")
        
        # Start the agent service
        await agent.run()
        
    except KeyboardInterrupt:
        print("⏹️ AutoToolWeatherAgent stopped by user")
    except Exception as e:
        print(f"❌ AutoToolWeatherAgent error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await agent.close()
        print("👋 AutoToolWeatherAgent shutdown complete")

if __name__ == "__main__":
    asyncio.run(main()) 