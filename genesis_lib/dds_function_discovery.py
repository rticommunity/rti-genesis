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
DDS Function Discovery - Direct DataReader-Based Function Discovery

This module provides a lightweight utility for discovering functions across the Genesis
network by reading directly from the DDS Advertisement DataReader. Unlike the legacy
FunctionRegistry, this class maintains NO internal cache - DDS is the source of truth.

=================================================================================================
ARCHITECTURE OVERVIEW
=================================================================================================

This utility is for INTER-APPLICATION function discovery only. For local/internal functions
within a service (same process), use InternalFunctionRegistry instead.

Key Design Principles:
1. **Stateless**: No caching, no callbacks, no internal state beyond the DataReader
2. **On-Demand**: Every query reads from DDS directly
3. **Simple**: Minimal API surface - list, get by ID, close
4. **Thin Wrapper**: Just parses DDS samples into Python dicts

Data Flow:
1. Application calls list_functions()
2. DDSFunctionDiscovery reads from Advertisement DataReader
3. Parses ALIVE FUNCTION advertisements
4. Returns list of function metadata dicts

=================================================================================================
USAGE PATTERNS
=================================================================================================

Basic Usage:
```python
discovery = DDSFunctionDiscovery(participant, domain_id=0)
functions = discovery.list_functions()
for func in functions:
    print(f"Found: {func['name']} - {func['description']}")
discovery.close()
```

Integration with FunctionRequester:
```python
requester = FunctionRequester(discovery=DDSFunctionDiscovery(participant))
result = await requester.call_function(function_id, **args)
```

=================================================================================================
COMPARISON WITH InternalFunctionRegistry
=================================================================================================

DDSFunctionDiscovery (this file):
- For discovering functions from OTHER applications
- Reads from DDS Advertisement topic
- No caching, stateless
- No registration capability

InternalFunctionRegistry (function_discovery.py):
- For registering functions within THIS service/application
- Publishes to DDS Advertisement topic
- Maintains local function table
- Supports registration and advertisement

"""

import logging
import json
import traceback
from typing import Dict, List, Any, Optional
import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path

logger = logging.getLogger("genesis_lib.dds_function_discovery")


class DDSFunctionDiscoveryListener(dds.DynamicData.NoOpDataReaderListener):
    """Listener that logs discovery events for FUNCTION advertisements.
    
    This does not maintain any cache; it only logs discovery so tests and monitoring
    can observe when new functions appear on the DDS network.
    """
    def __init__(self, discovery):
        super().__init__()
        self.discovery = discovery
    
    def on_data_available(self, reader):
        try:
            samples = reader.read()
            for ad, info in samples:
                if info.state.sample_state == dds.SampleState.NOT_READ and info.state.instance_state == dds.InstanceState.ALIVE:
                    function_name = ad.get_string("name") or "unknown"
                    # Emit both logger and print so scripts catch it regardless of logging config
                    logger.info(f"Updated/Added discovered function: {function_name}")
                    print(f"Updated/Added discovered function: {function_name}", flush=True)
        except Exception as e:
            logger.error(f"DDSFunctionDiscoveryListener error: {e}")
            logger.error(traceback.format_exc())


class DDSFunctionDiscovery:
    """
    Lightweight function discovery that reads directly from DDS without caching.
    
    This class provides a simple interface for discovering functions published by
    other applications in the Genesis network. It reads from the DDS Advertisement
    topic (filtered for FUNCTION kind) and returns parsed metadata on-demand.
    
    Key Characteristics:
    - No internal state beyond the DataReader
    - No caching of discovered functions
    - No callbacks or event-driven updates
    - Simple query-based API
    
    Use this for:
    - Agent function discovery (what functions are available?)
    - Client function lookup (how do I call function X?)
    - Dynamic tool generation for LLMs
    
    Do NOT use this for:
    - Registering local functions (use InternalFunctionRegistry)
    - Functions within the same process (use direct calls)
    """
    
    def __init__(self, participant: Optional[dds.DomainParticipant] = None, domain_id: int = 0):
        """
        Initialize DDS function discovery.
        
        Args:
            participant: DDS participant (creates one if None)
            domain_id: DDS domain ID if creating a participant
        """
        logger.debug("Initializing DDSFunctionDiscovery")
        
        # Create or use provided participant
        self._owns_participant = False
        if participant is None:
            self.participant = dds.DomainParticipant(domain_id)
            self._owns_participant = True
        else:
            self.participant = participant
        
        # Get types from XML
        config_path = get_datamodel_path()
        self.type_provider = dds.QosProvider(config_path)
        
        try:
            self.advertisement_type = self.type_provider.type("genesis_lib", "GenesisAdvertisement")
        except Exception as e:
            logger.error(f"Failed to load GenesisAdvertisement type: {e}")
            raise
        
        # Create subscriber
        self.subscriber = dds.Subscriber(self.participant)
        
        # Get shared advertisement bus for topic
        from genesis_lib.advertisement_bus import AdvertisementBus
        bus = AdvertisementBus.get(self.participant)
        self.advertisement_topic = bus.topic
        
        # Create content-filtered topic for FUNCTION advertisements only
        logger.debug("Creating content-filtered topic for FUNCTION advertisements")
        self.filtered_topic = dds.DynamicData.ContentFilteredTopic(
            self.advertisement_topic,
            "DDSFunctionDiscoveryFilter",
            dds.Filter("kind = %0", ["0"])  # FUNCTION kind = 0
        )
        
        # Create DataReader with TRANSIENT_LOCAL QoS to get historical data
        # Load QoS directly from USER_QOS_PROFILES.xml to avoid "Profile not found" errors
        from genesis_lib.utils import get_qos_provider
        _qos_provider = get_qos_provider()
        reader_qos = _qos_provider.datareader_qos_from_profile("cft_Library::cft_Profile")
        
        # Create listener to surface discovery events asynchronously
        self._listener = DDSFunctionDiscoveryListener(self)
        
        self.advertisement_reader = dds.DynamicData.DataReader(
            cft=self.filtered_topic,
            qos=reader_qos,
            subscriber=self.subscriber,
            listener=self._listener,
            mask=dds.StatusMask.DATA_AVAILABLE
        )
        
        logger.debug("DDSFunctionDiscovery initialized successfully")
        
        # CRITICAL: For TRANSIENT_LOCAL, retrieve historical data immediately
        # This ensures we see functions published before this discovery instance was created
        try:
            logger.debug("DDSFunctionDiscovery: Retrieving historical function advertisements...")
            historical_samples = self.advertisement_reader.read()
            logger.debug(f"DDSFunctionDiscovery: Retrieved {len(historical_samples)} historical samples")
            
            # Log discovered functions for test compatibility
            for ad, info in historical_samples:
                if info.state.instance_state == dds.InstanceState.ALIVE:
                    function_name = ad.get_string("name") or "unknown"
                    function_id = ad.get_string("advertisement_id") or ""
                    logger.info(f"Updated/Added discovered function: {function_name}")
                    print(f"Updated/Added discovered function: {function_name}", flush=True)
                    
        except Exception as e:
            logger.warning(f"Could not retrieve historical function advertisements: {e}")
            logger.debug(traceback.format_exc())
    
    def list_functions(self) -> List[Dict[str, Any]]:
        """
        List all currently available functions by reading from DDS.
        
        This method reads ALIVE function advertisements from the DDS DataReader
        and returns them as a list of dictionaries. Each call re-reads from DDS,
        ensuring the most up-to-date view of available functions.
        
        Returns:
            List of function metadata dictionaries, each containing:
            - function_id: Unique identifier (UUID)
            - name: Function name
            - description: Human-readable description
            - provider_id: ID of the service providing this function
            - schema: JSON schema for function parameters
            - capabilities: List of capability tags
            - service_name: Name of the providing service
            
        Example:
            ```python
            functions = discovery.list_functions()
            for func in functions:
                print(f"{func['name']}: {func['description']}")
            ```
        """
        result = []
        
        try:
            # Read all samples from DDS
            samples = self.advertisement_reader.read()
            
            for ad, info in samples:
                # Only include ALIVE instances (skip disposed/offline)
                if info.state.instance_state != dds.InstanceState.ALIVE:
                    continue
                
                # Parse advertisement fields
                function_id = ad.get_string("advertisement_id") or ""
                name = ad.get_string("name") or ""
                description = ad.get_string("description") or ""
                provider_id = ad.get_string("provider_id") or ""
                service_name = ad.get_string("service_name") or "UnknownService"
                payload_str = ad.get_string("payload") or "{}"
                
                # Parse payload JSON
                try:
                    payload = json.loads(payload_str) if payload_str else {}
                except Exception:
                    payload = {}
                
                schema = payload.get("parameter_schema") or {}
                capabilities = payload.get("capabilities") or []
                
                # Handle capabilities as string (backward compatibility)
                if isinstance(capabilities, str):
                    try:
                        capabilities = json.loads(capabilities) or []
                    except Exception:
                        capabilities = [capabilities]
                
                # Skip invalid entries
                if not function_id or not name or not provider_id:
                    continue
                
                # Build function metadata dict
                result.append({
                    "function_id": function_id,
                    "name": name,
                    "description": description,
                    "provider_id": provider_id,
                    "schema": schema,
                    "capabilities": capabilities,
                    "service_name": service_name,
                })
                
        except Exception as e:
            logger.error(f"Error reading functions from DDS: {e}")
            logger.error(traceback.format_exc())
            return []
        
        logger.debug(f"DDSFunctionDiscovery.list_functions() returned {len(result)} functions")
        return result
    
    def get_function_by_id(self, function_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific function by its ID.
        
        Args:
            function_id: UUID of the function to retrieve
            
        Returns:
            Function metadata dict or None if not found
        """
        functions = self.list_functions()
        for func in functions:
            if func["function_id"] == function_id:
                return func
        return None
    
    def get_function_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific function by its name.
        
        Note: If multiple functions have the same name, returns the first one found.
        
        Args:
            name: Name of the function to retrieve
            
        Returns:
            Function metadata dict or None if not found
        """
        functions = self.list_functions()
        for func in functions:
            if func["name"] == name:
                return func
        return None
    
    def close(self):
        """
        Clean up DDS resources.
        
        Closes the DataReader, subscriber, and participant (if owned by this instance).
        """
        logger.debug("Closing DDSFunctionDiscovery")
        
        try:
            if hasattr(self, 'advertisement_reader') and self.advertisement_reader:
                self.advertisement_reader.close()
            
            if hasattr(self, 'subscriber') and self.subscriber:
                self.subscriber.close()
            
            if self._owns_participant and hasattr(self, 'participant') and self.participant:
                self.participant.close()
                
        except Exception as e:
            logger.error(f"Error closing DDSFunctionDiscovery: {e}")
            logger.error(traceback.format_exc())
        
        logger.debug("DDSFunctionDiscovery closed successfully")

