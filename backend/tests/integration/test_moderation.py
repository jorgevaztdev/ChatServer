"""Integration tests for Phase 8 — US-MODERATION (T046-T051)."""
from fastapi.testclient import TestClient
from src.main import app
from src.api.deps import get_db
from tests.integration.conftest import _override_get_db


def _mk():
    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def _setup(client, email, username, password="pass1234"):
    client.post("/auth/register", json={"email": email, "password": password, "username": username})
    client.post("/auth/login", json={"email": email, "password": password})
    return client.get("/auth/me").json()["id"]


def _create_room(client, name, is_private=False):
    res = client.post("/rooms", json={"name": name, "is_private": is_private})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _join(client, room_id):
    res = client.post(f"/rooms/{room_id}/join")
    assert res.status_code in (200,), res.text


def _send_msg(client, room_id, content="hello"):
    res = client.post(f"/rooms/{room_id}/messages", json={"content": content})
    assert res.status_code == 201, res.text
    return res.json()["id"]


# ── T046: Admin delete message ────────────────────────────────────────────────

def test_admin_delete_message_returns_204(client):
    uid_a = _setup(client, "mod1a@t.com", "mod1a")
    c2 = _mk(); _setup(c2, "mod1b@t.com", "mod1b")
    room_id = _create_room(client, "mod_room1")
    _join(c2, room_id)
    msg_id = _send_msg(c2, room_id)
    res = client.delete(f"/rooms/{room_id}/messages/{msg_id}")
    assert res.status_code == 204


def test_admin_delete_wrong_room_msg_returns_404(client):
    _setup(client, "mod2@t.com", "mod2")
    room_id = _create_room(client, "mod_room2")
    res = client.delete(f"/rooms/{room_id}/messages/99999")
    assert res.status_code == 404


def test_non_admin_cannot_delete_other_message(client):
    _setup(client, "mod3a@t.com", "mod3a")
    c2 = _mk(); _setup(c2, "mod3b@t.com", "mod3b")
    room_id = _create_room(client, "mod_room3")
    _join(c2, room_id)
    msg_id = _send_msg(client, room_id)
    # c2 is a regular member, not admin
    res = c2.delete(f"/rooms/{room_id}/messages/{msg_id}")
    assert res.status_code == 403


# ── T047: Ban room member ─────────────────────────────────────────────────────

def test_ban_member_returns_201(client):
    _setup(client, "rban1a@t.com", "rban1a")
    c2 = _mk(); uid_b = _setup(c2, "rban1b@t.com", "rban1b")
    room_id = _create_room(client, "rban_room1")
    _join(c2, room_id)
    res = client.post(f"/rooms/{room_id}/ban/{uid_b}")
    assert res.status_code == 201
    assert res.json()["banned_user_id"] == uid_b


def test_ban_removes_membership(client):
    _setup(client, "rban2a@t.com", "rban2a")
    c2 = _mk(); uid_b = _setup(c2, "rban2b@t.com", "rban2b")
    room_id = _create_room(client, "rban_room2")
    _join(c2, room_id)
    client.post(f"/rooms/{room_id}/ban/{uid_b}")
    members = client.get(f"/rooms/{room_id}/members").json()
    assert not any(m["user_id"] == uid_b for m in members)


def test_ban_prevents_rejoin(client):
    _setup(client, "rban3a@t.com", "rban3a")
    c2 = _mk(); uid_b = _setup(c2, "rban3b@t.com", "rban3b")
    room_id = _create_room(client, "rban_room3")
    _join(c2, room_id)
    client.post(f"/rooms/{room_id}/ban/{uid_b}")
    res = c2.post(f"/rooms/{room_id}/join")
    assert res.status_code == 403


def test_ban_self_returns_400(client):
    uid_a = _setup(client, "rban4@t.com", "rban4")
    room_id = _create_room(client, "rban_room4")
    res = client.post(f"/rooms/{room_id}/ban/{uid_a}")
    assert res.status_code == 400


def test_cannot_ban_room_owner(client):
    uid_a = _setup(client, "rban5a@t.com", "rban5a")
    c2 = _mk(); _setup(c2, "rban5b@t.com", "rban5b")
    room_id = _create_room(client, "rban_room5")
    # Promote c2 to admin first via invite
    c2_res = c2.get("/auth/me").json()
    c2_id = c2_res["id"]
    client.post(f"/rooms/{room_id}/invite", json={"username": "rban5b"})
    client.post(f"/rooms/{room_id}/admins/{c2_id}")
    # c2 (admin) tries to ban owner
    res = c2.post(f"/rooms/{room_id}/ban/{uid_a}")
    assert res.status_code == 403


def test_ban_duplicate_returns_409(client):
    _setup(client, "rban6a@t.com", "rban6a")
    c2 = _mk(); uid_b = _setup(c2, "rban6b@t.com", "rban6b")
    room_id = _create_room(client, "rban_room6")
    _join(c2, room_id)
    client.post(f"/rooms/{room_id}/ban/{uid_b}")
    res = client.post(f"/rooms/{room_id}/ban/{uid_b}")
    assert res.status_code == 409


def test_non_admin_cannot_ban(client):
    _setup(client, "rban7a@t.com", "rban7a")
    c2 = _mk(); _setup(c2, "rban7b@t.com", "rban7b")
    c3 = _mk(); uid_c = _setup(c3, "rban7c@t.com", "rban7c")
    room_id = _create_room(client, "rban_room7")
    _join(c2, room_id)
    _join(c3, room_id)
    res = c2.post(f"/rooms/{room_id}/ban/{uid_c}")
    assert res.status_code == 403


# ── T048: Unban ───────────────────────────────────────────────────────────────

def test_unban_allows_rejoin(client):
    _setup(client, "unrban1a@t.com", "unrban1a")
    c2 = _mk(); uid_b = _setup(c2, "unrban1b@t.com", "unrban1b")
    room_id = _create_room(client, "unrban_room1")
    _join(c2, room_id)
    client.post(f"/rooms/{room_id}/ban/{uid_b}")
    res = client.delete(f"/rooms/{room_id}/ban/{uid_b}")
    assert res.status_code == 200
    # Now c2 can rejoin
    res2 = c2.post(f"/rooms/{room_id}/join")
    assert res2.status_code == 200


def test_unban_nonexistent_returns_404(client):
    _setup(client, "unrban2@t.com", "unrban2")
    c2 = _mk(); uid_b = _setup(c2, "unrban2b@t.com", "unrban2b")
    room_id = _create_room(client, "unrban_room2")
    res = client.delete(f"/rooms/{room_id}/ban/{uid_b}")
    assert res.status_code == 404


# ── T049: Promote / Demote ────────────────────────────────────────────────────

def test_promote_to_admin(client):
    _setup(client, "promo1a@t.com", "promo1a")
    c2 = _mk(); uid_b = _setup(c2, "promo1b@t.com", "promo1b")
    room_id = _create_room(client, "promo_room1")
    _join(c2, room_id)
    res = client.post(f"/rooms/{room_id}/admins/{uid_b}")
    assert res.status_code == 200
    members = client.get(f"/rooms/{room_id}/members").json()
    b = next(m for m in members if m["user_id"] == uid_b)
    assert b["role"] == "admin"


def test_demote_admin(client):
    _setup(client, "demote1a@t.com", "demote1a")
    c2 = _mk(); uid_b = _setup(c2, "demote1b@t.com", "demote1b")
    room_id = _create_room(client, "demote_room1")
    _join(c2, room_id)
    client.post(f"/rooms/{room_id}/admins/{uid_b}")
    res = client.delete(f"/rooms/{room_id}/admins/{uid_b}")
    assert res.status_code == 200
    members = client.get(f"/rooms/{room_id}/members").json()
    b = next(m for m in members if m["user_id"] == uid_b)
    assert b["role"] == "member"


def test_non_owner_cannot_promote(client):
    _setup(client, "promo2a@t.com", "promo2a")
    c2 = _mk(); _setup(c2, "promo2b@t.com", "promo2b")
    c3 = _mk(); uid_c = _setup(c3, "promo2c@t.com", "promo2c")
    room_id = _create_room(client, "promo_room2")
    _join(c2, room_id)
    _join(c3, room_id)
    # c2 is member (not owner) — cannot promote
    res = c2.post(f"/rooms/{room_id}/admins/{uid_c}")
    assert res.status_code == 403


def test_cannot_demote_owner(client):
    uid_a = _setup(client, "demote2a@t.com", "demote2a")
    c2 = _mk(); _setup(c2, "demote2b@t.com", "demote2b")
    room_id = _create_room(client, "demote_room2")
    c2_id = c2.get("/auth/me").json()["id"]
    client.post(f"/rooms/{room_id}/invite", json={"username": "demote2b"})
    client.post(f"/rooms/{room_id}/admins/{c2_id}")
    # Try to demote the owner (uid_a) — must fail
    res = client.delete(f"/rooms/{room_id}/admins/{uid_a}")
    assert res.status_code == 400


# ── T050: Delete room ─────────────────────────────────────────────────────────

def test_owner_can_delete_room(client):
    _setup(client, "delroom1@t.com", "delroom1")
    room_id = _create_room(client, "del_room1")
    res = client.delete(f"/rooms/{room_id}")
    assert res.status_code == 204


def test_non_owner_cannot_delete_room(client):
    _setup(client, "delroom2a@t.com", "delroom2a")
    c2 = _mk(); _setup(c2, "delroom2b@t.com", "delroom2b")
    room_id = _create_room(client, "del_room2")
    _join(c2, room_id)
    res = c2.delete(f"/rooms/{room_id}")
    assert res.status_code == 403


def test_deleted_room_returns_404(client):
    _setup(client, "delroom3@t.com", "delroom3")
    room_id = _create_room(client, "del_room3")
    client.delete(f"/rooms/{room_id}")
    res = client.get(f"/rooms/{room_id}")
    assert res.status_code == 404


# ── T051: List room bans ──────────────────────────────────────────────────────

def test_list_room_bans_empty(client):
    _setup(client, "blist1@t.com", "blist_rm1")
    room_id = _create_room(client, "blist_room1")
    res = client.get(f"/rooms/{room_id}/bans")
    assert res.status_code == 200
    assert res.json() == []


def test_list_room_bans_shows_banned_user(client):
    _setup(client, "blist2a@t.com", "blist_rm2a")
    c2 = _mk(); uid_b = _setup(c2, "blist2b@t.com", "blist_rm2b")
    room_id = _create_room(client, "blist_room2")
    _join(c2, room_id)
    client.post(f"/rooms/{room_id}/ban/{uid_b}")
    bans = client.get(f"/rooms/{room_id}/bans").json()
    assert any(b["banned_user_id"] == uid_b for b in bans)


def test_non_admin_cannot_list_bans(client):
    _setup(client, "blist3a@t.com", "blist_rm3a")
    c2 = _mk(); _setup(c2, "blist3b@t.com", "blist_rm3b")
    room_id = _create_room(client, "blist_room3")
    _join(c2, room_id)
    res = c2.get(f"/rooms/{room_id}/bans")
    assert res.status_code == 403
