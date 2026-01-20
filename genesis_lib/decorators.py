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

from __future__ import annotations

#!/usr/bin/env python3

"""
Genesis Function Decorator System

This module provides a powerful decorator system for automatically generating and managing
function schemas within the Genesis framework. It enables seamless integration between
Python functions and large language models by automatically inferring and validating
function signatures, parameters, and documentation.

Key features:
- Automatic schema generation from Python type hints and docstrings
- Support for complex type annotations (Unions, Lists, Dicts)
- Parameter validation and coercion using Pydantic models
- OpenAI-compatible function schema generation
- Intelligent parameter description extraction from docstrings

The @genesis_function decorator allows developers to expose their functions to LLMs
without manually writing JSON schemas, making the Genesis network more accessible
and maintainable.

Example:
    @genesis_function
    def calculate_sum(a: int, b: int) -> int:
        \"\"\"Add two numbers together.
        
        Args:
            a: First number to add
            b: Second number to add
        \"\"\"
        return a + b

"""

import json, inspect, typing, re, functools, logging
from typing import Any, Callable, Dict, Optional, Type, Union, get_origin, get_args, get_type_hints

logger = logging.getLogger(__name__)

__all__ = ["genesis_function", "genesis_tool", "infer_schema_from_annotations", "validate_args"]

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _extract_param_descriptions(docstring: Optional[str]) -> Dict[str, str]:
    """Extract parameter descriptions from docstring Args section."""
    if not docstring:
        return {}
    
    # Find the Args section
    args_match = re.search(r'Args:\s*\n(.*?)(?=\n\s*\n|\Z)', docstring, re.DOTALL)
    if not args_match:
        return {}
    
    args_section = args_match.group(1)
    descriptions = {}
    
    # Parse each parameter line
    for line in args_section.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Match parameter name and description
        param_match = re.match(r'(\w+):\s*(.*)', line)
        if param_match:
            param_name, description = param_match.groups()
            descriptions[param_name] = description.strip()
    
    return descriptions

def _python_type_to_json(t) -> Union[str, Dict[str, Any]]:
    """Convert Python type to JSON schema type with support for complex types."""
    # Handle Union types (including Optional)
    if get_origin(t) is Union:
        types = [arg for arg in get_args(t) if arg is not type(None)]
        if len(types) == 1:
            return _python_type_to_json(types[0])
        return {"oneOf": [_python_type_to_json(arg) for arg in types]}
    
    # Handle List/Sequence types
    if get_origin(t) in (list, typing.List, typing.Sequence):
        item_type = get_args(t)[0]
        return {"type": "array", "items": _python_type_to_json(item_type)}
    
    # Handle Dict types
    if get_origin(t) in (dict, typing.Dict):
        key_type, value_type = get_args(t)
        if key_type is str:  # Only support string keys for now
            return {
                "type": "object",
                "additionalProperties": _python_type_to_json(value_type)
            }
        return "object"  # Fallback for non-string keys
    
    # Basic types
    type_map = {
        int: "integer",
        float: "number",
        str: "string",
        bool: "boolean",
        type(None): "null",
        Dict: "object",
        dict: "object",
        Any: "object"
    }
    
    return type_map.get(t, "string")

def infer_schema_from_annotations(fn: Callable) -> Dict[str, Any]:
    """Draft‑07 JSON‑Schema synthesised from type annotations and docstring."""
    sig = inspect.signature(fn)
    hints = typing.get_type_hints(fn)
    descriptions = _extract_param_descriptions(fn.__doc__)

    props = {}
    required = []
    
    for name, param in sig.parameters.items():
        if name in ("self", "request_info"):
            continue
            
        typ = hints.get(name, Any)
        type_info = _python_type_to_json(typ)
        
        # Create schema with type and description
        if isinstance(type_info, str):
            schema = {
                "type": type_info,
                "description": descriptions.get(name, "")
            }
        else:
            schema = {
                **type_info,  # This includes type and any additional info
                "description": descriptions.get(name, "")
            }
        
        # Add example if available in docstring
        if name in descriptions and "example" in descriptions[name].lower():
            example_match = re.search(r'example:\s*([^\n]+)', descriptions[name], re.IGNORECASE)
            if example_match:
                try:
                    schema["example"] = eval(example_match.group(1))
                except:
                    pass
        
        props[name] = schema
        if param.default is inspect._empty:
            required.append(name)

    # Create the full schema in the format expected by the function registry
    schema = {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False  # Prevent additional properties
    }
    
    # Convert to JSON string and back to ensure it's serializable
    return json.loads(json.dumps(schema))

def validate_args(fn: Callable, kwargs: Dict[str, Any]) -> None:
    """If a Pydantic model was supplied, validate/coerce kwargs in‑place."""
    model = getattr(fn, "__genesis_meta__", {}).get("pydantic_model")
    if model:
        obj = model(**{k: v for k, v in kwargs.items() if k != "request_info"})
        kwargs.update(obj.model_dump())

# --------------------------------------------------------------------------- #
# Decorator                                                                   #
# --------------------------------------------------------------------------- #
def genesis_function(
    *,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    model: Optional[Type] = None,
    operation_type: Optional[str] = None,
    common_patterns: Optional[Dict[str, Any]] = None,
):
    """
    Attach JSON‑schema & metadata to a function so the service base can
    auto‑register it.
    
    The schema can be provided in three ways:
    1. Explicitly via the parameters argument
    2. Via a Pydantic model using the model argument
    3. Implicitly inferred from type hints and docstring (default)
    """
    def decorator(fn: Callable):
        # Build / derive schema
        if model is not None:
            schema = json.loads(model.schema_json())
        elif parameters is not None:
            schema = parameters
        else:
            schema = infer_schema_from_annotations(fn)

        # Ensure schema is serialized as JSON string
        schema_str = json.dumps(schema)

        fn.__genesis_meta__ = {
            "description": description or (fn.__doc__ or ""),
            "parameters": schema_str,  # Store as JSON string
            "operation_type": operation_type,
            "common_patterns": common_patterns,
            "pydantic_model": model,
        }
        return fn
    return decorator

def genesis_tool(description: str = None, 
                operation_type: str = "GENERAL",
                schema_format: str = "auto"):
    """
    Decorator for marking agent methods as auto-discoverable tools.
    
    This decorator enables automatic tool schema generation and injection
    into LLM clients (OpenAI, Anthropic, etc.) without manual schema definition.
    
    Args:
        description: Human-readable description of the tool (uses docstring if None)
        operation_type: Type of operation for classification
        schema_format: Target schema format ("openai", "anthropic", "auto")
    
    Returns:
        Decorated method with Genesis tool metadata
    """
    def decorator(func):
        # Get function signature and type hints
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        # Auto-generate description from docstring if not provided
        if description is None:
            auto_description = func.__doc__ or f"Execute {func.__name__}"
        else:
            auto_description = description
        
        # Extract parameters with enhanced type detection
        parameters = {}
        required_params = []
        
        for param_name, param in sig.parameters.items():
            # Skip special parameters
            if param_name in ['self', 'cls', 'request_info']:
                continue
            
            # Get type hint
            param_type = type_hints.get(param_name, str)
            
            # Convert Python types to schema types
            schema_type, schema_props = _python_type_to_schema(param_type)
            
            param_info = {
                "type": schema_type,
                "description": f"Parameter {param_name}",
                **schema_props
            }
            
            # Handle default values
            if param.default == inspect.Parameter.empty:
                required_params.append(param_name)
            else:
                param_info["default"] = param.default
            
            parameters[param_name] = param_info
        
        # Extract return type information
        return_type = type_hints.get('return', str)
        return_schema_type, return_schema_props = _python_type_to_schema(return_type)
        
        # Store comprehensive metadata on function
        func.__genesis_tool_meta__ = {
            "description": auto_description,
            "parameters": parameters,
            "required": required_params,
            "operation_type": operation_type,
            "schema_format": schema_format,
            "return_type": return_schema_type,
            "return_properties": return_schema_props,
            "function_name": func.__name__
        }
        
        # Mark as Genesis tool for discovery
        func.__is_genesis_tool__ = True
        
        logger.debug(f"Genesis tool registered: {func.__name__} with {len(parameters)} parameters")
        
        return func
    
    return decorator

def _python_type_to_schema(python_type) -> tuple[str, dict]:
    """
    Convert Python type hints to schema types and properties.
    
    Args:
        python_type: Python type hint
        
    Returns:
        Tuple of (schema_type, additional_properties)
    """
    # Handle basic types
    if python_type == str:
        return "string", {}
    elif python_type == int:
        return "integer", {}
    elif python_type == float:
        return "number", {}
    elif python_type == bool:
        return "boolean", {}
    elif python_type == list:
        return "array", {"items": {"type": "string"}}
    elif python_type == dict:
        return "object", {}
    
    # Handle generic types (List[str], Dict[str, int], etc.)
    origin = get_origin(python_type)
    args = get_args(python_type)
    
    if origin is list and args:
        item_type, item_props = _python_type_to_schema(args[0])
        return "array", {"items": {"type": item_type, **item_props}}
    elif origin is dict and args:
        if len(args) >= 2:
            value_type, value_props = _python_type_to_schema(args[1])
            return "object", {
                "additionalProperties": {"type": value_type, **value_props}
            }
        return "object", {}
    elif origin is tuple:
        # Handle Tuple types as arrays
        return "array", {"items": {"type": "string"}}
    
    # Handle Optional types (Union with None)
    if hasattr(python_type, '__origin__') and python_type.__origin__ is type(type(None).__class__):
        # This is a Union type, check if it's Optional
        if len(args) == 2 and type(None) in args:
            non_none_type = args[0] if args[1] is type(None) else args[1]
            schema_type, props = _python_type_to_schema(non_none_type)
            props["nullable"] = True
            return schema_type, props
    
    # Default fallback
    return "string", {"description": f"Type: {python_type}"}
