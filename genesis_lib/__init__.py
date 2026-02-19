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
GENESIS Library - A distributed function discovery and execution framework
"""

import logging
# from .logging_config import configure_genesis_logging # REMOVE THIS

# Configure root logger for genesis_lib
# configure_genesis_logging("genesis_lib", "genesis_lib", logging.INFO) # REMOVE THIS

# Instead of the above, just get a logger for the library. 
# The application using the library will set up handlers and levels.
logger = logging.getLogger(__name__) # or logging.getLogger("genesis_lib")

from .genesis_app import GenesisApp
from .genesis_agent import GenesisAgent
from .interface import GenesisInterface
from .function_discovery import (
    InternalFunctionRegistry,
    FunctionInfo
)
from .dds_function_discovery import DDSFunctionDiscovery
from .function_classifier import FunctionClassifier
from .llm import AnthropicChatAgent
from .llm_factory import LLMFactory
from .openai_genesis_agent import OpenAIGenesisAgent

# LocalGenesisAgent requires optional ollama dependency
try:
    from .local_genesis_agent import LocalGenesisAgent
    _HAS_LOCAL_GENESIS_AGENT = True
except ImportError:
    _HAS_LOCAL_GENESIS_AGENT = False

from .function_requester import FunctionRequester
from .genesis_service import GenesisService
from .monitored_service import MonitoredService
from .utils.openai_utils import convert_functions_to_openai_schema, generate_response_with_functions
from .utils.function_utils import call_function_thread_safe, find_function_by_name, filter_functions_by_relevance
from .utils import get_datamodel_path, load_datamodel
from .stream_publisher import StreamPublisher
from .stream_subscriber import StreamSubscriber

__all__ = [
    'GenesisApp',
    'GenesisAgent',
    'GenesisInterface',
    'InternalFunctionRegistry',
    'DDSFunctionDiscovery',
    'FunctionInfo',
    'FunctionClassifier',
    'AnthropicChatAgent',
    'LLMFactory',
    'OpenAIGenesisAgent',
    'FunctionRequester',
    'GenesisService',
    'MonitoredService',
    'convert_functions_to_openai_schema',
    'generate_response_with_functions',
    'call_function_thread_safe',
    'find_function_by_name',
    'filter_functions_by_relevance',
    'get_datamodel_path',
    'load_datamodel',
    'StreamPublisher',
    'StreamSubscriber',
]

# Add LocalGenesisAgent to __all__ only if ollama dependency is available
if _HAS_LOCAL_GENESIS_AGENT:
    __all__.append('LocalGenesisAgent') 