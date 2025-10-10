"""
Genesis RPC Client V2 (Unified Topics with Broadcast + First-Reply-Wins)

Client-side implementation that publishes requests to the unified request topic and
creates a per-request ContentFilteredTopic on the unified reply topic (filter by request_id).
The first matching reply wins; late/duplicate replies are ignored.
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
    def __init__(self, service_type: str, participant: Optional[dds.DomainParticipant] = None, timeout_seconds: float = 3.0):
        self.service_type = service_type
        self.participant = participant or dds.DomainParticipant(domain_id=0)
        self.timeout = dds.Duration.from_seconds(timeout_seconds)

        request_topic_name = f"rti/connext/genesis/rpc/{service_type}Request"
        reply_topic_name = f"rti/connext/genesis/rpc/{service_type}Reply"

        self._request_topic = dds.Topic(self.participant, request_topic_name, RPCRequestV2)
        self._reply_topic = dds.Topic(self.participant, reply_topic_name, RPCReplyV2)

        self.requester = Requester(
            request_type=RPCRequestV2,
            reply_type=RPCReplyV2,
            participant=self.participant,
            service_name=service_type,
            request_topic=self._request_topic,
            reply_topic=self._reply_topic,
        )

        self._requester_guid = format_guid(self.requester.request_datawriter.instance_handle)

    async def call(self, function_name: str, params: Dict[str, Any], target_service_guid: str = "", deadline_ms: int = 3000) -> Dict[str, Any]:
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

        # Create per-request filtered reply reader
        reply_cft = dds.ContentFilteredTopic(
            self._reply_topic,
            f"Filtered{self.service_type}Reply_{request_id}",
            dds.Filter("request_id = %0", dds.StringSeq([request_id]))
        )
        per_request_reader = dds.DataReader(dds.Subscriber(self.participant), reply_cft)

        try:
            send_id = self.requester.send_request(req)
            end_time = time.time() + (deadline_ms / 1000.0)
            while time.time() < end_time:
                try:
                    if not self.requester.wait_for_replies(self.timeout, related_request_id=send_id):
                        continue
                except dds.TimeoutError:
                    continue

                # Read via our per-request reader (ensures isolation)
                samples = per_request_reader.read()
                for sample in samples:
                    if not sample.info.valid:
                        continue
                    reply: RPCReplyV2 = sample.data
                    if reply.ok:
                        return json.loads(reply.result_json) if reply.result_json else {}
                    else:
                        raise RuntimeError(reply.error_message or reply.error_code or "RPC call failed")
            raise TimeoutError("RPC v2 call timed out")
        finally:
            per_request_reader.close()

    def close(self):
        try:
            self.requester.close()
        finally:
            self.participant.close()


