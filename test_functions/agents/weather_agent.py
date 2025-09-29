#!/usr/bin/env python3
"""
Weather Agent for Multi-Agent Testing - REAL API ONLY

This weather agent wrapper runs the real weather agent for multi-agent test scenarios.
It provides weather data using ONLY the OpenWeatherMap API - NO MOCK DATA.

CRITICAL REQUIREMENT: This agent requires a valid OpenWeatherMap API key.
Tests will FAIL if no API key is provided - this is intentional to ensure
no mock data is used in final testing.

Usage:
    export OPENWEATHERMAP_API_KEY="your-api-key"
    python test_functions/weather_agent.py

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import sys
import os
import logging

# Add the parent directory to the path so we can import genesis_lib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from examples.weather_agent.real_weather_agent import LLMWeatherAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Run the weather agent for multi-agent testing - REAL API ONLY"""
    
    # CRITICAL: Check for API key before starting
    api_key = os.getenv('OPENWEATHERMAP_API_KEY')
    if not api_key:
        logger.error("❌ CRITICAL ERROR: No OpenWeatherMap API key found!")
        logger.error("❌ This weather agent requires a REAL API key - NO MOCK DATA allowed")
        logger.error("❌ Set OPENWEATHERMAP_API_KEY environment variable")
        logger.error("❌ Test FAILED - Real API key required for completion")
        sys.exit(1)
    
    logger.info("✅ OpenWeatherMap API key found - starting real weather agent")
    logger.info("🌤️ Weather Agent will use REAL weather data only")
    
    # Create and run the weather agent
    agent = LLMWeatherAgent()
    
    # Verify the agent has the API key
    if not hasattr(agent, 'weather_api_key') or not agent.weather_api_key:
        logger.error("❌ CRITICAL ERROR: Weather agent failed to initialize with API key")
        logger.error("❌ Test FAILED - Real API required")
        sys.exit(1)
    
    logger.info(f"🚀 Starting Weather Agent with real API integration")
    logger.info("📡 Weather data will come from OpenWeatherMap API")
    logger.info("🚫 NO MOCK DATA - Real API only")
    
    try:
        await agent.run()
    except KeyboardInterrupt:
        logger.info("🛑 Weather Agent shutting down...")
    except Exception as e:
        logger.error(f"❌ Weather Agent error: {e}")
        raise
    finally:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(main()) 