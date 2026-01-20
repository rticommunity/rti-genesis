#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
#                                                                                    #
# RTI grants Licensee a license to use, modify, compile, and create derivative       #
# works of the Software. Licensee has the right to distribute object form only       #
# for use with RTI products. The Software is provided "as is", with no warranty      #
# of any type, including any warranty for fitness for any purpose. RTI is under no   #
# obligation to maintain or support the Software. RTI shall not be liable for any    #
# incidental or consequential damages arising out of the use or inability to use     #
# the software.                                                                      #
# ####################################################################################

# --------------------------------------------------------------------------- #
# CalculatorService: Docstring-Reliant Decorator Approach for Function Definition
#
# This service illustrates a straightforward method for defining functions
# within the Genesis framework. It uses the `@genesis_function` decorator,
# which, in this case, infers a JSON schema from Python type hints and
# docstrings for LLM consumption. Descriptions and parameter details are
# primarily extracted from the docstrings.
#
# Key characteristics of this approach:
#   - Decorator for Registration and Schema Inference: The `@genesis_function()`
#     decorator is used. It handles basic registration and, importantly,
#     attempts to automatically generate a JSON schema by introspecting
#     the function's type hints and parsing its docstring (especially the 'Args:' section).
#   - Docstrings for Description: The primary source for human-readable descriptions
#     and parameter details (including examples) that the decorator tries to parse.
#   - Type Hints: Standard Python type hints (e.g., float, str) are crucial inputs
#     for the schema inference process.
#   - Imperative Validation: Input validation (e.g., checking for division
#     by zero) is handled explicitly within the function bodies.
#   - Custom Exceptions: Defines and uses custom exceptions for error handling.
#
# Strengths:
#   - Simplicity: Appears simple at the service level for developers, relying on
#     standard Python features (type hints, docstrings).
#   - Automatic Schema Generation: A JSON schema is generated without requiring
#     explicit schema definition (like Pydantic models or raw JSON) in the service code.
#   - Low Perceived Overhead: Avoids direct use of additional libraries like Pydantic
#     at the service definition level if the inferred schema is sufficient.
#
# Considerations/Cons:
#   - Reliability of Inference: The robustness of the auto-generated schema depends heavily
#     on the capabilities of the `infer_schema_from_annotations` logic within the
#     `@genesis_function` decorator. Complex types or nuanced constraints might not be
#     fully or accurately captured compared to an explicit Pydantic model or schema.
#   - Docstring Dependency: The quality of parameter descriptions and examples in the
#     schema is tied to the meticulousness and format of the docstrings. Changes to
#     docstring parsing logic or inconsistent docstring formats can affect the schema.
#   - Limited Expressiveness: Type hints and docstrings might not be able to express all
#     the validation rules or schema details that can be defined with Pydantic or
#     direct JSON Schema (e.g., complex regex patterns, conditional logic within schema).
#   - Debugging Schema Issues: If the inferred schema is not what the LLM expects,
#     debugging might require understanding the inference logic in `decorators.py`.
#   - Maintenance of Docstrings: Requires discipline to keep docstrings detailed,
#     correctly formatted for parsing, and in sync with the code logic.
# --------------------------------------------------------------------------- #
import logging, asyncio, sys, os
from typing import Dict, Any
from datetime import datetime
from genesis_lib.decorators import genesis_function
from genesis_lib.monitored_service import MonitoredService
import contextlib

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
                    force=True)  # Force reconfiguration of the root logger
logger = logging.getLogger("calculator_service")
logger.setLevel(logging.DEBUG)  # Explicitly set logger level

class CalculatorService(MonitoredService):
    """Implementation of the calculator service using the decorator pattern.
    
    This service provides basic arithmetic operations with input validation
    and standardized response formatting. It extends MonitoredService to
    leverage built-in function registration, monitoring, and discovery.
    """

    def __init__(self, domain_id=0):
        logger.info(f"===== DDS TRACE: CalculatorService initializing on domain {domain_id}... =====")
        super().__init__("CalculatorService", capabilities=["calculator", "math"], domain_id=domain_id)
        logger.info("===== DDS TRACE: CalculatorService MonitoredService initialized. =====")
        logger.info("===== DDS TRACE: Calling _advertise_functions... =====")
        self._advertise_functions()
        logger.info("===== DDS TRACE: _advertise_functions called. =====")
        logger.info(f"CalculatorService initialized with unified RPC v2 on domain {domain_id}")

    @genesis_function()
    async def add(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Add two numbers together.
        
        Args:
            x: First number to add (example: 5.0)
            y: Second number to add (example: 3.0)
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the addition
            
        Examples:
            >>> await add(5, 3)
            {'result': 8}
            
        Raises:
            InvalidInputError: If either number is outside the valid range [-1,000,000, 1,000,000]
        """
        logger.info(f"Received add request: x={x}, y={y}")
        self.publish_function_call_event("add", {"x": x, "y": y}, request_info)
        
        try:
            result = x + y
            self.publish_function_result_event("add", {"result": result}, request_info)
            logger.info(f"Add result: {result}")
            return {"result": result}
        except Exception as e:
            logger.error(f"Error in add operation: {str(e)}")
            raise InvalidInputError(f"Failed to add numbers: {str(e)}")

    @genesis_function()
    async def subtract(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Subtract the second number from the first.
        
        Args:
            x: The number to subtract from (example: 5.0)
            y: The number to subtract (example: 3.0)
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the subtraction
            
        Examples:
            >>> await subtract(5, 3)
            {'result': 2}
            
        Raises:
            InvalidInputError: If either number is outside the valid range [-1,000,000, 1,000,000]
        """
        logger.info(f"Received subtract request: x={x}, y={y}")
        self.publish_function_call_event("subtract", {"x": x, "y": y}, request_info)
        
        try:
            result = x - y
            self.publish_function_result_event("subtract", {"result": result}, request_info)
            logger.info(f"Subtract result: {result}")
            return {"result": result}
        except Exception as e:
            logger.error(f"Error in subtract operation: {str(e)}")
            raise InvalidInputError(f"Failed to subtract numbers: {str(e)}")

    @genesis_function()
    async def multiply(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Multiply two numbers together.
        
        Args:
            x: First number to multiply (example: 5.0)
            y: Second number to multiply (example: 3.0)
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the multiplication
            
        Examples:
            >>> await multiply(5, 3)
            {'result': 15}
            
        Raises:
            InvalidInputError: If either number is outside the valid range [-1,000,000, 1,000,000]
        """
        logger.info(f"Received multiply request: x={x}, y={y}")
        self.publish_function_call_event("multiply", {"x": x, "y": y}, request_info)
        
        try:
            result = x * y
            self.publish_function_result_event("multiply", {"result": result}, request_info)
            logger.info(f"Multiply result: {result}")
            return {"result": result}
        except Exception as e:
            logger.error(f"Error in multiply operation: {str(e)}")
            raise InvalidInputError(f"Failed to multiply numbers: {str(e)}")

    @genesis_function()
    async def divide(self, x: float, y: float, request_info=None) -> Dict[str, Any]:
        """Divide the first number by the second.
        
        Args:
            x: The number to divide (example: 6.0)
            y: The number to divide by (example: 2.0)
            request_info: Optional request metadata
            
        Returns:
            Dict containing the result of the division
            
        Examples:
            >>> await divide(6, 2)
            {'result': 3}
            
        Raises:
            InvalidInputError: If either number is outside the valid range [-1,000,000, 1,000,000]
            DivisionByZeroError: If attempting to divide by zero
        """
        logger.info(f"Received divide request: x={x}, y={y}")
        self.publish_function_call_event("divide", {"x": x, "y": y}, request_info)
        
        try:
            if y == 0:
                raise DivisionByZeroError("Cannot divide by zero")
            result = x / y
            self.publish_function_result_event("divide", {"result": result}, request_info)
            logger.info(f"Divide result: {result}")
            return {"result": result}
        except DivisionByZeroError:
            logger.error("Attempted division by zero")
            raise
        except Exception as e:
            logger.error(f"Error in divide operation: {str(e)}")
            raise InvalidInputError(f"Failed to divide numbers: {str(e)}")

# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #
def main():
    import argparse
    parser = argparse.ArgumentParser(description='Calculator Service')
    parser.add_argument('--domain', type=int, default=None,
                       help='DDS domain ID (default: 0 or GENESIS_DOMAIN_ID env var)')
    args = parser.parse_args()
    
    # Priority: command line arg > env var > default (0)
    domain_id = args.domain if args.domain is not None else int(os.environ.get('GENESIS_DOMAIN_ID', 0))
    
    logger.info(f"SERVICE: Starting calculator service with unified RPC v2 on domain {domain_id}")
    try:
        service = CalculatorService(domain_id=domain_id)
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("SERVICE: Shutting down calculator service")

if __name__ == "__main__":
    main()
