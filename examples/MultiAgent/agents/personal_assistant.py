#!/usr/bin/env python3
"""
PersonalAssistant - Multi-Agent Example

Modern personal assistant demonstrating Genesis's advanced multi-agent
capabilities including automatic agent discovery, delegation, and
function service integration.

Features:
- Automatic agent discovery and delegation
- Function service integration (Calculator)
- Intelligent routing based on query content
- Agent-as-tool pattern with capability-based discovery
- Enhanced tracing and monitoring

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

# Import demo configuration
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.demo_config import should_trace_agents, demo_mode_active

# Configure logging based on demo mode
if demo_mode_active():
    logging.basicConfig(level=logging.WARNING)  # Minimal logging for demos
else:
    logging.basicConfig(level=logging.INFO)     # Full logging for debugging

logger = logging.getLogger(__name__)

class PersonalAssistant(OpenAIGenesisAgent):
    """
    General personal assistant agent with agent-to-agent communication capabilities.
    
    This agent demonstrates the complete Genesis ecosystem:
    - Agent discovery and delegation
    - Function service integration  
    - Clean demo mode vs debugging mode
    """
    
    def __init__(self):
        # Determine tracing mode based on demo configuration
        enable_tracing = should_trace_agents()
        
        if enable_tracing:
            logger.info("🚀 Initializing PersonalAssistant with tracing enabled")
        
        # Initialize with configuration-controlled tracing
        # RPC v2: No instance tags needed - uses unified topics with GUID targeting
        
        super().__init__(
            model_name="o3-2025-04-16",
            agent_name="PersonalAssistant",
            base_service_name="PersonalAssistant",
            description="General personal assistant with access to specialized agents and services",
            enable_agent_communication=True,
            enable_tracing=enable_tracing  # Use demo configuration
        )
        
        if enable_tracing:
            logger.info(f"✅ PersonalAssistant initialized with agent_id: {self.app.agent_id}")
        elif demo_mode_active():
            # In demo mode, show minimal startup message
            print("✅ PersonalAssistant ready")
        
        logger.info("PersonalAssistant ready for multi-agent interactions")

    def get_agent_capabilities(self):
        """Define PersonalAssistant capabilities"""
        return {
            "agent_type": "general",
            "specializations": ["coordination", "delegation", "general_assistance"],
            "capabilities": [
                "general_assistance", "conversation", "task_coordination",
                "agent_delegation", "function_calling", "multi_modal_support",
                "context_management", "user_interaction"
            ],
            "classification_tags": [
                "general", "assistant", "coordinator", "delegator", "helpful",
                "conversation", "chat", "support", "multi_agent", "integration"
            ],
            "model_info": {
                "type": "general_purpose_coordinator",
                "llm_model": "gpt-4o",
                "delegation_capable": True,
                "function_calling": True,
                "agent_discovery": True
            },
            "default_capable": True,  # General agent can handle various queries
            "performance_metrics": {
                "avg_response_time": 3.0,
                "delegation_success_rate": 92.0,
                "user_satisfaction": 88.0,
                "availability": 99.9
            }
        }

async def main():
    """Main entry point for PersonalAssistant"""
    logger.info("🤖 Starting PersonalAssistant with multi-agent capabilities...")
    logger.info("🌟 This agent demonstrates Genesis's advanced delegation patterns!")
    
    # Create and run assistant
    assistant = PersonalAssistant()
    
    try:
        logger.info("📡 PersonalAssistant starting - will be discoverable as 'PersonalAssistant'")
        logger.info("🔍 Will automatically discover:")
        logger.info("   • WeatherAgent (for weather queries)")
        logger.info("   • Calculator Service (for math operations)")
        logger.info("   • Any other available agents and functions")
        logger.info("🚀 Agent-to-agent delegation and function calling enabled!")
        await assistant.run()
    except KeyboardInterrupt:
        logger.info("⏹️ PersonalAssistant stopped by user")
    except Exception as e:
        logger.error(f"❌ PersonalAssistant error: {e}")
        raise
    finally:
        await assistant.close()
        logger.info("👋 PersonalAssistant shutdown complete")

if __name__ == "__main__":
    asyncio.run(main()) 