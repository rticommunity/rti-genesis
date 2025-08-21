#!/usr/bin/env python3
import os
import sys
from flask import Flask, render_template, jsonify, request
import argparse
from flask_socketio import SocketIO
import json

# Ensure local imports
sys.path.append(os.path.abspath("."))

from genesis_lib.graph_state import GraphService  # type: ignore
from genesis_lib.web.graph_viewer import register_graph_viewer  # type: ignore


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

    # Register the reusable viewer blueprint under /genesis-graph (also attaches Socket.IO bridge)
    register_graph_viewer(app, socketio, graph, url_prefix="/genesis-graph")

    @app.route("/")
    def index():
        return render_template("index.html")

    # Minimal reference page that uses the library's reference.js
    @app.route("/reference")
    def reference():
        return render_template("reference.html")

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
    # Allow CLI override: --port/-p
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=int(os.getenv("PORT", "5000")))
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    args = parser.parse_args()
    app, socketio, graph = create_app()
    try:
        socketio.run(app, host=args.host, port=args.port, allow_unsafe_werkzeug=True)
    finally:
        graph.stop()
