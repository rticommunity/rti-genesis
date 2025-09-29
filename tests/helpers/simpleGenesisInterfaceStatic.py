import asyncio
import logging
import sys
import argparse
from genesis_lib.monitored_interface import MonitoredInterface
from genesis_lib.logging_config import set_genesis_library_log_level

logger = logging.getLogger("SimpleGenesisInterfaceStatic")

INTERFACE_NAME = "SimpleStaticInterface-001"
MATH_QUESTION = "What is 123 plus 456?" # Predefined question
# EXPECTED_ANSWER_SUBSTRING = "579" # We'll check for this in the shell script via logs

async def main(verbose: bool = False, question: str = MATH_QUESTION):
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout # Ensure logs go to stdout for shell script to capture
    )

    if verbose:
        set_genesis_library_log_level(logging.DEBUG)

    logger.info(f"Initializing '{INTERFACE_NAME}' (Log Level: {logging.getLevelName(log_level)})...")
    interface = MonitoredInterface(
        interface_name=INTERFACE_NAME,
        service_name="StaticInterfaceService"
    )

    target_agent_id = None
    target_agent_service_name = None
    connected_agent_name = "N/A"
    exit_code = 1 # Default to failure

    try:
        logger.info("Waiting for any agent(s) to become available (up to 30s)...")
        try:
            await asyncio.wait_for(interface._agent_found_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.error("Timeout: No agent discovery signal received within 30 seconds. Exiting.")
            await interface.close()
            return exit_code

        logger.info("First agent(s) found. Waiting a moment for others to appear...")
        await asyncio.sleep(2) # Allow time for all agents to announce

        if not interface.available_agents:
            logger.error("No agents were discovered even after waiting. Exiting.")
            await interface.close()
            return exit_code

        logger.info("Available agents:")
        agent_list = list(interface.available_agents.values())
        for i, agent_info in enumerate(agent_list):
            logger.info(f"  {i+1}. Name: '{agent_info.get('prefered_name', 'N/A')}', ID: '{agent_info.get('instance_id')}', Service: '{agent_info.get('service_name')}'")

        if not agent_list:
            logger.error("No agents available to select. Exiting.")
            await interface.close()
            return exit_code

        # Automatically select the first agent
        selected_agent = agent_list[0]
        target_agent_id = selected_agent.get('instance_id')
        target_agent_service_name = selected_agent.get('service_name')
        connected_agent_name = selected_agent.get('prefered_name', target_agent_id)
        
        if not target_agent_id or not target_agent_service_name:
            logger.error(f"Failed to automatically select an agent or retrieve its details. Agent info: {selected_agent}. Exiting.")
            await interface.close()
            return exit_code

        logger.info(f"Attempting to connect to agent '{connected_agent_name}' (ID: {target_agent_id}) offering service '{target_agent_service_name}'...")
        
        connection_successful = await interface.connect_to_agent(
            service_name=target_agent_service_name,
            timeout_seconds=10.0
        )
        
        if connection_successful:
            # This was an internal detail for the CLI's display, not strictly necessary for connection status
            # but good for logging if the MonitoredInterface uses it.
            interface._connected_agent_id = target_agent_id 

        if not connection_successful:
            logger.error(f"Failed to establish RPC connection with agent '{connected_agent_name}' for service '{target_agent_service_name}'. Exiting.")
            await interface.close()
            return exit_code

        print(f"Successfully connected to agent: '{connected_agent_name}' (Service: '{target_agent_service_name}').")
        
        request_data = {"message": question}
        print(f"Sending to agent [{connected_agent_name}]: {request_data}")
        
        response = await interface.send_request(request_data, timeout_seconds=20.0)
        
        if response:
            print(f"Agent response: {response.get('message', 'No message content in response')}")
            if response.get('status', -1) == 0:
                # We will verify content in the shell script via grep
                print("Request successful and response received.")
                exit_code = 0 # Success
            else:
                logger.warning(f"Agent indicated an issue with status: {response.get('status')}")
        else:
            logger.error("No response from agent or request timed out.")
            if interface._connected_agent_id and interface._connected_agent_id not in interface.available_agents :
                 logger.error("Connection lost: The agent may have departed.")

    except KeyboardInterrupt:
        logger.info("\\\\nKeyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        logger.info(f"Closing '{INTERFACE_NAME}' and releasing resources...")
        if 'interface' in locals() and interface:
            await interface.close()
        logger.info(f"'{INTERFACE_NAME}' has been shut down. Exiting with code {exit_code}.")
        # The return from main will be used by sys.exit
        return exit_code

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Simple Genesis Static Interface.")
    parser.add_argument(
        "--question",
        type=str,
        default=MATH_QUESTION,
        help="The question to send to the agent."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level) for the script and Genesis libraries."
    )
    args = parser.parse_args()

    # The script will now exit with 0 on success, 1 on failure, based on main's return
    # This is important for the calling shell script to determine test pass/fail.
    script_result_code = 1 # Default to failure
    try:
        script_result_code = asyncio.run(main(verbose=args.verbose, question=args.question))
    except KeyboardInterrupt:
        logger.info("Script terminated by user.")
    except Exception as e:
        logger.error(f"Unhandled exception in __main__: {e}", exc_info=True)
    finally:
        sys.exit(script_result_code) 