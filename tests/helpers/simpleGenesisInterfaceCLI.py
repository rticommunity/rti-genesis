import asyncio
import logging
import sys
import argparse  # Added for command-line arguments
from typing import List, Optional
from genesis_lib.monitored_interface import MonitoredInterface
from genesis_lib.logging_config import set_genesis_library_log_level  # Import the new utility

# Logger will be configured in main() after parsing args
logger = logging.getLogger("SimpleGenesisInterfaceCLI")

INTERFACE_NAME = "SimpleCLI-111"
# AGENT_SERVICE_NAME is no longer a fixed target for initial connection filtering.
# The user will select an agent, and its specific service_name will be used.

async def main(
    verbose: bool = False,
    messages: Optional[List[str]] = None,
    messages_file: Optional[str] = None,
    select_service: Optional[str] = None,
    select_name: Optional[str] = None,
    select_first: bool = False,
    max_wait_seconds: float = 30.0,
    connect_timeout_seconds: float = 10.0,
    request_timeout_seconds: float = 20.0,
    sleep_between_seconds: float = 1.0,
):  # Added verbose and non-interactive parameters
    # Configure basic logging for this script
    log_level = logging.DEBUG if verbose else logging.INFO
    # Application script configures its own root logger and its desired level
    logging.basicConfig(
        level=log_level, # This sets the default for all loggers unless overridden
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # If verbose mode is enabled for the script, also make genesis_lib verbose.
    # Otherwise, genesis_lib loggers will respect the script's root logger setting (e.g., INFO).
    # We previously changed noisy INFOs in the library to DEBUGs, so this should be cleaner.
    if verbose:
        set_genesis_library_log_level(logging.DEBUG)
        # The lines below are now handled by set_genesis_library_log_level
        # logging.getLogger("genesis_lib.monitored_interface").setLevel(logging.DEBUG)
        # logging.getLogger("genesis_lib.interface").setLevel(logging.DEBUG)
        # logging.getLogger("genesis_app").setLevel(logging.DEBUG)
    # else:
        # Optional: If you wanted genesis_lib to be *quieter* than the script by default
        # (e.g. script is INFO, but library is WARNING unless script is DEBUG)
        # you could add: set_genesis_library_log_level(logging.WARNING)
        # But for now, let them inherit the script's level or be DEBUG if script is verbose.

    logger.info(
        f"Initializing '{INTERFACE_NAME}' (Log Level: {logging.getLevelName(log_level)})..."
    )
    # Initialize the MonitoredInterface. The service_name here is more of a default
    # or for how the interface itself might be identified, not for filtering agents initially.
    interface = MonitoredInterface(
        interface_name=INTERFACE_NAME,
        service_name="GenericInterfaceService" # Can be a generic name for the interface itself
    )

    target_agent_id = None
    target_agent_service_name = None
    connected_agent_name = "N/A"

    try:
        print(f"Waiting for any agent(s) to become available (up to {max_wait_seconds}s)...")
        try:
            await asyncio.wait_for(interface._agent_found_event.wait(), timeout=max_wait_seconds)
        except asyncio.TimeoutError:
            logger.error("Timeout: No agent discovery signal received within 30 seconds. Exiting.")
            await interface.close()
            return

        print("First agent(s) found. Waiting a moment for others to appear...")
        await asyncio.sleep(2)

        if not interface.available_agents:
            logger.error("No agents were discovered even after waiting. Exiting.")
            await interface.close()
            return

        # Prepare agent list
        agent_list = list(interface.available_agents.values())
        if not agent_list:
            logger.error("No agents were discovered even after waiting. Exiting.")
            await interface.close()
            return

        # Non-interactive selection if criteria provided OR if messages are supplied
        non_interactive = bool(messages or messages_file or select_service or select_name or select_first)
        selected_agent = None

        if non_interactive:
            # Try by service name
            if select_service:
                for agent in agent_list:
                    if agent.get('service_name') == select_service:
                        selected_agent = agent
                        break
            # Try by preferred name
            if selected_agent is None and select_name:
                for agent in agent_list:
                    if agent.get('prefered_name') == select_name:
                        selected_agent = agent
                        break
            # Fallback: first
            if selected_agent is None and (select_first or messages or messages_file):
                selected_agent = agent_list[0]

            if selected_agent is None:
                logger.error("Non-interactive selection criteria did not match any agent. Exiting.")
                await interface.close()
                return
            # Assign selection values
            target_agent_id = selected_agent.get('instance_id')
            target_agent_service_name = selected_agent.get('service_name')
            connected_agent_name = selected_agent.get('prefered_name', target_agent_id)
        else:
            # Interactive selection
            print("Available agents:")
            for i, agent_info in enumerate(agent_list):
                print(
                    f"  {i+1}. Name: '{agent_info.get('prefered_name', 'N/A')}', "
                    f"ID: '{agent_info.get('instance_id')}', Service: '{agent_info.get('service_name')}'"
                )
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
                    print("Input stream closed during selection.")
                    await interface.close()
                    return
        
        if not target_agent_id or not target_agent_service_name:
            logger.error("Failed to select a valid agent or retrieve its details. Exiting.")
            await interface.close()
            return

        # Derive a unique RPC service name. If the advertised service name does not include the
        # agent instance_id, append it so the Requester binds to a single replier.
        unique_service_name = target_agent_service_name
        if target_agent_id and (target_agent_id not in (target_agent_service_name or "")):
            unique_service_name = f"{target_agent_service_name}_{target_agent_id}"

        print(
            f"Attempting to connect to agent '{connected_agent_name}' "
            f"(ID: {target_agent_id}) offering service '{target_agent_service_name}' → binding RPC to '{unique_service_name}'..."
        )
        
        connection_successful = await interface.connect_to_agent(
            service_name=unique_service_name,
            timeout_seconds=connect_timeout_seconds,
        )
        
        if connection_successful:
            interface._connected_agent_id = target_agent_id

        if not connection_successful:
            logger.error(f"Failed to establish RPC connection with agent '{connected_agent_name}' for service '{target_agent_service_name}'. Exiting.")
            await interface.close()
            return

        print(f"Successfully connected to agent: '{connected_agent_name}' (RPC Service: '{unique_service_name}').")
        # If messages were provided, run in batch non-interactive mode
        aggregated_messages: List[str] = []
        if messages:
            aggregated_messages.extend([m for m in messages if m and m.strip()])
        if messages_file:
            try:
                with open(messages_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            aggregated_messages.append(line)
            except Exception as e:
                logger.error(f"Failed to read messages from file '{messages_file}': {e}")

        if aggregated_messages:
            logger.info(
                f"Sending {len(aggregated_messages)} message(s) to agent '{connected_agent_name}'"
            )
            for idx, msg in enumerate(aggregated_messages, start=1):
                request_data = {"message": msg}
                logger.info(f"[{idx}/{len(aggregated_messages)}] Sending to agent: {request_data}")
                # Explicit question print to observe ordering
                print(f"QUESTION[{idx}/{len(aggregated_messages)}]: {msg}", flush=True)
                response = await interface.send_request(
                    request_data, timeout_seconds=request_timeout_seconds
                )
                if response:
                    print(f"REPLY[{idx}/{len(aggregated_messages)}]: {response.get('message', 'No message content in response')}", flush=True)
                    if response.get('status', -1) != 0:
                        logger.warning(
                            f"Agent indicated an issue with status: {response.get('status')}"
                        )
                    # Strict serialization: first wait for ChainEvent COMPLETE if available
                    try:
                        await interface.wait_last_complete(timeout_seconds=1.5)
                    except Exception:
                        pass
                    # Then optional pacing
                    await asyncio.sleep(max(0.0, sleep_between_seconds))
                else:
                    logger.error("No response from agent or request timed out.")
                    print(f"REPLY[{idx}/{len(aggregated_messages)}]: <no response>", flush=True)
                    if (
                        interface._connected_agent_id
                        and interface._connected_agent_id not in interface.available_agents
                    ):
                        logger.error(
                            "Connection lost: The agent may have departed. Aborting batch."
                        )
                        break
                    # small pacing even on error to avoid tight loop
                    await asyncio.sleep(max(0.5, sleep_between_seconds))
        else:
            # Interactive loop
            print("You can now send messages. Type 'quit' or 'exit' to stop.")
            while True:
                try:
                    user_input = await asyncio.to_thread(
                        input, f"To [{connected_agent_name}]: "
                    )
                except RuntimeError:
                    print("Input stream closed.")
                    break

                if user_input.lower() in ['quit', 'exit']:
                    print("User requested exit.")
                    break

                if not user_input:
                    continue

                request_data = {"message": user_input}
                logger.info(f"Sending to agent: {request_data}")

                # Explicit question print in interactive mode
                print(f"QUESTION: {user_input}", flush=True)
                response = await interface.send_request(
                    request_data, timeout_seconds=request_timeout_seconds
                )

                if response:
                    print(f"REPLY: {response.get('message', 'No message content in response')}", flush=True)
                    if response.get('status', -1) != 0:
                        logger.warning(
                            f"Agent indicated an issue with status: {response.get('status')}"
                        )
                else:
                    logger.error("No response from agent or request timed out.")
                    print("REPLY: <no response>", flush=True)
                    if (
                        interface._connected_agent_id
                        and interface._connected_agent_id not in interface.available_agents
                    ):
                        logger.error(
                            "Connection lost: The agent may have departed. Please restart the CLI."
                        )
                        break

    except KeyboardInterrupt:
        print("\\nKeyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        print(f"Closing '{INTERFACE_NAME}' and releasing resources...")
        if 'interface' in locals() and interface:
            await interface.close()
        print(f"'{INTERFACE_NAME}' has been shut down.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Simple Genesis Interface CLI.")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level) for the CLI and Genesis libraries.",
    )
    # Non-interactive batch options
    parser.add_argument(
        "-m",
        "--message",
        action="append",
        dest="messages",
        help="Message to send to the connected agent. Can be specified multiple times.",
    )
    parser.add_argument(
        "--messages-file",
        dest="messages_file",
        help="Path to a file with one message per line to send sequentially.",
    )
    parser.add_argument(
        "--select-service",
        dest="select_service",
        help="Select the first discovered agent matching this service name (non-interactive).",
    )
    parser.add_argument(
        "--select-name",
        dest="select_name",
        help="Select the first discovered agent whose preferred name matches (non-interactive).",
    )
    parser.add_argument(
        "--select-first",
        action="store_true",
        help="Select the first discovered agent (non-interactive).",
    )
    parser.add_argument(
        "--max-wait",
        type=float,
        default=30.0,
        dest="max_wait_seconds",
        help="Max seconds to wait for initial agent discovery.",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=10.0,
        dest="connect_timeout_seconds",
        help="Timeout in seconds to establish connection to the selected agent.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=20.0,
        dest="request_timeout_seconds",
        help="Timeout in seconds for each request.",
    )
    parser.add_argument(
        "--sleep-between",
        type=float,
        default=1.0,
        dest="sleep_between_seconds",
        help="Seconds to sleep between sending messages in batch mode.",
    )

    args = parser.parse_args()

    try:
        asyncio.run(
            main(
                verbose=args.verbose,
                messages=args.messages,
                messages_file=args.messages_file,
                select_service=args.select_service,
                select_name=args.select_name,
                select_first=args.select_first,
                max_wait_seconds=args.max_wait_seconds,
                connect_timeout_seconds=args.connect_timeout_seconds,
                request_timeout_seconds=args.request_timeout_seconds,
                sleep_between_seconds=args.sleep_between_seconds,
            )
        )
    except KeyboardInterrupt:
        logger.info("CLI terminated by user.")
    sys.exit(0)
