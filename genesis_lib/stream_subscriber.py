"""
StreamSubscriber — Subscribes to StreamChunk events from a DDS topic.

Used by web servers and monitoring tools to receive real-time streaming events
published by agents during task execution.
"""

import json
import logging
import threading
import time

import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path
from genesis_lib.stream_publisher import TOPIC_NAME, _TOPIC_REGISTRY

logger = logging.getLogger(__name__)


class StreamSubscriber:
    """Subscribes to StreamChunk events, optionally filtered by request_id."""

    def __init__(self, participant, callback, request_id_filter=None):
        """
        Args:
            participant: DDS DomainParticipant.
            callback: Called with a dict for each received chunk:
                {request_id, sequence, chunk_type, content, metadata, timestamp}
            request_id_filter: If set, only receive chunks for this request_id.
        """
        config_path = get_datamodel_path()
        provider = dds.QosProvider(config_path)
        self._type = provider.type("genesis_lib", "StreamChunk")
        self._callback = callback
        self._running = True

        pid = id(participant)
        key = (pid, TOPIC_NAME)
        if key in _TOPIC_REGISTRY:
            topic = _TOPIC_REGISTRY[key]
        else:
            topic = dds.DynamicData.Topic(participant, TOPIC_NAME, self._type)
            _TOPIC_REGISTRY[key] = topic

        qos = dds.QosProvider.default.datareader_qos
        qos.durability.kind = dds.DurabilityKind.VOLATILE
        qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        qos.history.kind = dds.HistoryKind.KEEP_ALL

        subscriber = dds.Subscriber(participant)

        if request_id_filter:
            cft = dds.DynamicData.ContentFilteredTopic(
                topic,
                f"StreamChunkFilter_{request_id_filter[:8]}_{int(time.time()*1000)%100000}",
                dds.Filter(f"request_id = '{request_id_filter}'"),
            )
            self._reader = dds.DynamicData.DataReader(subscriber, cft, qos)
        else:
            self._reader = dds.DynamicData.DataReader(subscriber, topic, qos)

        # Poll for data in a background thread
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _poll_loop(self):
        """Background polling loop for incoming samples."""
        waitset = dds.WaitSet()
        status_cond = dds.StatusCondition(self._reader)
        status_cond.enabled_statuses = dds.StatusMask.DATA_AVAILABLE
        waitset += status_cond

        while self._running:
            try:
                waitset.wait(dds.Duration.from_milliseconds(200))
            except dds.TimeoutError:
                continue
            except Exception:
                if not self._running:
                    break
                continue

            samples = self._reader.take()
            for sample in samples:
                if not sample.info.valid:
                    continue
                chunk = {
                    "request_id": sample.data["request_id"],
                    "sequence": sample.data["sequence"],
                    "chunk_type": sample.data["chunk_type"],
                    "content": sample.data["content"],
                    "metadata": sample.data["metadata"],
                    "timestamp": sample.data["timestamp"],
                }
                try:
                    self._callback(chunk)
                except Exception as exc:
                    logger.error("StreamSubscriber callback error: %s", exc)

    def close(self):
        """Stop the polling thread and release DDS resources."""
        self._running = False
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)
        try:
            self._reader.close()
        except Exception:
            pass
