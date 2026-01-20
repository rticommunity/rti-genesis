# Copyright (c) 2025, RTI & Jason Upchurch
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
import os
import asyncio
import sys
import logging

# Configure logging
logging.getLogger("openai._base_client").setLevel(logging.WARNING)  # Suppress OpenAI client debug logs
logging.getLogger("genesis_lib.function_classifier").setLevel(logging.WARNING)  # Suppress function classifier debug logs

# Configure logger for this module
logger = logging.getLogger("test_agent")

class TestAgent(OpenAIGenesisAgent):
    def __init__(self, domain_id=0):
        # Initialize the base class with our specific configuration
        super().__init__(
            model_name="gpt-4o",  # You can change this to your preferred model
            classifier_model_name="gpt-4o-mini",  # You can change this to your preferred model
            agent_name="TestAgent",  # Match the class name
            description="A test agent for monitoring and function tests",
            enable_tracing=True,  # Enable tracing for testing
            domain_id=domain_id
        )

async def main():
    # Get domain from environment (set by test runner)
    domain_id = int(os.environ.get('GENESIS_DOMAIN_ID', 0))
    
    # Configure basic logging for the script and to see genesis_lib DEBUG logs
    log_level = logging.DEBUG # Or logging.INFO for less verbosity

    # AGGRESSIVE LOGGING RESET
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]: # Iterate over a copy
        root_logger.removeHandler(handler)
        handler.close() # Ensure handlers release resources

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout # Ensure logs go to stdout to be captured by test runner
    )
    # Ensure specific genesis_lib loggers are also at DEBUG if needed,
    # basicConfig might set root, but good to be explicit for key modules.
    logging.getLogger("genesis_lib.function_discovery").setLevel(logging.DEBUG)
    logging.getLogger("genesis_app").setLevel(logging.DEBUG) # For GenesisApp close logs

    # Create and run the agent
    agent = TestAgent(domain_id=domain_id)
    logger.info(f"TestAgent created on domain {domain_id}")
    
    try:
        # Give some time for initialization and announcement propagation
        await asyncio.sleep(5)  # Use async sleep instead of time.sleep
        
        # Log available functions
        available_functions = agent._get_available_functions()
        print("=== Available Functions ===")
        if available_functions:
            for func_name in available_functions.keys():
                print(f"Function: {func_name}")
        else:
            print("No functions discovered")
        print("===========================")
        
        # Get message from command line argument or use default
        message = sys.argv[1] if len(sys.argv) > 1 else "Hello, can you tell me a joke?"
        
        # Example usage
        response = await agent.process_message(message)
        print(f"Agent response: {response}")
        
    finally:
        # Clean up using parent class cleanup
        await agent.close()

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main()) 