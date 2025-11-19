import asyncio
import logging
import sys
import argparse
from genesis_lib.monitored_interface import MonitoredInterface
from genesis_lib.logging_config import set_genesis_library_log_level

logger = logging.getLogger("SimpleGenesisInterfaceCLI")
INTERFACE_NAME = "SimpleCLI-111"

async def main(verbose: bool = False, quiet: bool = False):
    """
    Main function to run the Simple Genesis Interface CLI.
    Discovers and connects to a Genesis agent, then sends messages interactively.

    Args:
        verbose: If True, sets logging to DEBUG level. Defaults to False (INFO level).
        quiet: If True, sets logging to WARNING level. Defaults to False.
    """
    # Configure logging level
    if verbose:
        log_level = logging.DEBUG
        set_genesis_library_log_level(logging.DEBUG)
    elif quiet:
        log_level = logging.WARNING
        set_genesis_library_log_level(logging.WARNING)
        # Suppress specific noisy loggers
        logging.getLogger("graph_monitoring").setLevel(logging.WARNING)
        logging.getLogger("").setLevel(logging.WARNING)  # Anonymous logger
    else:
        log_level = logging.INFO
    
    logging.basicConfig(
        level=log_level, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )
    logging.getLogger().setLevel(log_level)

    logger.info(f"Initializing '{INTERFACE_NAME}'...")
    
    interface = MonitoredInterface(
        interface_name=INTERFACE_NAME,
        service_name="GenericInterfaceService"
    )

    target_agent_id = None
    target_agent_service_name = None
    connected_agent_name = "N/A"

    try:
        # Wait for agents to become available
        logger.info("Waiting for agent(s) to become available (up to 30s)...")
        try:
            await asyncio.wait_for(interface._agent_found_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.error("No agents found within 30 seconds. Exiting.")
            await interface.close()
            return

        logger.info("Agents found. Waiting for more to appear...")
        await asyncio.sleep(2)

        if not interface.available_agents:
            logger.error("No agents available. Exiting.")
            await interface.close()
            return

        # Display available agents
        logger.info("Available agents:")
        agent_list = list(interface.available_agents.values())
        for i, agent_info in enumerate(agent_list):
            print(f"  {i+1}. Name: '{agent_info.get('prefered_name', 'N/A')}', ID: '{agent_info.get('instance_id')}', Service: '{agent_info.get('service_name')}'")

        # Get user selection
        selected_index = -1
        while True:
            try:
                choice = await asyncio.to_thread(input, "Select agent by number: ")
                selected_index = int(choice) - 1
                if 0 <= selected_index < len(agent_list):
                    selected_agent = agent_list[selected_index]
                    target_agent_id = selected_agent.get('instance_id')
                    target_agent_service_name = selected_agent.get('service_name')
                    connected_agent_name = selected_agent.get('prefered_name', target_agent_id)
                    break
                else:
                    print("Invalid selection. Please enter a number from the list.")
            except ValueError:
                print("Invalid input. Please enter a number.")
            except RuntimeError:
                logger.warning("Input stream closed during agent selection.")
                await interface.close()
                return
        
        if not target_agent_id or not target_agent_service_name:
            logger.error("Failed to select a valid agent. Exiting.")
            await interface.close()
            return

        logger.info(f"Connecting to agent '{connected_agent_name}'...")
        
        connection_successful = await interface.connect_to_agent(
            service_name=target_agent_service_name,
            timeout_seconds=10.0
        )
        
        if connection_successful:
            interface._connected_agent_id = target_agent_id

        if not connection_successful:
            logger.error(f"Failed to connect to agent '{connected_agent_name}'. Exiting.")
            await interface.close()
            return

        logger.info(f"Successfully connected to agent: '{connected_agent_name}'.")
        print("You can now send messages. Type 'quit' or 'exit' to stop.")

        # Main interaction loop
        while True:
            try:
                user_input = await asyncio.to_thread(input, f"To [{connected_agent_name}]: ")
            except RuntimeError:
                logger.warning("Input stream closed during message input.")
                break
                
            if user_input.lower() in ['quit', 'exit']:
                logger.info("User requested exit.")
                break

            if not user_input:
                continue

            request_data = {"message": user_input}
            logger.info(f"Sending to agent: {request_data}")
            
            response = await interface.send_request(request_data, timeout_seconds=20.0)
            
            if response:
                print(f"Agent response: {response.get('message', 'No message content in response')}")
                if response.get('status', 0) != 0:
                    logger.warning(f"Agent indicated an issue with status: {response.get('status')}")
            else:
                logger.error("No response from agent or request timed out.")
                if interface._connected_agent_id and \
                   interface._connected_agent_id not in interface.available_agents:
                     logger.error("Connection lost: The agent may have departed.")
                     break

    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logger.info("Closing interface...")
        if 'interface' in locals() and interface:
            await interface.close()
        logger.info("Interface shutdown complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Simple Genesis Interface CLI.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose logging (DEBUG level)")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Enable quiet mode (WARNING level) - suppress INFO logs")
    args = parser.parse_args()

    try:
        asyncio.run(main(verbose=args.verbose, quiet=args.quiet))
    except KeyboardInterrupt:
        logger.info("CLI terminated by user at top level.")
    sys.exit(0)
