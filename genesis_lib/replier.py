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
Genesis Replier - Unified Topics with Intelligent Request Handling

Service-side implementation using unified topics with intelligent request handling.
Supports both broadcast and targeted requests with automatic load balancing and
fault tolerance capabilities.

ARCHITECTURAL DECISION: Wrapper vs. direct RPC usage
====================================================
Genesis employs a unified DDS data model (GenesisRPCRequest/Reply) for all RPC traffic.
This wrapper is used for service function execution because it provides:
- Function registry and invocation helpers
- Standardized JSON packing/unpacking
- Consistent logs and simple error mapping (status/message)

For the Interface ↔ Agent path, Genesis intentionally uses a thinner, direct rti.rpc +
DynamicData approach to keep control messages flexible and to preserve exact log formats
and timings required by tests and monitoring. Both paths use the same types; the choice
is about ergonomics and stability, not data model differences.
"""

import json
import logging
import time
import inspect
from typing import Dict, Any, Optional

import rti.connextdds as dds
from rti.rpc import Replier

from genesis_lib.utils import get_datamodel_path
from genesis_lib.utils.guid_utils import format_guid


logger = logging.getLogger("GenesisReplier")

# =============================================================================
# GENESIS REPLIER CLASS - UNIFIED TOPICS WITH INTELLIGENT HANDLING
# =============================================================================
# The GenesisReplier class provides service-side request/reply communication
# with unified topics, intelligent request handling, and robust error management.
# =============================================================================

class GenesisReplier:
    def __init__(self, service_name: Optional[str] = None, service_type: Optional[str] = None, participant: Optional[dds.DomainParticipant] = None):
        """
        Initialize the replier service.
        
        Args:
            service_name: Name of the service (legacy parameter, used as service_type if service_type not provided)
            service_type: Service type for unified request/reply topics (if None, uses service_name)
            participant: Optional DDS participant (if None, one will be created on domain 0 or GENESIS_DOMAIN_ID env var)
        """
        # Accept either service_name (legacy) or service_type (new)
        if service_type is None and service_name is None:
            raise ValueError("Either service_name or service_type must be provided")
        
        self.service_type = service_type if service_type is not None else service_name
        
        if participant is None:
            # Read from environment if not explicitly provided
            import os
            domain_id = int(os.environ.get('GENESIS_DOMAIN_ID', 0))
            qos = dds.DomainParticipantQos()
            qos.transport_builtin.mask = dds.TransportBuiltinMask.UDPv4
            participant = dds.DomainParticipant(domain_id=domain_id, qos=qos)
            logger.debug(f"Created DomainParticipant on domain {domain_id} for {self.service_type}")
        self.participant = participant

        # Load unified RPC types from datamodel.xml
        provider = dds.QosProvider(get_datamodel_path())
        self.request_type = provider.type("genesis_lib", "GenesisRPCRequest")
        self.reply_type = provider.type("genesis_lib", "GenesisRPCReply")

        # Create Replier with unified types; let it create topics automatically
        writer_qos = dds.DataWriterQos()
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.history.kind = dds.HistoryKind.KEEP_ALL
        
        reader_qos = dds.DataReaderQos()
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.history.kind = dds.HistoryKind.KEEP_ALL
        
        self.replier = Replier(
            request_type=self.request_type,
            reply_type=self.reply_type,
            participant=self.participant,
            service_name=f"rti/connext/genesis/rpc/{self.service_type}",
            datawriter_qos=writer_qos,
            datareader_qos=reader_qos
        )
        # Self GUID for targeted checks
        self_guid = format_guid(self.replier.reply_datawriter.instance_handle)
        logger.info(
            "Replier initialized: reader_guid=%s, writer_guid=%s",
            format_guid(self.replier.request_datareader.instance_handle),
            self_guid
        )
        try:
            logger.info("Replier matched_requester_count=%s", self.replier.matched_requester_count)
        except Exception:
            pass

        # Function registry provided by service base via register_function
        self.functions: Dict[str, Any] = {}

    def register_function(self, func, description: str, parameters: Dict[str, Any], 
                         operation_type: Optional[str] = None, 
                         common_patterns: Optional[Dict[str, Any]] = None):
        """
        Register a function with the replier service (compatibility with legacy API).
        
        Args:
            func: The function implementation
            description: Function description
            parameters: Function parameters schema
            operation_type: Optional operation type classification
            common_patterns: Optional common validation patterns
            
        Returns:
            The registered function
        """
        func_name = func.__name__ if hasattr(func, '__name__') else str(func)
        
        # Store function metadata using SimpleNamespace to preserve attribute-style access
        import json
        from types import SimpleNamespace
        params_json = json.dumps(parameters) if isinstance(parameters, dict) else parameters
        function_def = SimpleNamespace(
            name=func_name,
            description=description,
            parameters=params_json,
            strict=True
        )
        tool = SimpleNamespace(type="function", function=function_def)
        self.functions[func_name] = {
            "tool": tool,
            "implementation": func,
            "operation_type": operation_type,
            "common_patterns": common_patterns
        }
        
        logger.info(f"Registered function: {func_name}")
        return func
    
    def get_request_type(self):
        """Get the request type for request/reply communication (legacy compatibility)."""
        return self.request_type
    
    def get_reply_type(self):
        """Get the reply type for request/reply communication (legacy compatibility)."""
        return self.reply_type

    def _should_abort_broadcast(self, request_id: str, self_guid: str) -> bool:
        # Attempt to detect an existing reply for this request_id.
        # If any error occurs (e.g., type/constructor mismatch), default to not aborting.
        temp_reader = None
        try:
            reply_topic = self.replier.reply_datawriter.topic
            reply_cft = dds.ContentFilteredTopic(
                reply_topic,
                f"Filtered{self.service_type}Reply_{request_id}",
                dds.Filter("request_id = %0", dds.StringSeq([f"'{request_id}'"]))
            )
            temp_reader = dds.DataReader(dds.Subscriber(self.participant), reply_cft)
            samples = temp_reader.read()
            for sample in samples:
                if sample.info.valid:
                    data = sample.data
                    try:
                        guid = data["replier_service_guid"]
                    except Exception:
                        guid = getattr(data, "replier_service_guid", "")
                    if guid and guid != self_guid:
                        return True
            return False
        except Exception:
            return False
        finally:
            try:
                if temp_reader is not None:
                    temp_reader.close()
            except Exception:
                pass

    async def _execute(self, function_name: str, arguments_json: str):
        start_ns = time.time_ns()
        func_data = self.functions.get(function_name)
        if func_data is None:
            raise RuntimeError(f"Unknown function: {function_name}")
        
        # Extract implementation from function data structure
        impl = func_data.get("implementation") if isinstance(func_data, dict) else func_data
        if impl is None:
            raise RuntimeError(f"No implementation for function: {function_name}")
        
        args = json.loads(arguments_json) if arguments_json else {}
        result = impl(**args)
        if inspect.iscoroutine(result):
            result = await result
        latency_ms = int((time.time_ns() - start_ns) / 1_000_000)
        return result, latency_ms

    async def run(self):
        try:
            logger.info("Replier run() called, initializing...")
            max_wait = dds.Duration.from_seconds(1)
            self_guid = format_guid(self.replier.reply_datawriter.instance_handle)
            logger.info("Replier service run loop started, self_guid=%s, waiting for requests...", self_guid)
        except Exception as e:
            logger.exception("Replier run() initialization failed: %s", e)
            raise
        while True:
            try:
                requests = self.replier.receive_requests(max_wait)
                if requests:
                    logger.info("Replier received %d requests", len(requests))
                for req_sample in requests:
                    if not req_sample.info.valid:
                        logger.debug("Replier skipping invalid request sample")
                        continue
                    req = req_sample.data
                    logger.info(
                        "Replier received request"
                    )
                    # Extract targeting and payload from unified request
                    try:
                        target_guid = req["target_service_guid"]
                    except Exception:
                        target_guid = ""
                    targeted = bool(target_guid)
                    if targeted and target_guid != self_guid:
                        continue
                    if not targeted:
                        try:
                            request_id = req["request_id"]
                        except Exception:
                            request_id = ""
                        if request_id and self._should_abort_broadcast(request_id, self_guid):
                            continue
                    # Decode function call from message JSON
                    try:
                        payload = req["message"] or "{}"
                    except Exception:
                        payload = "{}"
                    try:
                        call = json.loads(payload)
                    except Exception:
                        call = {}
                    function_name = call.get("function", "")
                    params = call.get("params", {})
                    # Execute and build unified reply
                    reply_sample = dds.DynamicData(self.reply_type)
                    try:
                        result, latency_ms = await self._execute(function_name, json.dumps(params))
                        try:
                            reply_sample["request_id"] = req["request_id"]
                            reply_sample["message"] = json.dumps(result)
                            reply_sample["status"] = 0
                            reply_sample["conversation_id"] = req.get("conversation_id", "") if hasattr(req, "get") else req["conversation_id"]
                            reply_sample["replier_service_guid"] = self_guid
                            reply_sample["service_instance_tag"] = ""
                        except Exception:
                            # Best-effort population; continue
                            pass
                    except Exception as e:
                        try:
                            reply_sample["request_id"] = req["request_id"]
                            reply_sample["message"] = str(e)
                            reply_sample["status"] = 1
                            reply_sample["conversation_id"] = req.get("conversation_id", "") if hasattr(req, "get") else req["conversation_id"]
                            reply_sample["replier_service_guid"] = self_guid
                            reply_sample["service_instance_tag"] = ""
                        except Exception:
                            pass
                    self.replier.send_reply(reply_sample, req_sample.info)
            except dds.TimeoutError:
                pass

    def close(self):
        try:
            self.replier.close()
        finally:
            self.participant.close()



