#!/usr/bin/env python3

"""
A simple calculator service that demonstrates basic Genesis service functionality.
Provides basic arithmetic operations: add and multiply.
"""

import logging
import asyncio
from typing import Dict, Any
from genesis_lib.enhanced_service_base import EnhancedServiceBase
from genesis_lib.decorators import genesis_function

# Configure logging to show INFO level messages
# This helps with debugging and monitoring service operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hello_calculator")

class HelloCalculator(EnhancedServiceBase):
    """A simple calculator service demonstrating Genesis functionality."""
    
    def __init__(self):
        """Initialize the calculator service."""
        # Initialize the base service with a name and capabilities
        # The capabilities list helps other services discover what this service can do
        super().__init__(
            "HelloCalculator",
            capabilities=["calculator", "math"]
        )
        logger.info("HelloCalculator service initialized")
        # Advertise the available functions to the Genesis network
        # This makes the functions discoverable by other services
        self._advertise_functions()
        logger.info("Functions advertised")

    # The @genesis_function decorator marks this as a callable function in the Genesis network
    # The function signature (x: float, y: float) and docstring Args section must match exactly
    # Both are used by Genesis to generate the function schema and validate calls
    # Note: Comments must be above the decorator, not in the docstring
    @genesis_function()
    async def add(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Add two numbers together.
        
        Args:
            x: First number to add
            y: Second number to add
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the addition
            
        Examples:
            >>> await add(5, 3)
            {'result': 8}
        """
        # Log the incoming request for debugging and monitoring
        logger.info(f"Received add request: x={x}, y={y}")
        
        try:
            # Perform the addition operation
            result = x + y
            # Log the result for debugging
            logger.info(f"Add result: {result}")
            # Return the result in a standardized format
            return {"result": result}
        except Exception as e:
            # Log any errors that occur during the operation
            logger.error(f"Error in add operation: {str(e)}")
            raise

    # The @genesis_function decorator marks this as a callable function in the Genesis network
    # The function signature (x: float, y: float) and docstring Args section must match exactly
    # Both are used by Genesis to generate the function schema and validate calls
    # Note: Comments must be above the decorator, not in the docstring
    @genesis_function()
    async def multiply(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Multiply two numbers together.
        
        Args:
            x: First number to multiply
            y: Second number to multiply
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the multiplication
            
        Examples:
            >>> await multiply(5, 3)
            {'result': 15}
        """
        # Log the incoming request for debugging and monitoring
        logger.info(f"Received multiply request: x={x}, y={y}")
        
        try:
            # Perform the multiplication operation
            result = x * y
            # Log the result for debugging
            logger.info(f"Multiply result: {result}")
            # Return the result in a standardized format
            return {"result": result}
        except Exception as e:
            # Log any errors that occur during the operation
            logger.error(f"Error in multiply operation: {str(e)}")
            raise

def main():
    """Run the calculator service."""
    # Initialize and start the service
    logger.info("Starting HelloCalculator service")
    try:
        # Create an instance of the calculator service
        service = HelloCalculator()
        # Run the service using asyncio
        asyncio.run(service.run())
    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C
        logger.info("Shutting down HelloCalculator service")

if __name__ == "__main__":
    main() 