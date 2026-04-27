#!/usr/bin/env python3

"""
HelloWorldLocalAgent Interactive - A simple example of a Genesis agent that uses Ollama 
for local inference to interact with a calculator service.

This interactive version allows you to have a conversation with the agent.

Prerequisites:
1. Install Ollama: curl -fsSL https://ollama.com/install.sh | sh
2. Pull a model: ollama pull nemotron-mini
3. Install Python client: pip install ollama
4. Start Ollama: ollama serve (if not already running)

Usage:
    python hello_world_local_agent_interactive.py
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
    """Run the HelloWorldLocalAgent with interactive question handling."""
    try:
        # Create and start agent
        agent = HelloWorldLocalAgent()
        logger.info("Agent started successfully")
        
        # Give some time for initialization
        await asyncio.sleep(2)
        
        print("\n" + "="*80)
        print("🤖 Hello! I'm your local AI assistant powered by Ollama.")
        print("   Ask me questions or give me tasks. Type 'exit' to quit.")
        print("="*80 + "\n")
        
        while True:
            # Prompt user for input
            try:
                message = input("You: ")
            except (EOFError, KeyboardInterrupt):
                print("\n\nGoodbye!")
                break
            
            # Exit if the user types 'exit'
            if message.lower() in ['exit', 'quit', 'bye']:
                print("Goodbye! 👋")
                break
            
            # Skip empty messages
            if not message.strip():
                continue
            
            # Process the message
            try:
                response = await agent.process_message(message)
                print(f"🤖 Agent: {response}\n")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                print("⚠️  An error occurred. Please try again.\n")
        
    except Exception as e:
        logger.error(f"Error in agent: {str(e)}")
        raise
    finally:
        if 'agent' in locals():
            await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
