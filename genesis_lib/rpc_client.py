"""
Genesis RPC Client

This module provides the core RPC client implementation for the Genesis framework,
enabling reliable function calling and communication between distributed components.
It serves as the foundation for all client-side RPC interactions in the Genesis network,
providing a robust and flexible interface for remote function invocation.

Key responsibilities include:
- DDS-based RPC communication with remote services
- Function call validation and error handling
- Service discovery and connection management
- Input validation with configurable patterns
- Timeout and error handling
- Resource lifecycle management

The GenesisRPCClient is designed to be extended by specialized clients (e.g.,
TextProcessorClient) and used by higher-level components like GenericFunctionClient
and GenesisInterface. It handles the complexity of DDS-based RPC communication,
allowing developers to focus on building their services without worrying about
the underlying communication details.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import rti.connextdds as dds
import rti.rpc
import asyncio
import logging
import json
import time
import uuid
from typing import Any, Dict, Optional

# Set up logging
logging.basicConfig(level=logging.WARNING,  # Reduce verbosity
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('GenesisRPCClient')
logger.setLevel(logging.INFO)  # Keep INFO level for important events

class GenesisRPCClient:
    """
    Base class for all Genesis RPC clients.
    Provides function calling and RPC communication.
    """
    def __init__(self, service_name: str = "GenesisRPCService", timeout: int = 10):
        """
        Initialize the RPC client.
        
        Args:
            service_name: Name of the service to connect to
            timeout: Timeout in seconds for function calls
        """
        logger.info("Initializing DDS Domain Participant...")
        self.participant = dds.DomainParticipant(domain_id=0)
        
        logger.info(f"Creating RPC Requester for service: {service_name}...")
        self.requester = rti.rpc.Requester(
            request_type=self.get_request_type(),
            reply_type=self.get_reply_type(),
            participant=self.participant,
            service_name=f"rti/connext/genesis/{service_name}"
        )
        
        self.timeout = dds.Duration(seconds=timeout)
        
        # Common validation patterns
        self.validation_patterns = {
            "text": {
                "min_length": 1,
                "max_length": None,
                "pattern": None
            },
            "letter": {
                "min_length": 1,
                "max_length": 1,
                "pattern": "^[a-zA-Z]$"
            },
            "count": {
                "minimum": 0,
                "maximum": 1000
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
    
    async def wait_for_service(self, timeout_seconds: int = 10) -> bool:
        """
        Wait for the service to be discovered.
        
        Args:
            timeout_seconds: How long to wait for service discovery
            
        Returns:
            True if service was discovered, False if timed out
            
        Raises:
            TimeoutError: If service is not discovered within timeout
        """
        logger.info("Waiting for service discovery...")
        start_time = time.time()
        while self.requester.matched_replier_count == 0:
            if time.time() - start_time > timeout_seconds:
                raise TimeoutError(f"Service discovery timed out after {timeout_seconds} seconds")
            await asyncio.sleep(0.1)
            
        logger.info(f"Service discovered! Matched replier count: {self.requester.matched_replier_count}")
        return True
    
    def validate_text(self, text: str, pattern_type: str = "text") -> None:
        """
        Validate text input using predefined patterns.
        
        Args:
            text: Text to validate
            pattern_type: Type of pattern to use (e.g., 'text', 'letter')
            
        Raises:
            ValueError: If validation fails
        """
        import re
        
        if pattern_type not in self.validation_patterns:
            raise ValueError(f"Unknown pattern type: {pattern_type}")
            
        pattern = self.validation_patterns[pattern_type]
        
        if not text:
            raise ValueError("Text cannot be empty")
            
        if pattern["min_length"] and len(text) < pattern["min_length"]:
            raise ValueError(f"Text must be at least {pattern['min_length']} character(s)")
            
        if pattern["max_length"] and len(text) > pattern["max_length"]:
            raise ValueError(f"Text cannot exceed {pattern['max_length']} character(s)")
            
        if pattern["pattern"] and not re.match(pattern["pattern"], text):
            raise ValueError(f"Text must match pattern: {pattern['pattern']}")

    def validate_numeric(self, value: float, pattern_type: str = "count") -> None:
        """
        Validate numeric input using predefined patterns.
        
        Args:
            value: Number to validate
            pattern_type: Type of pattern to use (e.g., 'count')
            
        Raises:
            ValueError: If validation fails
        """
        if pattern_type not in self.validation_patterns:
            raise ValueError(f"Unknown pattern type: {pattern_type}")
            
        pattern = self.validation_patterns[pattern_type]
        
        if pattern.get("minimum") is not None and value < pattern["minimum"]:
            raise ValueError(f"Value must be at least {pattern['minimum']}")
            
        if pattern.get("maximum") is not None and value > pattern["maximum"]:
            raise ValueError(f"Value cannot exceed {pattern['maximum']}")

    def handle_error_response(self, error_message: str) -> None:
        """
        Handle error responses with consistent error messages.
        
        Args:
            error_message: Error message from service
            
        Raises:
            ValueError: For validation errors
            RuntimeError: For other errors
        """
        # Common validation error patterns
        validation_patterns = [
            "must be at least",
            "cannot exceed",
            "must match pattern",
            "cannot be empty",
            "must be one of"
        ]
        
        # Check if this is a validation error
        if any(pattern in error_message.lower() for pattern in validation_patterns):
            raise ValueError(error_message)
        else:
            raise RuntimeError(error_message)

    async def call_function_with_validation(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """
        Call a function with input validation.
        
        Args:
            function_name: Name of the function to call
            **kwargs: Function arguments
            
        Returns:
            Function result
            
        Raises:
            ValueError: For validation errors
            RuntimeError: For other errors
        """
        try:
            result = await self.call_function(function_name, **kwargs)
            return result
        except Exception as e:
            self.handle_error_response(str(e))

    async def call_function(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """
        Call a remote function with the given name and arguments.
        
        Args:
            function_name: Name of the function to call
            **kwargs: Arguments to pass to the function
            
        Returns:
            Dictionary containing the function's result
            
        Raises:
            TimeoutError: If no reply is received within timeout
            RuntimeError: If the function call fails
            ValueError: If the result JSON is invalid
        """
        # Create a unique ID for this function call
        call_id = f"call_{uuid.uuid4().hex[:8]}"
        
        # Arguments are passed directly as kwargs
        arguments_json = json.dumps(kwargs)
        
        # Create the request with function call
        from genesis_lib.datamodel import FunctionCall
        request = self.get_request_type()(
            id=call_id,
            type="function",
            function=FunctionCall(
                name=function_name,
                arguments=arguments_json
            )
        )
        
        logger.info(f"Calling remote function: {function_name}")
        logger.debug(f"Call ID: {call_id}")
        logger.debug(f"Arguments: {arguments_json}")
        
        # Send the request
        request_id = self.requester.send_request(request)
        logger.debug("Request sent successfully")
        
        try:
            # Wait for and receive the reply
            logger.debug(f"Waiting for reply with timeout of {self.timeout.nanosec / 1e9} seconds")
            replies = self.requester.receive_replies(
                max_wait=self.timeout,
                related_request_id=request_id
            )
            
            if not replies:
                logger.error("No reply received within timeout period")
                raise TimeoutError(f"No reply received for function '{function_name}' within timeout period")
            
            # Process the reply
            reply = replies[0].data
            logger.debug(f"Received reply: success={reply.success}, error_message='{reply.error_message}'")
            
            if reply.success:
                # Parse the result JSON
                try:
                    result = json.loads(reply.result_json)
                    logger.info(f"Function {function_name} returned: {result}")
                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing result JSON: {str(e)}")
                    raise ValueError(f"Invalid result JSON: {str(e)}")
            else:
                logger.warning(f"Function call failed: {reply.error_message}")
                raise RuntimeError(f"Remote function call failed: {reply.error_message}")
                
        except dds.TimeoutError:
            logger.error(f"Timeout waiting for reply to '{function_name}' function call")
            raise TimeoutError(f"Timeout waiting for reply to '{function_name}' function call")
    
    def close(self):
        """Close the client resources."""
        logger.info("Cleaning up client resources...")
        self.requester.close()
        self.participant.close()
        logger.info("Client cleanup complete.") 