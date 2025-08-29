#!/usr/bin/env python3
import logging
import asyncio
import sys
import traceback
import time
import uuid
import json
import rti.connextdds as dds
from genesis_lib.monitored_agent import MonitoredAgent
import signal

# Configure root logger to handle all loggers
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Set all genesis_lib loggers to DEBUG
for name in ['genesis_lib', 'genesis_lib.agent', 'genesis_lib.monitored_agent', 'genesis_lib.genesis_app']:
    logging.getLogger(name).setLevel(logging.DEBUG)

# Get our specific logger
logger = logging.getLogger("MathTestAgent")
logger.setLevel(logging.DEBUG)

# Test log message
print("🔍 TRACE: Script starting, before any initialization (print)")
logger.info("🔍 TRACE: Script starting, before any initialization (logger)")

class MathTestAgent(MonitoredAgent):
    """
    A monitored agent for testing concurrent Interface <-> Agent RPC
    using simple math operations.
    """
    print("🏗️ TRACE: Starting MathTestAgent initialization... (print)")
    logger.info("🏗️ TRACE: Starting MathTestAgent initialization... (logger)")
    def __init__(self):
        logger.info("🏗️ TRACE: Starting MathTestAgent initialization...")
        try:
            super().__init__(
                agent_name="MathTestAgent",
                base_service_name="MathTestService",
                agent_type="TEST_AGENT",
                agent_id=str(uuid.uuid4())
            )
            logger.info("✅ TRACE: MonitoredAgent base class initialized")
            self._shutdown_event = asyncio.Event()
            logger.info("✅ TRACE: MathTestAgent initialization complete")
        except Exception as e:
            logger.error(f"💥 TRACE: Error during MathTestAgent initialization: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")

    async def process_request(self, request):
        """Process math operation requests"""
        try:
            # Get the message field from the dictionary
            message = request.get("message")
            if message is None:
                raise ValueError("Request dictionary missing 'message' key")
            
            # Parse request JSON (message itself is expected to be a JSON string)
            request_data = json.loads(message)
            
            # Extract operation and numbers from request
            operation = request_data["operation"]
            x = request_data["x"]
            y = request_data["y"]
            conversation_id = request_data["conversation_id"]
            
            # Perform operation
            result = 0
            if operation == "add":
                result = x + y
            elif operation == "multiply":
                result = x * y
            elif operation == "divide":
                if y == 0:
                    raise ValueError("Cannot divide by zero")
                result = x / y
            elif operation == "subtract":
                result = x - y
            else:
                raise ValueError(f"Unsupported operation: {operation}")
                
            # Return result
            return {
                "message": str(result),
                "status": 0,
                "conversation_id": conversation_id
            }
        except Exception as e:
            return {
                "message": f"Error processing request: {str(e)}",
                "status": 1,
                "conversation_id": ""
            }

async def main():
    """Main function"""
    try:
        # Create and run agent
        agent = MathTestAgent()
        logger.info("✅ TRACE: Agent created, starting run...")
        await agent.run()
    except KeyboardInterrupt:
        logger.info("👋 TRACE: Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"💥 TRACE: Error in main: {e}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
    finally:
        # Clean shutdown
        if 'agent' in locals():
            logger.info("🧹 TRACE: Cleaning up agent...")
            await agent.close()
            logger.info("✅ TRACE: Agent cleanup complete")

if __name__ == "__main__":
    asyncio.run(main()) 