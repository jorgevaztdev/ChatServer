"""Tests for DM history, unread tracking, room unread, and room CRUD extensions."""
import pytest


# ─── helpers ──────────────────────────────────────────────────────────────────

def _mk(client, email, password, username):
    client.post("/auth/register", json={"email": email, "password": password, "username": username})
    client.post("/auth/login", json={"email": email, "password": password})
    return client.get("/auth/me").json()


def _befriend(client, user_id):
    client.post(f"/friends/request/{user_id}")
    # To accept, we need to act as the target — but in single-client tests we'll
    # use admin or just test from the sender side.


def _setup_friends(client):
    """Register alice + bob, make them friends, return (alice_id, bob_id)."""
    alice = _mk(client, "alice@dm.com", "pass", "alice_dm")
    bob = _mk(client, "bob@dm.com", "pass", "bob_dm")

    # Alice sends request to Bob by username
    client.post("/auth/login", json={"email": "alice@dm.com", "password": "pass"})
    client.post("/friends/request", json={"username": "bob_dm"})

    # Bob accepts using Alice's user_id
    client.post("/auth/login", json={"email": "bob@dm.com", "password": "pass"})
    client.post(f"/friends/accept/{alice['id']}")

    return alice["id"], bob["id"]


# ─── GET /dms/{user_id}/messages ─────────────────────────────────────────────

def test_dm_history_empty_for_new_friendship(client):
    alice_id, bob_id = _setup_friends(client)
    # Still logged in as Bob
    r = client.get(f"/dms/{alice_id}/messages")
    assert r.status_code == 200
    assert r.json() == []


def test_dm_history_returns_sent_messages(client):
    alice_id, bob_id = _setup_friends(client)

    # Bob sends to Alice
    client.post(f"/dms/{alice_id}/messages", json={"content": "Hello Alice!"})

    r = client.get(f"/dms/{alice_id}/messages")
    assert r.status_code == 200
    msgs = r.json()
    assert len(msgs) == 1
    assert msgs[0]["content"] == "Hello Alice!"


def test_dm_history_bidirectional(client):
    alice_id, bob_id = _setup_friends(client)

    # Bob sends to Alice
    client.post(f"/dms/{alice_id}/messages", json={"content": "Hi from Bob"})

    # Alice sends to Bob
    client.post("/auth/login", json={"email": "alice@dm.com", "password": "pass"})
    client.post(f"/dms/{bob_id}/messages", json={"content": "Hi from Alice"})

    r = client.get(f"/dms/{bob_id}/messages")
    assert r.status_code == 200
    contents = {m["content"] for m in r.json()}
    assert "Hi from Bob" in contents
    assert "Hi from Alice" in contents


def test_dm_history_cursor_pagination(client):
    alice_id, bob_id = _setup_friends(client)

    for i in range(5):
        client.post(f"/dms/{alice_id}/messages", json={"content": f"msg {i}"})

    all_msgs = client.get(f"/dms/{alice_id}/messages").json()
    assert len(all_msgs) == 5

    # Fetch with before= cursor
    pivot = all_msgs[2]["id"]
    older = client.get(f"/dms/{alice_id}/messages?before={pivot}").json()
    assert all(m["id"] < pivot for m in older)


def test_dm_history_limit_param(client):
    alice_id, bob_id = _setup_friends(client)

    for i in range(10):
        client.post(f"/dms/{alice_id}/messages", json={"content": f"msg {i}"})

    r = client.get(f"/dms/{alice_id}/messages?limit=3")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_dm_history_nonexistent_user_returns_404(client):
    _mk(client, "alice2@dm.com", "pass", "alice_dm2")
    r = client.get("/dms/99999/messages")
    assert r.status_code == 404


def test_dm_history_requires_auth(client):
    r = client.get("/dms/1/messages")
    assert r.status_code == 401


# ─── GET /dms/unread ─────────────────────────────────────────────────────────

def test_dm_unread_zero_initially(client):
    alice_id, bob_id = _setup_friends(client)
    # Logged in as Bob
    r = client.get("/dms/unread")
    assert r.status_code == 200
    data = r.json()
    alice_entry = next((x for x in data if x["partner_id"] == alice_id), None)
    assert alice_entry is not None
    assert alice_entry["unread_count"] == 0


def test_dm_unread_increments_when_message_received(client):
    alice_id, bob_id = _setup_friends(client)

    # Alice sends Bob a message
    client.post("/auth/login", json={"email": "alice@dm.com", "password": "pass"})
    client.post(f"/dms/{bob_id}/messages", json={"content": "Hey Bob!"})

    # Bob checks unread
    client.post("/auth/login", json={"email": "bob@dm.com", "password": "pass"})
    r = client.get("/dms/unread")
    data = r.json()
    alice_entry = next(x for x in data if x["partner_id"] == alice_id)
    assert alice_entry["unread_count"] == 1


def test_dm_unread_resets_after_mark_read(client):
    alice_id, bob_id = _setup_friends(client)

    # Alice sends 2 messages
    client.post("/auth/login", json={"email": "alice@dm.com", "password": "pass"})
    client.post(f"/dms/{bob_id}/messages", json={"content": "msg 1"})
    client.post(f"/dms/{bob_id}/messages", json={"content": "msg 2"})

    # Bob marks as read
    client.post("/auth/login", json={"email": "bob@dm.com", "password": "pass"})
    client.post(f"/dms/{alice_id}/read")

    r = client.get("/dms/unread")
    data = r.json()
    alice_entry = next(x for x in data if x["partner_id"] == alice_id)
    assert alice_entry["unread_count"] == 0


def test_dm_unread_requires_auth(client):
    r = client.get("/dms/unread")
    assert r.status_code == 401


# ─── POST /dms/{user_id}/read ─────────────────────────────────────────────────

def test_mark_dm_read_returns_200(client):
    alice_id, bob_id = _setup_friends(client)
    # Bob marks alice convo as read
    r = client.post(f"/dms/{alice_id}/read")
    assert r.status_code == 200


def test_mark_dm_read_idempotent(client):
    alice_id, bob_id = _setup_friends(client)
    client.post(f"/dms/{alice_id}/read")
    r = client.post(f"/dms/{alice_id}/read")
    assert r.status_code == 200


def test_mark_dm_read_requires_auth(client):
    r = client.post("/dms/1/read")
    assert r.status_code == 401


# ─── GET /rooms/unread ────────────────────────────────────────────────────────

def test_room_unread_zero_for_member_with_no_messages(client):
    _mk(client, "roomuser@test.com", "pass", "room_unread_user")
    room = client.post("/rooms", json={"name": "unread-room", "is_private": False}).json()
    r = client.get("/rooms/unread")
    assert r.status_code == 200
    data = r.json()
    entry = next((x for x in data if x["room_id"] == room["id"]), None)
    assert entry is not None
    assert entry["unread_count"] == 0


def test_room_unread_increments_with_new_message(client):
    _mk(client, "ru2@test.com", "pass", "ru2_user")
    room = client.post("/rooms", json={"name": "unread-room2", "is_private": False}).json()
    client.post(f"/rooms/{room['id']}/messages", json={"content": "new msg"})

    r = client.get("/rooms/unread")
    entry = next(x for x in r.json() if x["room_id"] == room["id"])
    assert entry["unread_count"] == 1


def test_room_unread_resets_after_mark_read(client):
    _mk(client, "ru3@test.com", "pass", "ru3_user")
    room = client.post("/rooms", json={"name": "unread-room3", "is_private": False}).json()
    client.post(f"/rooms/{room['id']}/messages", json={"content": "hello"})
    client.post(f"/rooms/{room['id']}/messages", json={"content": "world"})

    client.post(f"/rooms/{room['id']}/read")
    r = client.get("/rooms/unread")
    entry = next(x for x in r.json() if x["room_id"] == room["id"])
    assert entry["unread_count"] == 0


def test_room_unread_requires_auth(client):
    r = client.get("/rooms/unread")
    assert r.status_code == 401


# ─── POST /rooms/{room_id}/read ───────────────────────────────────────────────

def test_mark_room_read_returns_200(client):
    _mk(client, "rmread@test.com", "pass", "rmread_user")
    room = client.post("/rooms", json={"name": "markread-room", "is_private": False}).json()
    r = client.post(f"/rooms/{room['id']}/read")
    assert r.status_code == 200


def test_mark_room_read_non_member_returns_403(client):
    _mk(client, "rmread2@test.com", "pass", "rmread_user2")
    room = client.post("/rooms", json={"name": "markread-room2", "is_private": False}).json()

    _mk(client, "rmread3@test.com", "pass", "rmread_user3")
    r = client.post(f"/rooms/{room['id']}/read")
    assert r.status_code == 403


def test_mark_room_read_idempotent(client):
    _mk(client, "rmread4@test.com", "pass", "rmread_user4")
    room = client.post("/rooms", json={"name": "markread-room4", "is_private": False}).json()
    client.post(f"/rooms/{room['id']}/read")
    r = client.post(f"/rooms/{room['id']}/read")
    assert r.status_code == 200


# ─── PUT /rooms/{room_id} ─────────────────────────────────────────────────────

def test_update_room_name_by_owner(client):
    _mk(client, "ruedit@test.com", "pass", "ruedit_user")
    room = client.post("/rooms", json={"name": "old-name", "is_private": False}).json()

    r = client.put(f"/rooms/{room['id']}", json={"name": "new-name"})
    assert r.status_code == 200
    assert r.json()["name"] == "new-name"


def test_update_room_description_by_owner(client):
    _mk(client, "ruedit2@test.com", "pass", "ruedit_user2")
    room = client.post("/rooms", json={"name": "desc-room", "is_private": False}).json()

    r = client.put(f"/rooms/{room['id']}", json={"description": "a description"})
    assert r.status_code == 200
    assert r.json()["description"] == "a description"


def test_update_room_privacy_by_owner(client):
    _mk(client, "ruedit3@test.com", "pass", "ruedit_user3")
    room = client.post("/rooms", json={"name": "pub-room", "is_private": False}).json()

    r = client.put(f"/rooms/{room['id']}", json={"is_private": True})
    assert r.status_code == 200
    assert r.json()["is_private"] is True


def test_update_room_name_conflict_returns_409(client):
    _mk(client, "ruedit4@test.com", "pass", "ruedit_user4")
    client.post("/rooms", json={"name": "taken-room", "is_private": False})
    room2 = client.post("/rooms", json={"name": "my-room", "is_private": False}).json()

    r = client.put(f"/rooms/{room2['id']}", json={"name": "taken-room"})
    assert r.status_code == 409


def test_update_room_non_owner_returns_403(client):
    _mk(client, "ruedit5@test.com", "pass", "ruedit_user5")
    room = client.post("/rooms", json={"name": "owner-room", "is_private": False}).json()

    _mk(client, "ruedit6@test.com", "pass", "ruedit_user6")
    client.post(f"/rooms/{room['id']}/join")
    r = client.put(f"/rooms/{room['id']}", json={"name": "hijacked"})
    assert r.status_code == 403


def test_update_room_requires_auth(client):
    r = client.put("/rooms/1", json={"name": "x"})
    assert r.status_code == 401


# ─── GET /rooms/{room_id} ─────────────────────────────────────────────────────

def test_get_room_detail_returns_fields(client):
    _mk(client, "getroom@test.com", "pass", "getroom_user")
    room = client.post("/rooms", json={"name": "detail-room", "description": "desc here", "is_private": False}).json()

    r = client.get(f"/rooms/{room['id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == room["id"]
    assert data["name"] == "detail-room"
    assert data["description"] == "desc here"
    assert "member_count" in data


def test_get_room_detail_nonexistent_returns_404(client):
    _mk(client, "getroom2@test.com", "pass", "getroom_user2")
    r = client.get("/rooms/99999")
    assert r.status_code == 404


def test_get_private_room_requires_membership(client):
    _mk(client, "getroom3@test.com", "pass", "getroom_user3")
    room = client.post("/rooms", json={"name": "priv-detail", "is_private": True}).json()

    _mk(client, "getroom4@test.com", "pass", "getroom_user4")
    r = client.get(f"/rooms/{room['id']}")
    assert r.status_code == 403


def test_get_room_detail_requires_auth(client):
    r = client.get("/rooms/1")
    assert r.status_code == 401
