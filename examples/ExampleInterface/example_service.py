#!/usr/bin/env python3
import logging, asyncio, sys
from typing import Dict, Any
# `datetime` was imported but not used. It can be removed if not needed for future extensions.
# from datetime import datetime 
from genesis_lib.decorators import genesis_function
from genesis_lib.enhanced_service_base import EnhancedServiceBase

# --------------------------------------------------------------------------- #
# Exceptions                                                                  #
# --------------------------------------------------------------------------- #
class CalculatorError(Exception):
    """Base exception for calculator service errors.
    This allows for catching all calculator-specific exceptions with a single except block.
    """
    pass

class InvalidInputError(CalculatorError):
    """Raised when input values are invalid (e.g., not numbers, out of expected range, etc.)."""
    pass

class DivisionByZeroError(CalculatorError):
    """Raised when an attempt is made to divide a number by zero."""
    pass

# --------------------------------------------------------------------------- #
# Service                                                                     #
# --------------------------------------------------------------------------- #

# Configure logging for the calculator service.
# `force=True` is used to ensure this configuration takes precedence if the
# root logger has already been configured by another module (though in a standalone
# service script, this is less likely to be an issue initially).
# Setting the level to DEBUG here means that all debug messages from this logger
# and its children will be processed, provided handlers also allow it.
logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    force=True)  # Force reconfiguration of the root logger

# Get a specific logger instance for this service.
# This allows for more targeted logging control if this service were part of a larger application.
logger = logging.getLogger("calculator_service")
# Explicitly set the logger level. If basicConfig already set the root logger to DEBUG,
# this specific logger would inherit it. However, explicit setting is clearer.
logger.setLevel(logging.DEBUG)

class CalculatorService(EnhancedServiceBase):
    """Implementation of a simple calculator service.
    
    This service demonstrates how to use the `EnhancedServiceBase` and the
    `@genesis_function` decorator to expose methods as part of a Genesis service.
    It provides basic arithmetic operations: add, subtract, multiply, and divide.
    Each operation includes input validation (implicitly by type hints, explicitly for division by zero)
    and uses the logger to record requests and results.
    It also demonstrates publishing function call and result events, which can be useful for monitoring.
    """

    def __init__(self):
        """Initializes the CalculatorService.
        
        Sets up the service name and capabilities using the parent class constructor.
        It then calls `_advertise_functions()` which is a method from `EnhancedServiceBase`
        that automatically registers methods decorated with `@genesis_function`.
        """
        # Call the parent class constructor to set up the service name and its capabilities.
        # "CalculatorService" is the name this service will be known by in the Genesis system.
        # "capabilities" is a list of strings that can be used for service discovery or categorization.
        super().__init__("CalculatorService", capabilities=["calculator", "math"])

        # This method (from EnhancedServiceBase) finds all methods in this class
        # decorated with `@genesis_function` and prepares them to be called via RPC.
        self._advertise_functions()
        # logger.info(f"'{self.service_name}' initialized with capabilities: {self.capabilities}.") # Commented out due to AttributeError

    @genesis_function()
    async def add(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Add two numbers together.
        
        Args:
            x (float): First number to add (example: 5.0)
            y (float): Second number to add (example: 3.0)
            request_info (optional): Optional request metadata provided by the Genesis framework.
                                     This can contain information about the caller or request context.
            
        Returns:
            Dict[str, Any]: A dictionary containing the result of the addition, typically `{'result': sum}`.
            
        Examples:
            If called via an RPC mechanism, a request like `add(x=5, y=3)` would be processed.
            The expected return would be `{'result': 8}`.
            
        Raises:
            InvalidInputError: If an error occurs during addition (though basic `+` on floats is unlikely to raise this directly
                               unless type checking/conversion fails before this point, or if more complex validation were added).
                               The current implementation catches a generic Exception and wraps it.
        """
        # Log the incoming request with its parameters.
        logger.info(f"Received add request: x={x}, y={y}, request_info: {request_info}")
        # Publish an event indicating a function call has been received.
        # This is useful for monitoring and tracing systems.
        self.publish_function_call_event("add", {"x": x, "y": y}, request_info)
        
        try:
            # Perform the addition.
            result = x + y
            # Publish an event with the result of the function call.
            self.publish_function_result_event("add", {"result": result}, request_info)
            logger.info(f"Add result: {result}")
            # Return the result in a dictionary, a common pattern for service responses.
            return {"result": result}
        except Exception as e:
            # Catch any unexpected errors during the operation.
            logger.error(f"Error in add operation: {str(e)}", exc_info=True) # Log with stack trace.
            # Re-raise as a service-specific exception for consistent error handling by clients.
            self.publish_function_error_event("add", {"error": str(e), "x": x, "y": y}, request_info)
            raise InvalidInputError(f"Failed to add numbers: {str(e)}")

    @genesis_function()
    async def subtract(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Subtract the second number from the first.
        
        Args:
            x (float): The number to subtract from (example: 5.0)
            y (float): The number to subtract (example: 3.0)
            request_info (optional): Optional request metadata.
            
        Returns:
            Dict[str, Any]: Dict containing the result of the subtraction, `{'result': difference}`.
            
        Raises:
            InvalidInputError: If an error occurs during subtraction.
        """
        logger.info(f"Received subtract request: x={x}, y={y}, request_info: {request_info}")
        self.publish_function_call_event("subtract", {"x": x, "y": y}, request_info)
        
        try:
            result = x - y
            self.publish_function_result_event("subtract", {"result": result}, request_info)
            logger.info(f"Subtract result: {result}")
            return {"result": result}
        except Exception as e:
            logger.error(f"Error in subtract operation: {str(e)}", exc_info=True)
            self.publish_function_error_event("subtract", {"error": str(e), "x": x, "y": y}, request_info)
            raise InvalidInputError(f"Failed to subtract numbers: {str(e)}")

    @genesis_function()
    async def multiply(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Multiply two numbers together.
        
        Args:
            x (float): First number to multiply (example: 5.0)
            y (float): Second number to multiply (example: 3.0)
            request_info (optional): Optional request metadata.
            
        Returns:
            Dict[str, Any]: Dict containing the result of the multiplication, `{'result': product}`.
            
        Raises:
            InvalidInputError: If an error occurs during multiplication.
        """
        logger.info(f"Received multiply request: x={x}, y={y}, request_info: {request_info}")
        self.publish_function_call_event("multiply", {"x": x, "y": y}, request_info)
        
        try:
            result = x * y
            self.publish_function_result_event("multiply", {"result": result}, request_info)
            logger.info(f"Multiply result: {result}")
            return {"result": result}
        except Exception as e:
            logger.error(f"Error in multiply operation: {str(e)}", exc_info=True)
            self.publish_function_error_event("multiply", {"error": str(e), "x": x, "y": y}, request_info)
            raise InvalidInputError(f"Failed to multiply numbers: {str(e)}")

    @genesis_function()
    async def divide(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Divide the first number by the second.
        
        Args:
            x (float): The number to divide (the dividend) (example: 6.0)
            y (float): The number to divide by (the divisor) (example: 2.0)
            request_info (optional): Optional request metadata.
            
        Returns:
            Dict[str, Any]: Dict containing the result of the division, `{'result': quotient}`.
            
        Raises:
            InvalidInputError: If an error occurs during division (other than division by zero).
            DivisionByZeroError: If attempting to divide by zero (y is 0).
        """
        logger.info(f"Received divide request: x={x}, y={y}, request_info: {request_info}")
        self.publish_function_call_event("divide", {"x": x, "y": y}, request_info)
        
        try:
            if y == 0:
                # Specific check for division by zero, raising a specific custom error.
                logger.warning("Attempted division by zero") # Log as warning, as it's a client error.
                raise DivisionByZeroError("Cannot divide by zero")
            result = x / y
            self.publish_function_result_event("divide", {"result": result}, request_info)
            logger.info(f"Divide result: {result}")
            return {"result": result}
        except DivisionByZeroError: # Catch the specific error to re-raise it.
            # This ensures that DivisionByZeroError is not caught by the generic Exception handler below
            # and wrapped in InvalidInputError.
            self.publish_function_error_event("divide", {"error": "DivisionByZeroError", "x": x, "y": y}, request_info)
            raise
        except Exception as e:
            logger.error(f"Error in divide operation: {str(e)}", exc_info=True)
            self.publish_function_error_event("divide", {"error": str(e), "x": x, "y": y}, request_info)
            raise InvalidInputError(f"Failed to divide numbers: {str(e)}")

# --------------------------------------------------------------------------- #
# Main execution block                                                        #
# --------------------------------------------------------------------------- #
def main():
    """Main function to start the CalculatorService.
    
    This function instantiates the service and runs its main loop using `asyncio.run()`.
    It includes a try-except block to catch `KeyboardInterrupt` for graceful shutdown.
    """
    logger.info("SERVICE: Starting calculator service...")
    service = None # Initialize service to None for the finally block
    try:
        # Create an instance of the service.
        service = CalculatorService()
        # Run the service. This is a blocking call that starts the service's
        # event loop and keeps it running until stopped (e.g., by KeyboardInterrupt or service.stop()).
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("SERVICE: KeyboardInterrupt received, shutting down calculator service...")
    except Exception as e:
        logger.error(f"SERVICE: An unexpected error occurred: {e}", exc_info=True)
    finally:
        # Ensures that if the service has a close or cleanup method, it could be called here.
        # For EnhancedServiceBase, cleanup is typically handled within its run/stop methods
        # or by asyncio.run() managing tasks.
        # If specific cleanup beyond what `service.run()` handles upon exit is needed,
        # it would be added here, e.g., `if service: await service.close_resources()`.
        logger.info("SERVICE: Calculator service has shut down.")

if __name__ == "__main__":
    # This ensures that main() is called only when the script is executed directly,
    # not when it's imported as a module.
    main()
