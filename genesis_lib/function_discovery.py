"""
Genesis Function Discovery System

This module provides the core function discovery and registration system for the Genesis
framework, enabling dynamic discovery and matching of functions across the distributed
network. It implements a DDS-based discovery mechanism that allows functions to be
advertised, discovered, and matched based on capabilities and requirements.

Key responsibilities include:
- DDS-based function capability advertisement and discovery
- Function registration and metadata management
- Intelligent function matching using LLM analysis
- Function validation and schema management
- Service integration and lifecycle management

Known Limitations:
- Current implementation may lead to recursive function discovery due to its deep
  integration in the library stack. This can cause functions to discover each other
  in unintended ways. Future versions will address this by:
  1. Moving function discovery to a higher level in the framework
  2. Implementing clearer boundaries between function providers and consumers
  3. Adding explicit discovery scoping and filtering

Copyright (c) 2025, RTI & Jason Upchurch
"""

#!/usr/bin/env python3

import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
import json
import uuid
import time
import rti.connextdds as dds
import rti.rpc as rpc
import re
import os
from genesis_lib.utils import get_datamodel_path
import asyncio
import sys
import traceback

# Configure root logger to handle all loggers
# logging.basicConfig( # REMOVE THIS BLOCK
#     level=logging.DEBUG,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler()
#     ]
# )

# Configure function discovery logger specifically
logger = logging.getLogger("function_discovery")
# logger.setLevel(logging.DEBUG) # REMOVE - Let the script control the level

# Set all genesis_lib loggers to DEBUG
# for name in ['genesis_lib', 'genesis_lib.function_discovery', 'genesis_lib.agent', 'genesis_lib.monitored_agent', 'genesis_lib.genesis_app']:
#     logging.getLogger(name).setLevel(logging.DEBUG) # REMOVE THIS LOOP

@dataclass
class FunctionInfo:
    """Information about a registered function"""
    function_id: str
    name: str
    description: str
    function: Callable
    schema: Dict[str, Any]
    categories: List[str]
    performance_metrics: Dict[str, Any]
    security_requirements: Dict[str, Any]
    match_info: Optional[Dict[str, Any]] = None
    classification: Optional[Dict[str, Any]] = None
    operation_type: Optional[str] = None  # One of: transformation, analysis, generation, calculation
    common_patterns: Optional[Dict[str, Any]] = None  # Common validation patterns used by this function

    def get_validation_patterns(self) -> Dict[str, Any]:
        """
        Get validation patterns for this function.
        
        Returns:
            Dictionary of validation patterns
        """
        if not self.common_patterns:
            return {}
            
        # Common validation patterns
        patterns = {
            "text": {
                "min_length": 1,
                "max_length": None,
                "pattern": None
            },
            "letter": {
                "min_length": 1,
                "max_length": 1,
                "pattern": "^[a-zA-Z]$"
            },
            "count": {
                "minimum": 0,
                "maximum": 1000
            },
            "number": {
                "minimum": None,
                "maximum": None
            }
        }
        
        # Update with function-specific patterns
        for pattern_type, pattern in self.common_patterns.items():
            if pattern_type in patterns:
                patterns[pattern_type].update(pattern)
                
        return patterns

    def validate_input(self, parameter_name: str, value: Any) -> None:
        """
        Validate input using common patterns.
        
        Args:
            parameter_name: Name of the parameter to validate
            value: Value to validate
            
        Raises:
            ValueError: If validation fails
        """
        if not self.common_patterns or parameter_name not in self.common_patterns:
            return
            
        pattern = self.common_patterns[parameter_name]
        pattern_type = pattern.get("type", "text")
        
        if pattern_type == "text":
            if not isinstance(value, str):
                raise ValueError(f"{parameter_name} must be a string")
                
            if pattern.get("min_length") and len(value) < pattern["min_length"]:
                raise ValueError(f"{parameter_name} must be at least {pattern['min_length']} character(s)")
                
            if pattern.get("max_length") and len(value) > pattern["max_length"]:
                raise ValueError(f"{parameter_name} cannot exceed {pattern['max_length']} character(s)")
                
            if pattern.get("pattern") and not re.match(pattern["pattern"], value):
                raise ValueError(f"{parameter_name} must match pattern: {pattern['pattern']}")
                
        elif pattern_type in ["number", "integer"]:
            if not isinstance(value, (int, float)):
                raise ValueError(f"{parameter_name} must be a number")
                
            if pattern.get("minimum") is not None and value < pattern["minimum"]:
                raise ValueError(f"{parameter_name} must be at least {pattern['minimum']}")
                
            if pattern.get("maximum") is not None and value > pattern["maximum"]:
                raise ValueError(f"{parameter_name} cannot exceed {pattern['maximum']}")

class FunctionMatcher:
    """Matches functions based on LLM analysis of requirements and available functions"""
    
    def __init__(self, llm_client=None):
        """Initialize the matcher with optional LLM client"""
        self.logger = logging.getLogger("function_matcher")
        self.llm_client = llm_client
    
    def find_matching_functions(self,
                              user_request: str,
                              available_functions: List[Dict[str, Any]],
                              min_similarity: float = 0.7) -> List[Dict[str, Any]]:
        """
        Find functions that match the user's request using LLM analysis.
        
        Args:
            user_request: The user's natural language request
            available_functions: List of available function metadata
            min_similarity: Minimum similarity score (0-1)
            
        Returns:
            List of matching function metadata with relevance scores
        """
        if not self.llm_client:
            self.logger.warning("No LLM client provided, falling back to basic matching")
            return self._fallback_matching(user_request, available_functions)
        
        # Create prompt for LLM
        prompt = f"""Given the following user request:

{user_request}

And the following functions:

{json.dumps([{
    "function_name": f["name"],
    "function_description": f.get("description", "")
} for f in available_functions], indent=2)}

For each relevant function, return a JSON array where each object has:
- function_name: The name of the matching function
- domain: The primary domain/category this function belongs to (e.g., "weather", "mathematics")
- operation_type: The type of operation this function performs (e.g., "lookup", "calculation")

Only include functions that are actually relevant to the request. Do not return anything else."""

        # Log the prompt being sent to the LLM
        self.logger.info(
            "LLM Classification Prompt",
            extra={
                "user_request": user_request,
                "prompt": prompt,
                "available_functions": [f["name"] for f in available_functions]
            }
        )

        try:
            # Get LLM response
            response = self.llm_client.generate_response(prompt, "function_matching")
            
            # Log the raw LLM response for monitoring
            self.logger.info(
                "LLM Function Classification Response",
                extra={
                    "user_request": user_request,
                    "raw_response": response[0],
                    "response_status": response[1],
                    "available_functions": [f["name"] for f in available_functions]
                }
            )
            
            # Parse response
            matches = json.loads(response[0])
            
            # Convert matches to full metadata
            result = []
            for match in matches:
                func = next((f for f in available_functions if f["name"] == match["function_name"]), None)
                if func:
                    # Add match info
                    func["match_info"] = {
                        "relevance_score": 1.0,  # Since we're just doing exact matches
                        "explanation": "Function name matched by LLM",
                        "inferred_params": {},  # Parameter inference happens later
                        "considerations": [],
                        "domain": match.get("domain", "unknown"),
                        "operation_type": match.get("operation_type", "unknown")
                    }
                    result.append(func)
            
            # Log the processed matches for monitoring
            self.logger.info(
                "Processed Function Matches",
                extra={
                    "user_request": user_request,
                    "matches": result,
                    "min_similarity": min_similarity
                }
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Error in LLM-based matching",
                extra={
                    "user_request": user_request,
                    "error": str(e),
                    "available_functions": [f["name"] for f in available_functions]
                }
            )
            return self._fallback_matching(user_request, available_functions)
    
    def _prepare_function_descriptions(self, functions: List[Dict[str, Any]]) -> str:
        """Prepare function descriptions for LLM analysis"""
        descriptions = []
        for func in functions:
            desc = f"Function: {func['name']}\n"
            desc += f"Description: {func.get('description', '')}\n"
            desc += "Parameters:\n"
            
            # Add parameter descriptions
            if "parameter_schema" in func and "properties" in func["parameter_schema"]:
                for param_name, param_schema in func["parameter_schema"]["properties"].items():
                    desc += f"- {param_name}: {param_schema.get('description', param_schema.get('type', 'unknown'))}"
                    if param_schema.get("required", False):
                        desc += " (required)"
                    desc += "\n"
            
            # Add performance and security info if available
            if "performance_metrics" in func:
                desc += "Performance:\n"
                for metric, value in func["performance_metrics"].items():
                    desc += f"- {metric}: {value}\n"
            
            if "security_requirements" in func:
                desc += "Security:\n"
                for req, value in func["security_requirements"].items():
                    desc += f"- {req}: {value}\n"
            
            descriptions.append(desc)
        
        return "\n".join(descriptions)
    
    def _convert_matches_to_metadata(self, 
                                   matches: List[Dict[str, Any]], 
                                   available_functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert LLM matches to function metadata format"""
        result = []
        for match in matches:
            # Find the original function metadata
            func = next((f for f in available_functions if f["name"] == match["function_name"]), None)
            if func:
                # Add match information
                func["match_info"] = {
                    "relevance_score": match["relevance_score"],
                    "explanation": match["explanation"],
                    "inferred_params": match["inferred_params"],
                    "considerations": match["considerations"],
                    "domain": match.get("domain", "unknown"),
                    "operation_type": match.get("operation_type", "unknown")
                }
                result.append(func)
        return result
    
    def _fallback_matching(self, user_request: str, available_functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback to basic matching if LLM is not available"""
        # Simple text-based matching as fallback
        matches = []
        request_lower = user_request.lower()
        request_words = set(request_lower.split())
        
        for func in available_functions:
            # Check function name and description
            name_match = func["name"].lower() in request_lower
            desc_match = func.get("description", "").lower() in request_lower
            
            # Check for word matches in both name and description
            func_name_words = set(func["name"].lower().split())
            func_desc_words = set(func.get("description", "").lower().split())
            
            # Calculate word overlap
            name_word_overlap = bool(func_name_words & request_words)
            desc_word_overlap = bool(func_desc_words & request_words)
            
            if name_match or desc_match or name_word_overlap or desc_word_overlap:
                # Calculate a simple relevance score based on matches
                if name_match and desc_match:
                    relevance_score = 0.5
                elif name_match or desc_match:
                    relevance_score = 0.5
                elif name_word_overlap and desc_word_overlap:
                    relevance_score = 0.5
                elif name_word_overlap or desc_word_overlap:
                    relevance_score = 0.4
                else:
                    relevance_score = 0.3
                
                # Try to infer parameters from the request
                inferred_params = {}
                if "parameter_schema" in func and "properties" in func["parameter_schema"]:
                    for param_name, param_schema in func["parameter_schema"]["properties"].items():
                        # Look for parameter values in the request
                        param_desc = param_schema.get("description", "").lower()
                        if param_desc in request_lower:
                            # Extract the value after the parameter description
                            value_start = request_lower.find(param_desc) + len(param_desc)
                            value_end = request_lower.find(" ", value_start)
                            if value_end == -1:
                                value_end = len(request_lower)
                            value = request_lower[value_start:value_end].strip()
                            if value:
                                inferred_params[param_name] = value
                
                # Log the fallback matching details
                self.logger.info(
                    "Fallback Matching Details",
                    extra={
                        "user_request": user_request,
                        "function_name": func["name"],
                        "name_match": name_match,
                        "desc_match": desc_match,
                        "name_word_overlap": name_word_overlap,
                        "desc_word_overlap": desc_word_overlap,
                        "relevance_score": relevance_score,
                        "inferred_params": inferred_params
                    }
                )
                
                func["match_info"] = {
                    "relevance_score": relevance_score,
                    "explanation": "Basic text matching",
                    "inferred_params": inferred_params,
                    "considerations": ["Using basic text matching - results may be less accurate"],
                    "domain": "unknown",
                    "operation_type": "unknown"
                }
                matches.append(func)
        
        # Sort matches by relevance score
        matches.sort(key=lambda x: x["match_info"]["relevance_score"], reverse=True)
        
        return matches 

class FunctionRegistry:
    """
    Registry for functions that can be called by the agent.
    
    This implementation supports DDS-based distributed function discovery
    and execution, where functions can be provided by:
    1. Other agents with specific expertise
    2. Traditional ML models wrapped as function providers
    3. Planning agents for complex task decomposition
    4. Simple procedural code exposed as functions
    
    The distributed implementation uses DDS topics for:
    - Function capability advertisement
    - Function discovery and matching
    - Function execution requests via DDS RPC
    - Function execution results via DDS RPC
    """
    
    def __init__(self, participant=None, domain_id=0, enable_discovery_listener: bool = True):
        """
        Initialize the function registry.
        
        Args:
            participant: DDS participant to use (creates one if None)
            domain_id: DDS domain ID to use if creating a participant
            enable_discovery_listener: Whether to enable the discovery listener
        """
        logger.debug("Initializing FunctionRegistry")
        
        # Store configuration
        self.domain_id = domain_id
        self.enable_discovery_listener = enable_discovery_listener
        
        # Initialize storage
        self.functions = {}  # function_id -> FunctionInfo
        self.function_by_name = {}  # name -> function_id
        self.discovered_functions = {}  # function_id -> dict with function details
        self.service_base = None  # Reference to service base for callbacks
        
        # Add callback mechanism for function discovery
        self.discovery_callbacks = []  # List of callback functions to call when functions are discovered
        
        # Create or use provided participant
        if participant is None:
            self.participant = dds.DomainParticipant(domain_id)
            self._owns_participant = True
        else:
            self.participant = participant
            self._owns_participant = False
        
        # Create publisher (always needed for advertising own functions)
        self.publisher = dds.Publisher(self.participant)
        
        # Get types from XML
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        self.capability_type = self.type_provider.type("genesis_lib", "FunctionCapability")
        
        # Create topics
        # Try to find the topic first, create if not found
        try:
            # find_topics returns all topics for the participant
            all_topics = self.participant.find_topics()
            found_topic = None
            for topic in all_topics:
                # Check if the topic name matches
                if topic.name == "rti/connext/genesis/FunctionCapability":
                     # Optional: Check type name if necessary
                     # if topic.type_name == self.capability_type.name:
                    found_topic = topic
                    break # Found the topic
            
            if found_topic:
                self.capability_topic = found_topic
                logger.debug("===== DDS TRACE: Found existing FunctionCapability topic. =====")
            else:
                 # Topic not found, create it
                logger.debug("===== DDS TRACE: FunctionCapability topic not found, creating new one... =====")
                self.capability_topic = dds.DynamicData.Topic(
                    participant=self.participant,
                    topic_name="rti/connext/genesis/FunctionCapability",
                    topic_type=self.capability_type
                )
                logger.debug("===== DDS TRACE: Created new FunctionCapability topic. =====")

        except dds.Error as e:
            # Handle potential errors during find_topics or create_topic
            logger.error(f"===== DDS TRACE: DDS Error finding/creating FunctionCapability topic: {e} ====")
            raise
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"===== DDS TRACE: Unexpected error during topic find/create: {e} ====")
            raise
        
        # Create DataWriter for capability advertisement (always needed)
        writer_qos = dds.QosProvider.default.datawriter_qos
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.history.kind = dds.HistoryKind.KEEP_LAST
        writer_qos.history.depth = 500
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.liveliness.kind = dds.LivelinessKind.AUTOMATIC
        writer_qos.liveliness.lease_duration = dds.Duration(seconds=2)
        
        self.capability_writer = dds.DynamicData.DataWriter(
            pub=self.publisher,
            topic=self.capability_topic,
            qos=writer_qos,
            mask=dds.StatusMask.ALL
        )

        if self.enable_discovery_listener:
            # Create subscriber
            self.subscriber = dds.Subscriber(self.participant)
            
            # Get types for execution (only if discovery is enabled)
            self.execution_request_type = self.type_provider.type("genesis_lib", "FunctionExecutionRequest")
            self.execution_reply_type = self.type_provider.type("genesis_lib", "FunctionExecutionReply")

            # Create DataReader for capability discovery
            reader_qos = dds.QosProvider.default.datareader_qos
            reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
            reader_qos.history.kind = dds.HistoryKind.KEEP_LAST
            reader_qos.history.depth = 500
            reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
            reader_qos.liveliness.kind = dds.LivelinessKind.AUTOMATIC
            reader_qos.liveliness.lease_duration = dds.Duration(seconds=2)
            
            self.capability_listener = FunctionCapabilityListener(self)
            self.capability_reader = dds.DynamicData.DataReader(
                topic=self.capability_topic,
                qos=reader_qos,
                listener=self.capability_listener,
                subscriber=self.subscriber,
                mask=dds.StatusMask.ALL
            )
            
            # Create RPC client for function execution
            self.execution_client = rpc.Requester(
                request_type=self.execution_request_type,
                reply_type=self.execution_reply_type,
                participant=self.participant,
                service_name="rti/connext/genesis/FunctionExecution"
            )
        else:
            self.subscriber = None
            self.capability_reader = None
            self.capability_listener = None
            self.execution_client = None
            # Ensure discovered_functions is initialized if discovery is off,
            # though it's already initialized above.
            self.discovered_functions = {}
            logger.info("FunctionRegistry initialized with discovery listener DISABLED.")
        
        # Initialize function matcher with LLM support
        self.matcher = FunctionMatcher()
        
        # Event to signal when the first function capability has been discovered
        self._discovery_event = asyncio.Event()
        
        logger.debug("FunctionRegistry initialized successfully")
    
    def register_function(self, 
                         func: Callable,
                         description: str,
                         parameter_descriptions: Dict[str, Any],
                         capabilities: List[str] = None,
                         performance_metrics: Dict[str, Any] = None,
                         security_requirements: Dict[str, Any] = None) -> str:
        """
        Register a function with the registry.
        
        Args:
            func: The function to register
            description: Human-readable description of the function
            parameter_descriptions: JSON Schema for function parameters
            capabilities: List of capability tags
            performance_metrics: Performance characteristics
            security_requirements: Security requirements
            
        Returns:
            Function ID of the registered function
        """
        # Generate function ID
        function_id = str(uuid.uuid4())
        
        # Log start of registration process
        logger.info(f"Starting function registration in FunctionRegistry",
                   extra={
                       "function_name": func.__name__,
                       "function_id": function_id,
                       "capabilities": capabilities,
                       "has_performance_metrics": bool(performance_metrics),
                       "has_security_requirements": bool(security_requirements)
                   })
        
        # Log detailed function information
        logger.debug(f"Detailed function registration information",
                    extra={
                        "function_name": func.__name__,
                        "function_id": function_id,
                        "description": description,
                        "parameter_schema": parameter_descriptions,
                        "capabilities": capabilities,
                        "performance_metrics": performance_metrics,
                        "security_requirements": security_requirements
                    })
        
        try:
            # Create function info
            logger.debug(f"Creating FunctionInfo object for '{func.__name__}'")
            function_info = FunctionInfo(
                function_id=function_id,
                name=func.__name__,
                description=description,
                function=func,
                schema=parameter_descriptions,
                categories=capabilities or [],
                performance_metrics=performance_metrics or {},
                security_requirements=security_requirements or {}
            )
            
            # Store function info
            logger.debug(f"Storing function info for '{func.__name__}' in registry")
            self.functions[function_id] = function_info
            self.function_by_name[function_info.name] = function_id
            
            # Advertise function capability
            logger.info(f"Advertising function capability for '{func.__name__}'")
            self._advertise_function(function_info)
            
            # Log successful registration
            logger.info(f"Successfully registered function '{func.__name__}'",
                       extra={
                           "function_id": function_id,
                           "function_name": func.__name__,
                           "categories": list(function_info.categories),
                           "registered_categories_count": len(function_info.categories)
                       })
            
            return function_id
            
        except Exception as e:
            # Log registration failure with detailed error info
            logger.error(f"Failed to register function '{func.__name__}'",
                        extra={
                            "function_id": function_id,
                            "function_name": func.__name__,
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "traceback": logging.traceback.format_exc()
                        })
            raise
    
    def find_matching_functions(self,
                              user_request: str,
                              min_similarity: float = 0.7) -> List[FunctionInfo]:
        """
        Find functions that match the user's request.
        
        Args:
            user_request: The user's natural language request
            min_similarity: Minimum similarity score (0-1)
            
        Returns:
            List of matching FunctionInfo objects
        """
        # Convert functions to format expected by matcher
        available_functions = [
            {
                "name": func.name,
                "description": func.description,
                "parameter_schema": func.schema,
                "capabilities": func.categories,
                "performance_metrics": func.performance_metrics,
                "security_requirements": func.security_requirements
            }
            for func in self.functions.values()
        ]
        
        # Find matches using the matcher
        matches = self.matcher.find_matching_functions(
            user_request=user_request,
            available_functions=available_functions,
            min_similarity=min_similarity
        )
        
        # Convert matches back to FunctionInfo objects
        result = []
        for match in matches:
            function_id = self.function_by_name.get(match["name"])
            if function_id and function_id in self.functions:
                func_info = self.functions[function_id]
                func_info.match_info = match.get("match_info", {})
                result.append(func_info)
        
        return result
    
    def _advertise_function(self, function_info: FunctionInfo):
        """Advertise function capability via DDS"""
        logger.debug(f"===== DDS TRACE: Preparing DDS data for advertising function: {function_info.name} ({function_info.function_id}) =====")
        capability = dds.DynamicData(self.capability_type)
        capability['function_id'] = function_info.function_id
        capability['name'] = function_info.name
        capability['description'] = function_info.description
        capability['provider_id'] = str(self.capability_writer.instance_handle)  # Use DataWriter GUID
        capability['parameter_schema'] = json.dumps(function_info.schema)
        capability['capabilities'] = json.dumps(function_info.categories)
        capability['performance_metrics'] = json.dumps(function_info.performance_metrics)
        capability['security_requirements'] = json.dumps(function_info.security_requirements)
        capability['classification'] = json.dumps(function_info.classification or {})
        capability['last_seen'] = int(time.time() * 1000)
        
        # Add the service name from the service_base reference
        if self.service_base and hasattr(self.service_base, 'service_name'):
            capability['service_name'] = self.service_base.service_name
        else:
            logger.warning(f"Could not determine service_name when advertising function {function_info.name}")
            capability['service_name'] = "UnknownService" # Default if service name is not found
        
        logger.debug(f"===== DDS TRACE: Publishing FunctionCapability for {function_info.name} ({function_info.function_id}): {capability} =====")
        try:
            self.capability_writer.write(capability)
            self.capability_writer.flush()
            logger.debug(f"===== DDS TRACE: Successfully published FunctionCapability for {function_info.name} =====")
        except Exception as e:
            logger.error(f"===== DDS TRACE: Error publishing FunctionCapability for {function_info.name}: {e} ====", exc_info=True)
            # Optionally re-raise or handle
    
    def handle_capability_advertisement(self, capability: dds.DynamicData, info: dds.SampleInfo):
        """Handle received function capability data"""
        function_id_str = "unknown_id"
        try:
            function_id_str = capability.get_string("function_id") # Get ID for logging early
            logger.debug(f"===== DDS TRACE: handle_capability_advertisement received data for function_id: {function_id_str} =====")

            # Check if instance state is ALIVE before processing
            if info.state.instance_state != dds.InstanceState.ALIVE:
                logger.debug(f"Ignoring non-alive capability sample: {info.state.instance_state}")
                return
            
            # Extract required fields
            function_id = capability["function_id"]
            name = capability["name"]
            provider_id = capability["provider_id"]
            description = capability.get_string("description") # Use get_string for safety
            schema_str = capability.get_string("parameter_schema") # Use get_string for safety
            capabilities_str = capability.get_string("capabilities") # Use get_string for safety
            service_name = capability.get_string("service_name") # Get service name
            
            # Basic validation
            if not all([function_id, name, provider_id]):
                logger.warning(f"Received capability advertisement with missing required fields")
                return

            # Deserialize JSON strings safely
            schema = json.loads(schema_str) if schema_str else {}
            capabilities = json.loads(capabilities_str) if capabilities_str else []
            
            # Store or update the discovered function
            # Use a dictionary to store structured info
            self.discovered_functions[function_id] = {
                "name": name,
                "description": description,
                "provider_id": provider_id,
                "schema": schema,
                "capabilities": capabilities,
                "service_name": service_name, # Store service name
                "capability": capability # Store the raw capability object for potential future use
            }
            
            logger.info(f"Updated/Added discovered function: {name} ({function_id}) from provider {provider_id} for service {service_name}")
            
            # Signal that at least one function has been discovered
            if not self._discovery_event.is_set():
                logger.debug(f"===== DDS TRACE: Setting _discovery_event for function_id: {function_id} =====")
                self._discovery_event.set()
                logger.debug("===== DDS TRACE: Discovery event set (first function discovered). =====")
            else:
                logger.debug(f"===== DDS TRACE: _discovery_event already set (function_id: {function_id}). =====")

            # Call discovery callbacks
            for callback in self.discovery_callbacks:
                callback(function_id, self.discovered_functions[function_id])

        except KeyError as e:
            logger.error(f"===== DDS TRACE: Missing key in capability data (function_id: {function_id_str}): {e} ====")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON in capability data: {e}")
        except Exception as e: # Add a general except block for the try
            logger.error(f"Error handling capability advertisement for function_id {function_id_str}: {e}")
            logger.error(logging.traceback.format_exc())
    
    def handle_capability_removal(self, reader: dds.DynamicData.DataReader):
        """Handle removal of function capabilities when a provider goes offline"""
        try:
            samples = reader.take()
            for data, info in samples:
                if data and info.state.instance_state != dds.InstanceState.ALIVE:
                    function_id = data['function_id']
                    if function_id in self.discovered_functions:
                        function_info = self.discovered_functions[function_id]
                        
                        # Build metadata for service base
                        metadata = {
                            "function_id": function_id,
                            "function_name": function_info['name'],
                            "provider_id": function_info['provider_id']
                        }
                        
                        # Notify EnhancedServiceBase about the removal
                        if self.service_base is not None:
                            self.service_base.handle_function_removal(
                                function_name=function_info['name'],
                                metadata=metadata
                            )
                        
                        logger.info(f"Removing function {function_id} due to provider going offline")
                        del self.discovered_functions[function_id]
        except Exception as e:
            logger.error(f"Error handling capability removal: {e}")
    
    def get_function_by_id(self, function_id: str) -> Optional[FunctionInfo]:
        """
        Get function by ID.
        
        Args:
            function_id: ID of function to retrieve
            
        Returns:
            FunctionInfo if found, None otherwise
        """
        return self.functions.get(function_id)
    
    def get_function_by_name(self, name: str) -> Optional[FunctionInfo]:
        """
        Get a function by its name.
        
        Args:
            name: The name of the function to retrieve
            
        Returns:
            The FunctionInfo object if found, None otherwise
        """
        function_id = self.function_by_name.get(name)
        if function_id:
            return self.functions.get(function_id)
        return None
    
    def get_all_discovered_functions(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns a shallow copy of the currently discovered functions on the network.
        The dictionary maps function_id to its details.
        """
        return dict(self.discovered_functions)

    def remove_discovered_function(self, function_id: str):
        """
        Removes a function from the discovered_functions cache.
        Typically called when a function provider is no longer available.
        """
        if function_id in self.discovered_functions:
            removed_function_name = self.discovered_functions[function_id].get("name", "unknown_function")
            del self.discovered_functions[function_id]
            logger.debug(f"===== DDS TRACE: Removed function {removed_function_name} ({function_id}) from discovered functions cache. =====")
        else:
            logger.warning(f"===== DDS TRACE: Attempted to remove non-existent function ID {function_id} from cache. =====")

    def close(self):
        """Clean up resources"""
        print("===== PRINT TRACE: FunctionRegistry.close() ENTERED =====", flush=True) # ADDED FOR DEBUGGING
        logger.debug("===== DDS TRACE: FunctionRegistry.close() ENTERED LOGGER =====") # ADDED FOR DEBUGGING

        if hasattr(self, '_closed') and self._closed:
            logger.debug("FunctionRegistry already closed.")
            return

        logger.debug("Closing FunctionRegistry and its resources")
        try:
            # Detach and delete StatusCondition and WaitSet first
            logger.debug("===== DDS TRACE: FunctionRegistry.close() - WaitSet/StatusCondition cleanup START ====")
            if hasattr(self, 'status_condition') and self.status_condition:
                logger.debug("===== DDS TRACE: FunctionRegistry.close() - 'status_condition' attribute exists. Disabling... =====")
                try:
                    self.status_condition.enabled_statuses = dds.StatusMask.NONE
                    logger.debug("===== DDS TRACE: FunctionRegistry.close() - status_condition.enabled_statuses set to NONE. =====")
                except Exception as sc_disable_ex:
                    logger.error(f"===== DDS TRACE: FunctionRegistry.close() - EXCEPTION during status_condition disable: {sc_disable_ex} =====")

            if hasattr(self, 'waitset') and self.waitset:
                logger.debug("===== DDS TRACE: FunctionRegistry.close() - 'waitset' attribute exists. =====")
                if hasattr(self, 'status_condition') and self.status_condition: # Check again as it might have been set to None
                    is_attached_before = self.status_condition.is_attached
                    logger.debug(f"===== DDS TRACE: FunctionRegistry.close() - StatusCondition.is_attached BEFORE detach: {is_attached_before} =====")
                    if is_attached_before:
                        try:
                            self.waitset.detach(self.status_condition)
                            logger.debug("===== DDS TRACE: FunctionRegistry.close() - waitset.detach(status_condition) CALLED. =====")
                            is_attached_after = self.status_condition.is_attached 
                            logger.debug(f"===== DDS TRACE: FunctionRegistry.close() - StatusCondition.is_attached AFTER detach: {is_attached_after} =====")
                        except Exception as detach_ex:
                            logger.error(f"===== DDS TRACE: FunctionRegistry.close() - EXCEPTION during waitset.detach(): {detach_ex} =====")
                    else:
                        logger.debug("===== DDS TRACE: FunctionRegistry.close() - StatusCondition was NOT attached, skipping detach. =====")
                else:
                    logger.debug("===== DDS TRACE: FunctionRegistry.close() - 'status_condition' is None or does not exist when trying to detach from waitset. =====")
                self.waitset = None # Allow garbage collection
                logger.debug("===== DDS TRACE: FunctionRegistry.close() - self.waitset set to None. =====")
            else:
                logger.debug("===== DDS TRACE: FunctionRegistry.close() - 'waitset' attribute does NOT exist. =====")
            
            if hasattr(self, 'status_condition') and self.status_condition: # Ensure it's nulled if not already
                self.status_condition = None # Allow garbage collection
                logger.debug("===== DDS TRACE: FunctionRegistry.close() - self.status_condition set to None (final check). =====")

            logger.debug("===== DDS TRACE: FunctionRegistry.close() - WaitSet/StatusCondition cleanup END ====")

            # Close DDS entities
            if hasattr(self, 'execution_client') and self.execution_client:
                self.execution_client.close()
            if hasattr(self, 'capability_reader') and self.capability_reader:
                self.capability_reader.close()
            
            # capability_writer and capability_topic are always created (or should be)
            if hasattr(self, 'capability_writer') and self.capability_writer:
                self.capability_writer.close()
            if hasattr(self, 'capability_topic') and self.capability_topic: # Topic is found or created
                self.capability_topic.close()

            if hasattr(self, 'subscriber') and self.subscriber:
                self.subscriber.close()
            
            # Publisher is always created
            if hasattr(self, 'publisher') and self.publisher:
                self.publisher.close()
            
            # Clear references
            self.capability_writer = None
            self.capability_reader = None
            self.capability_topic = None
            self.subscriber = None
            self.publisher = None
            self.execution_client = None

            logger.debug("===== DDS TRACE: FunctionRegistry.close() - DDS entities closed. =====")
        except Exception as e:
            logger.error(f"===== DDS TRACE: Error closing FunctionRegistry: {e} =====")
            logger.error(traceback.format_exc())

        logger.debug("===== DDS TRACE: FunctionRegistry.close() - Cleanup completed. =====")
        self._closed = True

    def add_discovery_callback(self, callback):
        """
        Add a callback function to be called when functions are discovered.
        
        Args:
            callback: Function to call with (function_id, function_info) when a function is discovered
        """
        self.discovery_callbacks.append(callback)
        logger.debug(f"Added discovery callback: {callback}")
    
    def remove_discovery_callback(self, callback):
        """
        Remove a discovery callback.
        
        Args:
            callback: Function to remove from callbacks
        """
        if callback in self.discovery_callbacks:
            self.discovery_callbacks.remove(callback)
            logger.debug(f"Removed discovery callback: {callback}")

class FunctionCapabilityListener(dds.DynamicData.NoOpDataReaderListener):
    """Listener for function capability advertisements"""

    def __init__(self, registry):
        """Initialize listener with a reference to the registry"""
        super().__init__()
        self.registry = registry
        logger.debug("FunctionCapabilityListener initialized")

    def on_subscription_matched(self, reader, info):
        """Handle subscription matches"""
        logger.debug(f"Capability subscription matched: {info.current_count} total writers")
        # Optionally, trigger an initial check or event if needed
        # maybe set the discovery event here if count > 0?
        # if info.current_count > 0 and not self.registry._discovery_event.is_set():
        #     self.registry._discovery_event.set()
        #     logger.info("Discovery event set via on_subscription_matched.")

    def on_data_available(self, reader):
        """Handle incoming capability data"""
        logger.debug("===== DDS TRACE: FunctionCapabilityListener.on_data_available entered =====")
        try:
            samples = reader.read() # Take all available samples
            logger.debug(f"===== DDS TRACE: Read {len(samples)} FunctionCapability samples =====")
            # Print sample details for debugging
            for sample, info in samples:
                logger.debug("===== DDS TRACE: Sample details =====")
                logger.debug(f"Sample data: {sample}")
                logger.debug(f"Sample info: {info}")
                logger.debug(f"Sample state: {info.state.sample_state}")
                logger.debug(f"Instance state: {info.state.instance_state}")
                logger.debug("===== DDS TRACE: End sample details =====")
            for capability_data, info in samples:
                # Check if the sample contains valid data that hasn't been read before
                if info.state.sample_state == dds.SampleState.NOT_READ: # FIX: Check for NOT_READ
                    # This sample contains valid data for a new or updated function
                    log_fid = "N/A"
                    if capability_data:
                        try:
                             log_fid = capability_data.get_string("function_id") or "ID_NOT_IN_DATA"
                        except Exception:
                             log_fid = "ERROR_GETTING_ID"
                    logger.debug(f"===== DDS TRACE: Processing READ sample - FuncID: {log_fid} =====")
                    # Re-log state for this specific case
                    logger.debug(f"===== DDS TRACE:   SampleState: {str(info.state.sample_state)}, InstanceState: {str(info.state.instance_state)} =====")

                    # Process the valid data
                    self.registry.handle_capability_advertisement(capability_data, info)

                # Separately check if the instance associated with the sample is no longer alive
                # This handles cases where the sample itself might not be marked as READ anymore,
                # but we still need to know the instance was disposed or unregistered.
                if info.state.instance_state != dds.InstanceState.ALIVE:
                    log_fid = "N/A"
                    key_holder = dds.DynamicData(self.registry.capability_type)
                    try:
                        reader.get_key_value(key_holder, info.instance_handle)
                        log_fid = key_holder.get_string("function_id") or "ID_NOT_IN_DATA"
                    except Exception:
                        log_fid = "ERROR_GETTING_ID"

                    logger.debug(f"===== DDS TRACE: Processing Non-ALIVE sample - FuncID: {log_fid} =====")
                    # Re-log state for this specific case
                    logger.debug(f"===== DDS TRACE:   SampleState: {str(info.state.sample_state)}, InstanceState: {str(info.state.instance_state)} =====")

                    # Process the removal
                    try:
                        # Attempt to get the key value from the instance handle
                        # reader.get_key_value(key_holder, info.instance_handle) # Already done above for logging
                        function_id_to_remove = log_fid if log_fid not in ["N/A", "ID_NOT_IN_DATA", "ERROR_GETTING_ID"] else None

                        if function_id_to_remove:
                            logger.debug(f"===== DDS TRACE: Instance for function ID {function_id_to_remove} no longer alive (state: {info.state.instance_state}). Attempting removal from registry. =====")
                            # Check if already removed to avoid redundant logging
                            if function_id_to_remove in self.registry.discovered_functions:
                                self.registry.remove_discovered_function(function_id_to_remove)
                            # else: # Optionally log if already removed
                            #    logger.debug(f"===== DDS TRACE: Function ID {function_id_to_remove} already removed (instance state: {info.state.instance_state}). =====")
                        else:
                            # This case should be rare if function_id is indeed the key
                            logger.warning(f"===== DDS TRACE: Could not retrieve function_id (key) for disposed/unregistered instance handle {info.instance_handle}. Cannot remove. =====")
                    except dds.Error as e: # Catch specific DDS errors
                        logger.error(f"===== DDS TRACE: DDS Error getting key for disposed/unregistered instance handle {info.instance_handle}: {e} =====")
                    except Exception as e: # Catch other unexpected errors
                        logger.error(f"===== DDS TRACE: Unexpected error getting key/removing for instance handle {info.instance_handle}: {e} =====")
                # else:
                    # Potentially other states, e.g. sample_state != READ and instance_state == ALIVE.
                    # logger.debug(f"===== DDS TRACE: Ignoring sample with info.state.sample_state={info.state.sample_state} and info.instance_state={info.instance_state} =====")

            logger.debug("===== DDS TRACE: Finished processing FunctionCapability samples in on_data_available =====")
        except dds.Error as e: # Catch DDS errors from reader.take()
            logger.error(f"DDS Error in on_data_available (e.g., during take()): {e}")
            logger.error(logging.traceback.format_exc())
        except Exception as e: # Catch other unexpected errors
            logger.error(f"Unexpected error in on_data_available: {e}")
            logger.error(logging.traceback.format_exc())