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
from typing import Dict, Any, Optional

import rti.connextdds as dds
from rti.rpc import Replier

from genesis_lib.datamodel import RPCRequestV2, RPCReplyV2
from genesis_lib.utils.guid_utils import format_guid


logger = logging.getLogger("GenesisRPCServiceV2")


class GenesisRPCServiceV2:
    def __init__(self, service_type: str, participant: Optional[dds.DomainParticipant] = None):
        self.service_type = service_type
        self.participant = participant or dds.DomainParticipant(domain_id=0)

        request_topic_name = f"rti/connext/genesis/rpc/{service_type}Request"
        reply_topic_name = f"rti/connext/genesis/rpc/{service_type}Reply"

        # Unified topics
        self._request_topic = dds.Topic(self.participant, request_topic_name, RPCRequestV2)
        self._reply_topic = dds.Topic(self.participant, reply_topic_name, RPCReplyV2)

        # CFT on requests: broadcast or targeted-to-self
        self._cft = dds.ContentFilteredTopic(
            self._request_topic,
            f"Filtered{service_type}Request",
            dds.Filter("target_service_guid = %0 OR target_service_guid = %1", dds.StringSeq(["", ""]))
        )

        # Create replier bound to the filtered request topic
        self.replier = Replier(
            request_type=RPCRequestV2,
            reply_type=RPCReplyV2,
            participant=self.participant,
            service_name=service_type,
            request_topic=self._cft,
        )

        # After creation, set filter parameter #1 to this instance's writer GUID
        self_guid = format_guid(self.replier.reply_datawriter.instance_handle)
        self._cft.filter_parameters = dds.StringSeq(["", f"{self_guid}"])

        # For arbitration checks
        self._reply_reader = dds.DataReader(
            dds.Subscriber(self.participant), self._reply_topic
        )

        # Function registry provided by EnhancedServiceBase via register_function
        self.functions: Dict[str, Any] = {}

    def register_function(self, name: str, func):
        self.functions[name] = func

    def _should_abort_broadcast(self, request_id: str, self_guid: str) -> bool:
        # Create a per-request CFT on replies
        reply_cft = dds.ContentFilteredTopic(
            self._reply_topic,
            f"Filtered{self.service_type}Reply_{request_id}",
            dds.Filter("request_id = %0", dds.StringSeq([request_id]))
        )
        temp_reader = dds.DataReader(dds.Subscriber(self.participant), reply_cft)
        try:
            samples = temp_reader.read()
            for sample in samples:
                if sample.info.valid:
                    # If someone replied and it's not us, abort
                    if sample.data.replier_service_guid and sample.data.replier_service_guid != self_guid:
                        return True
            return False
        finally:
            temp_reader.close()

    def _execute(self, function_name: str, arguments_json: str) -> RPCReplyV2:
        start_ns = time.time_ns()
        try:
            impl = self.functions.get(function_name)
            if impl is None:
                return RPCReplyV2(
                    ok=False,
                    error_code="UnknownFunction",
                    error_message=f"Unknown function: {function_name}",
                    result_json=""
                )
            args = json.loads(arguments_json) if arguments_json else {}
            result = impl(**args)
            result_json = json.dumps(result)
            latency_ms = int((time.time_ns() - start_ns) / 1_000_000)
            return RPCReplyV2(ok=True, result_json=result_json, latency_ms=latency_ms)
        except Exception as e:
            latency_ms = int((time.time_ns() - start_ns) / 1_000_000)
            return RPCReplyV2(ok=False, error_code="Internal", error_message=str(e), result_json="", latency_ms=latency_ms)

    async def run(self):
        max_wait = dds.Duration.from_seconds(1)
        self_guid = format_guid(self.replier.reply_datawriter.instance_handle)
        while True:
            try:
                requests = self.replier.receive_requests(max_wait)
                for req_sample in requests:
                    if not req_sample.info.valid:
                        continue
                    req: RPCRequestV2 = req_sample.data
                    # Targeted request → process directly
                    targeted = bool(req.target_service_guid)
                    if targeted and req.target_service_guid != self_guid:
                        continue

                    # Broadcast → check arbitration (if someone else replied first, abort)
                    if not targeted:
                        if self._should_abort_broadcast(req.request_id, self_guid):
                            continue

                    reply = self._execute(req.function_name, req.parameters_json)
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


