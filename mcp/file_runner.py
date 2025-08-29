#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import os
import shlex
import sys
import time
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUEUE_DIR = os.path.join(ROOT, "mcp", "queue")
RESULTS_DIR = os.path.join(ROOT, "mcp", "results")


def ensure_dirs():
    logger.info(f"Ensuring directories exist: {QUEUE_DIR}, {RESULTS_DIR}")
    os.makedirs(QUEUE_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    logger.info("Directories ready")


async def run_shell(cmd: str, timeout: int = 3600) -> Dict[str, Any]:
    start = time.time()
    logger.info(f"Starting shell command: {cmd}")
    logger.info(f"Timeout: {timeout}s, CWD: {ROOT}")
    
    env = os.environ.copy()
    # Load .env if present to pick up NDDSHOME/API keys
    dotenv = os.path.join(ROOT, ".env")
    source_env = f"source {shlex.quote(os.path.relpath(dotenv, ROOT))} && " if os.path.exists(dotenv) else ""
    if os.path.exists(dotenv):
        logger.info(f"Found .env file, will source: {dotenv}")
    else:
        logger.info("No .env file found")
    
    full_cmd = f"bash -lc '{source_env}{cmd}'"
    logger.info(f"Full command: {full_cmd}")
    
    p = await asyncio.create_subprocess_shell(
        full_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=ROOT,
        env=env,
    )
    logger.info(f"Subprocess started with PID: {p.pid}")
    
    try:
        out, err = await asyncio.wait_for(p.communicate(), timeout=timeout)
        code = p.returncode
        logger.info(f"Command completed with exit code: {code}")
    except asyncio.TimeoutError:
        logger.warning(f"Command timed out after {timeout}s, killing process")
        p.kill()
        out, err = await p.communicate()
        code = 124
        logger.info(f"Killed process, exit code: {code}")
    
    duration = round(time.time() - start, 3)
    logger.info(f"Command duration: {duration}s")
    logger.info(f"Stdout length: {len(out)} bytes, Stderr length: {len(err)} bytes")
    
    return {
        "exit_code": code,
        "stdout": out.decode(errors="ignore"),
        "stderr": err.decode(errors="ignore"),
        "duration_sec": duration,
    }


async def handle_one(req_path: str):
    logger.info(f"Processing request file: {req_path}")
    
    try:
        with open(req_path, "r", encoding="utf-8") as f:
            req = json.load(f)
        logger.info(f"Loaded request: {req}")
    except Exception as e:
        logger.error(f"Failed to load request from {req_path}: {e}")
        return
    
    req_id = os.path.splitext(os.path.basename(req_path))[0]
    kind = req.get("kind")  # triage | all | active
    name = req.get("name")
    timeout = int(req.get("timeout_sec", 1800))
    
    logger.info(f"Request ID: {req_id}, Kind: {kind}, Name: {name}, Timeout: {timeout}s")

    if kind == "triage":
        cmd = "./run_scripts/run_triage_suite.sh"
        logger.info(f"Executing triage suite: {cmd}")
    elif kind == "all":
        cmd = "./run_scripts/run_all_tests.sh"
        logger.info(f"Executing all tests: {cmd}")
    elif kind == "active" and name:
        active_path = os.path.join(ROOT, "run_scripts", "active", name)
        logger.info(f"Looking for active test: {active_path}")
        
        if not os.path.exists(active_path):
            logger.error(f"Active test not found: {active_path}")
            res = {"exit_code": 2, "stdout": "", "stderr": f"active test not found: {name}", "duration_sec": 0}
            out_path = os.path.join(RESULTS_DIR, f"{req_id}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=2)
            os.remove(req_path)
            logger.info(f"Wrote error result to {out_path}")
            return
        
        if active_path.endswith(".py"):
            cmd = f"PYTHONPATH=$PYTHONPATH:{ROOT} python {shlex.quote(active_path)}"
        else:
            cmd = f"bash {shlex.quote(active_path)}"
        logger.info(f"Executing active test: {cmd}")
    else:
        logger.error(f"Invalid request: {req}")
        res = {"exit_code": 2, "stdout": "", "stderr": f"invalid request: {req}", "duration_sec": 0}
        out_path = os.path.join(RESULTS_DIR, f"{req_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        os.remove(req_path)
        logger.info(f"Wrote error result to {out_path}")
        return

    # Ensure venv activation for commands that rely on it
    venv_activate = os.path.join(ROOT, "venv", "bin", "activate")
    prefix = f"source {shlex.quote(venv_activate)} && " if os.path.exists(venv_activate) else ""
    if os.path.exists(venv_activate):
        logger.info(f"Found venv, will activate: {venv_activate}")
    else:
        logger.info("No venv found, proceeding without activation")
    
    full_cmd = prefix + cmd
    logger.info(f"Final command to execute: {full_cmd}")
    
    res = await run_shell(full_cmd, timeout=timeout)

    out_path = os.path.join(RESULTS_DIR, f"{req_id}.json")
    logger.info(f"Writing result to: {out_path}")
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        logger.info(f"Successfully wrote result file: {out_path}")
    except Exception as e:
        logger.error(f"Failed to write result file {out_path}: {e}")
    
    try:
        os.remove(req_path)
        logger.info(f"Removed request file: {req_path}")
    except Exception as e:
        logger.error(f"Failed to remove request file {req_path}: {e}")
    
    logger.info(f"Completed processing request {req_id}")


async def watch(loop_delay: float = 1.0):
    logger.info(f"Starting file watcher: {QUEUE_DIR} -> {RESULTS_DIR}")
    logger.info(f"Loop delay: {loop_delay}s")
    ensure_dirs()
    
    loop_count = 0
    while True:
        loop_count += 1
        logger.debug(f"Watch loop iteration {loop_count}")
        
        try:
            queue_files = os.listdir(QUEUE_DIR)
            if queue_files:
                logger.info(f"Found {len(queue_files)} files in queue: {queue_files}")
            
            for entry in sorted(queue_files):
                if not entry.endswith(".json"):
                    logger.debug(f"Skipping non-JSON file: {entry}")
                    continue
                
                path = os.path.join(QUEUE_DIR, entry)
                logger.info(f"Processing queue file: {entry}")
                
                # Basic lock: rename to .working
                working = path + ".working"
                try:
                    os.rename(path, working)
                    logger.info(f"Acquired lock on {entry} -> {os.path.basename(working)}")
                except OSError as e:
                    logger.warning(f"Failed to acquire lock on {entry}: {e}")
                    continue
                
                logger.info(f"Starting to handle request: {entry}")
                await handle_one(working)
                logger.info(f"Completed handling request: {entry}")
                
        except Exception as e:
            logger.error(f"Error in watch loop: {e}", exc_info=True)
        
        logger.debug(f"Watch loop {loop_count} complete, sleeping {loop_delay}s")
        await asyncio.sleep(loop_delay)


def _wait_for_result(req_id: str, max_wait: int = 3600) -> int:
    """Wait until results/<id>.json exists or timeout. Returns 0 on success, 1 on timeout."""
    logger.info(f"Waiting for result: {req_id}.json (max wait: {max_wait}s)")
    out_path = os.path.join(RESULTS_DIR, f"{req_id}.json")
    start = time.time()
    last_emit = 0
    
    while time.time() - start < max_wait:
        if os.path.exists(out_path):
            logger.info(f"Result file found: {out_path}")
            try:
                with open(out_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    sys.stdout.write(content)
                    sys.stdout.flush()
                logger.info(f"Successfully read and output result file ({len(content)} bytes)")
            except Exception as e:
                logger.error(f"Error reading result file {out_path}: {e}")
            return 0
        
        # emit heartbeat every 5s
        current_time = int(time.time() - start)
        if current_time // 5 > last_emit:
            last_emit = current_time // 5
            logger.info(f"Waiting for result {req_id}.json... {current_time}s elapsed")
        time.sleep(1)
    
    logger.error(f"TIMEOUT waiting for result {req_id}.json after {max_wait}s")
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true", help="Watch queue and process tasks")
    ap.add_argument("--enqueue", choices=["triage", "all", "active"], help="Enqueue a task", nargs="?")
    ap.add_argument("--name", help="Active test filename when --enqueue active", default=None)
    ap.add_argument("--timeout", type=int, default=1800, help="Timeout seconds for the task")
    ap.add_argument("--wait", action="store_true", help="Block until result JSON is available and print it")
    ap.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = ap.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("Debug logging enabled")

    logger.info(f"File runner starting with args: {args}")
    ensure_dirs()

    if args.watch:
        logger.info("Starting watch mode")
        asyncio.run(watch())
        return

    if args.enqueue:
        rid = str(int(time.time() * 1000))
        req = {"kind": args.enqueue, "name": args.name, "timeout_sec": args.timeout}
        path = os.path.join(QUEUE_DIR, f"{rid}.json")
        
        logger.info(f"Enqueueing request: {req}")
        logger.info(f"Request file path: {path}")
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(req, f, indent=2)
            logger.info(f"Successfully wrote request file: {path}")
        except Exception as e:
            logger.error(f"Failed to write request file {path}: {e}")
            return
        
        print(path)
        
        if args.wait:
            logger.info("Wait mode enabled, will block until result is available")
            # give watcher a small head start and then block until result arrives
            time.sleep(1)
            sys.exit(_wait_for_result(rid, max_wait=args.timeout + 300))
        return

    logger.warning("No valid mode specified. Use --watch or --enqueue")
    print("Use --watch or --enqueue")


if __name__ == "__main__":
    main()
