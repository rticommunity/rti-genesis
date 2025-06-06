#!/usr/bin/env python3
"""
Genesis Schema Generators

This module provides automatic schema generation for different LLM providers
from Genesis tool metadata. It converts Python type hints and function metadata
into provider-specific tool schemas (OpenAI, Anthropic, etc.).

Copyright (c) 2025, RTI & Jason Upchurch
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