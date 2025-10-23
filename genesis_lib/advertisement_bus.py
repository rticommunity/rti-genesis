#!/usr/bin/env python3
# Copyright (c) 2025, RTI & Jason Upchurch

"""
Unified Advertisement Topic/Writer Manager

Provides a per-participant singleton for the unified advertisement
topic and durable writer so multiple components (functions, agents,
interfaces) reuse the same DDS Topic and DataWriter, avoiding duplicate
topic creation errors within a single process.
"""

from __future__ import annotations

import threading
import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path

_LOCK = threading.Lock()
_BUS_BY_PARTICIPANT: dict[int, "AdvertisementBus"] = {}


class AdvertisementBus:
    def __init__(self, participant: dds.DomainParticipant):
        self.participant = participant
        provider = dds.QosProvider(get_datamodel_path())
        self.ad_type = provider.type("genesis_lib", "GenesisAdvertisement")

        # Reuse existing topic if present, otherwise create
        try:
            topic = participant.find_topic("rti/connext/genesis/Advertisement", dds.Duration.from_seconds(1))
        except Exception:
            topic = None
        if topic is None:
            topic = dds.DynamicData.Topic(
                participant,
                "rti/connext/genesis/Advertisement",
                self.ad_type,
            )
        self.topic = topic

        # Publisher (one per bus)
        self.publisher = dds.Publisher(participant)

        # Durable writer QoS
        writer_qos = dds.QosProvider.default.datawriter_qos
        writer_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
        writer_qos.reliability.kind = dds.ReliabilityKind.RELIABLE
        writer_qos.history.kind = dds.HistoryKind.KEEP_LAST
        writer_qos.history.depth = 500

        self.writer = dds.DynamicData.DataWriter(
            pub=self.publisher,
            topic=self.topic,
            qos=writer_qos,
        )

    @classmethod
    def get(cls, participant: dds.DomainParticipant) -> "AdvertisementBus":
        pid = id(participant)
        with _LOCK:
            bus = _BUS_BY_PARTICIPANT.get(pid)
            if bus is None:
                bus = AdvertisementBus(participant)
                _BUS_BY_PARTICIPANT[pid] = bus
            return bus

