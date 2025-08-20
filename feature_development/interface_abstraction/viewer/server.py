#!/usr/bin/env python3
import os
import sys
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
import json

# Ensure local imports
sys.path.append(os.path.abspath("."))

from genesis_lib.graph_state import GraphService  # type: ignore
from genesis_lib.web.socketio_graph_bridge import attach_graph_to_socketio  # type: ignore


SNAPSHOT_DEFAULT = os.getenv(
    "GRAPH_SNAPSHOT_PATH",
    os.path.join("feature_development", "interface_abstraction", "logs", "graph_snapshot.json"),
)


def create_app() -> tuple[Flask, SocketIO, GraphService]:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config['SECRET_KEY'] = 'graph_viewer_secret'
    socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*", logger=False, engineio_logger=False)

    graph = GraphService(domain_id=int(os.getenv("GENESIS_DOMAIN", "0")))
    graph.start()

    attach_graph_to_socketio(graph, socketio)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/graph")
    def api_graph():
        source = request.args.get("source", "live")
        if source == "snapshot":
            path = request.args.get("path", SNAPSHOT_DEFAULT)
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                return jsonify(data)
            except Exception as e:
                return jsonify({"error": f"Failed to load snapshot: {e}", "elements": {"nodes": [], "edges": []}}), 200
        return jsonify(graph.to_cytoscape())

    return app, socketio, graph


if __name__ == "__main__":
    # Bind to all interfaces by default to handle localhost IPv6/IPv4 differences
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5080"))
    app, socketio, graph = create_app()
    try:
        socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)
    finally:
        graph.stop()
