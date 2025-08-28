# RTI DDS 7.3 RPC Client and Provider ID Identification

This document explains how to correctly obtain client and provider IDs (GUIDs) in RTI DDS 7.3 RPC framework. This information is specific to RTI Connext DDS 7.3 and may differ from older versions.

## Overview

In RTI DDS 7.3 RPC, there are two main ways to obtain the GUIDs:

1. From the RPC Requester's matched publications
2. From the reply info after sending a request

## Method 1: Using RPC Requester's Matched Publications

This is the preferred method for initial discovery, as it doesn't require sending a test request.

```python
# Get the replier's GUID from matched publications
replier_guids = requester.reply_datareader.matched_publications
first_replier_guid = replier_guids[0]  # Get the first matched replier's GUID
client_id = str(first_replier_guid)  # Convert to string for use
```

## Method 2: Using Reply Info

This method requires sending a test request and receiving a reply. It's useful for verification or when you need additional information from the reply.

```python
# Send a test request
test_request = dds.DynamicData(request_type)
request_id = requester.send_request(test_request)

# Receive replies
replies = requester.receive_replies(
    max_wait=dds.Duration(seconds=10),
    min_count=1,
    related_request_id=request_id
)

if replies:
    reply, info = replies[0]
    client_id = str(info.publication_handle)  # Get replier's GUID from reply info
```

## Important Notes

1. The GUIDs obtained from both methods should match for the same replier
2. The GUIDs are unique identifiers for DDS entities
3. Both methods return the same GUID format: a string representation of the DDS GUID

## Example Usage

Here's a complete example showing both methods:

```python
def wait_for_agent(self, timeout_seconds: int = 30) -> bool:
    # Wait for agent to be discovered
    while self.requester.matched_replier_count == 0:
        if time.time() - start_time > timeout_seconds:
            return False
        time.sleep(1)
    
    # Method 1: Get GUID from matched publications
    replier_guids = self.requester.reply_datareader.matched_publications
    first_replier_guid = replier_guids[0]
    client_id = str(first_replier_guid)
    
    # Method 2: Verify with reply info
    test_request = dds.DynamicData(self.request_type)
    request_id = self.requester.send_request(test_request)
    
    replies = self.requester.receive_replies(
        max_wait=dds.Duration(seconds=10),
        min_count=1,
        related_request_id=request_id
    )
    
    if replies:
        reply, info = replies[0]
        verified_client_id = str(info.publication_handle)
        # Both client_id and verified_client_id should match
```

## Common Pitfalls

1. Don't use `matched_replier_handles` - this property doesn't exist in RTI DDS 7.3
2. Don't try to access the builtin subscriber directly - use the RPC Requester's methods instead
3. Don't try to convert SampleIdentity objects directly to strings - use their specific properties

## Related Information

- The provider ID (your application's GUID) can be obtained from the participant:
  ```python
  provider_id = str(participant.instance_handle)
  ```
- The client ID (replier's GUID) can be obtained using either method described above
- These GUIDs are used for monitoring, discovery, and correlation of RPC calls 