from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
import asyncio
import logging # Added for script-level logging
import argparse # Added for command-line arguments

# Configure basic logging for this script
# The initial logging.basicConfig call has been removed as it's better to
# configure logging once in the main execution block, especially when
# log levels might depend on command-line arguments.
# logging.basicConfig(
#     level=logging.INFO, 
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )

# Get a logger instance for this specific module.
# This allows for more granular control over logging if needed elsewhere.
logger = logging.getLogger("SimpleGenesisAgentScript")

class SimpleGenesisAgent(OpenAIGenesisAgent):
    """
    A simple example of an agent built using the OpenAIGenesisAgent base class.
    RPC v2: Uses unified topics with GUID-based targeting. Multiple instances
    share the same DDS topics and are distinguished by their unique replier_guid.
    """
    def __init__(self):
        """
        Initializes the SimpleGenesisAgent with RPC v2 unified topic architecture.
        """
        # Initialize the base class (OpenAIGenesisAgent) with specific configurations.
        super().__init__(
            model_name="gpt-4o",  # Specifies the primary OpenAI model to be used.
            classifier_model_name="gpt-4o-mini",  # Specifies the OpenAI model for classification tasks.
            agent_name="SimpleGenesisAgentForTheWin",  # A friendly, descriptive name for this agent instance.
            # base_service_name="MyCustomChatService", # Optional: Uncomment to override the default OpenAIChat service name.
            description="A simple agent that listens for messages via Genesis interface and processes them.", 
            enable_tracing=True  # Enable OpenTelemetry tracing for observability.
        )
        # Log that the agent instance has been created.
        # The base class OpenAIGenesisAgent also performs its own logging during initialization.
        logger.info(f"'{self.agent_name}' instance created. RPC Service: '{self.base_service_name}' (unified topics). Ready to connect to Genesis services.")

async def main(tag: str = None, verbose: bool = False): # tag kept for CLI compatibility
    """
    The main asynchronous function to set up logging, initialize, and run the SimpleGenesisAgent.

    Args:
        tag (str, optional): Legacy parameter kept for CLI compatibility. Ignored in RPC v2.
        verbose (bool, optional): If True, sets logging to DEBUG level for this script
                                  and the `genesis_lib`. Defaults to False (INFO level).
    """
    # Note: tag parameter is no longer used - RPC v2 uses unified topics with GUID targeting
    if tag:
        logger.warning(f"Tag '{tag}' specified but ignored - RPC v2 uses unified topics with GUID targeting")
    # Determine the logging level based on the verbose flag.
    log_level = logging.DEBUG if verbose else logging.INFO

    # Configure the root logger.
    # This is the primary point of logging configuration for the application.
    # It's important to set this up before any loggers are used extensively.
    logging.basicConfig(
        level=log_level, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True # `force=True` ensures that if the root logger was already configured (e.g. by a library), this configuration will override it.
    )
    # The explicit setLevel on root logger after basicConfig is redundant if basicConfig is called with `force=True` and `level`.
    # logging.getLogger().setLevel(log_level)

    # If verbose mode is enabled, also set the `genesis_lib` logger to DEBUG.
    # This allows for more detailed output from the underlying Genesis library components.
    if verbose:
        genesis_lib_logger = logging.getLogger("genesis_lib")
        genesis_lib_logger.setLevel(logging.DEBUG) # Set to DEBUG
        # It's good practice to also ensure handlers are present if changing levels directly,
        # but basicConfig(force=True) should have set up a handler on the root logger
        # that child loggers like 'genesis_lib' will propagate to by default.
        logger.debug("Verbose logging enabled for 'genesis_lib'.")


    # Construct a display name for the agent, incorporating the tag if provided.
    agent_display_name = "SimpleGenesisAgent"
    logger.info(f"Initializing '{agent_display_name}' (Log Level: {logging.getLevelName(log_level)})...")
    
    # Instantiate the agent (RPC v2: No tag needed, uses unified topics).
    agent = SimpleGenesisAgent()
    
    try:
        # A short delay to allow for system components (like DDS discovery) to initialize
        # and for the agent's services to be announced on the network.
        logger.info("Allowing 2 seconds for agent components to initialize and announce themselves...")
        await asyncio.sleep(2)
        
        logger.info(f"Starting '{agent.agent_name}' main loop. It will now listen for messages via the Genesis interface.")
        logger.info("Press Ctrl+C to stop the agent.")
        
        # The `GenesisAgent` class (a base for `OpenAIGenesisAgent`) provides a `run()` method.
        # This method typically starts all necessary background tasks, such as listening for
        # incoming RPC requests or messages, and blocks until the agent is shut down.
        if hasattr(agent, 'run') and callable(getattr(agent, 'run', None)):
            await agent.run() # This is the primary call to start the agent's active lifecycle.
        else:
            # This case should ideally not be reached if using the standard GenesisAgent hierarchy.
            logger.error(f"Could not start '{agent.agent_name}' main loop: 'agent.run()' method not found or not callable.")
            logger.info("The agent will not be able to receive messages from the Genesis interface.")

    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C.
        logger.info(f"'{agent.agent_name}' received KeyboardInterrupt. Initiating shutdown...")
    except Exception as e:
        # Log any other unexpected exceptions that occur during the agent's runtime.
        logger.error(f"An unexpected error occurred in '{agent.agent_name}' main loop: {e}", exc_info=True)
    finally:
        # This block ensures that resources are cleaned up regardless of how the try block exits.
        logger.info(f"Closing '{agent.agent_name}' and releasing resources...")
        if 'agent' in locals() and agent: # Check if 'agent' variable exists and was initialized.
            # The `close()` method should handle shutting down services, closing connections, etc.
            await agent.close()
        logger.info(f"'{agent.agent_name}' has been shut down.")

if __name__ == "__main__":
    # This block executes when the script is run directly.
    
    # Set up an argument parser to handle command-line options.
    parser = argparse.ArgumentParser(description="Run the SimpleGenesisAgent.")
    parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="An optional instance tag to make the agent's RPC service name unique (e.g., 'instance1')."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true", # If this flag is present, args.verbose will be True.
        help="Enable verbose logging (DEBUG level) for the agent script and Genesis libraries."
    )
    args = parser.parse_args() # Parse the command-line arguments.

    # Run the main asynchronous function using asyncio.run().
    # Pass the parsed 'tag' and 'verbose' arguments to the main function.
    asyncio.run(main(tag=args.tag, verbose=args.verbose))
