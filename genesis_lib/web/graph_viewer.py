# Copyright (c) 2025, RTI & Jason Upchurch

from __future__ import annotations

import os
import json
from typing import Optional, Tuple

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from flask import Flask
from flask_socketio import SocketIO

from .socketio_graph_bridge import attach_graph_to_socketio
from ..graph_state import GraphService


def create_graph_viewer_blueprint(graph: GraphService, url_prefix: str = "/genesis-graph") -> Blueprint:
    """Create a Flask Blueprint exposing graph API endpoints and static assets for the reference viewer.

    Routes (mounted under url_prefix):
      - GET {url_prefix}/api/graph?source=live|snapshot&path=... → cytoscape JSON
      - GET {url_prefix}/static/<path:filename> → reference assets
    """
    bp = Blueprint(
        "genesis_graph_viewer",
        __name__,
        static_folder="static",
        static_url_path=f"{url_prefix}/static",
    )

    snapshot_default = os.getenv(
        "GRAPH_SNAPSHOT_PATH",
        os.path.join("feature_development", "interface_abstraction", "logs", "graph_snapshot.json"),
    )

    @bp.get("/api/graph")
    def api_graph():
        source = request.args.get("source", "live")
        if source == "snapshot":
            path = request.args.get("path", snapshot_default)
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                return jsonify(data)
            except Exception as e:  # return empty graph on failure
                return jsonify({"error": f"Failed to load snapshot: {e}", "elements": {"nodes": [], "edges": []}})
        return jsonify(graph.to_cytoscape())

    # Optional: serve reference assets (reference.js, styles)
    @bp.get("/static/<path:filename>")
    def serve_static(filename: str):
        return send_from_directory(bp.static_folder, filename)

    # Minimal reference page to embed the viewer without requiring an app template
    @bp.get("/reference")
    def reference_page():
        # Lightweight HTML that loads the 3D orbital viewer client
        html = f"""<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Genesis Graph Viewer (Reference)</title>
    <style>html,body,#graph{{height:100%;margin:0;background:#0b0f16;color:#eee}}</style>
    <script src=\"https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js\"></script>
    <script type=\"module\">\n      import {{ initGraphViewer3D }} from \"{url_prefix}/static/orbital_viewer.js\";\n      window.addEventListener('DOMContentLoaded', () => {{\n        const el = document.getElementById('graph');\n        initGraphViewer3D(el, {{ socketUrl: `${{location.protocol}}//${{location.host}}` }});\n      }});\n    </script>
  </head>
  <body><div id=\"graph\"></div></body>
</html>"""
        from flask import Response
        return Response(html, mimetype="text/html")

    return bp


def register_graph_viewer(app: Flask, socketio: SocketIO, graph: GraphService, url_prefix: str = "/genesis-graph") -> None:
    """Register the graph viewer blueprint and attach the Socket.IO bridge.

    This is the one-liner an app can call to enable the viewer endpoints and events.
    """
    bp = create_graph_viewer_blueprint(graph, url_prefix=url_prefix)
    app.register_blueprint(bp, url_prefix=url_prefix)
    attach_graph_to_socketio(graph, socketio)


def create_viewer_app(domain_id: int = 0) -> Tuple[Flask, SocketIO, GraphService]:
    """Create a standalone Flask+Socket.IO app serving the reference viewer.

    Returns (app, socketio, graph) so callers can run it or embed elsewhere.
    """
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'genesis_graph_viewer_secret'
    socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*", logger=False, engineio_logger=False)

    graph = GraphService(domain_id=domain_id)
    graph.start()

    # Mount under /genesis-graph
    register_graph_viewer(app, socketio, graph, url_prefix="/genesis-graph")

    return app, socketio, graph


def run_viewer(host: str = "0.0.0.0", port: int = 5080, domain_id: Optional[int] = None) -> None:
    """Run a standalone graph viewer server. Intended for quick manual runs.

    Example:
        python -c "from genesis_lib.web.graph_viewer import run_viewer; run_viewer()"
    """
    app, socketio, graph = create_viewer_app(domain_id=domain_id or int(os.getenv("GENESIS_DOMAIN", "0")))
    try:
        socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)
    finally:
        graph.stop()


