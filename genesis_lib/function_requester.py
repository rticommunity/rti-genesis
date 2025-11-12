"""
Genesis Function Requester — Discover and Invoke Network Functions

High-level requester for dynamic discovery and invocation of functions across the Genesis
distributed network. Serves as the primary integration point for agents and services
to find and call functions without prior knowledge of their implementation or location.

=================================================================================================
ARCHITECTURE OVERVIEW — What This Module Does
=================================================================================================

Responsibilities:
- Dynamic discovery via `DDSFunctionDiscovery` (direct DDS reads, no caching)
- Service requester lifecycle management (creates `GenesisRequester` per service)
- Intelligent routing by service capability metadata
- Schema access and function metadata handling
- Clean integration with the Genesis RPC system

Lifecycle:
1. Construct requester (optionally with an existing `DDSFunctionDiscovery`)
2. List available functions for schema/capabilities
3. Resolve service name for a function and obtain a `GenesisRequester`
4. Invoke function via RPC
5. Cleanup: close per-service requesters and discovery (if the requester created it)

Failure Handling & Cleanup:
- Functions are read on-demand from DDSFunctionDiscovery (no caching, always current)
- If a function or service name cannot be resolved, raises descriptive errors
- No participant sprawl: reuses `DDSFunctionDiscovery` participant for requesters
- `close()` shuts down created requesters and (optionally) the discovery

Thread-safety:
- Intended for typical async usage patterns; external synchronization is the caller's responsibility
- Maintains internal maps of service requesters; not designed for concurrent mutation from many tasks

Public API:
- `FunctionRequester(discovery=None, participant=None, domain_id=0)`
- `list_available_functions() -> list[dict]`
- `call_function(function_id, **kwargs) -> dict`
- `get_function_schema(function_id) -> dict`
- `get_service_requester(service_name) -> GenesisRequester`
- `close()`

Usage:
    requester = FunctionRequester()
    funcs = requester.list_available_functions()
    result = await requester.call_function(funcs[0]["function_id"], param="value")
    requester.close()

Copyright (c) 2025, RTI & Jason Upchurch
"""

#!/usr/bin/env python3

import logging
import asyncio
import json
import time
import uuid
from typing import Dict, Any, List, Optional
import rti.connextdds as dds
from genesis_lib.requester import GenesisRequester
from genesis_lib.dds_function_discovery import DDSFunctionDiscovery

# Configure logging
# logging.basicConfig(level=logging.WARNING,  # REMOVE THIS
#                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("function_requester")
# logger.setLevel(logging.INFO)  # REMOVE THIS

class FunctionRequester:
    """
    Function requester for discovering and invoking functions over Genesis RPC.

    Design:
    - Uses `DDSFunctionDiscovery` as the source of truth for discovered functions
    - Creates one `GenesisRequester` per service and reuses it for subsequent calls
    - Avoids creating additional DDS participants by reusing the discovery's participant

    Attributes:
        function_discovery: The DDSFunctionDiscovery instance used for discovery
        _created_discovery: Whether this requester created the discovery (affects cleanup)
        service_requesters: Map of `service_name` → `GenesisRequester`
    """
    
    def __init__(self, discovery: Optional[DDSFunctionDiscovery] = None, 
                 participant: Optional[dds.DomainParticipant] = None, 
                 domain_id: int = 0):
        """
        Initialize the function requester.
        
        Args:
            discovery: Optional existing DDSFunctionDiscovery instance to use.
                      If None, a new one will be created.
            participant: Optional existing DDS Participant instance to use for discovery.
            domain_id: DDS domain ID to use if creating a new discovery without a participant.
        """
        logger.debug("Initializing FunctionRequester")
        
        # Track if we created the discovery
        self._created_discovery = False
        if discovery is None:
            self.function_discovery = DDSFunctionDiscovery(participant=participant, domain_id=domain_id)
            self._created_discovery = True
        else:
            self.function_discovery = discovery
        
        # Store service-specific requesters
        self.service_requesters = {}
        
    def get_service_requester(self, service_name: str) -> GenesisRequester:
        """
        Get or create a requester for a specific service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            GenesisRequester for the service
        """
        if service_name not in self.service_requesters:
            logger.debug(f"Creating new requester for service: {service_name}")
            # Reuse the participant from function_discovery to avoid participant sprawl
            # This ensures each application has only ONE DDS participant
            participant = self.function_discovery.participant
            requester = GenesisRequester(
                service_type=service_name, 
                participant=participant,
                timeout_seconds=10.0
            )
            self.service_requesters[service_name] = requester
        
        return self.service_requesters[service_name]
    
    async def call_function(self, function_id: str, **kwargs) -> Dict[str, Any]:
        """
        Call a function by its ID with the given arguments.
        
        Args:
            function_id: ID of the function to call
            **kwargs: Arguments to pass to the function
            
        Returns:
            Function result
            
        Raises:
            ValueError: If the function is not found
            RuntimeError: If the function call fails
        """
        # Get function info directly from discovery
        func_info = self.function_discovery.get_function_by_id(function_id)

        if not func_info:
            logger.error(f"Function ID {function_id} not found in DDSFunctionDiscovery.")
            raise ValueError(f"Function not found: {function_id}")
        
        # Extract function name and service info
        function_name = func_info.get('name')
        provider_id = func_info.get('provider_id')
        service_name = func_info.get('service_name')
        
        if not function_name:
            raise RuntimeError(f"Function name not found for {function_id}")
        
        if not service_name:
            logger.error(f"Could not determine service name for function {function_id} (provider: {provider_id})")
            raise RuntimeError(f"Service name not found for function {function_id}")
        
        logger.debug(f"Using discovered service name: {service_name} for function: {function_name} (provider: {provider_id})")
        
        # Get or create a requester for this service
        requester = self.get_service_requester(service_name)
        
        # Wait for the service to be discovered
        logger.debug(f"Waiting for service {service_name} to be discovered")
        try:
            await requester.wait_for_service(timeout_seconds=5)
        except TimeoutError as e:
            logger.warning(f"Service discovery timed out, but attempting call anyway: {str(e)}")
        
        # Call the function through RPC
        logger.debug(f"Calling function {function_name} via RPC")
        try:
            return await requester.call_function(function_name, **kwargs)
        except Exception as e:
            raise RuntimeError(f"Error calling function {function_name}: {str(e)}")
    
    def get_function_schema(self, function_id: str) -> Dict[str, Any]:
        """
        Get the schema for a specific function.
        
        Args:
            function_id: ID of the function
            
        Returns:
            Function schema
            
        Raises:
            ValueError: If the function is not found
        """
        func_info = self.function_discovery.get_function_by_id(function_id)
        if not func_info:
            raise ValueError(f"Function not found: {function_id}")
        
        return func_info.get('schema', {})
    
    def list_available_functions(self) -> List[Dict[str, Any]]:
        """
        List all available functions with their descriptions and schemas.
        Directly queries DDSFunctionDiscovery for the most up-to-date list.
        
        Returns:
            List of function information dictionaries
        """
        # Get functions from DDS discovery
        functions_list = self.function_discovery.list_functions()
        
        # Return in expected format
        result = []
        for func in functions_list:
            result.append({
                "function_id": func["function_id"],
                "name": func["name"],
                "description": func["description"],
                "schema": func["schema"],
                "service_name": func["service_name"],
                "provider_id": func.get("provider_id")
            })
        
        return result
    
    def close(self):
        """Close all requester resources, including the DDSFunctionDiscovery if created by this instance"""
        logger.debug("Cleaning up FunctionRequester resources...")
        # Close service-specific requesters
        for requester in self.service_requesters.values():
            requester.close()
            
        # Close the DDSFunctionDiscovery if this requester created it
        if self._created_discovery and hasattr(self, 'function_discovery') and self.function_discovery:
            logger.debug("Closing DDSFunctionDiscovery created by FunctionRequester...")
            self.function_discovery.close()
            self.function_discovery = None # Clear reference
            
        logger.debug("FunctionRequester cleanup complete.")