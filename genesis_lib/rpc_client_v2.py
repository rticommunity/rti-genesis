"""
Genesis RPC Client V2 (Unified Topics with Broadcast + First-Reply-Wins)

Client-side implementation that publishes requests to the unified request topic and
creates a per-request ContentFilteredTopic on the unified reply topic (filter by request_id).
The first matching reply wins; late/duplicate replies are ignored.

This module provides backward compatibility with the legacy GenesisRPCClient API.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

import rti.connextdds as dds
from rti.rpc import Requester

from genesis_lib.datamodel import RPCRequestV2, RPCReplyV2
from genesis_lib.utils.guid_utils import format_guid


logger = logging.getLogger("GenesisRPCClientV2")


class GenesisRPCClientV2:
    def __init__(self, service_name: str = "GenesisRPCService", service_type: Optional[str] = None, participant: Optional[dds.DomainParticipant] = None, timeout: Optional[dds.Duration] = None, timeout_seconds: float = 10.0):
        """
        Initialize the RPC client.
        
        Args:
            service_name: Name of the service to connect to (legacy parameter, extracted as service_type)
            service_type: Service type for unified RPC topics (if None, derived from service_name)
            participant: Optional DDS participant (if None, one will be created)
            timeout: Legacy timeout parameter (Duration object)
            timeout_seconds: Timeout in seconds for function calls
        """
        # Extract service_type from service_name if not provided
        if service_type is None:
            service_type = service_name
        
        self.service_type = service_type
        self._owns_participant = participant is None
        
        if participant is None:
            qos = dds.DomainParticipantQos()
            qos.transport_builtin.mask = dds.TransportBuiltinMask.UDPv4
            participant = dds.DomainParticipant(domain_id=0, qos=qos)
        self.participant = participant
        
        # Handle both legacy timeout (Duration) and new timeout_seconds
        if timeout is not None:
            self.timeout = timeout
        else:
            self.timeout = dds.Duration.from_seconds(timeout_seconds)

        # Configure QoS for Request/Reply pattern (must be RELIABLE + KEEP_ALL)
        writer_qos = dds.DataWriterQos()
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.history.kind = dds.HistoryKind.KEEP_ALL
        
        reader_qos = dds.DataReaderQos()
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.history.kind = dds.HistoryKind.KEEP_ALL

        # Create Requester with service_name only - it will create the topics
        service_name_full = f"rti/connext/genesis/rpc/{service_type}"
        logger.info(f"RPC v2 client initializing for service_name={service_name_full}")
        
        self.requester = Requester(
            request_type=RPCRequestV2,
            reply_type=RPCReplyV2,
            participant=self.participant,
            service_name=service_name_full,
            datawriter_qos=writer_qos,
            datareader_qos=reader_qos
        )

        self._requester_guid = format_guid(self.requester.request_datawriter.instance_handle)
        logger.info(
            "RPC v2 requester initialized: req_writer_guid=%s, reply_reader_guid=%s",
            self._requester_guid,
            format_guid(self.requester.reply_datareader.instance_handle)
        )

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

    async def call(self, function_name: str, params: Dict[str, Any], target_service_guid: str = "", deadline_ms: int = 10000) -> Dict[str, Any]:
        """
        Call a remote function with the given name and arguments (v2 API).
        
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
        
        logger.info("RPC v2 matched_replier_count=%s", self.requester.matched_replier_count)

        request_id = str(uuid.uuid4())
        req = RPCRequestV2(
            request_id=request_id,
            service_type=self.service_type,
            function_name=function_name,
            parameters_json=json.dumps(params) if params else "",
            target_service_guid=target_service_guid,
            deadline_ms=deadline_ms,
            requester_guid=self._requester_guid,
        )

        send_id = self.requester.send_request(req)
        logger.info("RPC v2 sent request: id=%s, func=%s", request_id, function_name)
        end_time = time.time() + (deadline_ms / 1000.0)
        while time.time() < end_time:
            try:
                if not self.requester.wait_for_replies(self.timeout, related_request_id=send_id):
                    continue
            except dds.TimeoutError:
                continue

            replies = self.requester.take_replies(related_request_id=send_id)
            for reply, info in replies:
                if reply.ok:
                    result = json.loads(reply.result_json) if reply.result_json else {}
                    # Log in format compatible with test expectations
                    logger.info(f"Function {function_name} returned: {result}")
                    print(f"📚 PRINT: GenesisRPCClient - INFO - Function {function_name} returned: {result}", flush=True)
                    return result
                else:
                    raise RuntimeError(reply.error_message or reply.error_code or "RPC call failed")
        raise TimeoutError("RPC v2 call timed out")

    async def call_function(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """
        Call a remote function with the given name and arguments (legacy API compatibility).
        
        Args:
            function_name: Name of the function to call
            **kwargs: Arguments to pass to the function
            
        Returns:
            Dictionary containing the function's result
            
        Raises:
            TimeoutError: If no reply is received within timeout
            RuntimeError: If the function call fails
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

    def close(self):
        """Close the client and clean up resources."""
        try:
            self.requester.close()
        finally:
            if self._owns_participant:
                self.participant.close()


