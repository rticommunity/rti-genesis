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
Utility functions for working with OpenAI APIs in the Genesis framework
"""

import logging
import json
import traceback
from typing import List, Dict, Any, Tuple, Optional, Callable

logger = logging.getLogger(__name__)

def convert_functions_to_openai_schema(functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert discovered Genesis functions to OpenAI function schemas format.
    
    Args:
        functions: List of function metadata from Genesis function discovery
        
    Returns:
        List of function schemas in OpenAI's expected format
    """
    logger.info("===== TRACING: Converting function schemas for OpenAI =====")
    function_schemas = []
    
    for func in functions:
        function_schemas.append({
            "type": "function",
            "function": {
                "name": func["name"],
                "description": func["description"],
                "parameters": func["schema"]
            }
        })
        logger.info(f"===== TRACING: Added schema for function: {func['name']} =====")
    
    logger.info(f"===== TRACING: Total function schemas for OpenAI: {len(function_schemas)} =====")
    return function_schemas

def generate_response_with_functions(
    client: Any,
    message: str,
    model_name: str,
    system_prompt: str,
    relevant_functions: List[Dict],
    call_function_handler: Callable,
    conversation_history: Optional[List[Dict]] = None,
    conversation_id: Optional[str] = None
) -> Tuple[str, int, bool, Optional[List[Dict]]]:
    """
    Generate a response using OpenAI API with function calling capabilities.
    
    Args:
        client: OpenAI client instance
        message: The user's message
        model_name: The model to use (e.g., "gpt-3.5-turbo")
        system_prompt: The system prompt to use
        relevant_functions: List of relevant function metadata
        call_function_handler: Function to call when the model requests a function call
        conversation_history: Optional conversation history (list of message objects)
        conversation_id: Optional conversation ID for tracking
        
    Returns:
        Tuple of (response, status, used_functions, updated_conversation_history)
    """
    logger.info(f"===== TRACING: Processing request with functions: {message} =====")
    
    try:
        # Get function schemas for OpenAI from relevant functions
        function_schemas = convert_functions_to_openai_schema(relevant_functions)
        
        # Initialize messages with system prompt and user message
        messages = []
        
        # Add system message
        messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add current user message
        messages.append({"role": "user", "content": message})
        
        # If no function schemas available, process without functions
        if not function_schemas:
            logger.warning("===== TRACING: No function schemas available, processing without functions =====")
            response = client.chat.completions.create(
                model=model_name,
                messages=messages
            )
            
            # Update conversation history
            if conversation_history is not None:
                conversation_history.append({"role": "user", "content": message})
                conversation_history.append({"role": "assistant", "content": response.choices[0].message.content})
            
            return response.choices[0].message.content, 0, False, conversation_history
        
        # Call OpenAI API with function calling
        logger.info("===== TRACING: Calling OpenAI API with function schemas =====")
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=function_schemas,
            tool_choice="auto"
        )
        
        # Extract the response
        message_obj = response.choices[0].message
        
        # Update conversation history with user message
        if conversation_history is not None:
            conversation_history.append({"role": "user", "content": message})
        
        # Check if the model wants to call a function
        if message_obj.tool_calls:
            logger.info(f"===== TRACING: Model requested function call(s): {len(message_obj.tool_calls)} =====")
            
            # Update conversation history with assistant's function call
            if conversation_history is not None:
                conversation_history.append(message_obj.model_dump())
            
            # Process each function call
            function_responses = []
            for tool_call in message_obj.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"===== TRACING: Processing function call: {function_name} =====")
                
                # Call the function using the provided handler
                try:
                    function_result = call_function_handler(function_name, **function_args)
                    function_response = {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(function_result)
                    }
                    function_responses.append(function_response)
                    logger.info(f"===== TRACING: Function {function_name} returned: {function_result} =====")
                    
                    # Update conversation history with function response
                    if conversation_history is not None:
                        conversation_history.append(function_response)
                except Exception as e:
                    logger.error(f"===== TRACING: Error calling function {function_name}: {str(e)} =====")
                    error_message = f"Error: {str(e)}"
                    function_response = {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": error_message
                    }
                    function_responses.append(function_response)
                    
                    # Update conversation history with error response
                    if conversation_history is not None:
                        conversation_history.append(function_response)
            
            # If we have function responses, send them back to the model
            if function_responses:
                # Create a new conversation with the function responses
                logger.info("===== TRACING: Sending function responses back to OpenAI =====")
                second_response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *([m for m in conversation_history if m["role"] != "system"] if conversation_history else []),
                        {"role": "user", "content": message},
                        message_obj,  # The assistant's message requesting the function call
                        *function_responses  # The function responses
                    ]
                )
                
                # Extract the final response
                final_message = second_response.choices[0].message.content
                logger.info(f"===== TRACING: Final response: {final_message} =====")
                
                # Update conversation history with final assistant response
                if conversation_history is not None:
                    conversation_history.append({"role": "assistant", "content": final_message})
                
                return final_message, 0, True, conversation_history
        
        # If no function call, just return the response
        text_response = message_obj.content
        logger.info(f"===== TRACING: Response (no function call): {text_response} =====")
        
        # Update conversation history with assistant response
        if conversation_history is not None:
            conversation_history.append({"role": "assistant", "content": text_response})
        
        return text_response, 0, False, conversation_history
            
    except Exception as e:
        logger.error(f"===== TRACING: Error processing request: {str(e)} =====")
        logger.error(traceback.format_exc())
        return f"Error: {str(e)}", 1, False, conversation_history 