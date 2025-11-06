"""
Genesis Generic Function Client — Discover and Invoke Network Functions

High-level client for dynamic discovery and invocation of functions across the Genesis
distributed network. Serves as the primary integration point for agents and services
to find and call functions without prior knowledge of their implementation or location.

=================================================================================================
ARCHITECTURE OVERVIEW — What This Module Does
=================================================================================================

Responsibilities:
- Dynamic discovery via `DDSFunctionDiscovery` (direct DDS reads, no caching)
- Service client lifecycle management (creates `GenesisRequester` per service)
- Intelligent routing by service capability metadata
- Schema access and function metadata handling
- Clean integration with the Genesis RPC system

Lifecycle:
1. Construct client (optionally with an existing `DDSFunctionDiscovery`)
2. List available functions for schema/capabilities
3. Resolve service name for a function and obtain a `GenesisRequester`
4. Invoke function via RPC
5. Cleanup: close per-service clients and discovery (if the client created it)

Failure Handling & Cleanup:
- Functions are read on-demand from DDSFunctionDiscovery (no caching, always current)
- If a function or service name cannot be resolved, raises descriptive errors
- No participant sprawl: reuses `DDSFunctionDiscovery` participant for requesters
- `close()` shuts down created requesters and (optionally) the discovery

Thread-safety:
- Intended for typical async usage patterns; external synchronization is the caller's responsibility
- Maintains internal maps of service clients; not designed for concurrent mutation from many tasks

Public API:
- `GenericFunctionClient(discovery=None, participant=None, domain_id=0)`
- `list_available_functions() -> list[dict]`
- `call_function(function_id, **kwargs) -> dict`
- `get_function_schema(function_id) -> dict`
- `get_service_client(service_name) -> GenesisRequester`
- `close()`

Usage:
    client = GenericFunctionClient()
    funcs = client.list_available_functions()
    result = await client.call_function(funcs[0]["function_id"], param="value")
    client.close()

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
logger = logging.getLogger("generic_function_client")
# logger.setLevel(logging.INFO)  # REMOVE THIS

class GenericFunctionClient:
    """
    Generic function client for discovering and invoking functions over Genesis RPC.

    Design:
    - Uses `DDSFunctionDiscovery` as the source of truth for discovered functions
    - Creates one `GenesisRequester` per service and reuses it for subsequent calls
    - Avoids creating additional DDS participants by reusing the discovery's participant

    Attributes:
        function_discovery: The DDSFunctionDiscovery instance used for discovery
        _created_discovery: Whether this client created the discovery (affects cleanup)
        service_clients: Map of `service_name` → `GenesisRequester`
        function_registry: Backward-compat adapter exposing get_all_discovered_functions()
    """
    
    #TODO: Remove this adapter after all tests are migrated to the new discovery API
    class _LegacyRegistryAdapter:
        """
        Backward-compatibility adapter that exposes a minimal FunctionRegistry-like API
        backed by DDSFunctionDiscovery. It does NOT cache; it constructs the mapping
        on each call by reading directly from DDS.
        """
        def __init__(self, parent: "GenericFunctionClient"):
            self._parent = parent
        
        def get_all_discovered_functions(self) -> Dict[str, Dict[str, Any]]:
            """
            Returns a dict keyed by function_id with values matching the legacy shape:
            {
              "name": str,
              "description": str,
              "provider_id": str,
              "schema": Dict[str, Any],
              "capabilities": List[str],
              "service_name": str,
              "capability": {"service_name": str},
              "advertisement": None
            }
            """
            result: Dict[str, Dict[str, Any]] = {}
            try:
                functions = self._parent.function_discovery.list_functions()
                for func in functions:
                    fid = func.get("function_id")
                    if not fid:
                        continue
                    service_name = func.get("service_name", "UnknownService")
                    result[fid] = {
                        "name": func.get("name", fid),
                        "description": func.get("description", ""),
                        "provider_id": func.get("provider_id", ""),
                        "schema": func.get("schema", {}),
                        "capabilities": func.get("capabilities", []),
                        "service_name": service_name,
                        "capability": {"service_name": service_name},
                        # Advertisement DynamicData is not stored in this path; keep None for compat
                        "advertisement": None,
                    }
            except Exception as e:
                logger.error(f"Legacy registry adapter failed to read functions: {e}")
                return {}
            return result
    
    def __init__(self, discovery: Optional[DDSFunctionDiscovery] = None, 
                 participant: Optional[dds.DomainParticipant] = None, 
                 domain_id: int = 0):
        """
        Initialize the generic function client.
        
        Args:
            discovery: Optional existing DDSFunctionDiscovery instance to use.
                      If None, a new one will be created.
            participant: Optional existing DDS Participant instance to use for discovery.
            domain_id: DDS domain ID to use if creating a new discovery without a participant.
        """
        logger.debug("Initializing GenericFunctionClient")
        
        # Track if we created the discovery
        self._created_discovery = False
        if discovery is None:
            self.function_discovery = DDSFunctionDiscovery(participant=participant, domain_id=domain_id)
            self._created_discovery = True
        else:
            self.function_discovery = discovery
        
        # Store service-specific clients
        self.service_clients = {}
        
        # Backward-compatibility: expose a minimal registry-like adapter so existing
        # tests and integrations that poll client.function_registry continue to work.
        self.function_registry = GenericFunctionClient._LegacyRegistryAdapter(self)
        
    def get_service_client(self, service_name: str) -> GenesisRequester:
        """
        Get or create a client for a specific service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Requester client for the service
        """
        if service_name not in self.service_clients:
            logger.debug(f"Creating new requester for service: {service_name}")
            # Reuse the participant from function_discovery to avoid participant sprawl
            # This ensures each application has only ONE DDS participant
            participant = self.function_discovery.participant
            client = GenesisRequester(
                service_type=service_name, 
                participant=participant,
                timeout_seconds=10.0
            )
            self.service_clients[service_name] = client
        
        return self.service_clients[service_name]
    
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
        
        # Get or create a client for this service
        client = self.get_service_client(service_name)
        
        # Wait for the service to be discovered
        logger.debug(f"Waiting for service {service_name} to be discovered")
        try:
            await client.wait_for_service(timeout_seconds=5)
        except TimeoutError as e:
            logger.warning(f"Service discovery timed out, but attempting call anyway: {str(e)}")
        
        # Call the function through RPC
        logger.debug(f"Calling function {function_name} via RPC")
        try:
            return await client.call_function(function_name, **kwargs)
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
        """Close all client resources, including the DDSFunctionDiscovery if created by this instance"""
        logger.debug("Cleaning up GenericFunctionClient resources...")
        # Close service-specific clients
        for client in self.service_clients.values():
            client.close()
            
        # Close the DDSFunctionDiscovery if this client created it
        if self._created_discovery and hasattr(self, 'function_discovery') and self.function_discovery:
            logger.debug("Closing DDSFunctionDiscovery created by GenericFunctionClient...")
            self.function_discovery.close()
            self.function_discovery = None # Clear reference
            
        logger.debug("GenericFunctionClient cleanup complete.")

async def run_generic_client_test():
    """
    Run a test of the generic function client.
    This test has zero knowledge of function schemas or calling conventions.
    It simply discovers functions and tests the first function it finds.
    """
    client = GenericFunctionClient()
    
    try:
        # List available functions
        functions = client.list_available_functions()
        print("\nAvailable Functions:")
        for func in functions:
            print(f"  - {func['function_id']}: {func['name']} - {func['description']}")
        
        if functions:
            # Test the first function we find
            test_func = functions[0]
            print(f"\nTesting function: {test_func['name']} - {test_func['description']}")
            
            # Get the schema to understand what parameters are needed
            schema = test_func['schema']
            print(f"Function schema: {json.dumps(schema, indent=2)}")
            
            # Extract required parameters and their types
            required_params = {}
            if 'properties' in schema:
                for param_name, param_schema in schema['properties'].items():
                    # Check if parameter is required
                    is_required = 'required' in schema and param_name in schema['required']
                    
                    if is_required:
                        # Determine a test value based on the parameter type
                        if param_schema.get('type') == 'number' or param_schema.get('type') == 'integer':
                            # Use a simple number for testing
                            required_params[param_name] = 10
                        elif param_schema.get('type') == 'string':
                            # Use a simple string for testing
                            required_params[param_name] = "test"
                        elif param_schema.get('type') == 'boolean':
                            # Use a simple boolean for testing
                            required_params[param_name] = True
                        else:
                            # Default to a string for unknown types
                            required_params[param_name] = "test"
            
            if required_params:
                print(f"Calling function with parameters: {required_params}")
                try:
                    result = await client.call_function(test_func['function_id'], **required_params)
                    print(f"Function returned: {result}")
                    print("✅ Test passed.")
                except Exception as e:
                    print(f"❌ Error calling function: {str(e)}")
            else:
                print("No required parameters found in schema, skipping test.")
        else:
            print("\nNo functions found to test.")
            
    except Exception as e:
        logger.error(f"Error in test: {str(e)}", exc_info=True)
    finally:
        client.close()

def main():
    """Main entry point"""
    logger.debug("Starting GenericFunctionClient")
    try:
        asyncio.run(run_generic_client_test())
    except KeyboardInterrupt:
        logger.debug("Client shutting down due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 