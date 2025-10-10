"""
Genesis Function Call Data Model

This module defines the data structures used for function calling RPC (Remote Procedure Call)
within the Genesis framework. It implements OpenAI-style function calling interfaces using
RTI's IDL (Interface Definition Language) for type-safe serialization and deserialization.

Key responsibilities include:
- Defining function call request/reply structures for RPC communication
- Implementing OpenAI-compatible function calling interfaces
- Providing schema validation for function definitions
- Supporting session management operations

Note: This is a temporary implementation that will be integrated into the main
datamodel.xml in a future update. The current separation allows for rapid iteration
on the function calling interface while maintaining compatibility with the existing
DDS infrastructure.

Copyright (c) 2025, RTI & Jason Upchurch
"""

from dataclasses import field
from typing import Union, Sequence, Optional, Dict, Any
import rti.idl as idl
from enum import IntEnum
import sys
import os
import json

@idl.struct(
    member_annotations={
        'request_id': [idl.bound(64)],
        'service_type': [idl.bound(128)],
        'function_name': [idl.bound(128)],
        # parameters_json intentionally unbounded
        'target_service_guid': [idl.bound(128)],
        # deadline_ms is plain int
        'requester_guid': [idl.bound(128)],
    }
)
class RPCRequestV2:
    """
    Unified RPC request for v2 RPC path.
    """
    request_id: str = ""
    service_type: str = ""  # e.g., "CalculatorService"
    function_name: str = ""
    parameters_json: str = ""
    target_service_guid: str = ""
    deadline_ms: int = 3000
    requester_guid: str = ""

@idl.struct(
    member_annotations={
        'request_id': [idl.bound(64)],
        'service_type': [idl.bound(128)],
        # result_json intentionally unbounded
        'error_code': [idl.bound(64)],
        'error_message': [idl.bound(255)],
        'replier_service_guid': [idl.bound(128)],
        # latency_ms is plain int
    }
)
class RPCReplyV2:
    """
    Unified RPC reply for v2 RPC path.
    """
    request_id: str = ""
    service_type: str = ""
    ok: bool = False
    result_json: str = ""
    error_code: str = ""
    error_message: str = ""
    replier_service_guid: str = ""
    latency_ms: int = 0

@idl.struct(
    member_annotations = {
        'name': [idl.bound(255)],
        'description': [idl.bound(255)],
    }
)
class Function:
    """
    OpenAI-style function definition with name, description, and parameters.
    """
    name: str = ""  # Name of the function
    description: str = ""  # Description of what the function does
    parameters: str = ""  # JSON-encoded parameters schema
    strict: bool = True  # Whether to enforce strict type checking

@idl.struct(
    member_annotations = {
        'type': [idl.bound(255)],
    }
)
class Tool:
    """
    OpenAI-style tool definition, currently only supporting function tools.
    """
    type: str = "function"  # Type of tool (currently only "function" is supported)
    function: Function = field(default_factory=Function)  # Function definition

@idl.struct(
    member_annotations = {
        'name': [idl.bound(255)],
        'arguments': [idl.bound(255)],
    }
)
class FunctionCall:
    """
    OpenAI-style function call with name and arguments.
    """
    name: str = ""  # Name of the function to call
    arguments: str = ""  # JSON-encoded arguments for the function

@idl.struct(
    member_annotations = {
        'id': [idl.bound(255)],
        'type': [idl.bound(255)],
    }
)
class FunctionRequest:
    """
    OpenAI-style function request with unique ID and type.
    """
    id: str = ""  # Unique identifier for the function call
    type: str = "function"  # Always "function" to match OpenAI format
    function: FunctionCall = field(default_factory=FunctionCall)  # Nested function call details

@idl.struct(
    member_annotations = {
        'result_json': [],  # No bound annotation means unbounded
        'error_message': [idl.bound(255)],
    }
)
class FunctionReply:
    """
    Reply from a function execution with result and status.
    """
    result_json: str = ""  # JSON-encoded result from the function
    success: bool = False  # Whether the function executed successfully
    error_message: str = ""  # Error message if the function failed

@idl.struct
class SessionRequest:
    """Request for session management operations"""
    operation: str  # "CREATE", "JOIN", "LEAVE", "CLOSE"
    session_id: str  # UUID for the session
    client_id: str  # UUID of the client making the request
    metadata: str  # JSON string containing additional session metadata

@idl.struct
class SessionReply:
    """Reply to session management operations"""
    success: bool
    session_id: str  # UUID for the session
    error_message: str  # Empty if success is True
    metadata: str  # JSON string containing session state/metadata

@idl.struct
class SessionEvent:
    """Event published when session state changes"""
    event_type: str  # "CREATED", "JOINED", "LEFT", "CLOSED"
    session_id: str  # UUID for the session
    client_id: str  # UUID of the client involved
    timestamp: int  # Unix timestamp in milliseconds
    metadata: str  # JSON string containing event details

def validate_schema(schema: Dict[str, Any]) -> bool:
    """
    Validate that a schema follows OpenAI's function schema format.
    
    Args:
        schema: The schema to validate
        
    Returns:
        bool: True if valid, False otherwise
        
    Raises:
        ValueError: If the schema is invalid with details about why
    """
    required_fields = {"type", "properties"}
    if not isinstance(schema, dict):
        raise ValueError("Schema must be a dictionary")
    
    if not all(field in schema for field in required_fields):
        raise ValueError(f"Schema missing required fields: {required_fields - schema.keys()}")
    
    if schema["type"] != "object":
        raise ValueError('Schema "type" must be "object"')
    
    if not isinstance(schema["properties"], dict):
        raise ValueError("Schema properties must be a dictionary")
    
    for prop_name, prop in schema["properties"].items():
        if not isinstance(prop, dict):
            raise ValueError(f"Property {prop_name} must be a dictionary")
        if "type" not in prop:
            raise ValueError(f"Property {prop_name} missing required field 'type'")
        if "description" not in prop:
            raise ValueError(f"Property {prop_name} missing required field 'description'")
    
    return True 