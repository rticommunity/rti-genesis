#!/usr/bin/env python3
"""
Genesis Enhanced Service Base (Unified Graph Monitoring)

This module provides the core base class for all services in the Genesis framework,
implementing automatic function discovery, registration, and monitoring capabilities.
It now uses the unified GraphMonitor for all node/edge monitoring events, supporting
robust graph-based monitoring and DDS compatibility.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import logging
import asyncio
import json
from typing import Dict, Any, List, Optional, Callable
from genesis_lib.rpc_service import GenesisRPCService
from genesis_lib.function_discovery import FunctionRegistry
import uuid

from genesis_lib.graph_monitoring import (
    GraphMonitor,
    COMPONENT_TYPE,
    STATE,
    EDGE_TYPE,
)

logger = logging.getLogger("enhanced_service_base")

class EnhancedServiceBase(GenesisRPCService):
    """
    Enhanced base class for GENESIS RPC services.
    Now uses unified GraphMonitor for all node/edge monitoring events.
    """

    def __init__(self, service_name: str, capabilities: List[str], participant=None, domain_id=0, registry: FunctionRegistry = None):
        # Create participant FIRST if needed, before calling super().__init__
        if participant is None:
            import rti.connextdds as dds
            qos = dds.DomainParticipantQos()
            qos.transport_builtin.mask = dds.TransportBuiltinMask.UDPv4
            participant = dds.DomainParticipant(domain_id, qos)
        
        # Now call parent __init__ with the participant and service_type
        # V2 uses 'service_type' parameter instead of 'service_name'
        super().__init__(service_type=service_name, participant=participant)
        
        self.service_name = service_name
        self.participant = participant
        self.domain_id = domain_id
        self.service_capabilities = capabilities
        self._functions_advertised = False
        # Track advertised functions for durable edge refresh
        self._advertised_function_ids: Dict[str, str] = {}
        self._call_ids = {}
        self.logger = logging.getLogger("enhanced_service_base")
        self.registry = registry if registry is not None else FunctionRegistry(
            participant=self.participant,
            domain_id=domain_id,
            enable_discovery_listener=False
        )
        self.registry.service_base = self
        # Get GUID from Advertisement writer (capability_writer removed)
        self.app_guid = str(self.registry.advertisement_writer.instance_handle) if self.registry.advertisement_writer else str(self.participant.instance_handle)

        # Unified graph monitor
        self.graph = GraphMonitor(self.participant)

        # Auto-register decorated functions
        self._auto_register_decorated_functions()

    def _auto_register_decorated_functions(self):
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
        func_name = func.__name__
        logger.info(f"Starting enhanced function registration for '{func_name}'")
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON schema string for function '{func_name}'")
                raise
        try:
            wrapped_func = self.function_wrapper(func_name)(func)
            wrapped_func.__name__ = func_name
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
        if self._functions_advertised:
            logger.warning("Functions already advertised, skipping.")
            return

        logger.info("Starting function advertisement process...")
        total_functions = len(self.functions)
        logger.info(f"Found {total_functions} functions to advertise.")

        # Node for the service itself
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

        for i, (func_name, func_data) in enumerate(self.functions.items(), 1):
            schema = json.loads(func_data["tool"].function.parameters)
            description = func_data["tool"].function.description
            capabilities = self.service_capabilities.copy()
            if func_data.get("operation_type"):
                capabilities.append(func_data["operation_type"])

            # First, register the function in the FunctionRegistry to obtain the canonical function_id
            function_id = self.registry.register_function(
                func=func_data["implementation"],
                description=description,
                parameter_descriptions=schema,
                capabilities=capabilities,
                performance_metrics={"latency": "low"},
                security_requirements={"level": "public"}
            )

            # Node for function using the same function_id as the registry
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
            # Edge: service to function (consistent with registry id)
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
            # Track for durable refresh
            self._advertised_function_ids[func_name] = function_id
            logger.info(f"Advertised function: {func_name}")

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
        # (safe no-op for existing subscribers).
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
        logger.info("Finished function advertisement process.")

    def _get_function_id(self, func_name: str) -> str:
        """Return the UUID assigned to a function name, or empty string if unknown."""
        return self._advertised_function_ids.get(func_name, "")

    def publish_function_call_event(self, function_name: str, call_data: Dict[str, Any], request_info=None):
        # Node update: service busy
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
        # Node update: service ready
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
        # Node update: service degraded
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

    def function_wrapper(self, func_name: str):
        def decorator(func):
            def wrapper(*args, **kwargs):
                function_uuid = self._get_function_id(func_name)
                # Note: Activation events (FUNCTION_CALL_START/COMPLETE) are now published
                # by the agent via MonitoredAgent._publish_function_call_start/complete
                # Node update: service busy
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
                    result = func(*args, **kwargs)
                    # Node update: service ready
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
                    # Node update: service degraded
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

    async def run(self):
        if not self._functions_advertised:
            self._advertise_functions()
        try:
            await super().run()
        finally:
            if hasattr(self, 'registry'):
                self.registry.close()

    def close(self):
        logger.info(f"Closing {self.service_name}...")
        self.graph.publish_node(
            component_id=self.app_guid,
            component_type=COMPONENT_TYPE["SERVICE"],
            state=STATE["OFFLINE"],
            attrs={
                "service": self.service_name,
                "reason": f"Service {self.service_name} shutting down"
            }
        )
        if hasattr(self, 'registry'):
            self.registry.close()
        super().close()
        logger.info(f"{self.service_name} closed successfully")
