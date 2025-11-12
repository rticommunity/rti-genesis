# Copyright (c) 2025, RTI & Jason Upchurch

"""
Utility modules for the Genesis library
"""

from .openai_utils import convert_functions_to_openai_schema, generate_response_with_functions
from .function_utils import call_function_thread_safe, find_function_by_name, filter_functions_by_relevance

import os
import rti.connextdds as dds

__all__ = [
    'convert_functions_to_openai_schema', 
    'call_function_thread_safe', 
    'find_function_by_name', 
    'filter_functions_by_relevance',
    'generate_response_with_functions'
]

def get_datamodel_path():
    """
    Get the path to the datamodel.xml file.
    
    Returns:
        str: The absolute path to the datamodel.xml file
    """
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "datamodel.xml")

def load_datamodel():
    """
    Load the Python data model.
    
    Returns:
        module: The Python data model module containing all DDS types
    """
    import sys
    from importlib import import_module
    
    # Import the data model module
    try:
        return import_module('genesis_lib.datamodel')
    except ImportError as e:
        print(f"Error importing data model: {e}")
        raise 