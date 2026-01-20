#!/usr/bin/env python3
# Copyright (c) 2025, RTI & Jason Upchurch
import logging
import sys
import os
import time
import traceback
import asyncio

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from monitored_interface_cli import TracingMonitoredChatGPTInterface

# Configure logging with detailed format
log_file = os.path.join(project_root, 'logs', 'baseline_test_interface.log')
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'))

logger = logging.getLogger("BaselineTestInterface")
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

# Also configure root logger to show output in console
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

async def main():
    logger.info("🚀 TRACE: BaselineTestInterface starting - PID: %d", os.getpid())
    interface = None
    exit_code = 1 # Default to error

    try:
        logger.info("🏗️ TRACE: Creating ChatGPT interface...")
        # Use the same interface class as the CLI for consistency
        interface = TracingMonitoredChatGPTInterface()

        logger.info("🔍 TRACE: Waiting for agent discovery...")
        # Run wait_for_agent in a thread pool since it's not async
        loop = asyncio.get_event_loop()
        if not await loop.run_in_executor(None, interface.wait_for_agent):
            logger.error("❌ TRACE: No agent found, exiting")
            sys.exit(1)

        logger.info("✅ TRACE: Agent discovered successfully")
        test_message = "Tell me a joke."
        logger.info(f"📤 TRACE: Sending test message: '{test_message}'")

        # Send the request using the existing interface method
        # Run send_request in a thread pool since it's not async
        reply = await loop.run_in_executor(None, interface.send_request, {'message': test_message})
        if reply:
            logger.info(f"📥 TRACE: Received reply: {reply}")
            if reply.get('status') != 0:
                logger.warning("⚠️ TRACE: Reply indicated error status: %d", reply['status'])
            else:
                logger.info("✅ TRACE: Test completed successfully")
                exit_code = 0
        else:
            logger.error("❌ TRACE: No reply received from agent")

    except Exception as e:
        logger.error(f"❌ TRACE: Error in baseline test: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        if interface:
            logger.info("🧹 TRACE: Cleaning up interface")
            interface.close()
        logger.info(f"🏁 TRACE: BaselineTestInterface ending with exit code: {exit_code}")
        sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main()) 