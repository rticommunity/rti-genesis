import asyncio
import logging
import sys
import argparse # Added for command-line arguments
from genesis_lib.monitored_interface import MonitoredInterface
from genesis_lib.logging_config import set_genesis_library_log_level # Import the new utility

# Get a logger instance for this specific module.
# The actual configuration (level, formatters, handlers) will be done in the main() function.
logger = logging.getLogger("SimpleGenesisInterfaceCLI")

# Define a constant for the interface's own name.
# This can be used for identification in logs or discovery mechanisms if needed.
INTERFACE_NAME = "SimpleCLI-111"

# The AGENT_SERVICE_NAME is no longer a fixed target. Instead, the interface
# will discover available agents and allow the user to select one.

async def main(verbose: bool = False): # Added verbose parameter
    """
    The main asynchronous function to set up logging, initialize, and run the 
    Simple Genesis Interface Command Line Interface (CLI).

    This CLI allows a user to discover and connect to a Genesis agent, and then
    send messages to it interactively.

    Args:
        verbose (bool, optional): If True, sets logging to DEBUG level for this script
                                  and the `genesis_lib`. Defaults to False (INFO level).
    """
    # Determine the logging level based on the verbose flag.
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Configure basic logging for the application script.
    # This sets the default logging level for all loggers in the application
    # unless they are explicitly overridden.
    logging.basicConfig(
        level=log_level, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True # `force=True` ensures that if the root logger was already configured, this configuration will override it.
    )

    # If verbose mode is enabled for this script, also set the `genesis_lib` 
    # loggers to DEBUG level. This provides more detailed output from the library.
    if verbose:
        set_genesis_library_log_level(logging.DEBUG)
        logger.debug("Verbose logging enabled for 'genesis_lib'.")
    # If not verbose, `genesis_lib` loggers will typically inherit the level set by
    # the `logging.basicConfig` call (e.g., INFO).

    logger.info(f"Initializing '{INTERFACE_NAME}' (Log Level: {logging.getLevelName(log_level)})...")
    
    # Initialize the MonitoredInterface.
    # `interface_name` is a friendly name for this interface instance.
    # `service_name` here can be generic, as the specific agent service to connect to
    # will be determined by user selection from discovered agents.
    interface = MonitoredInterface(
        interface_name=INTERFACE_NAME,
        service_name="GenericInterfaceService" # A generic name for this interface service instance.
    )

    # Variables to store details of the agent the user selects to connect to.
    target_agent_id = None
    target_agent_service_name = None
    connected_agent_name = "N/A" # For display purposes once connected.

    try:
        # Initial phase: Wait for agent discovery.
        # The `_agent_found_event` is an asyncio.Event within MonitoredInterface that gets set
        # when the first agent advertisement is received.
        logger.info("Waiting for any agent(s) to become available (up to 30s)...")
        try:
            # Wait for the event to be set, with a timeout to prevent indefinite blocking.
            await asyncio.wait_for(interface._agent_found_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.error("Timeout: No agent discovery signal received within 30 seconds. Exiting.")
            await interface.close() # Ensure resources are released.
            return

        # Once the first agent is found, allow a brief moment for other agents that might be
        # starting up simultaneously to also announce themselves.
        logger.info("First agent(s) found. Waiting a moment for others to appear...")
        await asyncio.sleep(2)

        # Check if any agents are actually available in the interface's tracking.
        if not interface.available_agents:
            logger.error("No agents were discovered even after waiting. Exiting.")
            await interface.close()
            return

        # Agent selection phase.
        logger.info("Available agents:")
        # Convert the dictionary of available agents to a list for indexed selection.
        agent_list = list(interface.available_agents.values())
        for i, agent_info in enumerate(agent_list):
            # Display information about each discovered agent to the user.
            # `prefered_name` is usually the `agent_name` set by the agent.
            # `instance_id` is a unique identifier for the agent instance.
            # `service_name` is the RPC service name the agent is offering.
            print(f"  {i+1}. Name: '{agent_info.get('prefered_name', 'N/A')}', ID: '{agent_info.get('instance_id')}', Service: '{agent_info.get('service_name')}'")

        if not agent_list: # Should be redundant due to the earlier check, but good for safety.
            logger.error("No agents available to select. Exiting.")
            await interface.close()
            return

        # Loop to get valid user input for agent selection.
        selected_index = -1
        while True:
            try:
                # Use asyncio.to_thread to run the blocking input() call in a separate thread,
                # preventing it from blocking the asyncio event loop.
                choice = await asyncio.to_thread(input, "Select agent by number: ")
                selected_index = int(choice) - 1 # Convert to 0-based index.
                if 0 <= selected_index < len(agent_list):
                    selected_agent = agent_list[selected_index]
                    target_agent_id = selected_agent.get('instance_id')
                    target_agent_service_name = selected_agent.get('service_name')
                    connected_agent_name = selected_agent.get('prefered_name', target_agent_id) # Fallback to ID if name is missing.
                    break # Valid selection, exit loop.
                else:
                    print("Invalid selection. Please enter a number from the list.")
            except ValueError:
                print("Invalid input. Please enter a number.")
            except RuntimeError:
                # This can happen if the input stream is closed (e.g., piped input ends).
                logger.warning("Input stream closed during agent selection.")
                await interface.close()
                return
        
        # Ensure that agent details were successfully retrieved after selection.
        if not target_agent_id or not target_agent_service_name:
            logger.error("Failed to select a valid agent or retrieve its details. Exiting.")
            await interface.close()
            return

        logger.info(f"Attempting to connect to agent '{connected_agent_name}' (ID: {target_agent_id}) offering service '{target_agent_service_name}'...")
        
        # Attempt to establish an RPC connection to the selected agent's service.
        connection_successful = await interface.connect_to_agent(
            service_name=target_agent_service_name, # The specific service name of the chosen agent.
            timeout_seconds=10.0 # Timeout for the connection attempt.
        )
        
        # If connection is successful, MonitoredInterface internally sets up the RPC client.
        # Storing `_connected_agent_id` might be used by the interface for context, 
        # e.g. to verify if the connected agent is still among available_agents later.
        if connection_successful:
            interface._connected_agent_id = target_agent_id # Note: direct access to a protected member.
                                                        # Consider if MonitoredInterface should expose a method or property for this.

        if not connection_successful:
            logger.error(f"Failed to establish RPC connection with agent '{connected_agent_name}' for service '{target_agent_service_name}'. Exiting.")
            await interface.close()
            return

        logger.info(f"Successfully connected to agent: '{connected_agent_name}' (Service: '{target_agent_service_name}').")
        print("You can now send messages. Type 'quit' or 'exit' to stop.")

        # Main interaction loop: get user input and send to agent.
        while True:
            try:
                user_input = await asyncio.to_thread(input, f"To [{connected_agent_name}]: ")
            except RuntimeError:
                logger.warning("Input stream closed during message input.")
                break # Exit loop if input stream is closed.
                
            if user_input.lower() in ['quit', 'exit']:
                logger.info("User requested exit.")
                break # Exit loop if user types quit/exit.

            if not user_input: # Skip empty input.
                continue

            # Prepare the request data. The structure depends on what the agent expects.
            # For OpenAIGenesisAgent, it typically expects a dictionary with a "message" key.
            request_data = {"message": user_input}
            logger.info(f"Sending to agent: {request_data}")
            
            # Send the request to the connected agent and await the response.
            response = await interface.send_request(request_data, timeout_seconds=20.0)
            
            if response:
                # Process and display the agent's response.
                # The response structure also depends on the agent; OpenAIGenesisAgent usually
                # returns a dictionary with "message" and "status".
                print(f"Agent response: {response.get('message', 'No message content in response')}")
                if response.get('status', 0) != 0: # Assuming status 0 is success.
                    logger.warning(f"Agent indicated an issue with status: {response.get('status')}")
            else:
                logger.error("No response from agent or request timed out.")
                # Check if the lack of response might be due to the agent disappearing.
                # `available_agents` is updated by the discovery mechanism.
                if interface._connected_agent_id and \
                   interface._connected_agent_id not in interface.available_agents:
                     logger.error("Connection lost: The agent may have departed. Please restart the CLI.")
                     break # Exit loop as connection is lost.

    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C.
        print("\nKeyboard interrupt received. Shutting down...") # User-facing message for Ctrl+C.
    except Exception as e:
        # Log any other unexpected exceptions.
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        # This block ensures that resources are cleaned up.
        logger.info(f"Closing '{INTERFACE_NAME}' and releasing resources...")
        if 'interface' in locals() and interface: # Check if 'interface' was initialized.
            await interface.close() # Call the interface's close method.
        logger.info(f"'{INTERFACE_NAME}' has been shut down.")

if __name__ == "__main__":
    # This block executes when the script is run directly.

    # Set up an argument parser for command-line options.
    parser = argparse.ArgumentParser(description="Run the Simple Genesis Interface CLI.")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true", # If this flag is present, args.verbose will be True.
        help="Enable verbose logging (DEBUG level) for the CLI and Genesis libraries."
    )
    args = parser.parse_args() # Parse the arguments.

    try:
        # Run the main asynchronous function.
        asyncio.run(main(verbose=args.verbose)) # Pass the verbose flag.
    except KeyboardInterrupt:
        # This handles Ctrl+C if it occurs before or during asyncio.run() setup,
        # though the one inside main() is more typical for interrupting the running loop.
        logger.info("CLI terminated by user at top level.")
    # Exit the script. sys.exit(0) indicates successful termination.
    sys.exit(0)
