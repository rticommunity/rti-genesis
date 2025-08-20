#!/usr/bin/env python3
"""
WeatherAgent - @genesis_tool Example

Modern weather agent demonstrating the power of @genesis_tool decorators.
This agent shows how Genesis transforms complex tool definitions into
simple, elegant Python code.

Features:
- @genesis_tool decorators for automatic tool discovery
- Zero manual OpenAI schema definition
- Real OpenWeatherMap API integration
- Type-safe development with Python hints
- Automatic tool injection into OpenAI client

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any, Optional, List
from datetime import datetime

# Add the parent directories to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
from genesis_lib.decorators import genesis_tool

# Import demo configuration
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.demo_config import should_trace_agents, demo_mode_active, SHOW_WEATHER_API_STATUS

# Configure logging based on demo mode
if demo_mode_active():
    logging.basicConfig(level=logging.WARNING)  # Minimal logging for demos
else:
    logging.basicConfig(level=logging.INFO)     # Full logging for debugging

logger = logging.getLogger(__name__)

class WeatherAgent(OpenAIGenesisAgent):
    """
    Specialized weather agent using @genesis_tool auto-discovery.
    
    This agent demonstrates:
    - @genesis_tool decorator for automatic tool schema generation
    - Real weather API integration with fallback to mock data
    - Clean demo mode vs debugging mode
    - Zero manual OpenAI schema definition
    """
    
    def __init__(self):
        # Get weather API key first
        self.weather_api_key = os.getenv('OPENWEATHERMAP_API_KEY')
        
        # Determine tracing mode based on demo configuration (force-enable for debugging)
        enable_tracing = True
        
        # Show API status only if configured to do so
        if SHOW_WEATHER_API_STATUS:
            api_status = "✅ REAL API" if self.weather_api_key else "🔄 MOCK DATA"
            logger.info(f"Weather API Status: {api_status}")
        
        if enable_tracing:
            logger.info("🚀 Initializing WeatherAgent with @genesis_tool auto-discovery")
        
        # Initialize with specialized weather configuration
        super().__init__(
            model_name="gpt-4o",
            agent_name="WeatherExpert",
            base_service_name="OpenAIAgent",
            description="Specialized weather agent with @genesis_tool auto-discovery - provides real weather data and forecasts",
            enable_agent_communication=True,
            enable_tracing=enable_tracing  # Use demo configuration
        )
        
        if enable_tracing:
            logger.info(f"✅ WeatherAgent initialized with agent_id: {self.app.agent_id} (TRACING ENABLED)")
        elif demo_mode_active():
            # In demo mode, show minimal startup message
            print("✅ WeatherAgent ready")
        
        logger.info("WeatherAgent ready with @genesis_tool auto-discovery")

    def get_agent_capabilities(self):
        """Define weather-specific capabilities for agent discovery"""
        return {
            "agent_type": "specialized",
            "specializations": ["weather", "meteorology", "climate", "forecasting"],
            "capabilities": [
                "current_weather", "weather_forecast", "weather_analysis",
                "temperature_data", "humidity_readings", "wind_conditions",
                "atmospheric_pressure", "weather_alerts", "climate_trends"
            ],
            "classification_tags": [
                "weather", "temperature", "forecast", "humidity", "wind", "pressure",
                "rain", "snow", "storm", "climate", "meteorology", "conditions",
                "sunny", "cloudy", "precipitation", "celsius", "fahrenheit"
            ],
            "model_info": {
                "type": "weather_specialist",
                "llm_model": "gpt-4o",
                "data_source": "OpenWeatherMap API" if self.weather_api_key else "mock_data",
                "real_api": bool(self.weather_api_key),
                "auto_discovery": True
            },
            "default_capable": False,  # Specialized agent
            "performance_metrics": {
                "avg_response_time": 2.0,
                "accuracy_score": 95.0,
                "availability": 99.8,
                "data_freshness": "real_time" if self.weather_api_key else "simulated"
            }
        }

    # =============================================================================
    # @genesis_tool AUTO-DISCOVERED METHODS
    # Genesis automatically converts these into OpenAI tool schemas!
    # =============================================================================

    @genesis_tool(description="Get current weather conditions for any location worldwide")
    async def get_current_weather(self, location: str) -> dict:
        """
        Get current weather conditions for a specific location.
        
        Args:
            location: City and country (e.g., 'London, UK' or 'Tokyo, Japan')
            
        Returns:
            Current weather data including temperature, description, humidity, pressure, wind
        """
        logger.info(f"🌤️ Getting current weather for {location}")
        weather_data = await self._fetch_weather_data(location, forecast=False)
        
        # Add helpful context for the response
        if "error" not in weather_data:
            weather_data["query_type"] = "current_conditions"
            weather_data["location_queried"] = location
        
        return weather_data

    @genesis_tool(description="Get detailed weather forecast for multiple days")
    async def get_weather_forecast(self, location: str, days: int = 5) -> dict:
        """
        Get weather forecast for a specific location over multiple days.
        
        Args:
            location: City and country (e.g., 'Paris, France' or 'New York, USA')
            days: Number of days to forecast (1-7, default: 5)
            
        Returns:
            Multi-day weather forecast with detailed daily predictions
        """
        logger.info(f"📅 Getting {days}-day weather forecast for {location}")
        
        # Validate days parameter
        days = max(1, min(days, 7))  # Clamp between 1-7 days
        
        forecast_data = await self._fetch_weather_data(location, forecast=True)
        
        if "error" not in forecast_data:
            forecast_data["query_type"] = "multi_day_forecast"
            forecast_data["days_requested"] = days
            forecast_data["location_queried"] = location
        
        return forecast_data

    @genesis_tool(description="Analyze weather conditions and provide recommendations")
    def analyze_weather_conditions(self, 
                                 location: str, 
                                 temperature: float, 
                                 description: str, 
                                 humidity: int, 
                                 wind_speed: float = 0) -> dict:
        """
        Analyze weather conditions and provide clothing/activity recommendations.
        
        Args:
            location: The location being analyzed
            temperature: Temperature in Celsius
            description: Weather description (e.g., 'sunny', 'rainy', 'cloudy')
            humidity: Humidity percentage (0-100)
            wind_speed: Wind speed in m/s (optional, default: 0)
            
        Returns:
            Detailed weather analysis with recommendations and comfort indices
        """
        logger.info(f"📊 Analyzing weather conditions for {location}")
        
        # Temperature analysis
        temp_category = self._categorize_temperature(temperature)
        comfort_level = self._calculate_comfort_level(temperature, humidity, wind_speed)
        
        # Weather condition analysis
        activity_recommendations = self._get_activity_recommendations(description, temperature, wind_speed)
        clothing_suggestions = self._get_clothing_suggestions(temperature, description, wind_speed)
        
        # Build comprehensive analysis
        analysis = {
            "location": location,
            "conditions_summary": {
                "temperature": f"{temperature}°C ({temp_category})",
                "description": description.title(),
                "humidity": f"{humidity}% ({self._categorize_humidity(humidity)})",
                "wind": f"{wind_speed} m/s ({self._categorize_wind(wind_speed)})" if wind_speed > 0 else "Calm"
            },
            "comfort_assessment": {
                "comfort_level": comfort_level,
                "feel_description": self._get_feel_description(comfort_level)
            },
            "recommendations": {
                "clothing": clothing_suggestions,
                "activities": activity_recommendations,
                "health_tips": self._get_health_tips(temperature, humidity, description)
            },
            "indices": {
                "heat_index": self._calculate_heat_index(temperature, humidity),
                "wind_chill": self._calculate_wind_chill(temperature, wind_speed) if temperature < 10 else None
            }
        }
        
        return analysis

    @genesis_tool(description="Get weather alerts and warnings for a location")
    async def get_weather_alerts(self, location: str) -> dict:
        """
        Get current weather alerts and warnings for a specific location.
        
        Args:
            location: City and country to check for alerts
            
        Returns:
            Weather alerts, warnings, and safety recommendations
        """
        logger.info(f"⚠️ Checking weather alerts for {location}")
        
        # For demo purposes, we'll create realistic alert scenarios
        # In production, this would integrate with weather alert APIs
        
        alerts = {
            "location": location,
            "alert_status": "monitoring",
            "active_alerts": [],
            "general_safety": [
                "Stay informed about changing weather conditions",
                "Have emergency supplies ready",
                "Follow local weather service recommendations"
            ],
            "data_source": "Demo alert system" if not self.weather_api_key else "Weather API alerts"
        }
        
        # Add mock alerts based on current conditions if no real API
        if not self.weather_api_key:
            current_weather = await self._fetch_weather_data(location, forecast=False)
            if "temperature" in current_weather:
                temp = current_weather["temperature"]
                if temp > 35:
                    alerts["active_alerts"].append({
                        "type": "Heat Warning",
                        "severity": "Moderate",
                        "message": "High temperatures expected. Stay hydrated and avoid prolonged sun exposure."
                    })
                elif temp < 0:
                    alerts["active_alerts"].append({
                        "type": "Cold Weather Advisory", 
                        "severity": "Moderate",
                        "message": "Freezing temperatures. Protect exposed skin and dress in layers."
                    })
        
        return alerts

    # =============================================================================
    # INTERNAL HELPER METHODS (Not auto-discovered as tools)
    # =============================================================================

    async def _fetch_weather_data(self, location: str, forecast: bool = False) -> Dict[str, Any]:
        """Fetch weather data from API or generate mock data"""
        if self.weather_api_key:
            return await self._get_real_weather(location, forecast)
        else:
            return self._generate_mock_weather(location, forecast)

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
                        return self._format_api_response(data, forecast)
                    else:
                        logger.error(f"Weather API error {response.status}")
                        return {"error": f"Weather API error: {response.status}"}
                        
        except ImportError:
            logger.warning("aiohttp not available, using mock weather data")
            return self._generate_mock_weather(location, forecast)
        except Exception as e:
            logger.error(f"Error fetching real weather: {e}")
            return {"error": f"Weather service error: {str(e)}"}

    def _format_api_response(self, data: Dict[str, Any], forecast: bool = False) -> Dict[str, Any]:
        """Format weather API response into consistent structure"""
        if forecast:
            forecasts = []
            for item in data.get("list", [])[:5]:
                forecasts.append({
                    "datetime": item.get("dt_txt"),
                    "temperature": round(item["main"]["temp"], 1),
                    "description": item["weather"][0]["description"],
                    "humidity": item["main"]["humidity"],
                    "wind_speed": item.get("wind", {}).get("speed", 0),
                    "pressure": item["main"].get("pressure", 0)
                })
            
            return {
                "location": data["city"]["name"],
                "country": data["city"]["country"],
                "forecast": forecasts,
                "data_source": "OpenWeatherMap API",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "location": data["name"],
                "country": data["sys"]["country"],
                "temperature": round(data["main"]["temp"], 1),
                "description": data["weather"][0]["description"],
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "wind_speed": data.get("wind", {}).get("speed", 0),
                "visibility": data.get("visibility", 0) / 1000 if data.get("visibility") else None,
                "data_source": "OpenWeatherMap API",
                "timestamp": datetime.now().isoformat()
            }

    def _generate_mock_weather(self, location: str, forecast: bool = False) -> Dict[str, Any]:
        """Generate realistic mock weather data for demo purposes"""
        import random
        
        # Base weather parameters
        temperatures = [18, 22, 25, 28, 15, 12, 30, 8, 35, 20]
        descriptions = ["sunny", "partly cloudy", "cloudy", "light rain", "overcast", "clear", "misty"]
        
        if forecast:
            forecasts = []
            base_temp = random.choice(temperatures)
            
            for i in range(5):
                temp_variation = random.randint(-3, 3)
                forecasts.append({
                    "datetime": f"Day {i+1}",
                    "temperature": base_temp + temp_variation,
                    "description": random.choice(descriptions),
                    "humidity": random.randint(40, 85),
                    "wind_speed": round(random.uniform(0, 15), 1),
                    "pressure": random.randint(1010, 1025)
                })
            
            return {
                "location": location.split(',')[0],
                "country": location.split(',')[-1].strip() if ',' in location else "Unknown",
                "forecast": forecasts,
                "data_source": "Mock data (demonstration)",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "location": location.split(',')[0],
                "country": location.split(',')[-1].strip() if ',' in location else "Unknown",
                "temperature": random.choice(temperatures),
                "description": random.choice(descriptions),
                "humidity": random.randint(40, 85),
                "pressure": random.randint(1010, 1025),
                "wind_speed": round(random.uniform(0, 15), 1),
                "visibility": round(random.uniform(5, 20), 1),
                "data_source": "Mock data (demonstration)",
                "timestamp": datetime.now().isoformat()
            }

    # Analysis helper methods
    def _categorize_temperature(self, temp: float) -> str:
        if temp < 0: return "freezing"
        elif temp < 10: return "cold"
        elif temp < 20: return "cool"
        elif temp < 25: return "comfortable"
        elif temp < 30: return "warm"
        else: return "hot"

    def _categorize_humidity(self, humidity: int) -> str:
        if humidity < 30: return "dry"
        elif humidity < 60: return "comfortable"
        elif humidity < 80: return "humid"
        else: return "very humid"

    def _categorize_wind(self, wind_speed: float) -> str:
        if wind_speed < 2: return "calm"
        elif wind_speed < 8: return "light breeze"
        elif wind_speed < 15: return "moderate wind"
        else: return "strong wind"

    def _calculate_comfort_level(self, temp: float, humidity: int, wind: float) -> str:
        # Simplified comfort calculation
        comfort_score = 50
        
        # Temperature comfort (20-25°C is ideal)
        if 20 <= temp <= 25:
            comfort_score += 20
        else:
            comfort_score -= abs(temp - 22.5) * 2
        
        # Humidity comfort (40-60% is ideal)
        if 40 <= humidity <= 60:
            comfort_score += 15
        else:
            comfort_score -= abs(humidity - 50) * 0.3
        
        # Wind comfort (light breeze is nice)
        if 2 <= wind <= 6:
            comfort_score += 10
        elif wind > 15:
            comfort_score -= 10
        
        if comfort_score >= 70: return "very comfortable"
        elif comfort_score >= 60: return "comfortable"
        elif comfort_score >= 40: return "acceptable"
        else: return "uncomfortable"

    def _get_feel_description(self, comfort_level: str) -> str:
        descriptions = {
            "very comfortable": "Perfect weather for outdoor activities",
            "comfortable": "Pleasant conditions for most activities",
            "acceptable": "Manageable with appropriate clothing",
            "uncomfortable": "Consider indoor activities or protective measures"
        }
        return descriptions.get(comfort_level, "Weather conditions vary")

    def _get_clothing_suggestions(self, temp: float, description: str, wind: float) -> List[str]:
        suggestions = []
        
        if temp < 0:
            suggestions.extend(["Heavy winter coat", "Insulated boots", "Warm hat and gloves"])
        elif temp < 10:
            suggestions.extend(["Warm jacket", "Long pants", "Closed shoes"])
        elif temp < 20:
            suggestions.extend(["Light jacket or sweater", "Comfortable layers"])
        elif temp < 30:
            suggestions.extend(["Light clothing", "Comfortable fabrics"])
        else:
            suggestions.extend(["Lightweight clothing", "Sun protection", "Stay hydrated"])
        
        if "rain" in description.lower():
            suggestions.append("Umbrella or rain jacket")
        
        if wind > 10:
            suggestions.append("Windproof outer layer")
        
        return suggestions

    def _get_activity_recommendations(self, description: str, temp: float, wind: float) -> List[str]:
        activities = []
        
        if "sunny" in description.lower() and 15 <= temp <= 28:
            activities.extend(["Outdoor sports", "Hiking", "Picnic", "Cycling"])
        elif "rain" in description.lower():
            activities.extend(["Indoor activities", "Museum visits", "Shopping"])
        elif temp > 30:
            activities.extend(["Swimming", "Water activities", "Indoor venues"])
        elif temp < 0:
            activities.extend(["Winter sports", "Indoor entertainment"])
        else:
            activities.extend(["Walking", "Sightseeing", "General outdoor activities"])
        
        return activities

    def _get_health_tips(self, temp: float, humidity: int, description: str) -> List[str]:
        tips = []
        
        if temp > 30:
            tips.extend(["Stay hydrated", "Avoid prolonged sun exposure", "Take breaks in shade"])
        elif temp < 5:
            tips.extend(["Protect extremities from cold", "Stay warm and dry"])
        
        if humidity > 80:
            tips.append("High humidity may affect those with respiratory conditions")
        
        if "sunny" in description.lower():
            tips.append("Use sunscreen for UV protection")
        
        return tips

    def _calculate_heat_index(self, temp: float, humidity: int) -> Optional[float]:
        """Simplified heat index calculation"""
        if temp < 27:  # Heat index not meaningful below ~27°C
            return None
        
        # Simplified formula for demonstration
        hi = temp + (0.5 * (temp + 61.0) + ((temp - 68.0) * 1.2) + (humidity * 0.094))
        return round(hi, 1)

    def _calculate_wind_chill(self, temp: float, wind_speed: float) -> Optional[float]:
        """Simplified wind chill calculation"""
        if temp > 10 or wind_speed < 1:  # Wind chill not meaningful above 10°C or in calm conditions
            return None
        
        # Simplified wind chill formula
        wc = 13.12 + 0.6215 * temp - 11.37 * (wind_speed ** 0.16) + 0.3965 * temp * (wind_speed ** 0.16)
        return round(wc, 1)

    async def _ensure_functions_discovered(self):
        """Override to disable external function discovery for specialized agent"""
        logger.debug("WeatherAgent: Skipping external function discovery (specialized agent)")
        # WeatherAgent is self-contained and doesn't need external functions

async def main():
    """Main entry point for WeatherAgent"""
    logger.info("🌤️ Starting WeatherAgent with @genesis_tool auto-discovery...")
    logger.info("🚀 This agent demonstrates zero-boilerplate tool development!")
    
    # Check environment
    if os.getenv('OPENWEATHERMAP_API_KEY'):
        logger.info("✅ Real weather API available")
    else:
        logger.warning("⚠️ No OPENWEATHERMAP_API_KEY - using mock data")
        logger.info("💡 Get a free API key at: https://openweathermap.org/api")
    
    # Create and run agent
    agent = WeatherAgent()
    
    try:
        logger.info("📡 WeatherAgent starting - will be discoverable as 'WeatherExpert'")
        logger.info("🛠️ @genesis_tool methods will be auto-discovered and injected into OpenAI")
        await agent.run()
    except KeyboardInterrupt:
        logger.info("⏹️ WeatherAgent stopped by user")
    except Exception as e:
        logger.error(f"❌ WeatherAgent error: {e}")
        raise
    finally:
        await agent.close()
        logger.info("👋 WeatherAgent shutdown complete")

if __name__ == "__main__":
    asyncio.run(main()) 