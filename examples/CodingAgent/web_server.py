#!/usr/bin/env python3
"""
CodingAgent Web Server — Flask/SocketIO interface with DDS streaming.

Provides a polished web interface for the CodingGenesisAgent with:
- Real-time streaming of coding events (tool usage, text output)
- Workspace file tree (auto-refreshes after task completion)
- 3D Genesis network graph visualization
- Backend selector and connection status
"""

import argparse
import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit

# Ensure genesis_lib is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from genesis_lib.graph_state import GraphService
from genesis_lib.web.graph_viewer import register_graph_viewer
from genesis_lib.monitored_interface import MonitoredInterface
from genesis_lib.stream_subscriber import StreamSubscriber

import rti.connextdds as dds

logger = logging.getLogger(__name__)


def scan_file_tree(root_dir):
    """Scan a directory and return a JSON-serializable file tree."""
    if not root_dir or not os.path.isdir(root_dir):
        return []

    tree = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip hidden directories
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        rel = os.path.relpath(dirpath, root_dir)
        if rel == ".":
            rel = ""
        for fname in sorted(filenames):
            if fname.startswith("."):
                continue
            path = os.path.join(rel, fname) if rel else fname
            try:
                stat = os.stat(os.path.join(dirpath, fname))
                mtime = stat.st_mtime
                size = stat.st_size
            except OSError:
                mtime = 0
                size = 0
            tree.append({
                "path": path,
                "name": fname,
                "size": size,
                "mtime": mtime,
            })
    return tree


def create_app(workspace_dir=None):
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    static_dir = os.path.join(os.path.dirname(__file__), "static")

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config["SECRET_KEY"] = "coding_web_interface_secret"
    socketio = SocketIO(
        app,
        async_mode="threading",
        cors_allowed_origins="*",
        logger=False,
        engineio_logger=False,
    )

    domain_id = int(os.getenv("GENESIS_DOMAIN", "0"))

    # DDS graph service for 3D visualization
    graph = GraphService(domain_id=domain_id)
    graph.start()
    register_graph_viewer(app, socketio, graph, url_prefix="/genesis-graph")

    # DDS participant for stream subscription
    participant = dds.DomainParticipant(domain_id)

    # State
    state = {
        "interface": None,
        "connected_agent": None,
        "interface_lock": False,
        "workspace_dir": workspace_dir,
        "active_subscribers": {},  # request_id -> StreamSubscriber
        "conversation_id": None,
    }

    # ------- Routes -------

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})

    @app.route("/api/files")
    def api_files():
        return jsonify({"files": scan_file_tree(state["workspace_dir"])})

    # ------- SocketIO events -------

    @socketio.on("connect")
    def on_connect():
        emit("status", {"message": "Connected", "workspace": state["workspace_dir"] or ""})
        socketio.start_background_task(_initialize_interface_once_bg)
        # Send initial file tree
        if state["workspace_dir"]:
            emit("file_tree", {"files": scan_file_tree(state["workspace_dir"])})

    def _initialize_interface_once_bg():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_initialize_interface_once())
        finally:
            loop.close()

    async def _initialize_interface_once():
        if state["interface_lock"] or state["interface"] is not None:
            await _refresh_agents()
            return
        state["interface_lock"] = True
        try:
            if state["interface"] is None:
                state["interface"] = MonitoredInterface(
                    "CodingWebInterface", "CodingWebInterface"
                )
                logger.info("Created MonitoredInterface for web server")
        finally:
            state["interface_lock"] = False
        await _refresh_agents()

    def _refresh_agents_bg():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_refresh_agents())
        finally:
            loop.close()

    async def _refresh_agents():
        if state["interface"] is None:
            return
        await asyncio.sleep(2)
        agents = []
        for agent_id, info in state["interface"].available_agents.items():
            agents.append({
                "id": agent_id,
                "name": info.get("prefered_name", "Unknown"),
                "type": info.get("agent_type", "Unknown"),
                "service_name": info.get("service_name", ""),
                "description": info.get("description", ""),
            })
        socketio.emit("agents", {"agents": agents})

    @socketio.on("refresh_agents")
    def refresh_agents():
        socketio.start_background_task(_refresh_agents_bg)

    @socketio.on("connect_to_agent")
    def connect_to_agent(data):
        name = (data or {}).get("agent_name")
        if not name:
            emit("error", {"message": "agent_name required"})
            return
        socketio.start_background_task(_connect_agent_bg, name)

    def _connect_agent_bg(agent_name):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_connect_agent(agent_name))
        finally:
            loop.close()

    async def _connect_agent(agent_name):
        if state["interface"] is None:
            return
        target = None
        for _id, info in state["interface"].available_agents.items():
            if info.get("prefered_name") == agent_name:
                target = info
                break
        if not target:
            socketio.emit("error", {"message": f"Agent {agent_name} not found"})
            return
        ok = await state["interface"].connect_to_agent(target.get("service_name"))
        if ok:
            state["connected_agent"] = agent_name
            # Generate a new conversation_id for this connection
            state["conversation_id"] = str(uuid.uuid4())[:8]
            socketio.emit(
                "agent_connected",
                {"agent_name": agent_name, "agent_info": target},
            )
        else:
            socketio.emit("error", {"message": f"Failed to connect to {agent_name}"})

    @socketio.on("send_message")
    def send_message(data):
        msg = (data or {}).get("message")
        if not msg:
            emit("error", {"message": "message required"})
            return
        socketio.start_background_task(_send_message_bg, msg)

    def _send_message_bg(message):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_send_message(message))
        except Exception as exc:
            logger.error("_send_message_bg failed: %s", exc, exc_info=True)
            try:
                socketio.emit("error", {"message": f"Request failed: {exc}"})
            except Exception:
                pass
        finally:
            loop.close()

    async def _send_message(message):
        if state["interface"] is None or state["connected_agent"] is None:
            socketio.emit("error", {"message": "No agent connected"})
            return

        request_id = str(uuid.uuid4())
        socketio.emit(
            "message_sent",
            {
                "message": message,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        # Start stream subscriber BEFORE sending request to not miss early events
        def on_stream_chunk(chunk):
            socketio.emit("stream_event", chunk)

        sub = StreamSubscriber(
            participant, on_stream_chunk, request_id_filter=request_id
        )
        state["active_subscribers"][request_id] = sub

        try:
            # Send RPC request with request_id so agent uses it for stream
            resp = await state["interface"].send_request(
                {
                    "message": message,
                    "conversation_id": state.get("conversation_id", ""),
                    "request_id": request_id,
                },
                timeout_seconds=300.0,
            )

            if resp and resp.get("status") == 0:
                socketio.emit(
                    "agent_response",
                    {
                        "message": resp.get("message", ""),
                        "request_id": request_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "agent_name": state["connected_agent"],
                    },
                )
            else:
                socketio.emit(
                    "error",
                    {
                        "message": resp.get("message") if resp else "No response from agent",
                        "request_id": request_id,
                    },
                )
        except Exception as exc:
            logger.error("Error in _send_message: %s", exc, exc_info=True)
            socketio.emit(
                "error",
                {
                    "message": f"Request failed: {exc}",
                    "request_id": request_id,
                },
            )
        finally:
            # Clean up stream subscriber
            sub.close()
            state["active_subscribers"].pop(request_id, None)

            # Refresh file tree after task completion
            if state["workspace_dir"]:
                socketio.emit(
                    "file_tree",
                    {"files": scan_file_tree(state["workspace_dir"])},
                )

    @socketio.on("refresh_files")
    def refresh_files():
        if state["workspace_dir"]:
            emit("file_tree", {"files": scan_file_tree(state["workspace_dir"])})

    return app, socketio, graph


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CodingAgent Web Server")
    parser.add_argument(
        "-p", "--port", type=int, default=5080, help="Port (default: 5080)"
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--workspace",
        default=os.path.join(os.path.dirname(__file__), "workspace"),
        help="Workspace directory to monitor",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    host = args.host
    port = int(os.getenv("PORT", args.port))
    workspace = os.path.abspath(args.workspace)

    print(f"[CodingAgent Web] Starting on {host}:{port}")
    print(f"[CodingAgent Web] Workspace: {workspace}")

    app, socketio, graph = create_app(workspace_dir=workspace)
    try:
        socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)
    finally:
        graph.stop()
