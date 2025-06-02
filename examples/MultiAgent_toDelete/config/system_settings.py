#!/usr/bin/env python3
"""
System Settings and Configuration

This module defines system-wide settings, defaults, and environment
configuration for the Smart Assistant Ecosystem.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import os
from typing import Dict, Any, Optional

# Environment Configuration
DEFAULT_DOMAIN_ID = 0
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_DISCOVERY_TIMEOUT = 10.0

# API Configuration
OPENAI_MODEL_DEFAULT = "gpt-4o"
OPENAI_MODEL_CLASSIFIER = "gpt-4o-mini"

# System Behavior
AGENT_STARTUP_DELAY = 2.0  # Seconds between agent startups
SERVICE_DISCOVERY_TIMEOUT = 5.0  # Seconds to wait for services
AGENT_COMMUNICATION_TIMEOUT = 30.0  # Seconds for agent-to-agent calls

# Monitoring Configuration
ENABLE_MONITORING = True
ENABLE_CHAIN_TRACKING = True
ENABLE_PERFORMANCE_METRICS = True

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# CLI Configuration
CLI_COLORS = {
    "primary": "cyan", 
    "secondary": "blue",
    "success": "green",
    "warning": "yellow", 
    "error": "red",
    "info": "white"
}

CLI_REFRESH_RATE = 1.0  # Seconds between status updates

def get_system_config() -> Dict[str, Any]:
    """
    Get complete system configuration including environment variables.
    
    Returns:
        Dictionary containing all system configuration
    """
    config = {
        # DDS Configuration
        "domain_id": int(os.getenv("DDS_DOMAIN_ID", DEFAULT_DOMAIN_ID)),
        "timeout_seconds": float(os.getenv("SYSTEM_TIMEOUT", DEFAULT_TIMEOUT_SECONDS)),
        "discovery_timeout": float(os.getenv("DISCOVERY_TIMEOUT", DEFAULT_DISCOVERY_TIMEOUT)),
        
        # OpenAI Configuration
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_model": os.getenv("OPENAI_MODEL", OPENAI_MODEL_DEFAULT),
        "openai_classifier_model": os.getenv("OPENAI_CLASSIFIER_MODEL", OPENAI_MODEL_CLASSIFIER),
        
        # External APIs
        "weather_api_key": os.getenv("OPENWEATHERMAP_API_KEY"),
        "weather_api_url": "https://api.openweathermap.org/data/2.5",
        
        # Behavior Configuration
        "agent_startup_delay": AGENT_STARTUP_DELAY,
        "service_discovery_timeout": SERVICE_DISCOVERY_TIMEOUT,
        "agent_communication_timeout": AGENT_COMMUNICATION_TIMEOUT,
        
        # Monitoring Configuration
        "enable_monitoring": bool(os.getenv("ENABLE_MONITORING", ENABLE_MONITORING)),
        "enable_chain_tracking": bool(os.getenv("ENABLE_CHAIN_TRACKING", ENABLE_CHAIN_TRACKING)),
        "enable_performance_metrics": bool(os.getenv("ENABLE_PERFORMANCE_METRICS", ENABLE_PERFORMANCE_METRICS)),
        
        # Logging Configuration  
        "log_level": os.getenv("LOG_LEVEL", LOG_LEVEL),
        "log_format": LOG_FORMAT,
        
        # CLI Configuration
        "cli_colors": CLI_COLORS,
        "cli_refresh_rate": float(os.getenv("CLI_REFRESH_RATE", CLI_REFRESH_RATE)),
        
        # Development/Debug Configuration
        "debug_mode": bool(os.getenv("DEBUG", False)),
        "verbose_logging": bool(os.getenv("VERBOSE", False))
    }
    
    return config

def validate_environment() -> Dict[str, Any]:
    """
    Validate environment configuration and return status.
    
    Returns:
        Dictionary with validation results
    """
    validation = {
        "valid": True,
        "warnings": [],
        "errors": [],
        "config": get_system_config()
    }
    
    config = validation["config"]
    
    # Check required API keys
    if not config["openai_api_key"]:
        validation["warnings"].append("OPENAI_API_KEY not set - AI assistants will have limited functionality")
    
    if not config["weather_api_key"]:
        validation["warnings"].append("OPENWEATHERMAP_API_KEY not set - weather features will be limited")
    
    # Check domain ID range
    if config["domain_id"] < 0 or config["domain_id"] > 255:
        validation["errors"].append(f"Invalid DDS_DOMAIN_ID: {config['domain_id']} (must be 0-255)")
        validation["valid"] = False
    
    # Check timeout values
    if config["timeout_seconds"] <= 0:
        validation["errors"].append(f"Invalid SYSTEM_TIMEOUT: {config['timeout_seconds']} (must be > 0)")
        validation["valid"] = False
    
    if config["discovery_timeout"] <= 0:
        validation["errors"].append(f"Invalid DISCOVERY_TIMEOUT: {config['discovery_timeout']} (must be > 0)")
        validation["valid"] = False
    
    return validation

def get_agent_defaults() -> Dict[str, Any]:
    """
    Get default configuration values for agents.
    
    Returns:
        Dictionary with agent defaults
    """
    config = get_system_config()
    
    return {
        "domain_id": config["domain_id"],
        "enable_tracing": config["debug_mode"],
        "enable_agent_communication": True,
        "timeout_seconds": config["agent_communication_timeout"],
        "model_name": config["openai_model"],
        "classifier_model_name": config["openai_classifier_model"]
    }

def get_service_defaults() -> Dict[str, Any]:
    """
    Get default configuration values for services.
    
    Returns:
        Dictionary with service defaults
    """
    config = get_system_config()
    
    return {
        "domain_id": config["domain_id"],
        "enable_monitoring": config["enable_monitoring"],
        "timeout_seconds": config["timeout_seconds"]
    }

def get_interface_defaults() -> Dict[str, Any]:
    """
    Get default configuration values for interfaces.
    
    Returns:
        Dictionary with interface defaults
    """
    config = get_system_config()
    
    return {
        "discovery_timeout": config["discovery_timeout"],
        "agent_communication_timeout": config["agent_communication_timeout"],
        "refresh_rate": config["cli_refresh_rate"]
    }

# Development/Testing Configuration
DEV_CONFIG = {
    "test_mode": bool(os.getenv("TEST_MODE", False)),
    "mock_external_apis": bool(os.getenv("MOCK_APIS", False)),
    "fast_startup": bool(os.getenv("FAST_STARTUP", False)),  # Reduced delays for testing
    "test_data_dir": os.path.join(os.path.dirname(__file__), "..", "TEST", "data")
}

def get_dev_config() -> Dict[str, Any]:
    """Get development/testing configuration."""
    return DEV_CONFIG.copy()

def is_test_mode() -> bool:
    """Check if system is running in test mode."""
    return DEV_CONFIG["test_mode"]

def should_mock_apis() -> bool:
    """Check if external APIs should be mocked."""
    return DEV_CONFIG["mock_external_apis"] 