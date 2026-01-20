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

import asyncio
import json
import logging
import queue
import threading
import time
import traceback
from typing import Any, Dict, Optional, Tuple, Union, List

logger = logging.getLogger(__name__)

def call_function_thread_safe(
    function_client: Any,
    function_name: str,
    function_id: str,
    service_name: str,
    timeout: float = 10.0,
    **kwargs
) -> Any:
    """
    Call a function by name with the given arguments using a separate thread
    to avoid DDS exclusive area problems.
    
    Args:
        function_client: The requester to use for calling functions (typically FunctionRequester)
        function_name: Name of the function to call (for logging)
        function_id: ID of the function to call
        service_name: Name of the service providing the function (for logging)
        timeout: Maximum time to wait for function execution (seconds)
        **kwargs: Arguments to pass to the function
        
    Returns:
        Function result
        
    Raises:
        ValueError: If function is not found
        RuntimeError: If function execution fails or times out
    """
    logger.info(f"===== TRACING: Executing function call to {function_name} ({function_id}) on service {service_name} =====")
    
    # Create a queue for thread communication
    result_queue = queue.Queue()
    
    # Define the function to run in a separate thread
    def call_function_thread():
        try:
            # Create event loop for async calls
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Call the function using the requester
                start_time = time.time()
                result = loop.run_until_complete(function_client.call_function(function_id, **kwargs))
                end_time = time.time()
                logger.info(f"===== TRACING: Function call completed in {end_time - start_time:.2f} seconds =====")
                
                # Extract the result value
                if isinstance(result, dict) and "result" in result:
                    logger.info(f"===== TRACING: Function result: {result['result']} =====")
                    result_queue.put(("success", result["result"]))
                else:
                    logger.info(f"===== TRACING: Function raw result: {result} =====")
                    result_queue.put(("success", result))
            except Exception as e:
                logger.error(f"===== TRACING: Error calling function {function_name}: {str(e)} =====")
                logger.error(traceback.format_exc())
                result_queue.put(("error", str(e)))
            finally:
                # Clean up
                loop.close()
        except Exception as e:
            logger.error(f"===== TRACING: Thread error: {str(e)} =====")
            result_queue.put(("error", str(e)))
    
    # Start the thread
    thread = threading.Thread(target=call_function_thread)
    thread.daemon = True
    thread.start()
    
    # Wait for the thread to complete with timeout
    thread.join(timeout=timeout)
    
    # Check if we have a result
    try:
        status, result = result_queue.get(block=False)
        if status == "success":
            return result
        else:
            raise RuntimeError(f"Function execution failed: {result}")
    except queue.Empty:
        logger.error("===== TRACING: Function call timed out =====")
        raise RuntimeError(f"Function call to {function_name} timed out after {timeout} seconds")

def find_function_by_name(available_functions: list, function_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Find a function by name in the list of available functions.
    
    Args:
        available_functions: List of available functions
        function_name: Name of the function to find
        
    Returns:
        Tuple of (function_id, service_name) if found, (None, None) otherwise
    """
    for func in available_functions:
        if func.get("name") == function_name:
            return func.get("function_id"), func.get("service_name")
    return None, None

def filter_functions_by_relevance(
    message: str, 
    available_functions: list, 
    function_classifier: Any,
    model_name: str = None
) -> List[Dict]:
    """
    Filter functions based on their relevance to the user's message.
    
    Args:
        message: The user's message
        available_functions: List of available functions
        function_classifier: The function classifier to use
        model_name: Optional model name to use for classification
        
    Returns:
        List of relevant function metadata dictionaries
    """
    logger.info(f"===== TRACING: Filtering functions by relevance for message: {message} =====")
    
    # If no functions are available, return an empty list
    if not available_functions:
        logger.warning("===== TRACING: No functions available to filter =====")
        return []
    
    # Use the function classifier to filter functions
    try:
        # Pass model_name if provided
        if model_name:
            relevant_functions = function_classifier.classify_functions(
                message, 
                available_functions,
                model_name=model_name
            )
        else:
            relevant_functions = function_classifier.classify_functions(
                message, 
                available_functions
            )
            
        logger.info(f"===== TRACING: Found {len(relevant_functions)} relevant functions =====")
        for func in relevant_functions:
            logger.info(f"===== TRACING: Relevant function: {func.get('name')} =====")
        return relevant_functions
    except Exception as e:
        logger.error(f"===== TRACING: Error filtering functions: {str(e)} =====")
        logger.error(traceback.format_exc())
        # In case of error, return all functions
        return available_functions 