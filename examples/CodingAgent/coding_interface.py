#!/usr/bin/env python3
"""
CodingGenesisInterface — Interactive CLI for the CodingGenesisAgent.

Discovers available CodingGenesisAgents on the Genesis network,
lets the user select one, then provides an interactive chat loop
for sending coding tasks.

No genesis_lib modifications required.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import argparse
import asyncio
import logging
import sys

from genesis_lib.monitored_interface import MonitoredInterface
from genesis_lib.logging_config import set_genesis_library_log_level

logger = logging.getLogger("CodingGenesisInterface")

INTERFACE_NAME = "CodingCLI"

# Coding tasks can be long-running (subprocess compile, test, etc.)
DEFAULT_REQUEST_TIMEOUT = 300.0


async def main(verbose: bool = False):
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,
    )
    if verbose:
        set_genesis_library_log_level(logging.DEBUG)

    logger.info(f"Initializing '{INTERFACE_NAME}'...")

    interface = MonitoredInterface(
        interface_name=INTERFACE_NAME,
        service_name="CodingInterfaceService",
    )

    target_agent_id = None
    target_agent_service_name = None
    connected_agent_name = "N/A"

    try:
        # --- Agent discovery ---
        logger.info("Waiting for coding agent(s) to become available (up to 30s)...")
        try:
            await asyncio.wait_for(interface._agent_found_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.error("Timeout: No agents discovered within 30 seconds. Exiting.")
            await interface.close()
            return

        logger.info("Agent(s) found. Waiting briefly for additional agents...")
        await asyncio.sleep(2)

        if not interface.available_agents:
            logger.error("No agents available. Exiting.")
            await interface.close()
            return

        # --- Agent selection ---
        agent_list = list(interface.available_agents.values())
        print("\nAvailable agents:")
        for i, agent_info in enumerate(agent_list):
            print(
                f"  {i+1}. Name: '{agent_info.get('prefered_name', 'N/A')}', "
                f"Service: '{agent_info.get('service_name')}'"
            )

        # Auto-select if there's only one agent
        if len(agent_list) == 1:
            selected_agent = agent_list[0]
            target_agent_id = selected_agent.get("instance_id")
            target_agent_service_name = selected_agent.get("service_name")
            connected_agent_name = selected_agent.get("prefered_name", target_agent_id)
            print(f"\nAuto-selected: {connected_agent_name}")
        else:
            while True:
                try:
                    choice = await asyncio.to_thread(input, "Select agent by number: ")
                    selected_index = int(choice) - 1
                    if 0 <= selected_index < len(agent_list):
                        selected_agent = agent_list[selected_index]
                        target_agent_id = selected_agent.get("instance_id")
                        target_agent_service_name = selected_agent.get("service_name")
                        connected_agent_name = selected_agent.get(
                            "prefered_name", target_agent_id
                        )
                        break
                    else:
                        print("Invalid selection. Please enter a number from the list.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
                except RuntimeError:
                    logger.warning("Input stream closed.")
                    await interface.close()
                    return

        if not target_agent_id or not target_agent_service_name:
            logger.error("Failed to select a valid agent. Exiting.")
            await interface.close()
            return

        # --- Connect ---
        logger.info(
            f"Connecting to '{connected_agent_name}' "
            f"(service: {target_agent_service_name})..."
        )
        connection_ok = await interface.connect_to_agent(
            service_name=target_agent_service_name,
            timeout_seconds=10.0,
        )
        if connection_ok:
            interface._connected_agent_id = target_agent_id

        if not connection_ok:
            logger.error(
                f"Failed to connect to '{connected_agent_name}'. Exiting."
            )
            await interface.close()
            return

        logger.info(f"Connected to '{connected_agent_name}'.")
        print(
            f"\nConnected to coding agent: {connected_agent_name}\n"
            "Enter coding tasks below. Type 'quit' or 'exit' to stop.\n"
            f"(Request timeout: {DEFAULT_REQUEST_TIMEOUT}s)\n"
        )

        # --- Interactive loop ---
        while True:
            try:
                user_input = await asyncio.to_thread(
                    input, f"[{connected_agent_name}] > "
                )
            except (RuntimeError, EOFError):
                logger.warning("Input stream closed.")
                break

            if user_input.lower() in ("quit", "exit"):
                logger.info("User requested exit.")
                break

            if not user_input.strip():
                continue

            request_data = {"message": user_input}
            logger.info(f"Sending request to agent...")

            response = await interface.send_request(
                request_data, timeout_seconds=DEFAULT_REQUEST_TIMEOUT
            )

            if response:
                msg = response.get("message", "No message in response")
                status = response.get("status", 0)

                print(f"\n{msg}\n")

                if status != 0:
                    print(f"  [status={status}]\n")
            else:
                logger.error("No response from agent or request timed out.")
                if (
                    interface._connected_agent_id
                    and interface._connected_agent_id not in interface.available_agents
                ):
                    logger.error("Agent appears to have departed. Exiting.")
                    break

    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logger.info(f"Closing '{INTERFACE_NAME}'...")
        if "interface" in locals() and interface:
            await interface.close()
        logger.info(f"'{INTERFACE_NAME}' shut down.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CodingGenesisAgent Interface CLI")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(verbose=args.verbose))
    except KeyboardInterrupt:
        pass
    sys.exit(0)
