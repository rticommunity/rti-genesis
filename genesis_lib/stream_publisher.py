"""
StreamPublisher — Publishes StreamChunk events to a DDS topic.

Used by agents to broadcast real-time streaming events (tool usage, text output,
errors) alongside the existing RPC request/reply model.
"""

import json
import logging
import time
import threading

import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path

logger = logging.getLogger(__name__)

TOPIC_NAME = "rti/connext/genesis/streaming/StreamChunk"

# Reuse topic instances per participant to avoid duplicates
_TOPIC_REGISTRY = {}


class StreamPublisher:
    """Publishes StreamChunk events to a DDS topic."""

    def __init__(self, participant):
        config_path = get_datamodel_path()
        provider = dds.QosProvider(config_path)
        self._type = provider.type("genesis_lib", "StreamChunk")

        pid = id(participant)
        key = (pid, TOPIC_NAME)
        if key in _TOPIC_REGISTRY:
            topic = _TOPIC_REGISTRY[key]
        else:
            topic = dds.DynamicData.Topic(participant, TOPIC_NAME, self._type)
            _TOPIC_REGISTRY[key] = topic

        qos = dds.QosProvider.default.datawriter_qos
        qos.durability.kind = dds.DurabilityKind.VOLATILE
        qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        qos.history.kind = dds.HistoryKind.KEEP_ALL

        publisher = dds.Publisher(participant)
        self._writer = dds.DynamicData.DataWriter(
            pub=publisher, topic=topic, qos=qos,
        )
        self._sequences = {}  # request_id -> next sequence number
        self._lock = threading.Lock()

    def publish(self, request_id, chunk_type, content="", metadata=""):
        """Write a StreamChunk sample with auto-incrementing sequence."""
        with self._lock:
            seq = self._sequences.get(request_id, 0)
            self._sequences[request_id] = seq + 1

        sample = dds.DynamicData(self._type)
        sample["request_id"] = request_id
        sample["sequence"] = seq
        sample["chunk_type"] = chunk_type
        sample["content"] = content
        if isinstance(metadata, dict):
            metadata = json.dumps(metadata)
        sample["metadata"] = metadata or ""
        sample["timestamp"] = int(time.time() * 1000)

        self._writer.write(sample)
        logger.debug(
            "StreamPublisher: published chunk request_id=%s seq=%d type=%s",
            request_id, seq, chunk_type,
        )

    def close(self):
        """Clean up sequence tracking."""
        with self._lock:
            self._sequences.clear()
