#!/usr/bin/env python3
"""
Personal Assistant Agent

A simple demonstration of OpenAIGenesisAgent that automatically discovers
and calls available services (like calculator) while handling conversational
queries through OpenAI.

This shows the recommended pattern:
- Inherit from OpenAIGenesisAgent
- Enable agent communication for agent-as-tool pattern
- Let Genesis auto-start the RPC service on instantiation (run() optional)
- Genesis handles discovery and communication automatically
"""

import asyncio
import logging
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PersonalAssistant(OpenAIGenesisAgent):
    """
    A friendly, helpful personal assistant that can:
    - Have natural conversations using OpenAI
    - Automatically discover and call available services
    - Handle both conversational and functional requests
    """
    
    def __init__(self):
        super().__init__(
            model_name="gpt-4o",
            agent_name="PersonalAssistant",
            base_service_name="OpenAIAgent",
            description="A friendly, helpful general-purpose AI assistant for everyday tasks",
            enable_agent_communication=True  # Enable agent-as-tool pattern
        )
        logger.info("PersonalAssistant initialized successfully")

async def main():
    """
    Main entry point - creates and runs the PersonalAssistant.
    
    CRITICAL: Must use await self.run() to start the Genesis RPC service.
    This is what makes the agent discoverable and able to handle requests.
    """
    logger.info("🤖 Starting PersonalAssistant...")
    
    assistant = PersonalAssistant()
    
    logger.info("✅ PersonalAssistant created; running via auto-start (no explicit run())...")

    # Keep process alive while background service runs
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        try:
            await assistant.close()
        except Exception:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 PersonalAssistant shutting down...")
    except Exception as e:
        logger.error(f"❌ Error running PersonalAssistant: {e}")
        raise 
