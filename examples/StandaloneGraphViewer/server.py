#!/usr/bin/env python3
"""
Standalone Graph Viewer - Pure Visualization, No Chat Interface

This is a minimal example showing how to run just the graph visualization
without any agent interaction UI. Perfect for:
- Monitoring Genesis network topology in real-time
- Debugging service discovery issues
- Visualizing large-scale deployments
- Running on a separate monitor/dashboard
"""
import os
import sys
import argparse

# Add Genesis library to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from genesis_lib.web.graph_viewer import create_viewer_app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Standalone Genesis Graph Viewer - Real-time network topology visualization"
    )
    parser.add_argument(
        "-p", "--port", 
        type=int, 
        default=int(os.getenv("PORT", "5000")),
        help="Port to run server on (default: 5000)"
    )
    parser.add_argument(
        "--host", 
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--domain",
        type=int,
        default=int(os.getenv("GENESIS_DOMAIN", "0")),
        help="DDS domain ID (default: 0)"
    )
    args = parser.parse_args()
    
    print(f"[StandaloneGraphViewer] Starting on {args.host}:{args.port} (domain={args.domain})")
    print(f"[StandaloneGraphViewer] Open http://localhost:{args.port}/genesis-graph/reference")
    
    # Create the standalone viewer app (uses library's create_viewer_app)
    app, socketio, graph = create_viewer_app(domain_id=args.domain)
    
    # Add a root redirect for convenience
    @app.route("/")
    def index():
        from flask import redirect
        return redirect("/genesis-graph/reference")
    
    try:
        socketio.run(app, host=args.host, port=args.port, allow_unsafe_werkzeug=True)
    finally:
        graph.stop()
        print("[StandaloneGraphViewer] Stopped")

