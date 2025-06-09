#!/usr/bin/env python3
"""
PersonalAssistant Test Service

A test personal assistant service for testing agent-to-agent communication.
Uses the standard OpenAIGenesisAgent with built-in enhanced tracing.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PersonalAssistant(OpenAIGenesisAgent):
    """
    Test personal assistant with enhanced built-in tracing.
    """
    
    def __init__(self):
        print("🚀 TRACE: PersonalAssistant.__init__() starting...")
        
        # Initialize with built-in enhanced tracing enabled
        super().__init__(
            model_name="gpt-4o",
            agent_name="PersonalAssistant",
            base_service_name="OpenAIAgent",
            description="Test personal assistant with access to specialized agents and services",
            enable_agent_communication=True,
            enable_tracing=True  # Enable built-in enhanced tracing
        )
        
        print(f"✅ TRACE: PersonalAssistant initialized with agent_id: {self.app.agent_id}")
        logger.info("PersonalAssistant ready for multi-agent interactions")

async def main():
    """Main entry point for PersonalAssistant"""
    print("🤖 Starting PersonalAssistant test service...")
    logger.info("Starting PersonalAssistant test service...")
    
    agent = PersonalAssistant()
    
    # Check discovery status using built-in tracing
    await asyncio.sleep(2)
    if agent.enable_tracing:
        agent._trace_discovery_status("STARTUP CHECK")
    
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main()) 