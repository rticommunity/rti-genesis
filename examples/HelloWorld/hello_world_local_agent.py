#!/usr/bin/env python3

"""
HelloWorldLocalAgent - A simple example of a Genesis agent that uses Ollama for local inference
to interact with a calculator service.

This demonstrates how to use LocalGenesisAgent for completely local LLM inference without
any API costs or cloud dependencies.

Prerequisites:
1. Install Ollama: curl -fsSL https://ollama.com/install.sh | sh
2. Pull a model: ollama pull llama3.2:3b
3. Install Python client: pip install ollama
4. Start Ollama: ollama serve (if not already running)

Usage:
    python hello_world_local_agent.py "What is 42 plus 24?"
"""

import logging
import asyncio
import sys
from genesis_lib.local_genesis_agent import LocalGenesisAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hello_world_local_agent")

class HelloWorldLocalAgent(LocalGenesisAgent):
    """A simple agent that uses local Ollama inference with the calculator service."""
    
    def __init__(self):
        """Initialize the HelloWorldLocalAgent."""
        super().__init__(
            model_name="nemotron-mini:latest",  # Use your installed Ollama model
            classifier_model_name="nemotron-mini:latest",  # Same model for classification
            agent_name="HelloWorldLocalAgent",
            description="A simple local agent that can perform basic arithmetic operations",
            enable_tracing=True  # Enable to see detailed logs
        )
        logger.info("HelloWorldLocalAgent initialized with local Ollama model")

async def main():
    """Run the HelloWorldLocalAgent with test calculations."""
    try:
        # Create and start agent
        agent = HelloWorldLocalAgent()
        logger.info("Agent started successfully")
        
        # Give some time for initialization
        await asyncio.sleep(2)
        
        # Get message from command line argument or use default
        message = sys.argv[1] if len(sys.argv) > 1 else "What is 42 plus 24?"
        
        logger.info(f"Sending message: {message}")
        
        # Process the message
        response = await agent.process_message(message)
        print(f"\n{'='*80}")
        print(f"Agent response: {response}")
        print(f"{'='*80}\n")
        
    except Exception as e:
        logger.error(f"Error in agent: {str(e)}")
        raise
    finally:
        if 'agent' in locals():
            await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
