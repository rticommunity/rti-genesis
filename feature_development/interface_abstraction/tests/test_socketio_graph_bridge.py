import json
from flask import Flask
from flask_socketio import SocketIO

from genesis_lib.web.socketio_graph_bridge import attach_graph_to_socketio


class DummyGraph:
    def __init__(self):
        self._subs = []
        self._activity_subs = []

    # API expected by the bridge
    def subscribe(self, cb):
        self._subs.append(cb)

    def subscribe_activity(self, cb):
        self._activity_subs.append(cb)

    def to_cytoscape(self):
        return {"elements": {"nodes": [], "edges": []}}

    # Test helpers
    def notify_node(self):
        evt = ("node_update", {"node": {"id": "n1"}})
        for cb in self._subs:
            cb(*evt)

    def notify_edge(self):
        evt = ("edge_update", {"edge": {"source": "n1", "target": "n2"}})
        for cb in self._subs:
            cb(*evt)

    def notify_activity(self):
        act = {"chain_id": "c1", "source_id": "n1", "target_id": "n2", "event_type": "REQUEST"}
        for cb in self._activity_subs:
            cb(act)


def test_socketio_bridge_forwards_events():
    # Setup app and socket
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test'
    socketio = SocketIO(app, async_mode='threading', logger=False, engineio_logger=False, cors_allowed_origins="*")

    # Dummy graph and attach bridge
    graph = DummyGraph()
    attach_graph_to_socketio(graph, socketio)

    # Create test client
    client = socketio.test_client(app)
    assert client.is_connected()

    # Request snapshot
    client.emit('graph_snapshot')
    recvd = client.get_received()
    assert any(pkt['name'] == 'graph_snapshot' for pkt in recvd)

    # Simulate node/edge and activity events
    graph.notify_node()
    graph.notify_edge()
    graph.notify_activity()

    recvd = client.get_received()
    names = [pkt['name'] for pkt in recvd]
    assert 'node_update' in names
    assert 'edge_update' in names
    assert 'activity' in names

    client.disconnect()
