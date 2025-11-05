#!/usr/bin/env python3
"""
Monitored Service - Monitoring Decorator Layer for Genesis Services

This module provides the MonitoredService class, which adds automatic monitoring, observability,
and graph topology tracking to all Genesis services. It sits between GenesisService and service
implementations as a transparent decorator layer.

=================================================================================================
ARCHITECTURE OVERVIEW - Understanding the Inheritance Hierarchy
=================================================================================================

GenesisReplier (genesis_lib/replier.py)
├─ RPC Request/Reply Handling:
│  ├─ Unified topic management
│  ├─ Function registration
│  └─ Request processing loop
│
    ↓ inherits
│
GenesisService (genesis_lib/genesis_service.py)
├─ Service-Agnostic Business Logic:
│  ├─ Function auto-discovery (@genesis_function decorator)
│  ├─ Function registration and management
│  ├─ Service lifecycle (run, close)
│  └─ DDS advertisement via FunctionRegistry
│
    ↓ inherits
│
MonitoredService (THIS FILE - genesis_lib/monitored_service.py)
├─ Monitoring Decorator Layer (AUTOMATIC - Transparent to Services):
│  ├─ __init__() - Wraps initialization with monitoring setup
│  ├─ _advertise_functions() - Wraps with graph topology publishing
│  ├─ function_wrapper() - Wraps with state transitions (BUSY→READY)
│  ├─ close() - Wraps with OFFLINE state publishing
│  └─ Helper methods for publishing monitoring events
│
    ↓ inherits
│
CalculatorService (user implementation)
└─ Service-Specific Implementation:
   ├─ Implements business logic functions
   ├─ All monitoring is AUTOMATIC from MonitoredService
   └─ No monitoring code needed - just implement service logic

=================================================================================================
WHAT YOU GET FOR FREE - Automatic Monitoring Without Writing Code
=================================================================================================

When you create a service that inherits from MonitoredService, you automatically get ALL of this
monitoring without writing any monitoring code:

1. **State Machine Tracking** (via function_wrapper):
   - DISCOVERING → Service initializing and discovering functions
   - READY → Service idle and ready to process requests
   - BUSY → Service actively processing a function call
   - DEGRADED → Service encountered an error (with error logging)
   - OFFLINE → Service shutting down

2. **Graph Topology Publishing** (via _advertise_functions):
   - Service nodes: Lifecycle events, state transitions, capabilities
   - Function nodes: Discovered functions from @genesis_function decorators
   - Service→Function edges: Connections showing which service provides which functions
   - Consumed by: Network visualization UI, topology analyzers

3. **Function Call Tracking** (via function_wrapper):
   - State transitions: READY → BUSY → READY for each function call
   - Error states: BUSY → DEGRADED on exceptions
   - Consumed by: Monitoring dashboards, performance analysis

4. **Error Handling** (via function_wrapper exception handling):
   - Automatic DEGRADED state on exceptions
   - Error event publishing for alerting
   - Graceful error handling without crashes

Copyright (c) 2025, RTI & Jason Upchurch
"""

import logging
import json
import traceback
from typing import Dict, Any, List, Optional, Callable

from genesis_lib.genesis_service import GenesisService
from genesis_lib.graph_monitoring import (
    GraphMonitor,
    COMPONENT_TYPE,
    STATE,
    EDGE_TYPE,
)

logger = logging.getLogger("monitored_service")

class MonitoredService(GenesisService):
    """
    Monitored service class that adds monitoring capabilities to GenesisService.
    
    This class wraps GenesisService with monitoring functionality following the
    same decorator pattern as MonitoredAgent wraps GenesisAgent.
    """

    def __init__(self, service_name: str, capabilities: List[str], participant=None, 
                 domain_id=0, registry=None, enable_monitoring=True):
        """
        Initialize a MonitoredService with full observability and graph monitoring.
        
        Args:
            service_name: Name of the service (e.g., "CalculatorService")
            capabilities: List of capability tags (e.g., ["calculator", "math"])
            participant: Optional DDS participant (if None, one will be created)
            domain_id: DDS domain ID (default: 0)
            registry: Optional FunctionRegistry instance (if None, one will be created)
            enable_monitoring: Enable monitoring and observability features (default True)
                              When False: No GraphMonitor created, no state tracking, no events published
                              Use False for: lightweight testing, performance benchmarking, minimal deployments
        
        Initialization Sequence:
            1. Store monitoring flag before super().__init__
            2. Call super().__init__() → creates GenesisService with function registration
            3. Initialize GraphMonitor for publishing topology events
            4. Publish DISCOVERING state (announce "I am initializing")
        """
        logger.info(f"🚀 TRACE: MonitoredService {service_name} STARTING initializing")

        # ===== Step 1: Store monitoring flag =====
        self.enable_monitoring = enable_monitoring

        # ===== Step 2: Initialize base GenesisService =====
        # This creates:
        #   - GenesisReplier with DDS participant
        #   - FunctionRegistry for function advertisement
        #   - Auto-registers @genesis_function decorated methods
        super().__init__(
            service_name=service_name,
            capabilities=capabilities,
            participant=participant,
            domain_id=domain_id,
            registry=registry
        )
        logger.info(f"✅ TRACE: MonitoredService {service_name} initialized with base class")

        # ===== Step 3: Create unified graph monitor (if monitoring enabled) =====
        if self.enable_monitoring:
            self.graph = GraphMonitor(self.participant)
            
            # ===== Step 4: Publish DISCOVERING state =====
            # Announces to the network: "I am initializing and discovering functions"
            logger.debug(f"MonitoredService __init__: publishing DISCOVERING for {service_name} ({self.app_guid})")
            self.graph.publish_node(
                component_id=self.app_guid,
                component_type=COMPONENT_TYPE["SERVICE"],
                state=STATE["DISCOVERING"],
                attrs={
                    "service": self.service_name,
                    "capabilities": self.service_capabilities,
                    "reason": f"Service {service_name} is initializing"
                }
            )
        else:
            self.graph = None
            logger.info(f"Monitoring disabled for {service_name}")

        logger.info(f"✅ TRACE: Monitored service {service_name} initialized, guid={self.app_guid}")

    def _advertise_functions(self):
        """
        Advertise functions with graph topology publishing.
        
        DECORATOR PATTERN - Monitoring Wrapper Only:
        This method wraps the parent's _advertise_functions() with monitoring.
        
        What This Method Does (Monitoring Layer):
        1. Publish SERVICE node in DISCOVERING state
        2. Call parent's _advertise_functions() ← ACTUAL WORK HAPPENS HERE
        3. For each function: Publish FUNCTION node + SERVICE→FUNCTION edge
        4. Publish SERVICE node in READY state
        5. Refresh edges for durable discovery (late joiners)
        
        What The Parent Does (Actual Work):
        GenesisService._advertise_functions() handles:
        - Registering functions with FunctionRegistry (DDS advertisement)
        - Tracking advertised function IDs
        """
        if self._functions_advertised:
            logger.warning("Functions already advertised, skipping.")
            return

        logger.info("Starting function advertisement process with monitoring...")
        total_functions = len(self.functions)
        logger.info(f"Found {total_functions} functions to advertise.")

        # Monitoring: Publish service node in DISCOVERING state
        if self.enable_monitoring:
            self.graph.publish_node(
                component_id=self.app_guid,
                component_type=COMPONENT_TYPE["SERVICE"],
                state=STATE["DISCOVERING"],
                attrs={
                    "service": self.service_name,
                    "capabilities": self.service_capabilities,
                    "reason": f"Function app {self.service_name} discovered"
                }
            )

        # Call parent to do actual DDS advertisement
        for i, (func_name, func_data) in enumerate(self.functions.items(), 1):
            schema = json.loads(func_data["tool"].function.parameters)
            description = func_data["tool"].function.description
            capabilities = self.service_capabilities.copy()
            if func_data.get("operation_type"):
                capabilities.append(func_data["operation_type"])

            # Register the function in the FunctionRegistry to obtain the canonical function_id
            function_id = self.registry.register_function(
                func=func_data["implementation"],
                description=description,
                parameter_descriptions=schema,
                capabilities=capabilities,
                performance_metrics={"latency": "low"},
                security_requirements={"level": "public"}
            )

            # Monitoring: Publish function node
            if self.enable_monitoring:
                self.graph.publish_node(
                    component_id=function_id,
                    component_type=COMPONENT_TYPE["FUNCTION"],
                    state=STATE["DISCOVERING"],
                    attrs={
                        "function_name": func_name,
                        "description": description,
                        "capabilities": capabilities,
                        "reason": f"Function '{func_name}' available"
                    }
                )
                
                # Monitoring: Publish service→function edge
                self.graph.publish_edge(
                    source_id=self.app_guid,
                    target_id=function_id,
                    edge_type=EDGE_TYPE["SERVICE_TO_FUNCTION"],
                    attrs={
                        "edge_type": "function_connection",
                        "service": self.service_name,
                        "function_name": func_name,
                        "reason": f"Service {self.service_name} provides function {func_name}"
                    },
                    component_type=COMPONENT_TYPE["SERVICE"]
                )
            
            # Track for reference
            self._advertised_function_ids[func_name] = function_id
            logger.info(f"Advertised function: {func_name}")

        # Monitoring: Publish service node in READY state
        if self.enable_monitoring:
            self.graph.publish_node(
                component_id=self.app_guid,
                component_type=COMPONENT_TYPE["SERVICE"],
                state=STATE["READY"],
                attrs={
                    "service": self.service_name,
                    "capabilities": self.service_capabilities,
                    "reason": f"All {self.service_name} functions published and ready for calls"
                }
            )
            
            # Durable refresh of service→function edges to ensure late joiners reconstruct topology
            try:
                for func_name, function_id in self._advertised_function_ids.items():
                    self.graph.publish_edge(
                        source_id=self.app_guid,
                        target_id=function_id,
                        edge_type=EDGE_TYPE["SERVICE_TO_FUNCTION"],
                        attrs={
                            "edge_type": "function_connection",
                            "service": self.service_name,
                            "function_name": func_name,
                            "reason": f"Durable refresh: {self.service_name} provides {func_name}"
                        },
                        component_type=COMPONENT_TYPE["SERVICE"]
                    )
            except Exception:
                pass

        self._functions_advertised = True
        logger.info("Finished function advertisement process with monitoring.")

    def function_wrapper(self, func_name: str):
        """
        Create a monitored wrapper for function execution.
        
        DECORATOR PATTERN - Monitoring Wrapper:
        This method wraps the parent's function_wrapper with state tracking.
        
        What This Method Does (Monitoring Layer):
        1. Get parent wrapper (base execution)
        2. Wrap it with state transitions: READY → BUSY → READY
        3. On error: BUSY → DEGRADED, then raise
        
        Args:
            func_name: Name of the function to wrap
            
        Returns:
            Decorator function that wraps the target function with monitoring
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                function_uuid = self._get_function_id(func_name)
                
                # Monitoring: Publish BUSY state
                if self.enable_monitoring:
                    self.graph.publish_node(
                        component_id=self.app_guid,
                        component_type=COMPONENT_TYPE["SERVICE"],
                        state=STATE["BUSY"],
                        attrs={
                            "service": self.service_name,
                            "function_name": func_name,
                            "reason": f"Processing function call: {func_name}"
                        }
                    )
                
                try:
                    # Execute function
                    result = func(*args, **kwargs)
                    
                    # Monitoring: Publish READY state
                    if self.enable_monitoring:
                        self.graph.publish_node(
                            component_id=self.app_guid,
                            component_type=COMPONENT_TYPE["SERVICE"],
                            state=STATE["READY"],
                            attrs={
                                "service": self.service_name,
                                "function_name": func_name,
                                "reason": f"Completed function call: {func_name}"
                            }
                        )
                    
                    return result
                except Exception as e:
                    # Monitoring: Publish DEGRADED state
                    if self.enable_monitoring:
                        self.graph.publish_node(
                            component_id=self.app_guid,
                            component_type=COMPONENT_TYPE["SERVICE"],
                            state=STATE["DEGRADED"],
                            attrs={
                                "service": self.service_name,
                                "function_name": func_name,
                                "error": str(e),
                                "reason": f"Error in function {func_name}: {str(e)}"
                            }
                        )
                    raise
            return wrapper
        return decorator

    def publish_function_call_event(self, function_name: str, call_data: Dict[str, Any], request_info=None):
        """
        Publish a function call event (service entering BUSY state).
        
        This method is called by service implementations to track function calls.
        It publishes a node update showing the service is processing a request.
        
        Args:
            function_name: Name of the function being called
            call_data: Dict containing call parameters
            request_info: Optional request metadata
        """
        if not self.enable_monitoring:
            return
            
        self.graph.publish_node(
            component_id=self.app_guid,
            component_type=COMPONENT_TYPE["SERVICE"],
            state=STATE["BUSY"],
            attrs={
                "service": self.service_name,
                "function_name": function_name,
                "call_data": call_data,
                "reason": f"Function call: {function_name}"
            }
        )

    def publish_function_result_event(self, function_name: str, result_data: Dict[str, Any], request_info=None):
        """
        Publish a function result event (service returning to READY state).
        
        This method is called by service implementations after successful function execution.
        It publishes a node update showing the service is ready for new requests.
        
        Args:
            function_name: Name of the function that completed
            result_data: Dict containing result data
            request_info: Optional request metadata
        """
        if not self.enable_monitoring:
            return
            
        self.graph.publish_node(
            component_id=self.app_guid,
            component_type=COMPONENT_TYPE["SERVICE"],
            state=STATE["READY"],
            attrs={
                "service": self.service_name,
                "function_name": function_name,
                "result_data": result_data,
                "reason": f"Function result: {function_name}"
            }
        )

    def publish_function_error_event(self, function_name: str, error: Exception, request_info=None):
        """
        Publish a function error event (service entering DEGRADED state).
        
        This method is called by service implementations when a function encounters an error.
        It publishes a node update showing the service is in a degraded state.
        
        Args:
            function_name: Name of the function that failed
            error: The exception that occurred
            request_info: Optional request metadata
        """
        if not self.enable_monitoring:
            return
            
        self.graph.publish_node(
            component_id=self.app_guid,
            component_type=COMPONENT_TYPE["SERVICE"],
            state=STATE["DEGRADED"],
            attrs={
                "service": self.service_name,
                "function_name": function_name,
                "error": str(error),
                "reason": f"Function error: {function_name}"
            }
        )

    def close(self):
        """
        Gracefully shut down the service with automatic state notification.
        
        DECORATOR PATTERN - Monitoring Wrapper:
        Similar to other wrapped methods, this adds OFFLINE state publishing
        before calling the parent's cleanup logic.
        
        Shutdown Sequence:
        1. Publish OFFLINE state to network
        2. Call parent's close() ← ACTUAL CLEANUP HAPPENS HERE
           - GenesisService.close() shuts down registry, replier, etc.
        """
        if self.enable_monitoring:
            logger.debug(f"MonitoredService.close: publishing OFFLINE for {self.service_name} ({self.app_guid})")
            self.graph.publish_node(
                component_id=self.app_guid,
                component_type=COMPONENT_TYPE["SERVICE"],
                state=STATE["OFFLINE"],
                attrs={
                    "service": self.service_name,
                    "reason": f"Service {self.service_name} shutting down"
                }
            )
        
        # Call parent cleanup
        super().close()

