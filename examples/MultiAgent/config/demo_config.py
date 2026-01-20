#!/usr/bin/env python3
"""
Demo Configuration - Genesis Multi-Agent Example

Configuration settings and environment validation for the Genesis multi-agent demo.

"""

import os
from typing import Dict, Any, Optional

# Demo Configuration
# Control tracing and debug output for clean demonstrations

# =============================================================================
# TRACING CONTROL - Set to False for clean demo experience
# =============================================================================

# Master tracing control - turns off ALL debug output when False
ENABLE_DEMO_TRACING = False  # Set to True for debugging, False for clean demos

# Individual tracing controls (only used if ENABLE_DEMO_TRACING is True)
ENABLE_AGENT_TRACING = True      # Agent-level tracing (OpenAI calls, discovery, etc.)
ENABLE_GENESIS_TRACING = True    # Genesis library internal tracing
ENABLE_DDS_TRACING = False       # DDS communication tracing (very verbose)

# =============================================================================
# DEMO SETTINGS
# =============================================================================

# How long to wait for agent discovery
AGENT_DISCOVERY_TIMEOUT = 5

# Default timeout for agent requests
DEFAULT_REQUEST_TIMEOUT = 60

# Weather API settings
SHOW_WEATHER_API_STATUS = True if ENABLE_DEMO_TRACING else False

# Progress indicator settings
SHOW_PROGRESS_INDICATORS = True
PROGRESS_ANIMATION_SPEED = 0.8  # seconds between animation frames

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def should_trace_agents() -> bool:
    """Returns True if agent tracing should be enabled"""
    return ENABLE_DEMO_TRACING and ENABLE_AGENT_TRACING

def should_trace_genesis() -> bool:
    """Returns True if Genesis library tracing should be enabled"""
    return ENABLE_DEMO_TRACING and ENABLE_GENESIS_TRACING

def should_trace_dds() -> bool:
    """Returns True if DDS tracing should be enabled"""
    return ENABLE_DEMO_TRACING and ENABLE_DDS_TRACING

def demo_mode_active() -> bool:
    """Returns True if we're in clean demo mode (no tracing)"""
    return not ENABLE_DEMO_TRACING

# =============================================================================
# DEMO SCENARIOS
# =============================================================================

DEMO_SCENARIOS = [
    {
        "name": "Weather Delegation",
        "query": "What's the weather in Tokyo, Japan?",
        "description": "PersonalAssistant → WeatherAgent delegation"
    },
    {
        "name": "Function Calling", 
        "query": "Calculate 987 * 654",
        "description": "PersonalAssistant → Calculator service"
    },
    {
        "name": "Mixed Capabilities",
        "query": "Weather in London and calculate 15% tip on $85",
        "description": "Multi-service delegation"
    },
    {
        "name": "@genesis_tool Demo",
        "query": "Give me a 5-day forecast for Paris with analysis",
        "description": "Direct WeatherAgent @genesis_tool usage"
    }
]

class DemoConfig:
    """Configuration management for Genesis multi-agent demo"""
    
    # Demo settings
    DEMO_NAME = "Genesis Multi-Agent System"
    DEMO_VERSION = "3.0"
    
    # Agent configuration
    DEFAULT_MODEL = "gpt-4o"
    AGENT_STARTUP_DELAY = 8  # seconds to wait for agent discovery
    REQUEST_TIMEOUT = 60  # seconds for agent requests
    
    # API Keys
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENWEATHERMAP_API_KEY = os.getenv('OPENWEATHERMAP_API_KEY')
    
    @classmethod
    def check_environment(cls) -> Dict[str, Any]:
        """Check environment setup and return status"""
        status = {
            "openai_api": bool(cls.OPENAI_API_KEY),
            "weather_api": bool(cls.OPENWEATHERMAP_API_KEY),
            "required_met": bool(cls.OPENAI_API_KEY),
            "optional_met": bool(cls.OPENWEATHERMAP_API_KEY),
            "warnings": [],
            "recommendations": []
        }
        
        # Check required API keys
        if not cls.OPENAI_API_KEY:
            status["warnings"].append("OPENAI_API_KEY not set - agents will fail")
            status["recommendations"].append("Set OPENAI_API_KEY environment variable")
        
        # Check optional API keys
        if not cls.OPENWEATHERMAP_API_KEY:
            status["warnings"].append("OPENWEATHERMAP_API_KEY not set - using mock weather data")
            status["recommendations"].append("Get free API key at https://openweathermap.org/api")
        
        return status

    @classmethod
    def print_environment_status(cls):
        """Print environment setup status"""
        status = cls.check_environment()
        
        print("🔧 Environment Status")
        print("=" * 25)
        print(f"✅ OpenAI API: {'Available' if status['openai_api'] else '❌ Missing'}")
        print(f"🌤️ Weather API: {'Available' if status['weather_api'] else '⚠️ Missing (will use mock data)'}")
        print()
        
        if status["warnings"]:
            print("⚠️ Warnings:")
            for warning in status["warnings"]:
                print(f"   • {warning}")
            print()
        
        if status["recommendations"]:
            print("💡 Recommendations:")
            for rec in status["recommendations"]:
                print(f"   • {rec}")
            print()
        
        if status["required_met"]:
            print("✅ Ready to run demo!")
        else:
            print("❌ Missing required configuration - demo may fail")
        
        print()

    @classmethod
    def get_demo_info(cls) -> Dict[str, Any]:
        """Get demo information"""
        return {
            "name": cls.DEMO_NAME,
            "version": cls.DEMO_VERSION,
            "model": cls.DEFAULT_MODEL,
            "scenarios": len(DEMO_SCENARIOS),
            "features": [
                "@genesis_tool auto-discovery",
                "Agent-to-agent delegation", 
                "Function service integration",
                "Real API integration",
                "Enhanced monitoring"
            ]
        }

if __name__ == "__main__":
    # Print environment status when run directly
    DemoConfig.print_environment_status()
    
    info = DemoConfig.get_demo_info()
    print(f"🚀 {info['name']} v{info['version']}")
    print(f"🤖 Model: {info['model']}")
    print(f"🧪 Scenarios: {info['scenarios']}")
    print("🌟 Features:")
    for feature in info['features']:
        print(f"   • {feature}") 