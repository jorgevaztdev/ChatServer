"""Integration tests for Phase 6 — US-BAN."""
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


def _make_friends(ca, cb, uid_a):
    """ca sends request; cb accepts."""
    cb_user = cb.get("/auth/me").json()["username"]
    ca.post("/friends/request", json={"username": cb_user})
    cb.post(f"/friends/accept/{uid_a}")


# ── POST /bans/user/{id} ──────────────────────────────────────────────────────

def test_ban_user_returns_201(client):
    uid_a = _setup(client, "ban1a@t.com", "ban1a")
    c2 = _mk(); uid_b = _setup(c2, "ban1b@t.com", "ban1b")
    _make_friends(client, c2, uid_a)
    res = client.post(f"/bans/user/{uid_b}")
    assert res.status_code == 201
    assert res.json()["banned_user_id"] == uid_b


def test_ban_terminates_friendship(client):
    uid_a = _setup(client, "ban2a@t.com", "ban2a")
    c2 = _mk(); uid_b = _setup(c2, "ban2b@t.com", "ban2b")
    _make_friends(client, c2, uid_a)
    client.post(f"/bans/user/{uid_b}")
    friends = client.get("/friends").json()
    assert not any(f["user_id"] == uid_b for f in friends)


def test_ban_nonexistent_user(client):
    _setup(client, "ban3@t.com", "ban3")
    res = client.post("/bans/user/99999")
    assert res.status_code == 404


def test_ban_self_returns_400(client):
    uid = _setup(client, "ban4@t.com", "ban4")
    res = client.post(f"/bans/user/{uid}")
    assert res.status_code == 400


def test_ban_duplicate_returns_409(client):
    uid_a = _setup(client, "ban5a@t.com", "ban5a")
    c2 = _mk(); uid_b = _setup(c2, "ban5b@t.com", "ban5b")
    client.post(f"/bans/user/{uid_b}")
    res = client.post(f"/bans/user/{uid_b}")
    assert res.status_code == 409


def test_ban_requires_auth(client):
    c2 = _mk(); uid_b = _setup(c2, "ban6b@t.com", "ban6b")
    res = client.post(f"/bans/user/{uid_b}")
    assert res.status_code == 401


# ── GET /bans ─────────────────────────────────────────────────────────────────

def test_list_bans_empty(client):
    _setup(client, "blist1@t.com", "blist1")
    res = client.get("/bans")
    assert res.status_code == 200
    assert res.json() == []


def test_list_bans_shows_banned_user(client):
    _setup(client, "blist2a@t.com", "blist2a")
    c2 = _mk(); uid_b = _setup(c2, "blist2b@t.com", "blist2b")
    client.post(f"/bans/user/{uid_b}")
    bans = client.get("/bans").json()
    assert any(b["banned_user_id"] == uid_b for b in bans)


def test_list_bans_not_visible_to_banned_user(client):
    uid_a = _setup(client, "blist3a@t.com", "blist3a")
    c2 = _mk(); uid_b = _setup(c2, "blist3b@t.com", "blist3b")
    client.post(f"/bans/user/{uid_b}")
    # banned user's GET /bans should show empty (they didn't ban anyone)
    bans = c2.get("/bans").json()
    assert not any(b["banned_user_id"] == uid_a for b in bans)


# ── DELETE /bans/user/{id} — unban ───────────────────────────────────────────

def test_unban_user(client):
    _setup(client, "unban1a@t.com", "unban1a")
    c2 = _mk(); uid_b = _setup(c2, "unban1b@t.com", "unban1b")
    client.post(f"/bans/user/{uid_b}")
    res = client.delete(f"/bans/user/{uid_b}")
    assert res.status_code == 200
    bans = client.get("/bans").json()
    assert not any(b["banned_user_id"] == uid_b for b in bans)


def test_unban_nonexistent_ban(client):
    _setup(client, "unban2@t.com", "unban2")
    c2 = _mk(); uid_b = _setup(c2, "unban2b@t.com", "unban2b")
    res = client.delete(f"/bans/user/{uid_b}")
    assert res.status_code == 404


# ── GET /bans/check/{id} ──────────────────────────────────────────────────────

def test_check_ban_returns_false_when_no_ban(client):
    _setup(client, "chk1a@t.com", "chk1a")
    c2 = _mk(); uid_b = _setup(c2, "chk1b@t.com", "chk1b")
    res = client.get(f"/bans/check/{uid_b}")
    assert res.status_code == 200
    assert res.json()["banned"] is False


def test_check_ban_returns_true_after_ban(client):
    _setup(client, "chk2a@t.com", "chk2a")
    c2 = _mk(); uid_b = _setup(c2, "chk2b@t.com", "chk2b")
    client.post(f"/bans/user/{uid_b}")
    res = client.get(f"/bans/check/{uid_b}")
    assert res.json()["banned"] is True
    assert res.json()["you_banned_them"] is True


def test_check_ban_detects_reverse_ban(client):
    uid_a = _setup(client, "chk3a@t.com", "chk3a")
    c2 = _mk(); _setup(c2, "chk3b@t.com", "chk3b")
    # B bans A; A checks — should see banned=True, you_banned_them=False
    c2.post(f"/bans/user/{uid_a}")
    res = client.get(f"/bans/check/{c2.get('/auth/me').json()['id']}")
    assert res.json()["banned"] is True
    assert res.json()["you_banned_them"] is False


# ── T038: DM blocked after ban ────────────────────────────────────────────────

def test_dm_blocked_after_ban(client):
    uid_a = _setup(client, "dm_ban_a@t.com", "dm_ban_a")
    c2 = _mk(); uid_b = _setup(c2, "dm_ban_b@t.com", "dm_ban_b")
    _make_friends(client, c2, uid_a)
    # A bans B
    client.post(f"/bans/user/{uid_b}")
    # A tries to DM B — should be 403
    res = client.post(f"/dms/{uid_b}/messages", json={"content": "blocked?"})
    assert res.status_code == 403


def test_dm_blocked_reverse_ban(client):
    uid_a = _setup(client, "dm_rban_a@t.com", "dm_rban_a")
    c2 = _mk(); uid_b = _setup(c2, "dm_rban_b@t.com", "dm_rban_b")
    _make_friends(client, c2, uid_a)
    # B bans A; A tries to DM B — also 403 (ban in either direction blocks)
    c2.post(f"/bans/user/{uid_a}")
    res = client.post(f"/dms/{uid_b}/messages", json={"content": "hi?"})
    assert res.status_code == 403
