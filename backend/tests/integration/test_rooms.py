"""Integration tests for Phase 7 — US-ROOMS."""
import pytest


def _login(client, email="room@test.com", password="pass1234", username="roomuser"):
    client.post("/auth/register", json={"email": email, "password": password, "username": username})
    client.post("/auth/login", json={"email": email, "password": password})
    return client.get("/auth/me").json()["id"]


# ── T040: Create room ─────────────────────────────────────────────────────────

def test_create_public_room(client):
    _login(client)
    res = client.post("/rooms", json={"name": "general", "description": "Hello", "is_private": False})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "general"
    assert data["is_private"] is False


def test_create_private_room(client):
    _login(client)
    res = client.post("/rooms", json={"name": "secret", "is_private": True})
    assert res.status_code == 201
    assert res.json()["is_private"] is True


def test_create_room_duplicate_name(client):
    _login(client)
    client.post("/rooms", json={"name": "dup-room"})
    res = client.post("/rooms", json={"name": "dup-room"})
    assert res.status_code == 409


def test_create_room_requires_auth(client):
    res = client.post("/rooms", json={"name": "no-auth"})
    assert res.status_code == 401


# ── T041: List + search ───────────────────────────────────────────────────────

def test_list_rooms_returns_public_only(client):
    _login(client)
    client.post("/rooms", json={"name": "public-room", "is_private": False})
    client.post("/rooms", json={"name": "hidden-room", "is_private": True})
    res = client.get("/rooms")
    assert res.status_code == 200
    names = [r["name"] for r in res.json()]
    assert "public-room" in names
    assert "hidden-room" not in names


def test_list_rooms_has_member_count(client):
    _login(client)
    client.post("/rooms", json={"name": "counted-room"})
    rooms = client.get("/rooms").json()
    room = next(r for r in rooms if r["name"] == "counted-room")
    assert room["member_count"] >= 1


def test_search_rooms(client):
    _login(client)
    client.post("/rooms", json={"name": "python-talk"})
    client.post("/rooms", json={"name": "rust-talk"})
    res = client.get("/rooms/search?q=python")
    assert res.status_code == 200
    data = res.json()
    names = [r["name"] for r in data["results"]]
    assert "python-talk" in names
    assert "rust-talk" not in names


def test_search_rooms_empty_q_returns_all_public(client):
    _login(client)
    client.post("/rooms", json={"name": "open-1"})
    client.post("/rooms", json={"name": "open-2"})
    res = client.get("/rooms/search?q=")
    assert res.status_code == 200
    assert len(res.json()["results"]) >= 2


# ── T042: Join public room ────────────────────────────────────────────────────

def test_join_public_room(client):
    from fastapi.testclient import TestClient
    from src.main import app
    from src.api.deps import get_db
    from tests.integration.conftest import _override_get_db
    app.dependency_overrides[get_db] = _override_get_db

    _login(client)
    res_room = client.post("/rooms", json={"name": "joinable"})
    room_id = res_room.json()["id"]

    client2 = TestClient(app)
    _login(client2, email="joiner@test.com", username="joiner")
    res = client2.post(f"/rooms/{room_id}/join")
    assert res.status_code == 200


def test_join_private_room_fails(client):
    from fastapi.testclient import TestClient
    from src.main import app
    from src.api.deps import get_db
    from tests.integration.conftest import _override_get_db
    app.dependency_overrides[get_db] = _override_get_db

    _login(client)
    res_room = client.post("/rooms", json={"name": "private-join", "is_private": True})
    room_id = res_room.json()["id"]

    client2 = TestClient(app)
    _login(client2, email="blocked@test.com", username="blocked")
    res = client2.post(f"/rooms/{room_id}/join")
    assert res.status_code == 403


def test_join_nonexistent_room(client):
    _login(client)
    res = client.post("/rooms/99999/join")
    assert res.status_code == 404


# ── T043: Invite to private room ──────────────────────────────────────────────

def test_invite_to_private_room(client):
    from fastapi.testclient import TestClient
    from src.main import app
    from src.api.deps import get_db
    from tests.integration.conftest import _override_get_db
    app.dependency_overrides[get_db] = _override_get_db

    _login(client)
    room_id = client.post("/rooms", json={"name": "invite-room", "is_private": True}).json()["id"]

    client2 = TestClient(app)
    _login(client2, email="invitee@test.com", username="invitee")

    res = client.post(f"/rooms/{room_id}/invite", json={"username": "invitee"})
    assert res.status_code == 200

    # invitee can now access room details
    detail = client2.get(f"/rooms/{room_id}")
    assert detail.status_code == 200


def test_invite_requires_admin(client):
    from fastapi.testclient import TestClient
    from src.main import app
    from src.api.deps import get_db
    from tests.integration.conftest import _override_get_db
    app.dependency_overrides[get_db] = _override_get_db

    _login(client)
    room_id = client.post("/rooms", json={"name": "admin-only", "is_private": True}).json()["id"]

    client2 = TestClient(app)
    _login(client2, email="nonadmin@test.com", username="nonadmin")

    # nonadmin tries to invite — should fail
    client3 = TestClient(app)
    _login(client3, email="victim@test.com", username="victim")
    res = client2.post(f"/rooms/{room_id}/invite", json={"username": "victim"})
    assert res.status_code == 403


# ── T044: Leave room ──────────────────────────────────────────────────────────

def test_leave_room(client):
    from fastapi.testclient import TestClient
    from src.main import app
    from src.api.deps import get_db
    from tests.integration.conftest import _override_get_db
    app.dependency_overrides[get_db] = _override_get_db

    _login(client)
    room_id = client.post("/rooms", json={"name": "leavable"}).json()["id"]

    client2 = TestClient(app)
    _login(client2, email="leaver@test.com", username="leaver")
    client2.post(f"/rooms/{room_id}/join")
    res = client2.post(f"/rooms/{room_id}/leave")
    assert res.status_code == 200


def test_owner_cannot_leave(client):
    _login(client)
    room_id = client.post("/rooms", json={"name": "owner-leave"}).json()["id"]
    res = client.post(f"/rooms/{room_id}/leave")
    assert res.status_code == 403


def test_leave_room_not_member(client):
    from fastapi.testclient import TestClient
    from src.main import app
    from src.api.deps import get_db
    from tests.integration.conftest import _override_get_db
    app.dependency_overrides[get_db] = _override_get_db

    _login(client)
    room_id = client.post("/rooms", json={"name": "leave-fail"}).json()["id"]

    client2 = TestClient(app)
    _login(client2, email="nonmember@test.com", username="nonmember")
    res = client2.post(f"/rooms/{room_id}/leave")
    assert res.status_code == 404
