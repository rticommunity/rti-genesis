import os
import json
import pytest

from flask import Flask
from flask_socketio import SocketIO

from genesis_lib.graph_state import GraphService
from genesis_lib.web.graph_viewer import register_graph_viewer


@pytest.mark.parametrize("source", ["live", "snapshot"])
def test_api_graph_returns_json(tmp_path, source):
    # Prepare snapshot file if requested
    snapshot_path = tmp_path / "graph_snapshot.json"
    if source == "snapshot":
        data = {"elements": {"nodes": [], "edges": []}}
        snapshot_path.write_text(json.dumps(data))
        os.environ["GRAPH_SNAPSHOT_PATH"] = str(snapshot_path)

    app = Flask(__name__)
    app.config['TESTING'] = True
    socketio = SocketIO(app, async_mode='threading')

    graph = GraphService(domain_id=int(os.getenv("GENESIS_DOMAIN", "0")))
    graph.start()
    try:
        register_graph_viewer(app, socketio, graph, url_prefix="/genesis-graph")
        client = app.test_client()
        resp = client.get(f"/genesis-graph/api/graph?source={source}")
        assert resp.status_code == 200
        obj = resp.get_json()
        assert isinstance(obj, dict)
        assert "elements" in obj
        assert "nodes" in obj["elements"] and "edges" in obj["elements"]
    finally:
        graph.stop()


