#!/usr/bin/env python3
import os
import sys
import asyncio
import argparse
from datetime import datetime
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit

# Ensure local imports
sys.path.append(os.path.abspath("."))

from genesis_lib.graph_state import GraphService  # type: ignore
from genesis_lib.web.graph_viewer import register_graph_viewer  # type: ignore
from genesis_lib.monitored_interface import MonitoredInterface  # type: ignore


def create_app() -> tuple[Flask, SocketIO, GraphService]:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config['SECRET_KEY'] = 'graph_interface_example_secret'
    socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*", logger=False, engineio_logger=False)

    # Start graph service and mount the reusable viewer under /genesis-graph
    graph = GraphService(domain_id=int(os.getenv("GENESIS_DOMAIN", "0")))
    graph.start()
    register_graph_viewer(app, socketio, graph, url_prefix="/genesis-graph")

    # Simple in-memory state for chat/agent UX
    state = {
        "interface": None,         # MonitoredInterface
        "connected_agent": None,   # agent name
        "interface_lock": False,   # Prevent multiple interface creation
    }

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})

    # Socket.IO events for agent discovery and chat
    @socketio.on('connect')
    def on_connect():
        emit('status', {"message": "Connected"})
        # Initialize interface on first connection only
        socketio.start_background_task(_initialize_interface_once_bg)

    def _initialize_interface_once_bg():
        try:
            # Create a fresh loop in this background thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_initialize_interface_once())
        finally:
            try:
                loop.close()
            except Exception:
                pass

    async def _initialize_interface_once():
        # Use lock to prevent multiple interface creation
        if state["interface_lock"] or state["interface"] is not None:
            await _refresh_agents()
            return
            
        state["interface_lock"] = True
        try:
            if state["interface"] is None:
                state["interface"] = MonitoredInterface('GraphInterface', 'GraphInterface')
                print(f"[GraphInterface] Created single interface instance")
        finally:
            state["interface_lock"] = False
            
        await _refresh_agents()

    def _refresh_agents_bg():
        try:
            # Create a fresh loop in this background thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_refresh_agents())
        finally:
            try:
                loop.close()
            except Exception:
                pass

    async def _refresh_agents():
        if state["interface"] is None:
            return
        # Allow brief time for agent discovery
        await asyncio.sleep(2)
        agents = []
        for agent_id, info in state["interface"].available_agents.items():
            agents.append({
                "id": agent_id,
                "name": info.get('prefered_name', 'Unknown'),
                "type": info.get('agent_type', 'Unknown'),
                "service_name": info.get('service_name', ''),
                "description": info.get('description', ''),
            })
        socketio.emit('agents', {"agents": agents})

    @socketio.on('refresh_agents')
    def refresh_agents():
        socketio.start_background_task(_refresh_agents_bg)

    @socketio.on('connect_to_agent')
    def connect_to_agent(data):
        name = (data or {}).get('agent_name')
        if not name:
            emit('error', {"message": "agent_name required"})
            return
        socketio.start_background_task(_connect_agent_bg, name)

    def _connect_agent_bg(agent_name: str):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_connect_agent(agent_name))
        finally:
            try:
                loop.close()
            except Exception:
                pass

    async def _connect_agent(agent_name: str):
        if state["interface"] is None:
            return  # Interface should already be initialized
        # Find matching agent service
        target = None
        for _id, info in state["interface"].available_agents.items():
            if info.get('prefered_name') == agent_name:
                target = info
                break
        if not target:
            socketio.emit('error', {"message": f"Agent {agent_name} not found"})
            return
        ok = await state["interface"].connect_to_agent(target.get('service_name'))
        if ok:
            state["connected_agent"] = agent_name
            socketio.emit('agent_connected', {"agent_name": agent_name, "agent_info": target})
        else:
            socketio.emit('error', {"message": f"Failed to connect to {agent_name}"})

    @socketio.on('send_message')
    def send_message(data):
        msg = (data or {}).get('message')
        if not msg:
            emit('error', {"message": "message required"})
            return
        socketio.start_background_task(_send_message_bg, msg)

    def _send_message_bg(message: str):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_send_message(message))
        finally:
            try:
                loop.close()
            except Exception:
                pass

    async def _send_message(message: str):
        if state["interface"] is None or state["connected_agent"] is None:
            socketio.emit('error', {"message": "No agent connected"})
            return
        socketio.emit('message_sent', {"message": message, "timestamp": datetime.utcnow().isoformat()})
        resp = await state["interface"].send_request({"message": message, "conversation_id": "graph_interface_demo"}, timeout_seconds=30.0)
        if resp and resp.get('status') == 0:
            socketio.emit('agent_response', {"message": resp.get('message', ''), "timestamp": datetime.utcnow().isoformat(), "agent_name": state["connected_agent"]})
        else:
            socketio.emit('error', {"message": (resp.get('message') if resp else 'No response')})

    return app, socketio, graph


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GraphInterface Server")
    parser.add_argument("-p", "--port", type=int, default=5080, help="Port to run server on (default: 5080)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    args = parser.parse_args()
    
    # Use command line args, fallback to env vars, then defaults
    host = args.host or os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", args.port))
    
    print(f"[GraphInterface] Starting server on {host}:{port}")
    
    app, socketio, graph = create_app()
    try:
        socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)
    finally:
        graph.stop()


