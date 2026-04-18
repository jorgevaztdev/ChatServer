"""Integration tests for Phase 4 — US-PRESENCE."""
import pytest
from fastapi.testclient import TestClient


def _setup_user(client, email="p@test.com", password="pass123", username="puser"):
    client.post("/auth/register", json={"email": email, "password": password, "username": username})
    client.post("/auth/login", json={"email": email, "password": password})
    me = client.get("/auth/me").json()
    return me["id"]


# ── WebSocket presence endpoint ───────────────────────────────────────────────

def test_presence_ws_rejects_without_auth(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/presence") as ws:
            ws.receive_json()


def test_presence_ws_accepts_authenticated_user(client):
    _setup_user(client)
    with client.websocket_connect("/ws/presence") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "presence:ack"
        assert msg["payload"]["status"] == "online"


def test_presence_heartbeat_returns_ack(client):
    _setup_user(client)
    with client.websocket_connect("/ws/presence") as ws:
        ws.receive_json()  # initial ack
        ws.send_json({"type": "heartbeat", "tab_id": "tab-abc"})
        ack = ws.receive_json()
        assert ack["type"] == "presence:ack"
        assert ack["payload"]["status"] == "online"


def test_presence_broadcast_on_connect(client):
    """Second user sees first user go online when they connect."""
    uid1 = _setup_user(client, email="u1@t.com", username="user1")

    from fastapi.testclient import TestClient
    from src.main import app
    from src.api.deps import get_db
    from tests.integration.conftest import _override_get_db
    app.dependency_overrides[get_db] = _override_get_db

    client2 = TestClient(app)
    _setup_user(client2, email="u2@t.com", username="user2")

    with client.websocket_connect("/ws/presence") as ws1:
        ws1.receive_json()  # own ack
        with client2.websocket_connect("/ws/presence") as ws2:
            ws2.receive_json()  # own ack
            # ws1 should receive presence:update for user2 going online
            update = ws1.receive_json()
            assert update["type"] == "presence:update"
            assert update["payload"]["status"] == "online"


def test_get_status_returns_online_after_connect(client):
    _setup_user(client)
    from src.services import presence as p
    from src.services.websocket_hub import hub
    # No connections yet — offline
    assert p.get_status(999) == "offline"
