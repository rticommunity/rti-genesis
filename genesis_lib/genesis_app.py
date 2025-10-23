"""
Genesis Application Base Class

This module provides the foundational base class `GenesisApp` that serves as the core
integration point for all components in the Genesis framework. It establishes the
essential DDS infrastructure, function registration capabilities, and lifecycle
management that are required by both agents and interfaces.

Key responsibilities include:
- DDS participant and topic management
- Function registration and discovery infrastructure
- Agent registration and presence announcement
- Resource lifecycle management
- Error pattern handling and recovery
- Integration with the Genesis monitoring system

The GenesisApp class is designed to be extended by both `GenesisAgent` and
`GenesisInterface` classes, providing them with the necessary infrastructure
for DDS-based communication and function discovery. It handles the complexity
of DDS setup, QoS configuration, and resource management, allowing derived
classes to focus on their specific roles in the Genesis network.

Copyright (c) 2025, RTI & Jason Upchurch
"""

#!/usr/bin/env python3

import logging
import time
from typing import Dict, List, Any, Optional, Callable
import uuid
import rti.connextdds as dds
from genesis_lib.function_discovery import FunctionRegistry, FunctionInfo
from .function_patterns import SuccessPattern, FailurePattern, pattern_registry
import os
import traceback
from genesis_lib.utils import get_datamodel_path
import asyncio

# Configure logging
logger = logging.getLogger("genesis_app")

class GenesisApp:
    """
    Base class for Genesis applications that provides function registration
    and discovery capabilities.
    
    This class integrates with the FunctionRegistry to provide a clean
    interface for registering functions from Genesis applications.
    """
    
    def __init__(self, participant=None, domain_id=0, preferred_name="DefaultAgent", agent_id=None):
        """
        Initialize the Genesis application.
        
        Args:
            participant: DDS participant (if None, will create one)
            domain_id: DDS domain ID
            preferred_name: Preferred name for this application instance
            agent_id: Optional UUID for the agent (if None, will generate one)
        """
        # Generate or use provided agent ID
        self.agent_id = agent_id or str(uuid.uuid4())
        self.preferred_name = preferred_name
        
        # Initialize DDS participant
        if participant is None:
            participant_qos = dds.QosProvider.default.participant_qos
            self.participant = dds.DomainParticipant(domain_id, qos=participant_qos)
        else:
            self.participant = participant
            
        # Store DDS GUID
        self.dds_guid = str(self.participant.instance_handle)
        
        # Get types from XML
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        # GenesisRegistration topic removed - now using unified Advertisement topic
        
        # Create publisher and subscriber with QoS
        self.publisher = dds.Publisher(
            self.participant,
            qos=dds.QosProvider.default.publisher_qos
        )
        self.subscriber = dds.Subscriber(
            self.participant,
            qos=dds.QosProvider.default.subscriber_qos
        )
        
        # Create DataWriter with QoS
        writer_qos = dds.QosProvider.default.datawriter_qos
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.history.kind = dds.HistoryKind.KEEP_LAST
        writer_qos.history.depth = 500
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.liveliness.kind = dds.LivelinessKind.AUTOMATIC
        writer_qos.liveliness.lease_duration = dds.Duration(seconds=2)
        writer_qos.ownership.kind = dds.OwnershipKind.SHARED
        
        # Initialize function registry and pattern registry
        logger.debug("===== DDS TRACE: Initializing FunctionRegistry in GenesisApp =====")
        self.function_registry = FunctionRegistry(self.participant, domain_id)
        logger.debug(f"===== DDS TRACE: FunctionRegistry initialized with participant {self.participant.instance_handle} =====")
        self.pattern_registry = pattern_registry
        
        # Register built-in functions
        logger.debug("===== DDS TRACE: Starting built-in function registration =====")
        self._register_builtin_functions()
        logger.debug("===== DDS TRACE: Completed built-in function registration =====")
        
        logger.info(f"GenesisApp initialized with agent_id={self.agent_id}, dds_guid={self.dds_guid}")

    def get_available_functions(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves a snapshot of all currently discovered functions available on the network.
        This information is sourced from the FunctionRegistry.

        Returns:
            A dictionary mapping function_id to its details (name, description, provider_id, etc.).
        """
        if hasattr(self, 'function_registry') and self.function_registry:
            return self.function_registry.get_all_discovered_functions()
        else:
            logger.warning("FunctionRegistry not available in GenesisApp, cannot get available functions.")
            return {}

    async def close(self):
        """Close all DDS entities and cleanup resources"""
        if hasattr(self, '_closed') and self._closed:
            logger.info(f"GenesisApp {self.agent_id} is already closed")
            return

        try:
            # Close DDS entities in reverse order of creation
            resources_to_close = ['function_registry', 'publisher', 'subscriber', 'participant']
            
            for resource in resources_to_close:
                if hasattr(self, resource):
                    try:
                        resource_obj = getattr(self, resource)
                        if hasattr(resource_obj, 'close') and not getattr(resource_obj, '_closed', False):
                            if asyncio.iscoroutinefunction(resource_obj.close):
                                await resource_obj.close()
                            else:
                                resource_obj.close()
                    except Exception as e:
                        # Only log as warning if the error is not about being already closed
                        if "already closed" not in str(e).lower():
                            logger.warning(f"Error closing {resource}: {str(e)}")
            
            # Mark as closed
            self._closed = True
            logger.info(f"GenesisApp {self.agent_id} closed successfully")
        except Exception as e:
            logger.error(f"Error closing GenesisApp: {str(e)}")
            logger.error(traceback.format_exc())

    def _register_builtin_functions(self):
        """Register any built-in functions for this application"""
        logger.debug("===== DDS TRACE: _register_builtin_functions called =====")
        # Override this method in subclasses to register built-in functions
        pass

    def execute_function(self, function_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a registered function with error pattern checking.
        
        Args:
            function_id: ID of function to execute
            parameters: Function parameters
            
        Returns:
            Dictionary containing result or error information
        """
        try:
            # Execute the function
            result = super().execute_function(function_id, parameters)
            
            # Check result against patterns
            is_success, error_code, recovery_hint = self.pattern_registry.check_result(function_id, result)
            
            if is_success:
                return {
                    "status": "success",
                    "result": result
                }
            else:
                return {
                    "status": "error",
                    "error_code": error_code,
                    "message": str(result),
                    "recovery_hint": recovery_hint
                }
                
        except Exception as e:
            # Check if exception matches any failure patterns
            is_success, error_code, recovery_hint = self.pattern_registry.check_result(function_id, e)
            
            return {
                "status": "error",
                "error_code": error_code or "UNKNOWN_ERROR",
                "message": str(e),
                "recovery_hint": recovery_hint
            } 