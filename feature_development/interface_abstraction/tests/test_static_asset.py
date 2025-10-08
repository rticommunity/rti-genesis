import os
from flask import Flask
from flask_socketio import SocketIO

from genesis_lib.graph_state import GraphService
from genesis_lib.web.graph_viewer import register_graph_viewer


def test_static_reference_js_served():
    app = Flask(__name__)
    app.config['TESTING'] = True
    socketio = SocketIO(app, async_mode='threading')

    graph = GraphService(domain_id=int(os.getenv("GENESIS_DOMAIN", "0")))
    graph.start()
    try:
        register_graph_viewer(app, socketio, graph, url_prefix="/genesis-graph")
        client = app.test_client()
        resp = client.get("/genesis-graph/static/reference.js")
        assert resp.status_code == 200
        assert b"initGraphViewer" in resp.data
    finally:
        graph.stop()


