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
    'generate_response_with_functions',
    'get_qos_provider'
]

def get_datamodel_path():
    """
    Get the path to the datamodel.xml file.
    
    Returns:
        str: The absolute path to the datamodel.xml file
    """
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "datamodel.xml")

# Singleton QosProvider to avoid duplicate profile loading errors
_qos_provider = None

def get_qos_provider():
    """
    Get a singleton QosProvider instance loaded with Genesis QoS profiles.
    
    This function ensures that the USER_QOS_PROFILES.xml is only loaded once per process,
    avoiding DDS errors about duplicate profile registration when multiple Genesis
    components are created.
    
    Returns:
        dds.QosProvider: Singleton QosProvider instance with Genesis profiles loaded
    """
    global _qos_provider
    
    if _qos_provider is None:
        config_dir = os.path.dirname(get_datamodel_path())
        user_qos_path = os.path.join(config_dir, "USER_QOS_PROFILES.xml")
        
        try:
            _qos_provider = dds.QosProvider(user_qos_path)
        except dds.Error as e:
            # If profiles are already loaded (e.g., by default provider), use default
            if "already exists" in str(e):
                _qos_provider = dds.QosProvider.default
            else:
                raise
    
    return _qos_provider

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