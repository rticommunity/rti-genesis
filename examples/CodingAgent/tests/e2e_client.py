#!/usr/bin/env python3
"""
E2E client — sends a single RPC request to a running CodingGenesisAgent
and verifies the response.

Requires DDS environment and a running agent.
"""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import rti.connextdds as dds
import rti.rpc as rpc
from genesis_lib.utils import get_datamodel_path


async def main():
    config_path = get_datamodel_path()
    provider = dds.QosProvider(config_path)
    request_type = provider.type("genesis_lib", "InterfaceAgentRequest")
    reply_type = provider.type("genesis_lib", "InterfaceAgentReply")

    participant = dds.DomainParticipant(domain_id=0)

    requester = rpc.Requester(
        request_type=request_type,
        reply_type=reply_type,
        participant=participant,
        service_name="CodingAgent",
    )

    # Wait for discovery
    print("Waiting for CodingAgent service discovery...")
    await asyncio.sleep(5)

    # Build request
    request = dds.DynamicData(request_type)
    request["message"] = "Reply with only: GENESIS_E2E_TEST_OK"
    request["conversation_id"] = "e2e-test-001"

    print("Sending request...")
    request_id = requester.send_request(request)

    # Wait for reply (up to 120s for coding agents)
    print("Waiting for reply...")
    start = time.time()
    while time.time() - start < 120:
        replies = requester.take_replies(request_id)
        for reply, info in replies:
            if reply is None:
                continue

            result = {}
            for member in reply_type.members():
                try:
                    result[member.name] = reply[member.name]
                except Exception:
                    pass

            print(f"\nResponse received:")
            print(json.dumps(result, indent=2, default=str))

            # Validate
            failures = []
            if not result.get("message"):
                failures.append("message is empty")
            if str(result.get("status", "")) not in ("0", ""):
                failures.append(f"status is {result.get('status')}, expected 0")

            if failures:
                print(f"\nFAILURES: {failures}")
                participant.close()
                sys.exit(1)
            else:
                print("\nPASS: E2E response validated")
                participant.close()
                sys.exit(0)

        await asyncio.sleep(1)

    print("\nFAIL: Timed out waiting for reply")
    participant.close()
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
