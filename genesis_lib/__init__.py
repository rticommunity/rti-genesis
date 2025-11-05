# Copyright (c) 2025, RTI & Jason Upchurch

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
    FunctionRegistry,
    FunctionInfo
)
from .function_classifier import FunctionClassifier
from .llm import AnthropicChatAgent
from .llm_factory import LLMFactory
from .openai_genesis_agent import OpenAIGenesisAgent
from .generic_function_client import GenericFunctionClient
from .genesis_service import GenesisService
from .monitored_service import MonitoredService
from .utils.openai_utils import convert_functions_to_openai_schema, generate_response_with_functions
from .utils.function_utils import call_function_thread_safe, find_function_by_name, filter_functions_by_relevance
from .utils import get_datamodel_path, load_datamodel

__all__ = [
    'GenesisApp',
    'GenesisAgent',
    'GenesisInterface',
    'FunctionRegistry',
    'FunctionInfo',
    'FunctionClassifier',
    'AnthropicChatAgent',
    'LLMFactory',
    'OpenAIGenesisAgent',
    'GenericFunctionClient',
    'GenesisService',
    'MonitoredService',
    'convert_functions_to_openai_schema',
    'generate_response_with_functions',
    'call_function_thread_safe',
    'find_function_by_name',
    'filter_functions_by_relevance',
    'get_datamodel_path',
    'load_datamodel'
] 