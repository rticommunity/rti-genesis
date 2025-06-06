#!/usr/bin/env python3
"""
PersonalAssistant for Multi-Agent Demo V2

A general-purpose personal assistant that can:
- Handle general conversation and questions
- Discover and call other specialized agents (like WeatherAgent)
- Discover and call function services (like calculator)
- Demonstrate agent-as-tool pattern where agents can call each other

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PersonalAssistant(OpenAIGenesisAgent):
    """
    General-purpose personal assistant for multi-agent system.
    Can delegate to specialized agents and call function services.
    """
    
    def __init__(self):
        print("🚀 TRACE: PersonalAssistant.__init__() starting...")
        
        # Initialize with enhanced tracing enabled
        super().__init__(
            model_name="gpt-4o",
            agent_name="PersonalAssistant",
            base_service_name="OpenAIAgent",
            description="General-purpose personal assistant with access to specialized agents and services",
            enable_agent_communication=True,
            enable_tracing=True  # Enable detailed tracing built into base class
        )
        
        print(f"✅ TRACE: PersonalAssistant initialized with agent_id: {self.app.agent_id}")
        logger.info("PersonalAssistant ready for multi-agent interactions")

async def main():
    """Main entry point for PersonalAssistant"""
    print("🤖 Starting PersonalAssistant...")
    logger.info("Starting PersonalAssistant...")
    
    agent = PersonalAssistant()
    
    # Add a small delay and then check discovery status (using built-in tracing)
    await asyncio.sleep(2)
    if agent.enable_tracing:
        agent._trace_discovery_status("STARTUP CHECK")
    
    # Add another check after more time to see if WeatherAgent appears
    print("\n🕐 TRACE: Waiting 8 more seconds to see if more agents are discovered...")
    await asyncio.sleep(8)
    print("🕐 TRACE: === DELAYED DISCOVERY CHECK ===")
    if agent.enable_tracing:
        agent._trace_discovery_status("DELAYED CHECK")
    
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main()) 