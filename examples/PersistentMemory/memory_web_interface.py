#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
# ####################################################################################

"""
PersistentMemory Web Interface — Browser-based GUI for the PersistentMemoryAgent.

Flask + SocketIO web interface that:
- Auto-discovers PersistentMemoryAgents on the Genesis DDS network
- Provides a chat panel with markdown rendering
- Embeds the Genesis graph viewer for real-time network topology
- Shows memory statistics (token counts, compaction status)

Based on the MultiAgent GUI pattern (examples/MultiAgent/interfaces/gui_interface.py).
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import threading
import uuid
from datetime import datetime

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from genesis_lib.monitored_interface import MonitoredInterface
from genesis_lib.graph_state import GraphService
from genesis_lib.web.graph_viewer import register_graph_viewer

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class MemoryWebGUI:
    """Web-based GUI for PersistentMemory demo."""

    def __init__(self, host="127.0.0.1", port=5050):
        self.host = host
        self.port = port

        # Flask + SocketIO
        self.app = Flask(
            __name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        )
        self.app.config["SECRET_KEY"] = str(uuid.uuid4())
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        # Genesis graph viewer (3D orbital topology)
        self.graph_service = GraphService(
            domain_id=int(os.getenv("GENESIS_DOMAIN", "0"))
        )
        self.graph_service.start()
        register_graph_viewer(
            self.app, self.socketio, self.graph_service, url_prefix="/genesis-graph"
        )

        # Genesis interface (DDS agent communication)
        self.interface = None
        self.connected_agent = None
        self.conversation_id = f"web-{uuid.uuid4().hex[:8]}"

        self._setup_routes()
        self._setup_socketio_handlers()

    def _setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template("index.html")

        @self.app.route("/api/agents")
        def get_agents():
            if self.interface:
                agents = []
                for agent_id, info in self.interface.available_agents.items():
                    agents.append({
                        "id": agent_id,
                        "name": info.get("prefered_name", "Unknown"),
                        "type": info.get("agent_type", "Unknown"),
                        "service_name": info.get("service_name", ""),
                        "capabilities": info.get("capabilities", []),
                    })
                return jsonify({"agents": agents})
            return jsonify({"agents": []})

    def _setup_socketio_handlers(self):
        @self.socketio.on("connect")
        def handle_connect():
            emit("status", {"message": "Connected to Memory Web GUI"})
            if not self.interface:
                # First connection — initialize Genesis DDS
                self.socketio.start_background_task(self._init_genesis_wrapper)
            else:
                # Reconnect (e.g. browser refresh) — re-send current state
                agents = []
                for agent_id, info in self.interface.available_agents.items():
                    agents.append({
                        "id": agent_id,
                        "name": info.get("prefered_name", "Unknown"),
                        "type": info.get("agent_type", "Unknown"),
                        "service_name": info.get("service_name", ""),
                        "capabilities": info.get("capabilities", []),
                    })
                emit("agents_discovered", {"agents": agents})
                if self.connected_agent:
                    target = None
                    for aid, info in self.interface.available_agents.items():
                        if info.get("prefered_name") == self.connected_agent:
                            target = info
                            break
                    emit("agent_connected", {
                        "agent_name": self.connected_agent,
                        "agent_info": target or {},
                    })

        @self.socketio.on("connect_to_agent")
        def handle_connect_agent(data):
            agent_name = data.get("agent_name")
            if agent_name:
                self.socketio.start_background_task(
                    self._connect_agent_wrapper, agent_name
                )

        @self.socketio.on("send_message")
        def handle_send_message(data):
            message = data.get("message")
            if message and self.connected_agent:
                self.socketio.start_background_task(
                    self._send_message_wrapper, message
                )

        @self.socketio.on("disconnect_agent")
        def handle_disconnect():
            self.connected_agent = None
            emit("agent_disconnected")

    # ── Async wrappers (SocketIO background tasks) ───────────────

    def _init_genesis_wrapper(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._init_genesis())
        finally:
            loop.close()

    async def _init_genesis(self):
        try:
            self.socketio.emit("status", {"message": "Initializing Genesis DDS..."})
            self.interface = MonitoredInterface("MemoryWebGUI", "MemoryWebService")
            await asyncio.sleep(4)  # DDS discovery time

            agents = []
            for agent_id, info in self.interface.available_agents.items():
                agents.append({
                    "id": agent_id,
                    "name": info.get("prefered_name", "Unknown"),
                    "type": info.get("agent_type", "Unknown"),
                    "service_name": info.get("service_name", ""),
                    "capabilities": info.get("capabilities", []),
                })

            self.socketio.emit("agents_discovered", {"agents": agents})

            if len(agents) == 1:
                # Auto-connect to the only agent
                await self._connect_to_agent(agents[0]["name"])
            elif len(agents) == 0:
                self.socketio.emit(
                    "status",
                    {"message": "No agents found. Start the agent first."},
                )
            else:
                self.socketio.emit(
                    "status",
                    {"message": f"Found {len(agents)} agent(s). Select one to chat."},
                )

        except Exception as e:
            self.socketio.emit("error", {"message": f"Init failed: {e}"})

    def _connect_agent_wrapper(self, agent_name):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._connect_to_agent(agent_name))
        finally:
            loop.close()

    async def _connect_to_agent(self, agent_name):
        try:
            if not self.interface:
                self.socketio.emit("error", {"message": "Genesis not initialized"})
                return

            target = None
            for agent_id, info in self.interface.available_agents.items():
                if info.get("prefered_name") == agent_name:
                    target = info
                    break

            if not target:
                self.socketio.emit(
                    "error", {"message": f"Agent '{agent_name}' not found"}
                )
                return

            self.socketio.emit(
                "status", {"message": f"Connecting to {agent_name}..."}
            )
            service_name = target.get("service_name")
            connected = await self.interface.connect_to_agent(service_name)

            if connected:
                self.connected_agent = agent_name
                self.socketio.emit(
                    "agent_connected",
                    {"agent_name": agent_name, "agent_info": target},
                )
                self.socketio.emit(
                    "status", {"message": f"Connected to {agent_name}"}
                )
            else:
                self.socketio.emit(
                    "error", {"message": f"Failed to connect to {agent_name}"}
                )

        except Exception as e:
            self.socketio.emit("error", {"message": f"Connection error: {e}"})

    def _send_message_wrapper(self, message):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._send_message(message))
        finally:
            loop.close()

    async def _send_message(self, message):
        try:
            if not self.interface or not self.connected_agent:
                self.socketio.emit("error", {"message": "No agent connected"})
                return

            self.socketio.emit(
                "message_sent",
                {"message": message, "timestamp": datetime.now().isoformat()},
            )

            response = await self.interface.send_request(
                {"message": message, "conversation_id": self.conversation_id},
                timeout_seconds=60.0,
            )

            if response and response.get("status", 1) == 0:
                self.socketio.emit(
                    "agent_response",
                    {
                        "message": response.get("message", ""),
                        "agent_name": self.connected_agent,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
            else:
                error_msg = (
                    response.get("message", "Unknown error") if response else "Timeout"
                )
                self.socketio.emit("error", {"message": f"Agent error: {error_msg}"})

        except Exception as e:
            self.socketio.emit("error", {"message": f"Send error: {e}"})

    def run(self):
        print(f"Genesis PersistentMemory Web GUI")
        print(f"  URL: http://{self.host}:{self.port}")
        print(f"  Graph viewer: http://{self.host}:{self.port}/genesis-graph/reference")
        print(f"  Press Ctrl+C to stop")
        print()

        try:
            self.socketio.run(
                self.app,
                host=self.host,
                port=self.port,
                debug=False,
                allow_unsafe_werkzeug=True,
            )
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            if self.graph_service:
                self.graph_service.stop()


def main():
    parser = argparse.ArgumentParser(description="PersistentMemory Web GUI")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5050, help="Port to bind to")
    args = parser.parse_args()

    gui = MemoryWebGUI(host=args.host, port=args.port)
    gui.run()


if __name__ == "__main__":
    main()
