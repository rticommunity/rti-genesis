"""
Genesis RPC Service V2 (Unified Topics with Broadcast + First-Reply-Wins)

Service-side implementation using a unified request topic with a ContentFilteredTopic
to receive broadcast requests (target_service_guid='') or requests targeted to this
specific instance. For broadcast requests, the service observes the reply stream for
the same request_id and aborts early if another instance already replied.
"""

import json
import logging
import time
import inspect
from typing import Dict, Any, Optional

import rti.connextdds as dds
from rti.rpc import Replier

from genesis_lib.datamodel import RPCRequestV2, RPCReplyV2
from genesis_lib.utils.guid_utils import format_guid


logger = logging.getLogger("GenesisRPCServiceV2")


class GenesisRPCServiceV2:
    def __init__(self, service_name: Optional[str] = None, service_type: Optional[str] = None, participant: Optional[dds.DomainParticipant] = None):
        """
        Initialize the RPC service.
        
        Args:
            service_name: Name of the service (legacy parameter, used as service_type if service_type not provided)
            service_type: Service type for unified RPC topics (if None, uses service_name)
            participant: Optional DDS participant (if None, one will be created)
        """
        # Accept either service_name (legacy) or service_type (new)
        if service_type is None and service_name is None:
            raise ValueError("Either service_name or service_type must be provided")
        
        self.service_type = service_type if service_type is not None else service_name
        
        if participant is None:
            qos = dds.DomainParticipantQos()
            qos.transport_builtin.mask = dds.TransportBuiltinMask.UDPv4
            participant = dds.DomainParticipant(domain_id=0, qos=qos)
        self.participant = participant

        request_topic_name = f"rti/connext/genesis/rpc/{self.service_type}Request"
        reply_topic_name = f"rti/connext/genesis/rpc/{self.service_type}Reply"

        self._request_topic = dds.Topic(self.participant, request_topic_name, RPCRequestV2)
        self._reply_topic = dds.Topic(self.participant, reply_topic_name, RPCReplyV2)

        # Configure QoS for Request/Reply pattern (must be RELIABLE + KEEP_ALL)
        writer_qos = dds.DataWriterQos()
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.history.kind = dds.HistoryKind.KEEP_ALL
        
        reader_qos = dds.DataReaderQos()
        reader_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        reader_qos.history.kind = dds.HistoryKind.KEEP_ALL

        # Create Replier with service_name only - let it create topics automatically
        # This matches what the Requester does
        self.replier = Replier(
            request_type=RPCRequestV2,
            reply_type=RPCReplyV2,
            participant=self.participant,
            service_name=f"rti/connext/genesis/rpc/{self.service_type}",
            datawriter_qos=writer_qos,
            datareader_qos=reader_qos
        )
        # Self GUID for targeted checks
        self_guid = format_guid(self.replier.reply_datawriter.instance_handle)
        logger.info(
            "RPC v2 replier initialized: reader_guid=%s, writer_guid=%s",
            format_guid(self.replier.request_datareader.instance_handle),
            self_guid
        )
        try:
            logger.info("RPC v2 matched_requester_count=%s", self.replier.matched_requester_count)
        except Exception:
            pass

        # Function registry provided by EnhancedServiceBase via register_function
        self.functions: Dict[str, Any] = {}

    def register_function(self, func, description: str, parameters: Dict[str, Any], 
                         operation_type: Optional[str] = None, 
                         common_patterns: Optional[Dict[str, Any]] = None):
        """
        Register a function with the service (compatibility with legacy API).
        
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
        
        # Create a simple tool definition for compatibility
        from genesis_lib.datamodel import Tool, Function as FunctionDef
        import json
        
        # Store function with metadata matching legacy format
        function_def = FunctionDef(
            name=func_name,
            description=description,
            parameters=json.dumps(parameters) if isinstance(parameters, dict) else parameters
        )
        tool = Tool(type="function", function=function_def)
        
        self.functions[func_name] = {
            "tool": tool,
            "implementation": func,
            "operation_type": operation_type,
            "common_patterns": common_patterns
        }
        
        logger.info(f"Registered function: {func_name}")
        return func
    
    def get_request_type(self):
        """Get the request type for RPC communication (legacy compatibility)."""
        return RPCRequestV2
    
    def get_reply_type(self):
        """Get the reply type for RPC communication (legacy compatibility)."""
        return RPCReplyV2

    def _should_abort_broadcast(self, request_id: str, self_guid: str) -> bool:
        # Get the reply topic from the replier's writer
        reply_topic = self.replier.reply_datawriter.topic
        reply_cft = dds.ContentFilteredTopic(
            reply_topic,
            f"Filtered{self.service_type}Reply_{request_id}",
            dds.Filter("request_id = %0", dds.StringSeq([f"'{request_id}'"]))
        )
        temp_reader = dds.DataReader(dds.Subscriber(self.participant), reply_cft)
        try:
            samples = temp_reader.read()
            for sample in samples:
                if sample.info.valid:
                    if sample.data.replier_service_guid and sample.data.replier_service_guid != self_guid:
                        return True
            return False
        finally:
            temp_reader.close()

    async def _execute(self, function_name: str, arguments_json: str) -> RPCReplyV2:
        start_ns = time.time_ns()
        try:
            func_data = self.functions.get(function_name)
            if func_data is None:
                return RPCReplyV2(
                    ok=False,
                    error_code="UnknownFunction",
                    error_message=f"Unknown function: {function_name}",
                    result_json=""
                )
            
            # Extract implementation from function data structure
            if isinstance(func_data, dict):
                impl = func_data.get("implementation")
            else:
                impl = func_data
            
            if impl is None:
                return RPCReplyV2(
                    ok=False,
                    error_code="UnknownFunction",
                    error_message=f"No implementation for function: {function_name}",
                    result_json=""
                )
            
            args = json.loads(arguments_json) if arguments_json else {}
            result = impl(**args)
            if inspect.iscoroutine(result):
                result = await result
            result_json = json.dumps(result)
            latency_ms = int((time.time_ns() - start_ns) / 1_000_000)
            return RPCReplyV2(ok=True, result_json=result_json, latency_ms=latency_ms)
        except Exception as e:
            latency_ms = int((time.time_ns() - start_ns) / 1_000_000)
            return RPCReplyV2(ok=False, error_code="Internal", error_message=str(e), result_json="", latency_ms=latency_ms)

    async def run(self):
        try:
            logger.info("RPC v2 run() called, initializing...")
            max_wait = dds.Duration.from_seconds(1)
            self_guid = format_guid(self.replier.reply_datawriter.instance_handle)
            logger.info("RPC v2 service run loop started, self_guid=%s, waiting for requests...", self_guid)
        except Exception as e:
            logger.exception("RPC v2 run() initialization failed: %s", e)
            raise
        while True:
            try:
                requests = self.replier.receive_requests(max_wait)
                if requests:
                    logger.info("RPC v2 received %d requests", len(requests))
                for req_sample in requests:
                    if not req_sample.info.valid:
                        logger.debug("RPC v2 skipping invalid request sample")
                        continue
                    req = req_sample.data
                    logger.info(
                        "RPC v2 received request: id=%s func=%s target_guid=%s",
                        req.request_id, req.function_name, req.target_service_guid
                    )
                    targeted = bool(req.target_service_guid)
                    if targeted and req.target_service_guid != self_guid:
                        continue
                    if not targeted:
                        if self._should_abort_broadcast(req.request_id, self_guid):
                            continue
                    reply = await self._execute(req.function_name, req.parameters_json)
                    reply.request_id = req.request_id
                    reply.service_type = req.service_type
                    reply.replier_service_guid = self_guid
                    self.replier.send_reply(reply, req_sample.info)
            except dds.TimeoutError:
                pass

    def close(self):
        try:
            self.replier.close()
        finally:
            self.participant.close()


