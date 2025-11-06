import time
import rti.connextdds as dds
from ExpLongLongValueType import ExpLongLongValueType

# Create a DomainParticipant on domain 0
participant = dds.DomainParticipant(domain_id=0)

# Create a Topic for ExpLongLongValueType
topic = dds.Topic(participant, "ExpLongLongTopic", ExpLongLongValueType)

# Create a DataWriter for the topic
writer = dds.DataWriter(participant, topic)

while writer.publication_matched_status.current_count == 0:
    print("Waiting for a DataReader to be discovered...")
    time.sleep(0.1)

# Write a sample with a unique id
sample = ExpLongLongValueType(longlongValue=0)
for i in range(5):
    sample.longlongValue = 0 + i
    writer.write(sample)
    print(f"Wrote: {sample}")
    time.sleep(2)

# Keep the application alive for discovery (optional)
time.sleep(2)
