from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
import asyncio
import logging
import argparse

logger = logging.getLogger("SimpleGenesisAgentScript")

class SimpleGenesisAgent(OpenAIGenesisAgent):
    """
    A simple example agent that responds to messages sent through the Genesis interface.
    """
    def __init__(self):
        super().__init__(
            model_name="gpt-4o",
            classifier_model_name="gpt-4o-mini",
            agent_name="SimpleGenesisAgentForTheWin",
            description="A simple agent that listens for messages via Genesis interface and processes them.", 
            enable_tracing=True
        )
        logger.info(f"Agent '{self.agent_name}' initialized and ready.")

async def main(verbose: bool = False, quiet: bool = False):
    """
    Main function to set up logging, initialize, and run the SimpleGenesisAgent.

    Args:
        verbose: If True, sets logging to DEBUG level. Defaults to False (INFO level).
        quiet: If True, sets logging to WARNING level. Defaults to False.
    """
    # Configure logging level
    if verbose:
        log_level = logging.DEBUG
    elif quiet:
        log_level = logging.WARNING
    else:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )
    
    # Apply quiet mode to genesis_lib if needed
    if quiet:
        logging.getLogger("genesis_lib").setLevel(logging.WARNING)
        logging.getLogger("graph_monitoring").setLevel(logging.WARNING)
        logging.getLogger("").setLevel(logging.WARNING)  # Anonymous logger

    logger.info(f"Initializing SimpleGenesisAgent (Log Level: {logging.getLevelName(log_level)})...")
    
    agent = SimpleGenesisAgent()
    
    try:
        logger.info("Waiting for initialization...")
        await asyncio.sleep(2)
        
        logger.info(f"Starting '{agent.agent_name}' - Press Ctrl+C to stop.")
        await agent.run()

    except KeyboardInterrupt:
        logger.info("Shutdown requested...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logger.info("Closing agent...")
        if 'agent' in locals() and agent:
            await agent.close()
        logger.info("Agent shutdown complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the SimpleGenesisAgent.")
    parser.add_argument("-v", "--verbose", action="store_true", 
                        help="Enable verbose logging (DEBUG level)")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Enable quiet mode (WARNING level) - suppress INFO logs")
    args = parser.parse_args()

    asyncio.run(main(verbose=args.verbose, quiet=args.quiet))
