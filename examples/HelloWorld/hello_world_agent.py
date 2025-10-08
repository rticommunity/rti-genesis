#!/usr/bin/env python3

"""
HelloWorldAgent - A simple example of a Genesis agent that uses OpenAI capabilities
to interact with a calculator service.
"""

import logging
import asyncio
import sys
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hello_world_agent")

class HelloWorldAgent(OpenAIGenesisAgent):
    """A simple agent that can use the calculator service."""
    
    def __init__(self):
        """Initialize the HelloWorldAgent."""
        super().__init__(
            model_name="gpt-4o",
            classifier_model_name="gpt-4o-mini",
            agent_name="HelloWorldAgent",
            description="A simple agent that can perform basic arithmetic operations",
            enable_tracing=True
        )
        logger.info("HelloWorldAgent initialized")

async def main():
    """Run the HelloWorldAgent with test calculations."""
    try:
        # Create and start agent
        agent = HelloWorldAgent()
        logger.info("Agent started successfully")
        
        # Give some time for initialization
        await asyncio.sleep(2)
        
        # Get message from command line argument or use default
        message = sys.argv[1] if len(sys.argv) > 1 else "What is 42 plus 24?"
        
        # Process the message
        response = await agent.process_message(message)
        print(f"Agent response: {response}")
        
    except Exception as e:
        logger.error(f"Error in agent: {str(e)}")
        raise
    finally:
        if 'agent' in locals():
            await agent.close()

if __name__ == "__main__":
    asyncio.run(main()) 