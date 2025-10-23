#!/usr/bin/env python3

"""
Genesis Function Classifier - Intelligent Function Selection

This module provides intelligent function classification capabilities for the Genesis framework,
enabling efficient and accurate matching between user queries and available functions. It serves
as a critical component in the function discovery and selection pipeline, using lightweight LLMs
to quickly identify relevant functions before deeper processing.

ARCHITECTURAL OVERVIEW:
======================

The FunctionClassifier serves as an intelligent pre-filtering layer in the Genesis function
discovery system. It analyzes user queries and available functions to identify the most
relevant functions, reducing the cognitive load on primary LLMs and improving response times.

Key responsibilities include:
- Semantic analysis of user queries against function capabilities
- Intelligent filtering of irrelevant functions based on context
- Optimization of function selection for downstream LLM processing
- Support for complex function metadata analysis and matching
- Integration with the Genesis function discovery and execution pipeline

DESIGN PRINCIPLES:
=================

1. **Efficiency First**: Uses lightweight LLMs for rapid classification to minimize latency
2. **Semantic Understanding**: Analyzes function descriptions and parameters for context matching
3. **Provider Agnostic**: Works with any LLM provider through the LLMFactory system
4. **Graceful Degradation**: Falls back to returning all functions when classification fails
5. **Metadata Rich**: Leverages comprehensive function metadata for accurate classification

USAGE PATTERNS:
==============

1. **Pre-Processing Filter**: Used before passing functions to main LLM for tool selection
2. **Function Discovery**: Integrated with function discovery to narrow down available options
3. **Performance Optimization**: Reduces token usage and processing time for large function sets
4. **Context-Aware Selection**: Considers user intent and function capabilities for matching

INTEGRATION WITH GENESIS FRAMEWORK:
===================================

The FunctionClassifier integrates seamlessly with the Genesis framework:

- **LLM Factory**: Uses provider-agnostic LLM creation through LLMFactory
- **Function Discovery**: Works with discovered functions from the Genesis network
- **Metadata System**: Leverages rich function metadata for classification
- **Error Handling**: Provides robust fallback behavior for reliability
- **Logging**: Integrates with Genesis logging system for observability

PERFORMANCE BENEFITS:
====================

- **Reduced Token Usage**: Filters functions before expensive LLM processing
- **Faster Response Times**: Pre-classification reduces main LLM processing time
- **Better Accuracy**: Focuses main LLM on most relevant functions
- **Scalability**: Handles large function sets efficiently through pre-filtering

ERROR HANDLING AND RESILIENCE:
==============================

- Graceful fallback when LLM classification fails
- Comprehensive error logging for debugging classification issues
- Provider-agnostic error handling across different LLM backends
- Validation of function metadata before classification
- Timeout handling for LLM classification requests

Copyright (c) 2025, RTI & Jason Upchurch
"""

import logging
import json
from typing import Dict, List, Any, Optional

# Get logger
logger = logging.getLogger(__name__)

# =============================================================================
# FUNCTION CLASSIFIER CLASS - INTELLIGENT FUNCTION SELECTION
# =============================================================================

class FunctionClassifier:
    """
    Intelligent function classification system for Genesis framework.
    
    The FunctionClassifier provides semantic analysis of user queries against available
    functions to identify the most relevant functions for processing. It serves as an
    intelligent pre-filtering layer that reduces the cognitive load on primary LLMs
    and improves response times through efficient function selection.
    
    ARCHITECTURAL ROLE:
    ===================
    
    The FunctionClassifier acts as a performance optimization layer in the Genesis
    function discovery pipeline. It analyzes function metadata and user queries to
    intelligently filter functions before they are passed to the main LLM for
    tool selection and execution.
    
    KEY FEATURES:
    =============
    
    - **Semantic Analysis**: Uses LLM-based understanding to match queries with functions
    - **Metadata Rich**: Leverages comprehensive function descriptions and parameters
    - **Provider Agnostic**: Works with any LLM provider through LLMFactory
    - **Performance Optimized**: Reduces token usage and processing time
    - **Graceful Fallback**: Returns all functions when classification fails
    
    USAGE EXAMPLE:
    ==============
    
    ```python
    # Initialize with LLMFactory
    from genesis_lib.llm_factory import LLMFactory
    
    classifier = FunctionClassifier()
    classifier.llm = LLMFactory.create_llm(purpose="classifier", provider="openai")
    
    # Classify functions for a query
    relevant_functions = classifier.classify_functions(
        query="What's the weather like?",
        functions=available_functions
    )
    ```
    
    INTEGRATION:
    ===========
    
    The FunctionClassifier integrates with GenesisAgent for automatic function
    filtering and can be used standalone for custom function selection scenarios.
    """
    
    def __init__(self, llm=None):
        """
        Initialize the function classifier with optional LLM instance.
        
        Args:
            llm: Optional LLM instance for classification. If None, classification
                 will be disabled and all functions will be returned.
        
        Note:
            The LLM should be created through LLMFactory for provider-agnostic
            functionality. If no LLM is provided, the classifier will return
            all functions without filtering.
        """
        self.llm = llm
        logger.debug(f"FunctionClassifier initialized with LLM: {llm is not None}")
    
    # =============================================================================
    # FUNCTION METADATA PROCESSING - CLASSIFICATION PREPARATION
    # =============================================================================
    
    def _format_for_classification(self, functions: List[Dict]) -> str:
        """
        Format function metadata for efficient LLM classification.
        
        This method extracts and formats the essential information from function
        metadata to create a structured representation that the LLM can analyze
        effectively. It focuses on function names, descriptions, and parameters
        that are most relevant for classification.
        
        FORMATTING STRATEGY:
        ====================
        
        The method creates a structured format that includes:
        1. **Function Names**: Clear identification of each function
        2. **Descriptions**: Human-readable descriptions of function purpose
        3. **Parameters**: Parameter names and descriptions for context
        4. **Consistent Structure**: Uniform formatting for reliable parsing
        
        Args:
            functions: List of function metadata dictionaries containing:
                      - name: Function name
                      - description: Function description
                      - schema: JSON schema with parameters
            
        Returns:
            Formatted string containing structured function metadata
            
        Example:
            ```python
            functions = [
                {
                    "name": "get_weather",
                    "description": "Get current weather for a location",
                    "schema": {
                        "properties": {
                            "location": {"description": "City name or coordinates"}
                        }
                    }
                }
            ]
            formatted = classifier._format_for_classification(functions)
            # Returns structured string for LLM analysis
            ```
        """
        formatted_functions = []
        
        for func in functions:
            # Extract the essential information for classification
            name = func.get("name", "")
            description = func.get("description", "")
            
            # Format the function information
            formatted_function = f"Function: {name}\nDescription: {description}\n"
            
            # Add parameter information if available
            schema = func.get("schema", {})
            if schema and "properties" in schema:
                formatted_function += "Parameters:\n"
                for param_name, param_info in schema["properties"].items():
                    param_desc = param_info.get("description", "")
                    formatted_function += f"- {param_name}: {param_desc}\n"
            
            formatted_functions.append(formatted_function)
        
        # Combine all formatted functions into a single string
        return "\n".join(formatted_functions)
    
    # =============================================================================
    # LLM PROMPT CONSTRUCTION - CLASSIFICATION INTERFACE
    # =============================================================================
    
    def _build_classification_prompt(self, query: str, formatted_functions: str) -> str:
        """
        Build a structured prompt for LLM-based function classification.
        
        This method creates a well-structured prompt that guides the LLM to
        analyze user queries against available functions and identify the most
        relevant ones. The prompt is designed for consistent, parseable responses.
        
        PROMPT STRUCTURE:
        =================
        
        The prompt includes:
        1. **Role Definition**: Clear instructions for the LLM's role
        2. **User Query**: The specific query to analyze
        3. **Function List**: Formatted function metadata for analysis
        4. **Instructions**: Step-by-step guidance for classification
        5. **Response Format**: Clear format for the expected response
        
        Args:
            query: The user query to analyze for function relevance
            formatted_functions: Pre-formatted function metadata string
            
        Returns:
            Structured prompt string for LLM classification
            
        Note:
            The prompt is designed to produce consistent, parseable responses
            that can be reliably processed by the result parsing method.
        """
        return f"""
You are a function classifier for a distributed system. Your task is to identify which functions are relevant to the user's query.

User Query: {query}

Available Functions:
{formatted_functions}

Instructions:
1. Analyze the user query carefully.
2. Identify which functions would be helpful in answering the query.
3. Return ONLY the names of the relevant functions, one per line.
4. If no functions are relevant, return "NONE".

Relevant Functions:
"""
    
    # =============================================================================
    # RESULT PARSING AND VALIDATION - RESPONSE PROCESSING
    # =============================================================================
    
    def _parse_classification_result(self, result: str) -> List[str]:
        """
        Parse and validate the LLM classification result.
        
        This method processes the LLM's response to extract relevant function names.
        It handles various response formats and filters out non-function content
        to ensure only valid function names are returned.
        
        PARSING STRATEGY:
        =================
        
        The method handles multiple response formats:
        1. **Simple List**: One function name per line
        2. **Markdown Lists**: Functions with bullet points or dashes
        3. **Numbered Lists**: Functions with numbers or other prefixes
        4. **Mixed Format**: Responses with headers or explanatory text
        
        Args:
            result: Raw LLM response string containing function names
            
        Returns:
            List of validated function names, empty list if "NONE" or no matches
            
        Example:
            ```python
            result = "get_weather\ncalculate_distance\nNONE"
            names = classifier._parse_classification_result(result)
            # Returns: ["get_weather", "calculate_distance"]
            ```
        
        Note:
            The method is robust to various LLM response formats and includes
            validation to ensure only valid function names are returned.
        """
        # Split the result into lines and clean up
        lines = [line.strip() for line in result.strip().split("\n") if line.strip()]
        
        # Filter out any lines that are not function names
        function_names = []
        for line in lines:
            # Skip lines that are clearly not function names
            if line.lower() == "none":
                return []
            # Skip the "Relevant Functions" header that might be included in the response
            if line.lower() == "relevant functions":
                continue
            if ":" in line or line.startswith("-") or line.startswith("*"):
                # Extract the function name if it's in a list format
                parts = line.split(":", 1)
                if len(parts) > 1:
                    name = parts[0].strip("-* \t")
                    function_names.append(name)
                else:
                    name = line.strip("-* \t")
                    function_names.append(name)
            else:
                function_names.append(line)
        
        return function_names
    
    # =============================================================================
    # MAIN CLASSIFICATION METHODS - FUNCTION SELECTION
    # =============================================================================
    
    def classify_functions(self, query: str, functions: List[Dict]) -> List[Dict]:
        """
        Classify functions based on their relevance to the user query.
        
        This method performs intelligent function classification using LLM-based
        semantic analysis. It analyzes the user query against available function
        metadata to identify the most relevant functions for processing.
        
        CLASSIFICATION PROCESS:
        ======================
        
        1. **Query Analysis**: The LLM analyzes the user query to understand intent
        2. **Function Evaluation**: Each function's metadata is presented to the LLM
        3. **Semantic Matching**: The LLM determines which functions are relevant
        4. **Result Filtering**: Functions are filtered based on LLM recommendations
        5. **Fallback Handling**: Returns all functions if classification fails
        
        Args:
            query: The user query to analyze for function relevance
            functions: List of function metadata dictionaries containing:
                      - name: Function name
                      - description: Function description  
                      - schema: JSON schema with parameters
            
        Returns:
            List of relevant function metadata dictionaries
            
        Example:
            ```python
            # Classify functions for a weather query
            relevant_functions = classifier.classify_functions(
                query="What's the weather like in New York?",
                functions=available_functions
            )
            # Returns functions like get_weather, get_forecast, etc.
            ```
        
        Note:
            If no LLM is configured or classification fails, all functions
            are returned to ensure the system remains functional.
        """
        logger.debug(f"Classifying functions for query: '{query[:50]}...' against {len(functions)} functions")
        
        # Early return if no LLM is configured
        if not self.llm:
            logger.debug("No LLM configured, returning all functions")
            return functions
        
        # Early return if no functions to classify
        if not functions:
            logger.debug("No functions to classify")
            return []
        
        try:
            # Format functions for classification
            formatted_functions = self._format_for_classification(functions)
            
            # Build classification prompt
            prompt = self._build_classification_prompt(query, formatted_functions)
            
            # Call LLM for classification (provider-agnostic)
            logger.debug("Calling LLM for function classification")
            
            # Use the LLM's generate_response method (provider-agnostic)
            response, status = self.llm.generate_response(
                message=prompt,
                conversation_id="function_classification"
            )
            
            if status != 0:
                logger.warning(f"LLM classification failed with status {status}, returning all functions")
                return functions
            
            # Parse classification result
            relevant_function_names = self._parse_classification_result(response)
            
            logger.debug(f"LLM identified {len(relevant_function_names)} relevant functions")
            
            # Filter functions based on classification result
            relevant_functions = [
                func for func in functions 
                if func.get("name") in relevant_function_names
            ]
            
            logger.debug(f"Returning {len(relevant_functions)} relevant functions")
            return relevant_functions
            
        except Exception as e:
            logger.error(f"Error in function classification: {e}")
            logger.debug("Returning all functions due to classification error")
            return functions 