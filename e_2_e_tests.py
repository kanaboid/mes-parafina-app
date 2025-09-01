import pytest
import socketio
from app import create_app, db

# --- FIXTURES ---

@pytest.fixture(scope="session")
def app():
    app = create_app(testing=True)
    return app

@pytest.fixture(scope="function")
def client(app):
    with app.test_client() as c:
        with app.app_context():
            db.create_all()
        yield c
        with app.app_context():
            db.drop_all()

@pytest.fixture(scope="function")
def sio_client(live_server):
    client = socketio.Client()
    client.connect(live_server.url())
    yield client
    client.disconnect()

# --- TESTS ---

# Smoke test – sprawdza czy backend wstaje i /api/partie/aktywne działa
def test_smoke_active_batches(client):
    resp = client.get("/api/partie/aktywne")
    assert resp.status_code == 200
    assert isinstance(resp.json, list)

# Scenariusz: utworzenie partii i mieszaniny
def test_create_batch_and_mix(client):
    resp = client.post("/api/partie", json={"surowiec": "Parafina A", "masa": 1000})
    assert resp.status_code == 200
    batch_id = resp.json["id"]

    resp2 = client.post("/api/mix", json={"batch_id": batch_id, "sprzet_id": 1})
    assert resp2.status_code == 200
    mix_id = resp2.json["id"]

    resp3 = client.get("/api/partie/aktualny-stan")
    assert resp3.status_code == 200
    assert any(p["id"] == batch_id for p in resp3.json)

# Test realtime – emit i odbiór broadcastu
def test_realtime_command_broadcast(sio_client):
    messages = []

    @sio_client.on("dashboard_update")
    def on_update(data):
        messages.append(data)

    sio_client.emit("command_from_client", {"action": "start_cykl", "partia": 123})
    sio_client.sleep(1)

    assert any("partia" in msg for msg in messages)
