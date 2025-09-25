"""
Genesis RPC Service

This module provides the core RPC service implementation for the Genesis framework,
enabling reliable function execution and communication between distributed components.
It serves as the foundation for all service-side RPC interactions in the Genesis network,
providing a robust and flexible interface for remote function handling.

Key responsibilities include:
- DDS-based RPC communication with remote clients
- Function registration and schema management
- Request handling and validation
- Error handling and response formatting
- Resource lifecycle management
- Common validation patterns for inputs

The GenesisRPCService is designed to be extended by specialized services and used by
higher-level components like EnhancedServiceBase. It handles the complexity of
DDS-based RPC communication, allowing developers to focus on implementing their
service functions without worrying about the underlying communication details.

The service supports:
- Automatic function registration with schemas
- JSON-based request/response handling
- Input validation with common patterns
- Asynchronous function execution
- Comprehensive error handling
- Resource cleanup and lifecycle management

Copyright (c) 2025, RTI & Jason Upchurch
"""

import rti.connextdds as dds
import rti.rpc
import asyncio
import logging
import json
import inspect
from typing import Dict, Any, Optional
from dataclasses import field
import jsonschema
import re

# Set up logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GenesisRPCService')

class GenesisRPCService:
    """
    Base class for all Genesis RPC services.
    Provides function registration, request handling, and RPC communication.
    """
    def __init__(self, service_name: str = "GenesisRPCService"):
        """
        Initialize the RPC service.
        
        Args:
            service_name: Name of the service for RPC discovery
        """
        logger.info("Initializing DDS Domain Participant...")
        self.participant = dds.DomainParticipant(domain_id=0)
        
        logger.info("Creating RPC Replier...")
        self.replier = rti.rpc.Replier(
            request_type=self.get_request_type(),
            reply_type=self.get_reply_type(),
            participant=self.participant,
            service_name=f"rti/connext/genesis/{service_name}"
        )
        
        # Dictionary to store registered functions and their schemas
        self.functions: Dict[str, Dict[str, Any]] = {}
        
        # Common schema patterns
        self.common_schemas = {
            "text": {
                "type": "string",
                "description": "Text input",
                "minLength": 1
            },
            "count": {
                "type": "integer",
                "description": "Count parameter",
                "minimum": 0,
                "maximum": 1000
            },
            "letter": {
                "type": "string",
                "description": "Single letter input",
                "minLength": 1,
                "maxLength": 1,
                "pattern": "^[a-zA-Z]$"
            },
            "number": {
                "type": "number",
                "description": "Numeric input"
            }
        }
    
    def get_request_type(self):
        """Get the request type for RPC communication. Override if needed."""
        from genesis_lib.datamodel import FunctionRequest
        return FunctionRequest
    
    def get_reply_type(self):
        """Get the reply type for RPC communication. Override if needed."""
        from genesis_lib.datamodel import FunctionReply
        return FunctionReply
    
    def register_function(self, 
                         func, 
                         description: str, 
                         parameters: Dict[str, Any],
                         operation_type: Optional[str] = None,
                         common_patterns: Optional[Dict[str, Any]] = None):
        """
        Register a function with its OpenAI-style schema
        
        Args:
            func: The function to register
            description: A description of what the function does
            parameters: JSON schema for the function parameters
            operation_type: Type of operation (e.g., "calculation", "transformation")
            common_patterns: Common validation patterns used by this function
            
        Returns:
            The registered function (allows use as a decorator)
        """
        from genesis_lib.datamodel import Tool, Function, validate_schema
        
        func_name = func.__name__
        logger.info(f"Registering function: {func_name}")
        
        # Validate the parameters schema
        try:
            validate_schema(parameters)
        except ValueError as e:
            logger.error(f"Invalid schema for function {func_name}: {str(e)}")
            raise
        
        # Create OpenAI-compliant function definition
        function = Function(
            name=func_name,
            description=description,
            parameters=json.dumps(parameters),
            strict=True
        )
        
        # Create OpenAI-compliant tool definition
        tool = Tool(type="function", function=function)
        
        # Store function and its schema
        self.functions[func_name] = {
            "tool": tool,
            "implementation": func,  # Store actual function for execution
            "operation_type": operation_type,
            "common_patterns": common_patterns
        }
        
        return func
    
    async def run(self):
        """Run the service and handle incoming requests."""
        logger.info(f"Service running with {len(self.functions)} registered functions.")
        logger.info(f"Available functions: {', '.join(self.functions.keys())}")
        logger.info("Waiting for requests...")
        
        try:
            while True:
                logger.debug("Waiting for next request...")
                requests = self.replier.receive_requests(max_wait=dds.Duration(3600))
                
                for request_sample in requests:
                    request = request_sample.data
                    request_info = request_sample.info  # Get the request info with publication handle
                    function_name = request.function.name
                    arguments_json = request.function.arguments
                    
                    logger.info(f"Received request: id={request.id}, function={function_name}, args={arguments_json}")
                    
                    reply = None
                    
                    try:
                        # Check if the function exists
                        if function_name in self.functions:
                            func = self.functions[function_name]["implementation"]
                            tool = self.functions[function_name]["tool"]
                            
                            # Parse the JSON arguments
                            try:
                                args_data = json.loads(arguments_json)
                                
                                # If strict mode is enabled, validate arguments against schema
                                if tool.function.strict:
                                    schema = json.loads(tool.function.parameters)
                                    jsonschema.validate(args_data, schema)
                                
                                # Call the function with the parsed arguments and request info
                                logger.debug(f"Calling {function_name} with args={args_data}")
                                
                                # Add request_info to the function call
                                args_data["request_info"] = request_info
                                
                                # Call the function
                                result = func(**args_data)
                                
                                # If the result is a coroutine, await it
                                if inspect.iscoroutine(result):
                                    result = await result
                                    
                                # Convert result to JSON
                                result_json = json.dumps(result)
                                logger.info(f"Function {function_name} returned: {result_json}")
                                
                                reply = self.get_reply_type()(
                                    result_json=result_json,
                                    success=True,
                                    error_message=""
                                )
                            except json.JSONDecodeError as e:
                                logger.error(f"Invalid JSON arguments: {str(e)}")
                                reply = self.get_reply_type()(
                                    result_json="null",
                                    success=False,
                                    error_message=f"Invalid JSON arguments: {str(e)}"
                                )
                            except Exception as e:
                                logger.error(f"Error executing function: {str(e)}", exc_info=True)
                                reply = self.get_reply_type()(
                                    result_json="null",
                                    success=False,
                                    error_message=f"Error executing function: {str(e)}"
                                )
                        else:
                            logger.warning(f"Unknown function requested: {function_name}")
                            reply = self.get_reply_type()(
                                result_json="null",
                                success=False,
                                error_message=f"Unknown function: {function_name}"
                            )
                    except Exception as e:
                        logger.error(f"Unexpected error processing request: {str(e)}", exc_info=True)
                        reply = self.get_reply_type()(
                            result_json="null",
                            success=False,
                            error_message=f"Internal service error: {str(e)}"
                        )
                    
                    if reply is None:
                        logger.error("No reply was created - this should never happen")
                        reply = self.get_reply_type()(
                            result_json="null",
                            success=False,
                            error_message="Internal service error: No reply created"
                        )
                        
                    logger.info(f"Sending reply: success={reply.success}")
                    self.replier.send_reply(reply, request_sample.info)

        except KeyboardInterrupt:
            logger.info("Service shutting down.")
        except Exception as e:
            logger.error(f"Unexpected error in service: {str(e)}", exc_info=True)
        finally:
            logger.info("Cleaning up service resources...")
            self.replier.close()
            self.participant.close()
            logger.info("Service cleanup complete.")

    def format_response(self, inputs: Dict[str, Any], result: Any, include_inputs: bool = True) -> Dict[str, Any]:
        """
        Format a function response with consistent structure.
        
        Args:
            inputs: Original input parameters
            result: Function result
            include_inputs: Whether to include input parameters in response
            
        Returns:
            Formatted response dictionary
        """
        response = {}
        
        # Include original inputs if requested
        if include_inputs:
            response.update(inputs)
            
        # Add result based on type
        if isinstance(result, dict):
            response.update(result)
        else:
            response["result"] = result
            
        return response

    def validate_text_input(self, text: str, min_length: int = 1, max_length: Optional[int] = None,
                          pattern: Optional[str] = None) -> None:
        """
        Validate text input against common constraints.
        
        Args:
            text: Text to validate
            min_length: Minimum length required
            max_length: Maximum length allowed (if any)
            pattern: Regex pattern to match (if any)
            
        Raises:
            ValueError: If validation fails
        """
        if not text or len(text) < min_length:
            raise ValueError(f"Text must be at least {min_length} character(s)")
            
        if max_length and len(text) > max_length:
            raise ValueError(f"Text cannot exceed {max_length} character(s)")
            
        if pattern and not re.match(pattern, text):
            raise ValueError(f"Text must match pattern: {pattern}")

    def validate_numeric_input(self, value: float, minimum: Optional[float] = None,
                             maximum: Optional[float] = None) -> None:
        """
        Validate numeric input against common constraints.
        
        Args:
            value: Number to validate
            minimum: Minimum value allowed (if any)
            maximum: Maximum value allowed (if any)
            
        Raises:
            ValueError: If validation fails
        """
        if minimum is not None and value < minimum:
            raise ValueError(f"Value must be at least {minimum}")
            
        if maximum is not None and value > maximum:
            raise ValueError(f"Value cannot exceed {maximum}")

    def get_common_schema(self, schema_type: str) -> Dict[str, Any]:
        """
        Get a common schema by type.
        
        Args:
            schema_type: Type of schema to get (e.g., 'text', 'count', 'letter', 'number')
            
        Returns:
            Schema dictionary
            
        Raises:
            ValueError: If schema type is not found
        """
        if schema_type not in self.common_schemas:
            raise ValueError(f"Unknown schema type: {schema_type}")
        return self.common_schemas[schema_type].copy()

    def close(self):
        """Clean up service resources"""
        logger.info("Cleaning up service resources...")
        if hasattr(self, 'replier'):
            self.replier.close()
        if hasattr(self, 'participant'):
            self.participant.close()
        logger.info("Service cleanup complete") 