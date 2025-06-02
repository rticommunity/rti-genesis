#!/usr/bin/env python3
"""
Test Configuration System

Simple test to validate that our configuration system loads correctly
and provides expected values.
"""

import sys
import os

# Add the parent directory to the path so we can import config modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.agent_configs import (
    get_agent_config, 
    get_all_general_assistants, 
    list_available_agents
)
from config.system_settings import (
    get_system_config, 
    validate_environment,
    get_agent_defaults
)

def test_agent_configs():
    """Test agent configuration loading."""
    print("🧪 Testing Agent Configurations...")
    
    # Test getting all general assistants
    general_assistants = get_all_general_assistants()
    print(f"✅ Found {len(general_assistants)} general assistants:")
    for name, config in general_assistants.items():
        print(f"   - {config['display_name']}: {config['description'][:50]}...")
    
    # Test getting specific agent config
    personal_config = get_agent_config("personal_assistant")
    print(f"✅ Personal Assistant config loaded: {personal_config['name']}")
    print(f"   Capabilities: {', '.join(personal_config['capabilities'])}")
    
    # Test listing all agents
    all_agents = list_available_agents()
    print(f"✅ Total agents available: {len(all_agents)}")
    
    return True

def test_system_settings():
    """Test system settings loading."""
    print("\n🧪 Testing System Settings...")
    
    # Test system config
    config = get_system_config()
    print(f"✅ System config loaded with {len(config)} settings")
    print(f"   Domain ID: {config['domain_id']}")
    print(f"   OpenAI Model: {config['openai_model']}")
    print(f"   Debug Mode: {config['debug_mode']}")
    
    # Test environment validation
    validation = validate_environment()
    print(f"✅ Environment validation: {'VALID' if validation['valid'] else 'INVALID'}")
    if validation['warnings']:
        print(f"   Warnings: {len(validation['warnings'])}")
        for warning in validation['warnings']:
            print(f"     ⚠️  {warning}")
    if validation['errors']:
        print(f"   Errors: {len(validation['errors'])}")
        for error in validation['errors']:
            print(f"     ❌ {error}")
    
    # Test agent defaults
    agent_defaults = get_agent_defaults()
    print(f"✅ Agent defaults: {len(agent_defaults)} settings")
    
    return validation['valid']

def main():
    """Run all configuration tests."""
    print("🚀 Multi-Agent Configuration System Test")
    print("=" * 50)
    
    try:
        # Test agent configurations
        config_success = test_agent_configs()
        
        # Test system settings
        settings_success = test_system_settings()
        
        # Overall result
        print("\n" + "=" * 50)
        if config_success and settings_success:
            print("🎉 All configuration tests PASSED!")
            return 0
        else:
            print("❌ Some configuration tests FAILED!")
            return 1
    
    except Exception as e:
        print(f"\n❌ Configuration test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main()) 