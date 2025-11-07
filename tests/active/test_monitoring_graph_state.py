#!/usr/bin/env python3
"""
Monitoring Consistency Test (Graph State)

Asserts core monitoring invariants using the unified GraphMonitor + GraphService:
- One unique node per endpoint (service and each function)
- Service→Function edges exist for advertised functions
- For every function request (BUSY), a corresponding READY follows (closed reply)

Scope: uses CalculatorService as the target service; drives one RPC call via GenesisRequester.

Prereqs: DDS installed (`NDDSHOME`), Python 3.10, repo environment activated.
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

# Make repo importable
# Repo root: .../run_scripts/active/<this> → parents[2]
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(REPO_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
sys.path.insert(0, REPO_ROOT)

from genesis_lib.graph_state import GraphService, NodeInfo, EdgeInfo  # type: ignore
from genesis_lib.requester import GenesisRequester  # type: ignore


EXPECTED_FUNCTIONS = {"add", "subtract", "multiply", "divide"}


@dataclass
class Observed:
    service_nodes: Dict[str, NodeInfo]
    function_nodes: Dict[str, NodeInfo]
    edges: List[EdgeInfo]
    service_busy_events: List[NodeInfo]
    service_ready_events: List[NodeInfo]


def start_calculator_service() -> tuple[subprocess.Popen, str]:
    """Start calculator service with repo on PYTHONPATH and log to file.

    Returns (process, log_path).
    """
    script = os.path.join(REPO_ROOT, "test_functions", "services", "calculator_service.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    # Pass domain ID from environment
    domain_id = int(os.environ.get('GENESIS_DOMAIN_ID', 0))
    log_path = os.path.join(LOG_DIR, "monitor_calc_service.log")
    log_fp = open(log_path, "w")
    proc = subprocess.Popen(
        [sys.executable, script, "--domain", str(domain_id)],
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        cwd=REPO_ROOT,
    )
    return proc, log_path


async def wait_for(pred, timeout: float, interval: float = 0.25) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        await asyncio.sleep(interval)
    return pred()


async def main() -> int:
    # Basic DDS env check
    if not os.environ.get("NDDSHOME"):
        print("ERROR: NDDSHOME is not set. DDS is required for monitoring test.")
        return 2

    # Get domain from environment
    domain_id = int(os.environ.get('GENESIS_DOMAIN_ID', 0))
    graph = GraphService(domain_id=domain_id)
    obs = Observed(service_nodes={}, function_nodes={}, edges=[], service_busy_events=[], service_ready_events=[])

    def on_graph(event: str, payload: Dict[str, Any]):
        if event == "node_update":
            node: NodeInfo = payload["node"]
            # Partition by node_type
            if node.node_type == "SERVICE":
                obs.service_nodes[node.node_id] = node
                # Track BUSY/READY transitions
                if node.node_state == "BUSY":
                    obs.service_busy_events.append(node)
                elif node.node_state == "READY":
                    obs.service_ready_events.append(node)
            elif node.node_type == "FUNCTION":
                obs.function_nodes[node.node_id] = node
        elif event == "edge_update":
            edge: EdgeInfo = payload["edge"]
            obs.edges.append(edge)

    graph.subscribe(on_graph)
    graph.start()

    # Start service process
    svc, svc_log = start_calculator_service()
    try:
        # Wait for service node + function nodes
        ok_nodes = await wait_for(lambda: len(obs.service_nodes) >= 1 and len(obs.function_nodes) >= 4, timeout=25)
        if not ok_nodes:
            print("ERROR: Did not observe expected SERVICE/FUNCTION nodes in time")
            print(f"Observed services: {len(obs.service_nodes)}, functions: {len(obs.function_nodes)}")
            # If the service died early, report exit code
            if svc.poll() is not None:
                print(f"NOTE: Calculator service exited with code {svc.returncode}")
            # Tail the calculator service log for diagnostics
            try:
                print("--- Calculator service log (tail 200) ---")
                with open(svc_log, "r") as f:
                    lines = f.readlines()
                    tail = "".join(lines[-200:])
                    print(tail, end="")
                print("--- end calculator service log ---")
            except Exception as e:
                print(f"WARN: Could not read calculator service log: {e}")
            return 1

        # Validate service nodes for CalculatorService: exactly one and unique among matching nodes
        calc_services = [n for n in obs.service_nodes.values() if (n.metadata or {}).get("service") == "CalculatorService"]
        if len(calc_services) != 1:
            print(f"ERROR: Expected exactly 1 CalculatorService node, saw {len(calc_services)}")
            return 1
        if len({n.node_id for n in calc_services}) != 1:
            print("ERROR: Duplicate CalculatorService node IDs observed")
            return 1

        # Validate that function nodes match exactly the expected set (by metadata)
        fn_names: Set[str] = set()
        for node in obs.function_nodes.values():
            try:
                meta = node.metadata or {}
                name = meta.get("function_name") or meta.get("name")
                if name:
                    fn_names.add(name)
            except Exception:
                pass
        missing = EXPECTED_FUNCTIONS - fn_names
        if missing:
            print(f"ERROR: Missing function nodes for: {sorted(missing)}")
            print(f"Seen function names: {sorted(fn_names)}")
            return 1
        extras = fn_names - EXPECTED_FUNCTIONS
        if extras:
            print(f"ERROR: Unexpected function nodes present: {sorted(extras)}")
            return 1

        # Validate SERVICE→FUNCTION edges exist and match expected exactly for CalculatorService
        stf = [e for e in obs.edges if e.edge_type in ("SERVICE_TO_FUNCTION", "FUNCTION_CONNECTION", "function_connection")]
        if len(stf) < len(EXPECTED_FUNCTIONS):
            # Give a moment for durable refresh
            await asyncio.sleep(3)
            stf = [e for e in obs.edges if e.edge_type in ("SERVICE_TO_FUNCTION", "FUNCTION_CONNECTION", "function_connection")]
        
        # Filter to edges belonging to CalculatorService
        stf_calc = []
        for e in stf:
            try:
                if (e.metadata or {}).get("service") == "CalculatorService":
                    stf_calc.append(e)
            except Exception:
                pass
        
        fn_from_edges: Set[str] = set()
        extras_from_edges: Set[str] = set()
        for e in stf_calc:
            try:
                fname = (e.metadata or {}).get("function_name")
                if fname:
                    (fn_from_edges if fname in EXPECTED_FUNCTIONS else extras_from_edges).add(fname)
            except Exception:
                pass
        missing_edges = EXPECTED_FUNCTIONS - fn_from_edges
        if missing_edges:
            print(f"ERROR: Missing SERVICE→FUNCTION edges for: {sorted(missing_edges)}")
            return 1
        if extras_from_edges:
            print(f"ERROR: Unexpected SERVICE→FUNCTION edges for: {sorted(extras_from_edges)}")
            return 1

        # Drive one RPC call to assert matched BUSY↔READY pairing (no extras for other functions)
        client = GenesisRequester(service_type="CalculatorService")
        await client.wait_for_service(timeout_seconds=10)
        pre_busy = len(obs.service_busy_events)
        pre_ready = len(obs.service_ready_events)
        res = await client.call_function("add", x=1, y=2)
        if (res or {}).get("result") != 3:
            print(f"ERROR: Unexpected RPC result: {res}")
            return 1

        # Wait until deltas are present and matched (same count of BUSY and READY)
        async def deltas_matched(timeout: float = 10.0) -> bool:
            end = time.time() + timeout
            while time.time() < end:
                db = len(obs.service_busy_events) - pre_busy
                dr = len(obs.service_ready_events) - pre_ready
                if db >= 1 and dr >= 1 and db == dr:
                    return True
                await asyncio.sleep(0.25)
            return (len(obs.service_busy_events) - pre_busy) >= 1 and (len(obs.service_ready_events) - pre_ready) >= 1 and (len(obs.service_busy_events) - pre_busy) == (len(obs.service_ready_events) - pre_ready)

        if not await deltas_matched(10.0):
            db = len(obs.service_busy_events) - pre_busy
            dr = len(obs.service_ready_events) - pre_ready
            print(f"ERROR: BUSY/READY increments not matched (BUSY+{db}, READY+{dr}) after the call")
            return 1

        new_busy = obs.service_busy_events[pre_busy:]
        new_ready = obs.service_ready_events[pre_ready:]
        # Ensure all new events correspond to the called function ('add') and no extras
        bad_busy = [ (b.metadata or {}).get("function_name") for b in new_busy if (b.metadata or {}).get("function_name") not in ("add", None) ]
        bad_ready = [ (r.metadata or {}).get("function_name") for r in new_ready if (r.metadata or {}).get("function_name") not in ("add", None) ]
        if bad_busy or bad_ready:
            print(f"ERROR: Observed unexpected function names in BUSY/READY stream: BUSY={bad_busy} READY={bad_ready}")
            return 1

        print("✅ Monitoring consistency test passed: unique nodes, edges present, BUSY→READY pairing observed")
        return 0

    finally:
        try:
            svc.terminate()
        except Exception:
            pass
        try:
            graph.stop()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        rc = asyncio.run(main())
    except KeyboardInterrupt:
        rc = 130
    sys.exit(rc)
