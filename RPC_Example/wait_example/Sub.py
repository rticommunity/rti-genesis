import time
import rti.connextdds as dds
from ExpLongLongValueType import ExpLongLongValueType

# Create a DomainParticipant on domain 0
participant = dds.DomainParticipant(domain_id=0)

# Create a Topic for ExpLongLongValueType
topic = dds.Topic(participant, "ExpLongLongTopic", ExpLongLongValueType)

# Create a DataReader for the topic
reader = dds.DataReader(participant, topic)

print("Waiting for data on ExpLongLongTopic...")
try:
    while True:
        # Take all available samples
        for data in reader.take():
            print(f"Received: {data}")
        time.sleep(1)
except KeyboardInterrupt:
    print("Subscriber stopped.")
