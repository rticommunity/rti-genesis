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

"""
Genesis Schema Generators - Provider-Specific Tool Schema Adapters

This module converts Genesis tool metadata (captured by decorators) into the
provider-specific tool schema formats required by different LLMs (OpenAI, Anthropic, local).

=================================================================================================
ARCHITECTURE OVERVIEW - Components
=================================================================================================

1) SchemaGenerator (Abstract Base)
   - Defines the interface for provider adapters:
     • generate_tool_schema(tool_meta) → provider-specific tool schema
     • generate_tools_list(tool_metas) → list of provider-specific schemas

2) Provider Implementations
   - OpenAISchemaGenerator: outputs OpenAI function-calling format
   - AnthropicSchemaGenerator: outputs Anthropic tool format
   - LocalLLMSchemaGenerator: generic/local schema for non-vended LLMs

3) Registry + Factory
   - _schema_generators: map of provider key → generator instance
   - get_schema_generator(format_type): returns the appropriate adapter

=================================================================================================
CURRENT RUNTIME USAGE - Where It’s Used Today
=================================================================================================

- Provider agents (e.g., OpenAIGenesisAgent) call get_schema_generator(...)
  and pass the universal tool metadata harvested by @genesis_tool to produce
  provider-specific schemas exposed to the LLM at runtime.

Call Chain (simplified):
```
@genesis_tool → tool.__genesis_tool_meta__ (provider-agnostic metadata)
  → provider agent caches internal tools
  → get_schema_generator(\"openai\") (or other)
  → generate_tool_schema(meta) per tool
  → LLM API receives provider-specific tool schemas
```

=================================================================================================
WHY THIS IS SEPARATED - Decorators vs Schema Generators vs Function Patterns
=================================================================================================

- Decorators (decorators.py):
  • Capture provider-agnostic metadata at definition time (names, params, types)
  • Perform annotation-based schema inference/validation for RPC and tools
  • DO NOT commit to any provider’s schema shape

- Schema Generators (THIS MODULE):
  • Adapt that universal metadata into provider-specific formats at runtime
  • Isolate provider churn (OpenAI vs Anthropic vs local) from core metadata
  • Allow adding new providers without changing decorator logic

- Function Patterns (function_patterns.py):
  • Classify execution results AFTER a function is called (success/failure, hints)
  • Orthogonal to schema generation (result semantics vs input schema)

Separation of concerns:
- Decorators define how to describe and validate tools/functions (agnostic).
- Schema generators define how to present those tools to specific LLMs.
- Patterns define how to interpret results from executed functions.

=================================================================================================
STATUS & TODO
=================================================================================================

Implemented:
- OpenAI, Anthropic, and Local adapters
- Simple registry + factory (auto defaults to OpenAI)

TODO (future enhancements):
- Add additional providers (e.g., Google/Gemini) with parity tests
- Support advanced/nested types and richer constraints consistently
- Versioned provider mappings and compatibility gates
- Streaming/partial tool schemas where supported
- Validation/asserts to catch mismatches between metadata and provider expectations

=================================================================================================
EXTENSION POINTS - Adding a New Provider
=================================================================================================

1) Implement a SchemaGenerator subclass:
   - generate_tool_schema(tool_meta) → dict in provider shape
   - generate_tools_list(tool_metas) → list of dicts

2) Register it in _schema_generators with a unique key.

3) In your provider agent, call get_schema_generator(\"your_key\").

Design note:
This keeps provider-specific schema churn localized and testable, while the rest
of the system continues to operate on a single provider-agnostic metadata format.

"""

import logging
from typing import Dict, Any, List, Type
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class SchemaGenerator(ABC):
    """Abstract base class for LLM-specific schema generators."""
    
    @abstractmethod
    def generate_tool_schema(self, tool_meta: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a tool schema from Genesis tool metadata."""
        pass
    
    @abstractmethod
    def generate_tools_list(self, tool_metas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate a list of tool schemas for the LLM client."""
        pass

class OpenAISchemaGenerator(SchemaGenerator):
    """Schema generator for OpenAI function calling format."""
    
    def generate_tool_schema(self, tool_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate OpenAI-compatible function schema from Genesis tool metadata.
        
        Args:
            tool_meta: Genesis tool metadata from @genesis_tool decorator
            
        Returns:
            OpenAI function schema dictionary
        """
        function_name = tool_meta.get("function_name", "unknown_function")
        description = tool_meta.get("description", f"Execute {function_name}")
        parameters = tool_meta.get("parameters", {})
        required = tool_meta.get("required", [])
        
        # Build OpenAI function schema
        openai_schema = {
            "type": "function",
            "function": {
                "name": function_name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": parameters,
                    "required": required
                }
            }
        }
        
        logger.debug(f"Generated OpenAI schema for {function_name}")
        return openai_schema
    
    def generate_tools_list(self, tool_metas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate list of OpenAI tool schemas."""
        return [self.generate_tool_schema(meta) for meta in tool_metas]

class AnthropicSchemaGenerator(SchemaGenerator):
    """Schema generator for Anthropic tool format."""
    
    def generate_tool_schema(self, tool_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate Anthropic-compatible tool schema from Genesis tool metadata.
        
        Args:
            tool_meta: Genesis tool metadata from @genesis_tool decorator
            
        Returns:
            Anthropic tool schema dictionary
        """
        function_name = tool_meta.get("function_name", "unknown_function")
        description = tool_meta.get("description", f"Execute {function_name}")
        parameters = tool_meta.get("parameters", {})
        
        # Build Anthropic tool schema
        anthropic_schema = {
            "name": function_name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": parameters,
                "required": tool_meta.get("required", [])
            }
        }
        
        logger.debug(f"Generated Anthropic schema for {function_name}")
        return anthropic_schema
    
    def generate_tools_list(self, tool_metas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate list of Anthropic tool schemas."""
        return [self.generate_tool_schema(meta) for meta in tool_metas]

class LocalLLMSchemaGenerator(SchemaGenerator):
    """Schema generator for local/custom LLM formats."""
    
    def generate_tool_schema(self, tool_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate generic tool schema for local LLMs.
        
        Args:
            tool_meta: Genesis tool metadata from @genesis_tool decorator
            
        Returns:
            Generic tool schema dictionary
        """
        return {
            "name": tool_meta.get("function_name", "unknown_function"),
            "description": tool_meta.get("description", ""),
            "parameters": tool_meta.get("parameters", {}),
            "required_parameters": tool_meta.get("required", []),
            "return_type": tool_meta.get("return_type", "string"),
            "operation_type": tool_meta.get("operation_type", "GENERAL")
        }
    
    def generate_tools_list(self, tool_metas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate list of generic tool schemas."""
        return [self.generate_tool_schema(meta) for meta in tool_metas]

# Schema generator registry
_schema_generators = {
    "openai": OpenAISchemaGenerator(),
    "anthropic": AnthropicSchemaGenerator(), 
    "local": LocalLLMSchemaGenerator(),
    "auto": OpenAISchemaGenerator()  # Default to OpenAI
}

def get_schema_generator(format_type: str) -> SchemaGenerator:
    """
    Get the appropriate schema generator for the specified format.
    
    Args:
        format_type: Schema format type ("openai", "anthropic", "local", "auto")
        
    Returns:
        SchemaGenerator instance
    """
    generator = _schema_generators.get(format_type.lower())
    if generator is None:
        logger.warning(f"Unknown schema format '{format_type}', defaulting to OpenAI")
        generator = _schema_generators["openai"]
    
    return generator

def generate_schemas_for_tools(tool_metas: List[Dict[str, Any]], 
                              format_type: str = "auto") -> List[Dict[str, Any]]:
    """
    Generate tool schemas for a list of Genesis tool metadata.
    
    Args:
        tool_metas: List of Genesis tool metadata dictionaries
        format_type: Target schema format ("openai", "anthropic", "local", "auto")
        
    Returns:
        List of tool schemas in the specified format
    """
    generator = get_schema_generator(format_type)
    return generator.generate_tools_list(tool_metas) 