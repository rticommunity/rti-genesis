#!/usr/bin/env python3

import rti.connextdds as dds
from genesis_lib.utils import get_datamodel_path
import time

print("Starting DDS check...")
participant = dds.DomainParticipant(0)
print("Created participant")

provider = dds.QosProvider(get_datamodel_path())
print("Created QoS provider")

# Check ComponentLifecycleEvent
lifecycle_type = provider.type('genesis_lib', 'ComponentLifecycleEvent')
lifecycle_topic = dds.DynamicData.Topic(participant, 'ComponentLifecycleEvent', lifecycle_type)
subscriber = dds.Subscriber(participant)
reader_qos = dds.QosProvider.default.datareader_qos
reader_qos.durability.kind = dds.DurabilityKind.TRANSIENT_LOCAL
reader = dds.DynamicData.DataReader(subscriber, lifecycle_topic, reader_qos)
print("Created DDS reader")

print('Checking for ComponentLifecycleEvent data...')
time.sleep(2)
samples = reader.take()
print(f'Found {len(samples)} ComponentLifecycleEvent samples')

for data, info in samples:
    if data and info.state.instance_state == dds.InstanceState.ALIVE:
        print(f'Event: {data["component_id"]} - Type: {data["component_type"]} - Category: {data["event_category"]}')

print("Closing participant...")
participant.close()
print("Done.") 