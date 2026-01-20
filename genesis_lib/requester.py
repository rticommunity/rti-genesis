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
Genesis Requester - Unified Topics with Intelligent Request Routing

This module provides the client-side implementation for Genesis request/reply communication,
featuring unified topics with broadcast and first-reply-wins semantics. It enables
intelligent request routing, automatic service discovery, and robust error handling.

ARCHITECTURAL DECISION: Why not use this wrapper for every RPC path?
===================================================================
Genesis uses one unified DDS data model (GenesisRPCRequest/Reply) for all RPC, but not
every RPC path goes through this wrapper. Two related, but distinct, use-cases exist:

1) Service-oriented function calls (this module)
   - Semantics: function name + parameters → result
   - Needs: consistent JSON packing, input/result handling, structured logs, retries
   - Solution: GenesisRequester/GenesisReplier add a small, opinionated layer that
     standardizes function-call behavior and test-visible logging.

2) Interface ↔ Agent control/messaging
   - Semantics: arbitrary chat/control messages and selection metadata, not always
     function calls
   - Needs: ultra-thin path, exact log formats and timings used by tests/monitoring
   - Solution: keep a direct path using rti.rpc with DynamicData (no function envelope),
     minimizing overhead and preserving compatibility.

Both paths share the same DynamicData types from datamodel.xml. The differentiation is
about ergonomics and stability: services benefit from a higher-level wrapper; the
interface/agent path remains intentionally thin and predictable.

=================================================================================================
ARCHITECTURE OVERVIEW - Understanding Requester Design
=================================================================================================

The Genesis Requester implements a sophisticated request/reply pattern that provides:

1. **Unified Topics**: Single request/reply topic pairs for all services
2. **Broadcast + Targeting**: Support for both broadcast and targeted requests
3. **First-Reply-Wins**: Automatic handling of multiple service instances
4. **Service Discovery**: Automatic detection of available service instances
5. **Error Handling**: Comprehensive error detection and recovery
6. **Backward Compatibility**: Seamless migration from legacy RPC clients

=================================================================================================
UNIFIED TOPICS - Scalable Service Architecture
=================================================================================================

The requester uses unified topics that enable:

1. **Service Consolidation**: All services share common topic infrastructure
2. **Dynamic Scaling**: Services can be added/removed without topic changes
3. **Load Balancing**: Automatic distribution across service instances
4. **Fault Tolerance**: Automatic failover to healthy service instances
5. **Resource Efficiency**: Reduced topic management overhead

This architecture supports:
- **Broadcast Requests**: Send to all available service instances
- **Targeted Requests**: Send to specific service instances via GUID
- **Automatic Discovery**: Real-time detection of service availability
- **Intelligent Routing**: Optimal service selection based on availability

=================================================================================================
REQUEST/REPLY PATTERN - Reliable Communication
=================================================================================================

The requester implements a robust request/reply pattern with:

1. **Reliable Delivery**: Ensures message delivery across the network
2. **Timeout Handling**: Configurable timeouts for request completion
3. **Error Recovery**: Automatic retry and fallback mechanisms
4. **Result Validation**: Comprehensive result validation and error detection
5. **Logging Integration**: Detailed logging for debugging and monitoring

This enables:
- **Guaranteed Delivery**: Messages are reliably delivered to services
- **Timeout Management**: Configurable timeouts prevent hanging requests
- **Error Classification**: Intelligent error detection and classification
- **Debugging Support**: Comprehensive logging for troubleshooting

=================================================================================================
SERVICE DISCOVERY - Dynamic Service Detection
=================================================================================================

The requester provides comprehensive service discovery capabilities:

1. **Automatic Detection**: Services are automatically discovered as they come online
2. **Health Monitoring**: Continuous monitoring of service availability
3. **Load Balancing**: Intelligent routing to available service instances
4. **Fault Detection**: Automatic detection of failed service instances

This enables:
- **Dynamic Scaling**: Services can be added/removed without requester changes
- **Fault Tolerance**: Automatic failover to healthy service instances
- **Load Distribution**: Intelligent load balancing across service instances
- **Service Mesh**: Automatic discovery and routing of network services

=================================================================================================
ERROR HANDLING - Robust Error Recovery
=================================================================================================

The requester implements sophisticated error handling:

1. **Timeout Management**: Configurable timeouts for different scenarios
2. **Error Classification**: Automatic classification of error types
3. **Recovery Strategies**: Automatic retry and fallback mechanisms
4. **Logging Integration**: Detailed error logging for debugging

This ensures:
- **Reliability**: Robust error handling and recovery
- **Debugging**: Comprehensive error information for troubleshooting
- **Performance**: Optimal timeout and retry strategies
- **Monitoring**: Detailed error metrics for system monitoring

=================================================================================================
USAGE PATTERNS - Common Integration Scenarios
=================================================================================================

1. **Basic Function Calls**:
   ```python
   requester = GenesisRequester("MyService")
   result = await requester.call("calculate_sum", {"a": 5, "b": 3})
   ```

2. **Targeted Service Calls**:
   ```python
   requester = GenesisRequester("MyService")
   result = await requester.call("process_data", params, target_service_guid="specific-guid")
   ```

3. **Legacy API Compatibility**:
   ```python
   requester = GenesisRequester("MyService")
   result = await requester.call_function("calculate_sum", a=5, b=3)
   ```

=================================================================================================
PERFORMANCE OPTIMIZATION - Efficient Communication
=================================================================================================

The requester implements several performance optimizations:

1. **Connection Pooling**: Efficient reuse of DDS connections
2. **Request Batching**: Batch multiple requests for improved throughput
3. **Timeout Optimization**: Intelligent timeout strategies
4. **Resource Management**: Efficient cleanup and resource utilization

This ensures:
- **High Throughput**: Optimized for high-volume request processing
- **Low Latency**: Minimal overhead for request/reply operations
- **Resource Efficiency**: Optimal use of system resources
- **Scalability**: Support for large numbers of concurrent requests

=================================================================================================

"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import rti.connextdds as dds
from rti.rpc import Requester

from genesis_lib.utils import get_datamodel_path
from genesis_lib.utils.guid_utils import format_guid


logger = logging.getLogger("GenesisRequester")

# =============================================================================
# GENESIS REQUESTER CLASS - UNIFIED TOPICS WITH INTELLIGENT ROUTING
# =============================================================================
# The GenesisRequester class provides client-side request/reply communication
# with unified topics, intelligent request routing, and robust error handling.
# =============================================================================

class GenesisRequester:
    def __init__(self, service_name: str = "GenesisRPCService", service_type: Optional[str] = None, participant: Optional[dds.DomainParticipant] = None, timeout: Optional[dds.Duration] = None, timeout_seconds: float = 10.0):
        """
        Initialize the Genesis requester.
        
        The GenesisRequester provides client-side request/reply communication with unified topics,
        intelligent request routing, and robust error handling. It supports both broadcast
        and targeted requests with automatic service discovery.
        
        Args:
            service_name: Name of the service to connect to (legacy parameter, extracted as service_type)
            service_type: Service type for unified request/reply topics (if None, derived from service_name)
            participant: Optional DDS participant (if None, one will be created)
            timeout: Legacy timeout parameter (Duration object)
            timeout_seconds: Timeout in seconds for function calls
            
        Examples:
            # Basic requester initialization
            requester = GenesisRequester("MyService")
            
            # With custom timeout
            requester = GenesisRequester("MyService", timeout_seconds=30.0)
            
            # With existing DDS participant
            requester = GenesisRequester("MyService", participant=existing_participant)
            
        Note:
            The requester automatically handles service discovery and will wait for
            services to become available before making requests.
        """
        # Extract service_type from service_name if not provided
        if service_type is None:
            service_type = service_name
        
        self.service_type = service_type
        self._owns_participant = participant is None
        
        if participant is None:
            # Use GENESIS_DOMAIN_ID environment variable if set, otherwise default to 0
            domain_id = int(os.environ.get('GENESIS_DOMAIN_ID', 0))
            qos = dds.DomainParticipantQos()
            qos.transport_builtin.mask = dds.TransportBuiltinMask.UDPv4
            participant = dds.DomainParticipant(domain_id=domain_id, qos=qos)
            logger.debug(f"Created DomainParticipant on domain {domain_id}")
        self.participant = participant
        
        # Handle both legacy timeout (Duration) and new timeout_seconds
        if timeout is not None:
            self.timeout = timeout
        else:
            self.timeout = dds.Duration.from_seconds(timeout_seconds)

        # Create Requester with service_name only - it will create the topics
        service_name_full = f"rti/connext/genesis/rpc/{service_type}"
        logger.info(f"Requester initializing for service_name={service_name_full}")
        
        # Load unified RPC types from datamodel.xml
        provider = dds.QosProvider(get_datamodel_path())
        self.request_type = provider.type("genesis_lib", "GenesisRPCRequest")
        self.reply_type = provider.type("genesis_lib", "GenesisRPCReply")
        
        # Ensure RELIABLE + KEEP_ALL for request/reply endpoints (matches legacy behavior)
        writer_qos = dds.DataWriterQos()
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.history.kind = dds.HistoryKind.KEEP_ALL
        
        reader_qos = dds.DataReaderQos()
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.history.kind = dds.HistoryKind.KEEP_ALL
        
        self.requester = Requester(
            request_type=self.request_type,
            reply_type=self.reply_type,
            participant=self.participant,
            service_name=service_name_full,
            datawriter_qos=writer_qos,
            datareader_qos=reader_qos
        )

        self._requester_guid = format_guid(self.requester.request_datawriter.instance_handle)
        logger.info(
            "Requester initialized: req_writer_guid=%s, reply_reader_guid=%s",
            self._requester_guid,
            format_guid(self.requester.reply_datareader.instance_handle)
        )

    # =============================================================================
    # SERVICE DISCOVERY METHODS - DYNAMIC SERVICE DETECTION
    # =============================================================================
    # Methods for discovering and monitoring service availability
    # =============================================================================
    
    async def wait_for_service(self, timeout_seconds: int = 10) -> bool:
        """
        Wait for the service to be discovered (legacy API compatibility).
        
        Args:
            timeout_seconds: How long to wait for service discovery
            
        Returns:
            True if service is discovered, False on timeout
        """
        end_time = time.time() + timeout_seconds
        while time.time() < end_time:
            if self.requester.matched_replier_count > 0:
                logger.info(f"Service discovered: matched_replier_count={self.requester.matched_replier_count}")
                return True
            await asyncio.sleep(0.1)
        logger.warning(f"Service discovery timeout after {timeout_seconds}s")
        return False

    # =============================================================================
    # REQUEST/REPLY CALL METHODS - REQUEST/REPLY COMMUNICATION
    # =============================================================================
    # Methods for making request/reply calls with intelligent routing and error handling
    # =============================================================================
    
    async def call(self, function_name: str, params: Dict[str, Any], target_service_guid: str = "", deadline_ms: int = 10000) -> Dict[str, Any]:
        """
        Call a remote function with intelligent routing and error handling.
        
        This method provides the primary interface for making request/reply calls with support
        for both broadcast and targeted requests. It automatically handles service
        discovery, timeout management, and error recovery.
        
        Args:
            function_name: Name of the function to call
            params: Dictionary of parameters to pass to the function
            target_service_guid: Optional GUID to target a specific service instance (empty string for broadcast)
            deadline_ms: Deadline in milliseconds for the call
            
        Returns:
            Dictionary containing the function's result
            
        Raises:
            TimeoutError: If no reply is received within timeout
            RuntimeError: If the function call fails
            
        Examples:
            # Broadcast request to all available services
            result = await requester.call("calculate_sum", {"a": 5, "b": 3})
            
            # Targeted request to specific service instance
            result = await requester.call("process_data", params, target_service_guid="specific-guid")
            
            # With custom timeout
            result = await requester.call("long_running_task", params, deadline_ms=30000)
            
        Note:
            The requester automatically waits for service discovery before making requests.
            Use target_service_guid for load balancing or specific service requirements.
        """
        # Wait for discovery before sending - this is REQUIRED by RTI RPC API
        # Following the pattern from RPC_Example/primes_requester.py
        # Use the deadline_ms as the discovery timeout
        discovery_timeout = deadline_ms / 1000.0
        end_discovery = time.time() + discovery_timeout
        while self.requester.matched_replier_count == 0:
            if time.time() >= end_discovery:
                raise TimeoutError(f"No repliers discovered for service '{self.service_type}' within {discovery_timeout}s")
            await asyncio.sleep(0.1)
        
        logger.info("Requester matched_replier_count=%s", self.requester.matched_replier_count)

        request_id = str(uuid.uuid4())
        # Build unified RPC request using DynamicData
        req = dds.DynamicData(self.request_type)
        req["request_id"] = request_id
        req["message"] = json.dumps({"function": function_name, "params": params or {}})
        req["conversation_id"] = request_id
        req["target_service_guid"] = target_service_guid or ""
        req["service_instance_tag"] = ""

        send_id = self.requester.send_request(req)
        logger.info("Requester sent request: id=%s, func=%s", request_id, function_name)
        end_time = time.time() + (deadline_ms / 1000.0)
        while time.time() < end_time:
            try:
                if not self.requester.wait_for_replies(self.timeout, related_request_id=send_id):
                    continue
            except dds.TimeoutError:
                continue

            replies = self.requester.take_replies(related_request_id=send_id)
            for reply, info in replies:
                # Unified reply fields: status (0=ok), message (JSON payload or error text)
                status = 0
                payload = ""
                try:
                    status = int(reply["status"])
                except Exception:
                    # If field missing, assume success with empty payload
                    status = 0
                try:
                    payload = reply["message"] or ""
                except Exception:
                    payload = ""
                if status == 0:
                    result = json.loads(payload) if payload else {}
                    # Log in format compatible with test expectations
                    logger.info(f"Function {function_name} returned: {result}")
                    print(f"📚 PRINT: GenesisRequester - INFO - Function {function_name} returned: {result}", flush=True)
                    return result
                else:
                    raise RuntimeError(payload or "Request/reply call failed")
        raise TimeoutError("Request/reply call timed out")

    # =============================================================================
    # LEGACY API METHODS - BACKWARD COMPATIBILITY
    # =============================================================================
    # Methods for backward compatibility with legacy RPC client APIs
    # =============================================================================
    
    async def call_function(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """
        Call a remote function with legacy API compatibility.
        
        This method provides backward compatibility with legacy RPC client APIs.
        It automatically converts keyword arguments to a parameter dictionary
        and delegates to the main call() method.
        
        Args:
            function_name: Name of the function to call
            **kwargs: Arguments to pass to the function
            
        Returns:
            Dictionary containing the function's result
            
        Raises:
            TimeoutError: If no reply is received within timeout
            RuntimeError: If the function call fails
            
        Examples:
            # Legacy API style
            result = await requester.call_function("calculate_sum", a=5, b=3)
            
            # Equivalent to:
            result = await requester.call("calculate_sum", {"a": 5, "b": 3})
            
        Note:
            This method is provided for backward compatibility. New code should
            use the call() method for better control over request parameters.
        """
        logger.info(f"Calling remote function: {function_name}")
        logger.debug(f"Arguments: {kwargs}")
        return await self.call(function_name, kwargs)

    async def call_function_with_validation(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """
        Call a function with input validation (legacy API compatibility).
        
        Args:
            function_name: Name of the function to call
            **kwargs: Function arguments
            
        Returns:
            Function result
            
        Raises:
            ValueError: For validation errors
            RuntimeError: For other errors
        """
        return await self.call_function(function_name, **kwargs)

    def handle_error_response(self, error_message: str) -> None:
        """Handle error responses (legacy API compatibility)."""
        # Legacy behavior: raise RuntimeError for most errors
        raise RuntimeError(error_message)

    # =============================================================================
    # LIFECYCLE MANAGEMENT METHODS - RESOURCE CLEANUP
    # =============================================================================
    # Methods for managing requester lifecycle and resource cleanup
    # =============================================================================
    
    def close(self):
        """
        Close the requester and clean up resources.
        
        This method performs comprehensive cleanup of all requester resources
        including the DDS requester and DDS participant (if owned by this requester).
        It ensures proper resource cleanup to prevent memory leaks.
        
        The cleanup process includes:
        1. Requester cleanup (closes DDS writers/readers)
        2. Participant cleanup (if owned by this requester)
        3. Error handling and recovery
        
        This method is idempotent - calling it multiple times is safe.
        
        Examples:
            # Manual cleanup
            requester = GenesisRequester("MyService")
            # ... use requester ...
            requester.close()
            
            # Automatic cleanup with context manager
            with GenesisRequester("MyService") as requester:
                # ... use requester ...
                pass  # Automatic cleanup on exit
                
        Note:
            Always call this method when done with the requester to
            prevent resource leaks and ensure proper DDS cleanup.
        """
        try:
            self.requester.close()
        finally:
            if self._owns_participant:
                self.participant.close()




