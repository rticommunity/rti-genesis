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
Genesis Service Base Class

This module provides the core base class for all services in the Genesis framework,
implementing automatic function discovery, registration, and lifecycle management.
This is the base layer WITHOUT monitoring - monitoring is added by MonitoredService.

Architecture:
    GenesisReplier (RPC handling)
      ↓ inherits
    GenesisService (THIS FILE - core functionality, NO monitoring)
      ↓ inherits
    MonitoredService (adds monitoring decorator layer)
      ↓ inherits
    UserService (e.g., CalculatorService)

"""

import logging
import asyncio
import json
from typing import Dict, Any, List, Optional, Callable
from genesis_lib.replier import GenesisReplier
from genesis_lib.function_discovery import InternalFunctionRegistry

logger = logging.getLogger("genesis_service")

class GenesisService(GenesisReplier):
    """
    Base class for Genesis services with core functionality (no monitoring).
    
    Provides:
    - Function registration and auto-discovery
    - Function management and execution
    - DDS advertisement via FunctionRegistry
    - Service lifecycle management
    
    Does NOT provide:
    - Monitoring/observability (added by MonitoredService)
    - Graph topology publishing (added by MonitoredService)
    """

    def __init__(self, service_name: str, capabilities: List[str], participant=None, domain_id=0, registry: InternalFunctionRegistry = None):
        """
        Initialize the Genesis service.
        
        Args:
            service_name: Name of the service (e.g., "CalculatorService")
            capabilities: List of capability tags (e.g., ["calculator", "math"])
            participant: Optional DDS participant (if None, one will be created)
            domain_id: DDS domain ID (default: 0)
            registry: Optional InternalFunctionRegistry instance (if None, one will be created)
        """
        # Create participant FIRST if needed, before calling super().__init__
        if participant is None:
            import rti.connextdds as dds
            # Transport configuration (UDPv4) is set in USER_QOS_PROFILES.xml
            # UDPv4 is the default for Genesis distributed systems; users can modify the XML
            # to use shared memory (SHMEM) or other transports for single-host deployments.
            participant = dds.DomainParticipant(domain_id)
        
        # Now call parent __init__ with the participant and service_type
        # V2 uses 'service_type' parameter instead of 'service_name'
        super().__init__(service_type=service_name, participant=participant)
        
        self.service_name = service_name
        self.participant = participant
        self.domain_id = domain_id
        self.service_capabilities = capabilities
        self._functions_advertised = False
        # Track advertised functions for reference
        self._advertised_function_ids: Dict[str, str] = {}
        self._call_ids = {}
        self.logger = logging.getLogger("genesis_service")
        
        # Local registry for this service's own functions (discovery disabled; DDS handles discovery)
        self.registry = registry if registry is not None else InternalFunctionRegistry(
            participant=self.participant,
            domain_id=domain_id,
            enable_discovery_listener=False
        )
        self.registry.service_base = self
        
        # Get GUID from Advertisement writer
        # The InternalFunctionRegistry owns the DDS Advertisement writer and advertises this service's functions.
        # Use the writer's instance_handle as the app GUID so advertisements and monitoring share a stable provider_id.
        # Fallback to participant handle if the writer is not available.
        self.app_guid = str(self.registry.advertisement_writer.instance_handle) if self.registry.advertisement_writer else str(self.participant.instance_handle)

        # Auto-register decorated functions
        self._auto_register_decorated_functions()

    def _auto_register_decorated_functions(self):
        """
        Automatically find and register methods decorated with @genesis_function.
        
        Scans the service instance for methods with __genesis_meta__ attribute
        and registers them as callable functions.
        """
        for attr in dir(self):
            fn = getattr(self, attr)
            meta = getattr(fn, "__genesis_meta__", None)
            if not meta:
                continue
            if fn.__name__ in self.functions:
                continue
            self.register_enhanced_function(
                fn,
                meta["description"],
                meta["parameters"],
                operation_type=meta.get("operation_type"),
                common_patterns=meta.get("common_patterns"),
            )

    def register_enhanced_function(self,
                                  func: Callable,
                                  description: str,
                                  parameters: Dict[str, Any],
                                  operation_type: Optional[str] = None,
                                  common_patterns: Optional[Dict[str, Any]] = None):
        """
        Register a function with enhanced metadata.
        
        This is the programmatic alternative to using the @genesis_function decorator.
        Decorated methods are auto-found and forwarded here; call this directly to
        register functions without decorators (e.g., dynamically created callables,
        wrappers, or functions loaded from external modules/config) by supplying
        explicit description and parameter schema.
        Both paths converge to the same pipeline (wrapping, local registry, DDS advertisement).

        Args:
            func: The function to register
            description: Human-readable description of the function
            parameters: JSON schema for function parameters
            operation_type: Optional operation type tag (e.g., "arithmetic")
            common_patterns: Optional dict of common usage patterns
            
        Returns:
            Result of parent's register_function() call
            
        Raises:
            json.JSONDecodeError: If parameters is a string but not valid JSON
        """
        func_name = func.__name__
        logger.info(f"Starting enhanced function registration for '{func_name}'")
        
        # Handle parameters as string (parse JSON) or dict
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON schema string for function '{func_name}'")
                raise
        
        try:
            # Wrap function with execution wrapper
            wrapped_func = self.function_wrapper(func_name)(func)
            wrapped_func.__name__ = func_name
            
            # Register with parent GenesisReplier
            result = self.register_function(
                func=wrapped_func,
                description=description,
                parameters=parameters,
                operation_type=operation_type,
                common_patterns=common_patterns
            )
            logger.info(f"Successfully registered enhanced function '{func_name}'")
            return result
        except Exception as e:
            logger.error(f"Failed to register enhanced function '{func_name}': {e}")
            raise

    def _advertise_functions(self):
        """
        Advertise all registered functions via DDS FunctionRegistry.
        
        This method registers functions with the FunctionRegistry for discovery
        by agents and other services. It does NOT publish graph monitoring events
        (that's handled by MonitoredService).
        """
        if self._functions_advertised:
            logger.warning("Functions already advertised, skipping.")
            return

        logger.info("Starting function advertisement process...")
        total_functions = len(self.functions)
        logger.info(f"Found {total_functions} functions to advertise.")

        for i, (func_name, func_data) in enumerate(self.functions.items(), 1):
            schema = json.loads(func_data["tool"].function.parameters)
            description = func_data["tool"].function.description
            capabilities = self.service_capabilities.copy()
            # operation_type: optional per-function classification tag (e.g., "analysis").
            # Used to append a keyword to capabilities for better discovery/prompting; execution is unchanged.
            # Needed so dynamic services can expose fine-grained tags beyond service-level capabilities.
            if func_data.get("operation_type"):
                capabilities.append(func_data["operation_type"])

            # Register the function in the FunctionRegistry to obtain the canonical function_id
            # Note: performance_metrics and security_requirements are placeholders that demonstrate
            # the pattern for future performance-based routing or security filtering implementations.
            function_id = self.registry.register_function(
                func=func_data["implementation"],
                description=description,
                parameter_descriptions=schema,
                capabilities=capabilities,
                performance_metrics={"latency": "low"},
                security_requirements={"level": "public"}
            )

            # Track for reference
            self._advertised_function_ids[func_name] = function_id
            logger.info(f"Advertised function: {func_name} (ID: {function_id[:8]}...)")

        self._functions_advertised = True
        logger.info("Finished function advertisement process.")

    def _get_function_id(self, func_name: str) -> str:
        """
        Return the UUID assigned to a function name, or empty string if unknown.
        
        Args:
            func_name: Name of the function
            
        Returns:
            Function ID (UUID) or empty string
        """
        return self._advertised_function_ids.get(func_name, "")

    def function_wrapper(self, func_name: str):
        """
        Create a wrapper for function execution.
        
        This wrapper handles function execution without monitoring.
        MonitoredService overrides this to add monitoring events.
        
        Args:
            func_name: Name of the function to wrap
            
        Returns:
            Decorator function that wraps the target function
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Execute function (no monitoring in base class)
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    logger.error(f"Error in function {func_name}: {e}")
                    raise
            return wrapper
        return decorator

    async def run(self):
        """
        Run the service (start listening for requests).
        
        Advertises functions if not already done, then starts the RPC listener loop.
        """
        if not self._functions_advertised:
            self._advertise_functions()
        try:
            await super().run()
        finally:
            if hasattr(self, 'registry'):
                self.registry.close()

    def close(self):
        """
        Clean up service resources.
        
        Closes the FunctionRegistry and calls parent cleanup.
        """
        logger.info(f"Closing {self.service_name}...")
        if hasattr(self, 'registry'):
            self.registry.close()
        super().close()
        logger.info(f"{self.service_name} closed successfully")

