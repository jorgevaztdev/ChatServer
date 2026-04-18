"""Integration tests — Phase 5: US-CONTACTS (T032–T035)."""


# ── helpers ───────────────────────────────────────────────────────────────────

def _reg(client, email, password, username):
    return client.post("/auth/register", json={"email": email, "password": password, "username": username})


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def _setup_alice(client):
    _reg(client, "alice@test.com", "pass123", "alice")
    _login(client, "alice@test.com", "pass123")


def _setup_bob(client):
    from fastapi.testclient import TestClient
    from src.main import app
    from src.api.deps import get_db
    from tests.integration.conftest import _override_get_db  # reuse same DB override

    bob = TestClient(app)
    app.dependency_overrides[get_db] = _override_get_db
    _reg(bob, "bob@test.com", "pass123", "bob")
    _login(bob, "bob@test.com", "pass123")
    return bob


# ── T032: POST /friends/request ───────────────────────────────────────────────

def test_send_request_returns_201(client):
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    res = client.post("/friends/request", json={"username": "bob"})
    assert res.status_code == 201
    data = res.json()
    assert data["addressee"] == "bob"
    assert data["status"] == "pending"


def test_send_request_unknown_user_returns_404(client):
    _setup_alice(client)
    res = client.post("/friends/request", json={"username": "nobody"})
    assert res.status_code == 404


def test_send_request_to_self_returns_400(client):
    _setup_alice(client)
    res = client.post("/friends/request", json={"username": "alice"})
    assert res.status_code == 400


def test_send_duplicate_request_returns_409(client):
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    client.post("/friends/request", json={"username": "bob"})
    res = client.post("/friends/request", json={"username": "bob"})
    assert res.status_code == 409


def test_send_request_requires_auth(client):
    res = client.post("/friends/request", json={"username": "bob"})
    assert res.status_code == 401


def test_send_request_with_optional_message(client):
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    res = client.post("/friends/request", json={"username": "bob", "message": "Hey!"})
    assert res.status_code == 201


# ── T033: POST /friends/accept/{requester_id} ────────────────────────────────

def test_accept_request_returns_200(client):
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    # Alice sends request to Bob
    client.post("/friends/request", json={"username": "bob"})

    # Get alice's user_id
    alice_id = client.get("/auth/me").json()["id"]

    # Switch to Bob
    client.post("/auth/logout")
    _login(client, "bob@test.com", "pass123")

    res = client.post(f"/friends/accept/{alice_id}")
    assert res.status_code == 200
    assert res.json()["detail"] == "Friend request accepted"


def test_accept_nonexistent_request_returns_404(client):
    _setup_alice(client)
    res = client.post("/friends/accept/9999")
    assert res.status_code == 404


def test_accept_request_requires_auth(client):
    res = client.post("/friends/accept/1")
    assert res.status_code == 401


# ── T033: DELETE /friends/{user_id} ──────────────────────────────────────────

def test_remove_friend_returns_200(client):
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    client.post("/friends/request", json={"username": "bob"})
    alice_id = client.get("/auth/me").json()["id"]

    client.post("/auth/logout")
    _login(client, "bob@test.com", "pass123")
    client.post(f"/friends/accept/{alice_id}")

    res = client.delete(f"/friends/{alice_id}")
    assert res.status_code == 200
    assert res.json()["detail"] == "Friend removed"


def test_remove_nonexistent_friend_returns_404(client):
    _setup_alice(client)
    res = client.delete("/friends/9999")
    assert res.status_code == 404


def test_remove_pending_request_returns_404(client):
    """Cannot use DELETE /friends/{id} on a pending request — use decline instead."""
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    client.post("/friends/request", json={"username": "bob"})
    bob_id_res = client.post("/auth/logout")

    _login(client, "bob@test.com", "pass123")
    bob_id = client.get("/auth/me").json()["id"]

    client.post("/auth/logout")
    _login(client, "alice@test.com", "pass123")

    res = client.delete(f"/friends/{bob_id}")
    assert res.status_code == 404


def test_remove_friend_requires_auth(client):
    res = client.delete("/friends/1")
    assert res.status_code == 401


# ── T033: DELETE /friends/decline/{requester_id} ─────────────────────────────

def test_decline_request_returns_200(client):
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    client.post("/friends/request", json={"username": "bob"})
    alice_id = client.get("/auth/me").json()["id"]

    client.post("/auth/logout")
    _login(client, "bob@test.com", "pass123")
    res = client.delete(f"/friends/decline/{alice_id}")
    assert res.status_code == 200


def test_decline_nonexistent_request_returns_404(client):
    _setup_alice(client)
    res = client.delete("/friends/decline/9999")
    assert res.status_code == 404


# ── T034: GET /friends ────────────────────────────────────────────────────────

def test_list_friends_empty_returns_200(client):
    _setup_alice(client)
    res = client.get("/friends")
    assert res.status_code == 200
    assert res.json() == []


def test_list_friends_shows_accepted_friend(client):
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    client.post("/friends/request", json={"username": "bob"})
    alice_id = client.get("/auth/me").json()["id"]

    client.post("/auth/logout")
    _login(client, "bob@test.com", "pass123")
    client.post(f"/friends/accept/{alice_id}")

    friends = client.get("/friends").json()
    assert len(friends) == 1
    assert friends[0]["username"] == "alice"
    assert "presence" in friends[0]


def test_list_friends_bidirectional(client):
    """Both alice and bob see each other after accept."""
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    client.post("/friends/request", json={"username": "bob"})
    alice_id = client.get("/auth/me").json()["id"]

    client.post("/auth/logout")
    _login(client, "bob@test.com", "pass123")
    client.post(f"/friends/accept/{alice_id}")
    bob_friends = client.get("/friends").json()
    assert any(f["username"] == "alice" for f in bob_friends)

    client.post("/auth/logout")
    _login(client, "alice@test.com", "pass123")
    alice_friends = client.get("/friends").json()
    assert any(f["username"] == "bob" for f in alice_friends)


def test_list_friends_not_shown_after_remove(client):
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    client.post("/friends/request", json={"username": "bob"})
    alice_id = client.get("/auth/me").json()["id"]

    client.post("/auth/logout")
    _login(client, "bob@test.com", "pass123")
    client.post(f"/friends/accept/{alice_id}")

    client.delete(f"/friends/{alice_id}")
    friends = client.get("/friends").json()
    assert friends == []


def test_list_friends_requires_auth(client):
    res = client.get("/friends")
    assert res.status_code == 401


def test_list_friends_pending_not_shown(client):
    """Pending request not shown in friends list."""
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    client.post("/friends/request", json={"username": "bob"})

    friends = client.get("/friends").json()
    assert friends == []


# ── T035: GET /friends/requests ──────────────────────────────────────────────

def test_list_requests_empty_returns_200(client):
    _setup_alice(client)
    res = client.get("/friends/requests")
    assert res.status_code == 200
    assert res.json() == []


def test_list_requests_shows_pending_incoming(client):
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    client.post("/friends/request", json={"username": "bob"})
    alice_id = client.get("/auth/me").json()["id"]

    client.post("/auth/logout")
    _login(client, "bob@test.com", "pass123")

    reqs = client.get("/friends/requests").json()
    assert len(reqs) == 1
    assert reqs[0]["username"] == "alice"
    assert reqs[0]["requester_id"] == alice_id


def test_list_requests_not_shown_for_requester(client):
    """Sender does NOT see own outgoing request in /friends/requests."""
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    client.post("/friends/request", json={"username": "bob"})

    reqs = client.get("/friends/requests").json()
    assert reqs == []


def test_list_requests_cleared_after_accept(client):
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    client.post("/friends/request", json={"username": "bob"})
    alice_id = client.get("/auth/me").json()["id"]

    client.post("/auth/logout")
    _login(client, "bob@test.com", "pass123")
    client.post(f"/friends/accept/{alice_id}")

    reqs = client.get("/friends/requests").json()
    assert reqs == []


def test_list_requests_cleared_after_decline(client):
    _setup_alice(client)
    _reg(client, "bob@test.com", "pass123", "bob")
    client.post("/friends/request", json={"username": "bob"})
    alice_id = client.get("/auth/me").json()["id"]

    client.post("/auth/logout")
    _login(client, "bob@test.com", "pass123")
    client.delete(f"/friends/decline/{alice_id}")

    reqs = client.get("/friends/requests").json()
    assert reqs == []


def test_list_requests_requires_auth(client):
    res = client.get("/friends/requests")
    assert res.status_code == 401
