"""Integration tests for Phase 4 — US-PRESENCE."""
import pytest
from fastapi.testclient import TestClient


def _setup_user(client, email="p@test.com", password="pass1234", username="puser"):
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


def test_presence_status_offline_after_disconnect(client):
    """User is offline once their WS connection closes."""
    uid = _setup_user(client)
    from src.services.websocket_hub import hub
    with client.websocket_connect("/ws/presence") as ws:
        ws.receive_json()  # initial ack
        assert hub.is_online(uid)
    # after context exit, connection is closed
    assert not hub.is_online(uid)


def test_presence_status_string_values(client):
    """get_presence_status returns 'online' for active user, 'offline' for unknown."""
    uid = _setup_user(client, email="strval@t.com", username="strval")
    from src.services.websocket_hub import hub
    assert hub.get_presence_status(uid) == "offline"
    with client.websocket_connect("/ws/presence") as ws:
        ws.receive_json()  # ack
        status = hub.get_presence_status(uid)
        assert status == "online"
    assert hub.get_presence_status(uid) == "offline"


def test_presence_unknown_user_is_offline(client):
    """Non-existent user ID always returns offline."""
    from src.services.websocket_hub import hub
    assert hub.get_presence_status(999999) == "offline"
    assert not hub.is_online(999999)


def test_afk_status_on_heartbeat_with_stale_activity(client):
    """Heartbeat that is older than AFK threshold makes user AFK."""
    uid = _setup_user(client, email="afktest@t.com", username="afktest")
    from src.services.websocket_hub import hub
    from datetime import datetime, timedelta

    with client.websocket_connect("/ws/presence") as ws:
        ws.receive_json()  # ack
        assert hub.get_presence_status(uid) == "online"

        # Manually backdate the tab activity to simulate 61s of idle
        tab_data = hub._activity.get(uid, {})
        past_time = datetime.utcnow() - timedelta(seconds=61)
        for tab_id in tab_data:
            tab_data[tab_id] = past_time

        # Now presence status should be AFK
        assert hub.get_presence_status(uid) == "AFK"


def test_multi_tab_online_while_any_tab_active(client):
    """User stays online as long as at least one tab is connected."""
    uid = _setup_user(client, email="multitab@t.com", username="multitab")
    from src.services.websocket_hub import hub
    import time

    with client.websocket_connect("/ws/presence") as ws1:
        ws1.receive_json()
        with client.websocket_connect("/ws/presence") as ws2:
            ws2.receive_json()
            tab_count = len(hub._activity.get(uid, {}))
            assert tab_count >= 1
            assert hub.is_online(uid)
        # ws2 closed — ws1 still open
        assert hub.is_online(uid)
    # all closed
    assert not hub.is_online(uid)
