import os
from flask import Flask
from flask_socketio import SocketIO

from genesis_lib.graph_state import GraphService
from genesis_lib.web.socketio_graph_bridge import attach_graph_to_socketio


def test_socketio_graph_snapshot_event_returns_elements():
    app = Flask(__name__)
    app.config['TESTING'] = True
    socketio = SocketIO(app, async_mode='threading')

    # Use an empty GraphService; we don't need DDS for this snapshot test
    graph = GraphService(domain_id=int(os.getenv("GENESIS_DOMAIN", "0")))

    attach_graph_to_socketio(graph, socketio)

    client = socketio.test_client(app, namespace='/')
    assert client.is_connected('/'), "Socket should connect"

    # Request a snapshot and capture the emitted message
    client.emit('graph_snapshot', namespace='/')
    received = client.get_received('/')

    # Find the graph_snapshot event
    payload = None
    for pkt in received:
        if pkt.get('name') == 'graph_snapshot':
            payload = pkt.get('args', [{}])[0]
            break

    assert payload is not None, f"Expected graph_snapshot event, got: {received}"
    assert 'elements' in payload
    assert 'nodes' in payload['elements'] and 'edges' in payload['elements']


