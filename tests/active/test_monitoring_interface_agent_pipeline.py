#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
#                                                                                    #
# RTI grants Licensee a license to use, modify, compile, and create derivative       #
# works of the Software. Licensee has the right to distribute object form only       #
# for use with RTI products. The Software is provided "as is", with no warranty      #
# of any type, including any warranty for fitness for any purpose. RTI is under no   #
# obligation to maintain or support the Software. RTI shall not be liable for any    #
# incidental or consequential damages arising out of the use or inability to use     #
# the software.                                                                      #
# ####################################################################################

"""
Monitoring Test: Interface → Agent → Service Path

Runs the existing pipeline script and asserts monitoring behavior via GraphState:
- An INTERFACE→AGENT edge is observed
- INTERFACE_REQUEST_START is followed by INTERFACE_REQUEST_COMPLETE
- (Optionally) at least one SERVICE→FUNCTION edge is present during the run

This test does not alter the pipeline's own assertions; it layers monitoring checks on top.
"""

import asyncio
import os
import subprocess
import sys
import time
from typing import Any, Dict, List

# Repo root: .../run_scripts/active/<this> → parents[2]
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

from genesis_lib.graph_state import GraphService  # type: ignore


async def wait_for(pred, timeout: float, interval: float = 0.25) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        await asyncio.sleep(interval)
    return pred()


async def main() -> int:
    if not os.environ.get("NDDSHOME"):
        print("ERROR: NDDSHOME is not set. DDS is required for monitoring test.")
        return 2

    # Get domain from environment
    domain_id = int(os.environ.get('GENESIS_DOMAIN_ID', 0))
    graph = GraphService(domain_id=domain_id)
    edges: List[Dict[str, Any]] = []
    activities: List[Dict[str, Any]] = []

    def on_graph(event: str, payload: Dict[str, Any]):
        if event == "edge_update":
            e = payload.get("edge")
            if e:
                edges.append({
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "edge_type": e.edge_type,
                })

    def on_activity(activity: Dict[str, Any]):
        activities.append(activity)

    graph.subscribe(on_graph)
    graph.subscribe_activity(on_activity)
    graph.start()

    pipeline_script = os.path.join(REPO_ROOT, "tests", "active", "run_interface_agent_service_test.sh")
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    # Preserve GENESIS_DOMAIN_ID for the subprocess
    if 'GENESIS_DOMAIN_ID' in os.environ:
        env['GENESIS_DOMAIN_ID'] = os.environ['GENESIS_DOMAIN_ID']
    proc = subprocess.Popen(["bash", pipeline_script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=os.path.join(REPO_ROOT, "tests", "active"))

    try:
        # Wait for process to finish, but keep collecting events
        try:
            outs_bytes, _ = proc.communicate(timeout=120)
            # Decode with error handling for any binary data
            if outs_bytes:
                outs = outs_bytes.decode('utf-8', errors='replace')
                sys.stdout.write(outs)
        except subprocess.TimeoutExpired:
            proc.kill()
            print("ERROR: Pipeline script timed out")
            # Tail diagnostic logs from the pipeline
            logs_dir = os.path.join(REPO_ROOT, "logs")
            for name in ("test_sga_pipeline.log", "test_calc_pipeline.log", "test_static_interface_pipeline.log", "test_pipeline_spy.log"):
                p = os.path.join(logs_dir, name)
                if os.path.exists(p):
                    print(f"--- tail: {p} ---")
                    try:
                        with open(p, 'r') as f:
                            lines = f.readlines()
                            print(''.join(lines[-200:]), end='')
                    except Exception as e:
                        print(f"(unable to read {p}: {e})")
                    print("--- end ---")
            return 1

        if proc.returncode != 0:
            print(f"ERROR: Pipeline script exited with {proc.returncode}")
            # Tail diagnostic logs from the pipeline
            logs_dir = os.path.join(REPO_ROOT, "logs")
            for name in ("test_sga_pipeline.log", "test_calc_pipeline.log", "test_static_interface_pipeline.log", "test_pipeline_spy.log"):
                p = os.path.join(logs_dir, name)
                if os.path.exists(p):
                    print(f"--- tail: {p} ---")
                    try:
                        with open(p, 'r') as f:
                            lines = f.readlines()
                            print(''.join(lines[-200:]), end='')
                    except Exception as e:
                        print(f"(unable to read {p}: {e})")
                    print("--- end ---")
            return 1

        # Basic monitoring assertions
        # 1) Interface→Agent edge observed
        def has_interface_agent_edge() -> bool:
            for e in edges:
                et = (e.get("edge_type") or "").upper()
                if "INTERFACE_TO_AGENT" in et or "INTERFACE" in et and "AGENT" in et:
                    return True
            return False

        if not await wait_for(has_interface_agent_edge, timeout=5):
            print("ERROR: Did not observe INTERFACE→AGENT edge in monitoring events")
            return 1

        # 2) Interface request start → complete pairing
        def has_start_and_complete() -> bool:
            saw_start = any(a.get("event_type") == "INTERFACE_REQUEST_START" for a in activities)
            saw_complete = any(a.get("event_type") == "INTERFACE_REQUEST_COMPLETE" for a in activities)
            return saw_start and saw_complete

        if not await wait_for(has_start_and_complete, timeout=5):
            print("ERROR: Did not observe INTERFACE_REQUEST_START and COMPLETE activities")
            return 1

        # 3) Optional: SERVICE→FUNCTION edge presence (non-fatal if missing here)
        has_service_function = any(
            (e.get("edge_type") or "").upper() in ("SERVICE_TO_FUNCTION", "FUNCTION_CONNECTION") for e in edges
        )
        if not has_service_function:
            # Allow pass but report diagnostic; pipeline still validates RPC path in its own assertions
            print("WARN: No SERVICE→FUNCTION edge observed during pipeline window (may be timing)")

        print("✅ Monitoring test (interface→agent pipeline) passed: edge + activity pairing observed")
        return 0

    finally:
        try:
            graph.stop()
        except Exception:
            pass


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
