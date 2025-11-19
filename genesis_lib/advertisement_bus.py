#!/usr/bin/env python3
# Copyright (c) 2025, RTI & Jason Upchurch

"""
Unified Advertisement Bus — Per-Participant Topic/Writer Manager

Provides a per-participant singleton for the unified advertisement Topic and
DataWriter so multiple Genesis components (interfaces, agents, services) reuse
the same DDS entities, avoiding duplicate-topic errors when sharing a single
DDS participant.

=================================================================================================
ARCHITECTURE OVERVIEW — Why This Exists
=================================================================================================

- DDS constraint: Within a single `dds.DomainParticipant`, topic names must be unique.
  Creating the same topic multiple times raises errors.
- Genesis commonly runs multiple components in the same process, all sharing one
  participant for efficiency.
- The Advertisement Bus centralizes creation and reuse of the unified Advertisement
  Topic and its DataWriter to prevent conflicts and promote consistency.

What this provides:
1. Thread-safe, per-participant singleton via `AdvertisementBus.get(participant)`
2. Reuse of the same Topic and DataWriter across components in the process
3. QoS configured via XML profile (`cft_Library::cft_Profile`) with explicit fallback
4. Simple lifecycle: cleanup is delegated to `participant.close()`

How it works:
- Loads the datamodel types from `datamodel.xml` via `dds.QosProvider`
- Attempts to find an existing `rti/connext/genesis/Advertisement` Topic; if not found,
  creates a `dds.DynamicData.Topic`
- Creates a `dds.Publisher` and a `dds.DynamicData.DataWriter` with QoS pulled from
  the configured XML profile; falls back to `USER_QOS_PROFILES.xml` if needed
- Caches one `AdvertisementBus` per participant in a process-wide map under a lock

Failure handling & cleanup:
- `find_topic` failures are tolerated and treated as "not found"
- QoS retrieval first uses the default provider; on failure, explicitly loads
  `USER_QOS_PROFILES.xml`
- No explicit closes on topics/writers; `participant.close()` handles cleanup of all
  contained entities

Thread-safety:
- A global lock protects bus creation
- One bus instance per participant (keyed by `id(participant)`)

Public API:
- `AdvertisementBus.get(participant) -> AdvertisementBus`

Usage:
    bus = AdvertisementBus.get(participant)
    bus.writer.write(ad_dynamic_data)  # Publish a `GenesisAdvertisement` instance
"""

from __future__ import annotations

import threading
import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path

_LOCK = threading.Lock()
_BUS_BY_PARTICIPANT: dict[int, "AdvertisementBus"] = {}


class AdvertisementBus:
    """
    Per-participant manager for the unified Advertisement Topic and DataWriter.

    Attributes:
        participant: The `dds.DomainParticipant` backing all DDS entities.
        ad_type: The DynamicData type for `GenesisAdvertisement` loaded from XML.
        topic: The shared `dds.Topic` named `rti/connext/genesis/Advertisement`.
        publisher: The `dds.Publisher` used by the advertisement writer.
        writer: The `dds.DynamicData.DataWriter` that publishes advertisements.
    """
    def __init__(self, participant: dds.DomainParticipant):
        """
        Initialize the bus for a given participant.

        Args:
            participant: The DDS participant shared by components in this process.

        Notes:
            - Loads `GenesisAdvertisement` from the datamodel XML.
            - Finds or creates the shared advertisement Topic.
            - Creates a `Publisher` and `DataWriter` with QoS from the
              `cft_Library::cft_Profile` profile (falls back to explicit XML load).
            - No explicit cleanup; rely on `participant.close()` for all DDS entities.
        """
        self.participant = participant
        # Load datamodel.xml for types
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

        # DataWriter QoS configured in XML (genesis_lib/config/USER_QOS_PROFILES.xml)
        # Using default profile: RELIABLE, TRANSIENT_LOCAL, KEEP_LAST(500),
        # AUTOMATIC liveliness, SHARED ownership
        # Load QoS directly from USER_QOS_PROFILES.xml to avoid "Profile not found" errors
        import os
        config_dir = os.path.dirname(get_datamodel_path())
        user_qos_path = os.path.join(config_dir, "USER_QOS_PROFILES.xml")
        qos_provider = dds.QosProvider(user_qos_path)
        writer_qos = qos_provider.datawriter_qos_from_profile("cft_Library::cft_Profile")

        self.writer = dds.DynamicData.DataWriter(
            pub=self.publisher,
            topic=self.topic,
            qos=writer_qos,
        )

    @classmethod
    def get(cls, participant: dds.DomainParticipant) -> "AdvertisementBus":
        """
        Return the thread-safe, per-participant singleton bus instance.

        Ensures only one `AdvertisementBus` is created per `dds.DomainParticipant`
        within the process. Subsequent calls with the same participant reuse the
        same bus, including its Topic and DataWriter.

        Args:
            participant: The DDS participant for which to obtain the bus.

        Returns:
            The `AdvertisementBus` instance bound to the provided participant.
        """
        pid = id(participant)
        with _LOCK:
            bus = _BUS_BY_PARTICIPANT.get(pid)
            if bus is None:
                bus = AdvertisementBus(participant)
                _BUS_BY_PARTICIPANT[pid] = bus
            return bus

