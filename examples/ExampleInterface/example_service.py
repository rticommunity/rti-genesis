#!/usr/bin/env python3
import logging, asyncio
from typing import Dict, Any
from genesis_lib.decorators import genesis_function
from genesis_lib.monitored_service import MonitoredService

# --------------------------------------------------------------------------- #
# Exceptions                                                                  #
# --------------------------------------------------------------------------- #
class CalculatorError(Exception):
    """Base exception for calculator service errors."""
    pass

class InvalidInputError(CalculatorError):
    """Raised when input values are invalid."""
    pass

class DivisionByZeroError(CalculatorError):
    """Raised when attempting to divide by zero."""
    pass

# --------------------------------------------------------------------------- #
# Service                                                                     #
# --------------------------------------------------------------------------- #

logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    force=True)
logger = logging.getLogger("calculator_service")
logger.setLevel(logging.DEBUG)

class CalculatorService(MonitoredService):
    """A simple calculator service demonstrating Genesis service implementation.
    
    Provides basic arithmetic operations: add, subtract, multiply, and divide.
    Each operation is exposed via the @genesis_function decorator.
    """

    def __init__(self):
        super().__init__("CalculatorService", capabilities=["calculator", "math"])
        self._advertise_functions()

    @genesis_function()
    async def add(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Add two numbers together.
        
        Args:
            x: First number (example: 5.0)
            y: Second number (example: 3.0)
            
        Returns:
            Dict containing the result, e.g. {'result': 8.0}
        """
        logger.info(f"Received add request: x={x}, y={y}")
        self.publish_function_call_event("add", {"x": x, "y": y}, request_info)
        
        try:
            result = x + y
            self.publish_function_result_event("add", {"result": result}, request_info)
            logger.info(f"Add result: {result}")
            return {"result": result}
        except Exception as e:
            logger.error(f"Error in add operation: {str(e)}", exc_info=True)
            self.publish_function_error_event("add", {"error": str(e), "x": x, "y": y}, request_info)
            raise InvalidInputError(f"Failed to add numbers: {str(e)}")

    @genesis_function()
    async def subtract(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Subtract the second number from the first.
        
        Args:
            x: Number to subtract from (example: 5.0)
            y: Number to subtract (example: 3.0)
            
        Returns:
            Dict containing the result, e.g. {'result': 2.0}
        """
        logger.info(f"Received subtract request: x={x}, y={y}")
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
            x: First number (example: 5.0)
            y: Second number (example: 3.0)
            
        Returns:
            Dict containing the result, e.g. {'result': 15.0}
        """
        logger.info(f"Received multiply request: x={x}, y={y}")
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
            x: Number to divide (dividend) (example: 6.0)
            y: Number to divide by (divisor) (example: 2.0)
            
        Returns:
            Dict containing the result, e.g. {'result': 3.0}
            
        Raises:
            DivisionByZeroError: If attempting to divide by zero
        """
        logger.info(f"Received divide request: x={x}, y={y}")
        self.publish_function_call_event("divide", {"x": x, "y": y}, request_info)
        
        try:
            if y == 0:
                logger.warning("Attempted division by zero")
                raise DivisionByZeroError("Cannot divide by zero")
            result = x / y
            self.publish_function_result_event("divide", {"result": result}, request_info)
            logger.info(f"Divide result: {result}")
            return {"result": result}
        except DivisionByZeroError:
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
    """Start the CalculatorService."""
    logger.info("Starting calculator service...")
    service = None
    try:
        service = CalculatorService()
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logger.info("Calculator service has shut down.")

if __name__ == "__main__":
    main()
