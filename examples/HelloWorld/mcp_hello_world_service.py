#!/usr/bin/env python3

"""
A simple calculator service that demonstrates basic Genesis service functionality.
Provides basic arithmetic operations: add and multiply and divide.
"""

import logging
import asyncio
from typing import Dict, Any
from genesis_lib.mcp_service_base import MCPServiceBase
from genesis_lib.decorators import genesis_function

# Configure logging to show INFO level messages
# This helps with debugging and monitoring service operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_hello_world")

class HelloWorld(MCPServiceBase):
    """A simple service demonstrating how MCP tools are integrated in GENESIS."""
    
    def __init__(self):
        """Initialize the calculator service."""
        # Initialize the base service with a name and capabilities
        # The capabilities list helps other services discover what this service can do
        super().__init__(
            "HelloWorld",
            capabilities=["mcp", "generic"]
        )
        logger.info("HelloWorld service initialized")
        # Advertise the available functions to the Genesis network
        # This makes the functions discoverable by other services
        


async def main():
    """Run the calculator service."""
    # Initialize and start the service
    logger.info("Starting HelloCalculator service")
    try:
        # Create an instance of the calculator service
        service = HelloWorld()
        await service.connect_to_mcp_server("http://nuc:8000/mcp")
        service._advertise_functions()
        await service.run()
    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C
        logger.info("Shutting down HelloCalculator service")

if __name__ == "__main__":
    asyncio.run(main()) 