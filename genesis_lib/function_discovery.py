"""
Function Discovery - Distributed Capability Advertisement and Matching

This module provides the core discovery and registration system for Genesis services.
It integrates with DDS via a unified `GenesisAdvertisement` topic and DDS RPC to:
- Register local functions and advertise their capabilities
- Discover remote functions provided by other services
- Match user requests to available functions (LLM-assisted with fallback)

=================================================================================================
ARCHITECTURE OVERVIEW
=================================================================================================

Components:
- FunctionRegistry: Registers local functions, advertises them to DDS, discovers remote ones,
  and exposes query utilities. Owns the DDS entities (publisher, subscriber, readers).
- FunctionMatcher: Classifies/matches functions against user requests (LLM or fallback).
- GenesisAdvertisementListener: Handles unified advertisements delivered via a content-filtered
  topic for FUNCTION-kind ads.

Data Model (Advertisement payload JSON):
- parameter_schema: JSON Schema of the function parameters
- capabilities: List[str] tags describing the function and service
- performance_metrics: Dict[str, Any]
- security_requirements: Dict[str, Any]
- classification: Dict[str, Any] (optional metadata)

=================================================================================================
WHAT YOU GET
=================================================================================================
- Distributed discovery out-of-the-box using TRANSIENT_LOCAL durability
- Content-filtered topic to receive only FUNCTION advertisements
- Registry API to register, discover, and match functions
- Structured logging for discover/advertise/match lifecycle

=================================================================================================
DATA FLOW
=================================================================================================
1) register_function() → publishes `GenesisAdvertisement(kind=FUNCTION)` with payload
2) other registries receive via content-filtered reader → handle_advertisement()
3) get_all_discovered_functions() reads current ALIVE instances from DDS (no side cache)
4) find_matching_functions() (registry) → delegates to FunctionMatcher

=================================================================================================
ERROR HANDLING POLICY
=================================================================================================
All external operations are guarded and logged. Business-logic errors use INFO; unexpected
exceptions use ERROR. Silent failures are considered bugs, and defensive checks are employed.

=================================================================================================
KNOWN LIMITATIONS
=================================================================================================
- The system can become recursive if discovery and consumption are deeply intertwined.
  Future work: decouple provider/consumer roles and add explicit discovery scoping.

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
from genesis_lib.advertisement_bus import AdvertisementBus
import asyncio
import sys
import traceback

logger = logging.getLogger("genesis_lib.function_discovery")

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


@dataclass
class AdvertisementPayload:
    """Structured payload for `GenesisAdvertisement(kind=FUNCTION)`.

    Fields:
        parameter_schema: JSON schema for function parameters
        capabilities: List of capability tags
        performance_metrics: Arbitrary perf metrics
        security_requirements: Arbitrary security metadata
        classification: Optional classification metadata

    Methods:
        to_json(): JSON string of the payload suitable for DDS DynamicData field
    """
    parameter_schema: Dict[str, Any]
    capabilities: List[str]
    performance_metrics: Dict[str, Any]
    security_requirements: Dict[str, Any]
    classification: Dict[str, Any]

    def to_json(self) -> str:
        return json.dumps({
            "parameter_schema": self.parameter_schema,
            "capabilities": self.capabilities,
            "performance_metrics": self.performance_metrics,
            "security_requirements": self.security_requirements,
            "classification": self.classification,
        })

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
    
    # Removed unused helpers: _prepare_function_descriptions, _convert_matches_to_metadata
    
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
        # Possible improvement: Consider requiring callers to pass a non-None DomainParticipant
        # rather than creating one here. This avoids per-node participant creation and makes
        # ownership/lifecycle explicit. Keeping current behavior for back-compat and tests.
        logger.debug("Initializing FunctionRegistry")
        
        # Store configuration
        self.domain_id = domain_id
        self.enable_discovery_listener = enable_discovery_listener
        
        # Initialize storage
        self.functions = {}  # function_id -> FunctionInfo
        self.function_by_name = {}  # name -> function_id
        # Note: discovered_functions cache removed - now reading directly from DDS via get_all_discovered_functions()
        self.service_base = None  # Reference to service base for callbacks
        
        # Add callback mechanism for function discovery
        self.discovery_callbacks = []  # List of callback functions to call when functions are discovered
        
        # Event to signal when the first function capability has been discovered
        # Initialize this EARLY so it's available during historical sample processing
        self._discovery_event = asyncio.Event()
        
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
        # FunctionCapability topic removed - now using unified Advertisement topic
        # Unified advertisement type
        try:
            self.advertisement_type = self.type_provider.type("genesis_lib", "GenesisAdvertisement")
        except Exception:
            self.advertisement_type = None
            logger.error("Failed to load GenesisAdvertisement type - discovery will not work!")
        
        # FunctionCapability topic removed - using unified Advertisement topic instead
        
        # Unified advertisement writer via shared bus (replaces capability_writer)
        self.advertisement_topic = None
        self.advertisement_writer = None
        if self.advertisement_type is not None:
            try:
                bus = AdvertisementBus.get(self.participant)
                self.advertisement_topic = bus.topic
                self.advertisement_writer = bus.writer
            except Exception as e:
                logger.warning(f"Unified advertisement writer setup skipped: {e}")

        if self.enable_discovery_listener:
            # Create subscriber
            self.subscriber = dds.Subscriber(self.participant)

            # Get types for execution (only if discovery is enabled)
            self.execution_request_type = self.type_provider.type("genesis_lib", "FunctionExecutionRequest")
            self.execution_reply_type = self.type_provider.type("genesis_lib", "FunctionExecutionReply")

            # Create DataReader(s) for discovery
            # QoS sourced from XML profiles (no inline overrides)

            # Phase 3b: prefer unified advertisement; do not create legacy FunctionCapability reader
            self.capability_listener = None
            self.capability_reader = None

            # Unified advertisement reader
            self.advertisement_reader = None
            if self.advertisement_type is not None and self.advertisement_topic is not None:
                try:
                    self.advertisement_listener = GenesisAdvertisementListener(self)
                    
                    # Create content-filtered topic to only receive FUNCTION advertisements (kind=0)
                    # This filters at DDS layer - much more efficient than in-code filtering!
                    logger.debug("🔍 FunctionRegistry: Creating content-filtered topic for FUNCTION advertisements...")
                    filtered_topic = dds.DynamicData.ContentFilteredTopic(
                        self.advertisement_topic,
                        "FunctionAdvertisementFilter",
                        dds.Filter("kind = %0", ["0"])  # FUNCTION kind enum value
                    )
                    
                    # CRITICAL: Use the same XML QoS profile as the AdvertisementBus writer
                    # Try default provider first, then explicit USER_QOS_PROFILES.xml fallback
                    try:
                        ad_reader_qos = dds.QosProvider.default.datareader_qos_from_profile("cft_Library::cft_Profile")
                    except Exception:
                        import os as _os
                        _config_dir = _os.path.dirname(get_datamodel_path())
                        _user_qos_path = _os.path.join(_config_dir, "USER_QOS_PROFILES.xml")
                        _qos_provider = dds.QosProvider(_user_qos_path)
                        ad_reader_qos = _qos_provider.datareader_qos_from_profile("cft_Library::cft_Profile")
                    
                    self.advertisement_reader = dds.DynamicData.DataReader(
                        cft=filtered_topic,  # Use content-filtered topic instead of base topic
                        qos=ad_reader_qos,
                        listener=self.advertisement_listener,
                        subscriber=self.subscriber,
                        mask=dds.StatusMask.DATA_AVAILABLE,
                    )
                    logger.info(f"FunctionRegistry: Created Advertisement reader with matching QoS")
                    print(f"📚 PRINT: FunctionRegistry about to retrieve historical advertisements...", flush=True)
                    
                    # CRITICAL: For TRANSIENT_LOCAL, retrieve historical data without sleeps
                    # Use a WaitSet + ReadCondition to wait for available samples
                    try:
                        data_state = dds.DataState(
                            sample_state=dds.SampleState.ANY,
                            view_state=dds.ViewState.ANY,
                            instance_state=dds.InstanceState.ALIVE,
                        )
                        read_condition = dds.ReadCondition(self.advertisement_reader, data_state)
                        waitset = dds.WaitSet()
                        try:
                            waitset.attach_condition(read_condition)
                        except AttributeError:
                            # Fallback for API variants
                            waitset.attach(read_condition)
                        print(f"📚 PRINT: Waiting for historical FUNCTION advertisements...", flush=True)
                        try:
                            waitset.wait(dds.Duration.from_seconds(1))
                        except dds.TimeoutError:
                            # It's okay if no historical samples are available within the window
                            pass
                        print(f"📚 PRINT: Calling read() on advertisement_reader...", flush=True)
                        historical_samples = self.advertisement_reader.read()
                        print(f"📚 PRINT: Retrieved {len(historical_samples)} historical advertisement samples", flush=True)
                        logger.info(f"📚 FunctionRegistry: Retrieved {len(historical_samples)} historical advertisement samples")
                        for ad_data, info in historical_samples:
                            if info.state.instance_state == dds.InstanceState.ALIVE:
                                print(f"📚 PRINT: Processing historical FUNCTION advertisement...", flush=True)
                                logger.info(f"📚 Processing historical FUNCTION advertisement...")
                                self.handle_advertisement(ad_data, info)
                        print(f"📚 PRINT: Finished processing historical advertisements", flush=True)
                    except Exception as hist_err:
                        print(f"📚 PRINT: ERROR retrieving historical advertisements: {hist_err}", flush=True)
                        logger.warning(f"Could not retrieve historical advertisements: {hist_err}")
                        logger.warning(traceback.format_exc())
                    finally:
                        try:
                            try:
                                waitset.detach_condition(read_condition)
                            except AttributeError:
                                waitset.detach(read_condition)
                        except Exception:
                            pass
                except Exception as e:
                    logger.error(f"Unified advertisement reader setup FAILED: {e}")
                    logger.error(traceback.format_exc())
            
            # Create RPC client for function execution
            # Create function execution client using unified RPC v2 naming
            self.execution_client = rpc.Requester(
                request_type=self.execution_request_type,
                reply_type=self.execution_reply_type,
                participant=self.participant,
                service_name="rti/connext/genesis/rpc/FunctionExecution"
            )
        else:
            # Rationale: Allow constructing a registry without a discovery listener in
            # narrowly scoped scenarios where discovery is not required or is owned
            # elsewhere. Examples include:
            #  - Offline/unit tests that exercise schema/matching without DDS I/O
            #  - Provider-only flows where a higher layer owns DDS readers/subscriber
            #  - Benchmarks or minimal-footprint runs that don't consume remote ads
            #
            # In production, discovery should typically be enabled. This flag exists
            # to support the above cases and to avoid duplicate DDS entities when a
            # caller injects a preconfigured participant/subscriber.
            self.subscriber = None
            self.capability_reader = None
            self.capability_listener = None
            self.advertisement_reader = None
            self.execution_client = None
            logger.info("FunctionRegistry initialized with discovery listener DISABLED.")
        
        # Initialize function matcher with LLM support
        self.matcher = FunctionMatcher()
        
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
            user_request: Natural-language request
            min_similarity: Minimum similarity score (0-1)

        Returns:
            List[FunctionInfo] annotated with `match_info` per item, where
            match_info has the shape:
            {
              "relevance_score": float,
              "explanation": str,
              "inferred_params": Dict[str, Any],
              "considerations": List[str],
              "domain": str,
              "operation_type": str
            }
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
        """Advertise function capability via unified Advertisement topic"""
        logger.debug(f"===== DDS TRACE: Preparing DDS data for advertising function: {function_info.name} ({function_info.function_id}) =====")
        
        # Determine service name
        if self.service_base and hasattr(self.service_base, 'service_name'):
            service_name = self.service_base.service_name
        else:
            logger.warning(f"Could not determine service_name when advertising function {function_info.name}")
            service_name = "UnknownService"
        
        # Publish to unified Advertisement topic (FUNCTION kind)
        if self.advertisement_writer is not None and self.advertisement_type is not None:
            try:
                ad = dds.DynamicData(self.advertisement_type)
                ad["advertisement_id"] = function_info.function_id
                # AdvertisementKind order: FUNCTION=0, AGENT=1, REGISTRATION=2
                ad["kind"] = 0
                ad["name"] = function_info.name
                ad["description"] = function_info.description
                ad["provider_id"] = str(self.advertisement_writer.instance_handle)
                ad["service_name"] = service_name
                ad["last_seen"] = int(time.time() * 1000)
                payload_obj = AdvertisementPayload(
                    parameter_schema=function_info.schema,
                    capabilities=list(function_info.categories or []),
                    performance_metrics=dict(function_info.performance_metrics or {}),
                    security_requirements=dict(function_info.security_requirements or {}),
                    classification=dict(function_info.classification or {}),
                )
                ad["payload"] = payload_obj.to_json()
                self.advertisement_writer.write(ad)
                self.advertisement_writer.flush()
                logger.debug(f"===== DDS TRACE: Published GenesisAdvertisement(kind=FUNCTION) for {function_info.name} =====")
            except Exception as e:
                logger.error(f"===== DDS TRACE: Error publishing GenesisAdvertisement for {function_info.name}: {e} =====", exc_info=True)
        else:
            logger.error(f"Cannot advertise function {function_info.name} - Advertisement writer not available!")
    
    # handle_capability_advertisement() removed - now using handle_advertisement() for unified discovery

    def handle_advertisement(self, ad: dds.DynamicData, info: dds.SampleInfo):
        """Handle received GenesisAdvertisement for FUNCTION kind.

        Builds a transient function_info dict with the shape:
        {
          "name": str,
          "description": str,
          "provider_id": str,
          "schema": Dict[str, Any],
          "capabilities": List[str],
          "service_name": str,
          "capability": {"service_name": str},
          "advertisement": DynamicData
        }
        and invokes discovery callbacks with (function_id, function_info).
        """
        try:
            # Content filter ensures only FUNCTION ads are delivered - no in-code filtering needed
            function_id = ad.get_string("advertisement_id") or ""
            name = ad.get_string("name") or ""
            description = ad.get_string("description") or ""
            provider_id = ad.get_string("provider_id") or ""
            service_name = ad.get_string("service_name") or "UnknownService"
            payload_str = ad.get_string("payload") or "{}"
            try:
                payload = json.loads(payload_str) if payload_str else {}
            except Exception:
                payload = {}
            schema = payload.get("parameter_schema") or {}
            capabilities = payload.get("capabilities") or []
            if isinstance(capabilities, str):
                try:
                    capabilities = json.loads(capabilities) or []
                except Exception:
                    capabilities = [capabilities]

            if not function_id or not name or not provider_id:
                return

            # Build function info for callbacks (no longer caching in memory)
            function_info = {
                "name": name,
                "description": description,
                "provider_id": provider_id,
                "schema": schema,
                "capabilities": capabilities,
                "service_name": service_name,
                "capability": {"service_name": service_name},
                "advertisement": ad,
            }

            # Use same log format as legacy path for test compatibility
            # Also print to ensure test scripts can detect discovery even if logging is misconfigured
            print(f"📚 PRINT: Updated/Added discovered function: {name}", flush=True)
            logger.info(f"Updated/Added discovered function: {name} ({function_id}) from provider {provider_id} for service {service_name}")
            
            # Signal that first discovery has occurred
            if not self._discovery_event.is_set():
                self._discovery_event.set()
            
            # Invoke callbacks with function info (callbacks can query DDS if they need persistent access)
            for callback in self.discovery_callbacks:
                callback(function_id, function_info)
        except Exception as e:
            logger.error(f"Error handling GenesisAdvertisement: {e}")
    
    def handle_capability_removal(self, reader: dds.DynamicData.DataReader):
        """DEPRECATED: Legacy FunctionCapability path.

        This method is kept for backward compatibility. Unified advertisements are the
        preferred mechanism. If invoked, it logs a warning and attempts to notify service_base.
        """
        try:
            logger.warning("handle_capability_removal called on unified advertisement path (deprecated)")
            samples = reader.take()
            for data, info in samples:
                if data and info.state.instance_state != dds.InstanceState.ALIVE:
                    function_id = data['function_id']
                    
                    # Read current DDS state to get function info for notification
                    # DDS automatically handles disposal - we just need to notify service_base
                    function_name = data.get('name', 'unknown_function') if hasattr(data, 'get') else 'unknown_function'
                    provider_id = data.get('provider_id', 'unknown_provider') if hasattr(data, 'get') else 'unknown_provider'
                    
                    # Build metadata for service base
                    metadata = {
                        "function_id": function_id,
                        "function_name": function_name,
                        "provider_id": provider_id
                    }
                    
                    # Notify the service base about the removal
                    if self.service_base is not None:
                        self.service_base.handle_function_removal(
                            function_name=function_name,
                            metadata=metadata
                        )
                    
                    logger.info(f"Function {function_id} removed (provider went offline) - DDS handles disposal automatically")
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
        Read ALIVE function advertisements directly from DDS and return a mapping.

        Returns:
            Dict[str, Dict[str, Any]] where the key is `function_id` and the value has shape:
            {
              "name": str,
              "description": str,
              "provider_id": str,
              "schema": Dict[str, Any],
              "capabilities": List[str],
              "service_name": str,
              "capability": {"service_name": str},
              "advertisement": DynamicData
            }

        Example minimal structure:
            {
              "<uuid>": {
                "name": "add",
                "description": "Add two numbers",
                "provider_id": "<writer handle>",
                "schema": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}},
                "capabilities": ["math", "calculator"],
                "service_name": "CalculatorService",
                "capability": {"service_name": "CalculatorService"},
                "advertisement": <DynamicData>
              }
            }

        Notes:
            - No additional in-memory cache is maintained; DDS is the source of truth.
        """
        if not self.enable_discovery_listener or self.advertisement_reader is None:
            return {}
        
        result = {}
        try:
            samples = self.advertisement_reader.read()
            for ad, info in samples:
                # Only include ALIVE instances (exclude disposed/offline)
                if info.state.instance_state != dds.InstanceState.ALIVE:
                    continue
                
                # Parse advertisement
                function_id = ad.get_string("advertisement_id") or ""
                name = ad.get_string("name") or ""
                description = ad.get_string("description") or ""
                provider_id = ad.get_string("provider_id") or ""
                service_name = ad.get_string("service_name") or "UnknownService"
                payload_str = ad.get_string("payload") or "{}"
                
                try:
                    payload = json.loads(payload_str) if payload_str else {}
                except Exception:
                    payload = {}
                
                schema = payload.get("parameter_schema") or {}
                capabilities = payload.get("capabilities") or []
                if isinstance(capabilities, str):
                    try:
                        capabilities = json.loads(capabilities) or []
                    except Exception:
                        capabilities = [capabilities]
                
                if not function_id or not name or not provider_id:
                    continue
                
                result[function_id] = {
                    "name": name,
                    "description": description,
                    "provider_id": provider_id,
                    "schema": schema,
                    "capabilities": capabilities,
                    "service_name": service_name,
                    "capability": {"service_name": service_name},
                    "advertisement": ad,
                }
        except Exception as e:
            logger.error(f"Error reading discovered functions from DDS: {e}")
            logger.error(traceback.format_exc())
            return {}
        
        return result

    def close(self):
        """Clean up resources"""
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
            if hasattr(self, 'advertisement_reader') and self.advertisement_reader:
                try:
                    self.advertisement_reader.close()
                except Exception:
                    pass
            
            # capability_writer and capability_topic are always created (or should be)
            if hasattr(self, 'capability_writer') and self.capability_writer:
                self.capability_writer.close()
            if hasattr(self, 'capability_topic') and self.capability_topic: # Topic is found or created
                self.capability_topic.close()
            # Do not close shared advertisement writer/topic (owned by bus)

            if hasattr(self, 'subscriber') and self.subscriber:
                self.subscriber.close()
            
            # Publisher is always created
            if hasattr(self, 'publisher') and self.publisher:
                self.publisher.close()
            
            # Clear references
            self.capability_writer = None
            self.capability_reader = None
            self.capability_topic = None
            self.advertisement_writer = None
            self.advertisement_reader = None
            self.advertisement_topic = None
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

# FunctionCapabilityListener removed - now using GenesisAdvertisementListener for unified discovery

class GenesisAdvertisementListener(dds.DynamicData.NoOpDataReaderListener):
    """Listener for unified GenesisAdvertisement (FUNCTION)"""
    def __init__(self, registry):
        super().__init__()
        self.registry = registry
        logger.debug("GenesisAdvertisementListener initialized")

    def on_data_available(self, reader):
        try:
            logger.info("🔔 GenesisAdvertisementListener.on_data_available() CALLED!")
            samples = reader.read()
            logger.info(f"📊 GenesisAdvertisementListener got {len(samples)} advertisement samples")
            for ad_data, info in samples:
                if info.state.sample_state == dds.SampleState.NOT_READ and info.state.instance_state == dds.InstanceState.ALIVE:
                    logger.info(f"📨 Processing FUNCTION advertisement...")
                    self.registry.handle_advertisement(ad_data, info)
        except Exception as e:
            logger.error(f"Error in GenesisAdvertisementListener.on_data_available: {e}")
            logger.error(traceback.format_exc())
