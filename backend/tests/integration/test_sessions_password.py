"""Tests for session management and password operations (T025-T027, T030-T031)."""
import pytest


# ─── helpers ──────────────────────────────────────────────────────────────────

def _register_login(client, email, password, username):
    client.post("/auth/register", json={"email": email, "password": password, "username": username})
    return client.post("/auth/login", json={"email": email, "password": password})


# ─── GET /auth/sessions ────────────────────────────────────────────────────────

def test_list_sessions_returns_current_session(client):
    _register_login(client, "sess@test.com", "pass123", "sess_user")
    r = client.get("/auth/sessions")
    assert r.status_code == 200
    sessions = r.json()
    assert isinstance(sessions, list)
    assert len(sessions) >= 1
    current = [s for s in sessions if s["is_current"]]
    assert len(current) == 1


def test_list_sessions_includes_fields(client):
    _register_login(client, "sess2@test.com", "pass123", "sess_user2")
    r = client.get("/auth/sessions")
    assert r.status_code == 200
    s = r.json()[0]
    assert "id" in s
    assert "created_at" in s
    assert "user_agent" in s
    assert "ip_address" in s
    assert "is_current" in s


def test_list_sessions_requires_auth(client):
    r = client.get("/auth/sessions")
    assert r.status_code == 401


def test_multiple_logins_create_multiple_sessions(client):
    client.post("/auth/register", json={"email": "multi@test.com", "password": "pass123", "username": "multi_user"})
    client.post("/auth/login", json={"email": "multi@test.com", "password": "pass123"})
    client.post("/auth/login", json={"email": "multi@test.com", "password": "pass123"})
    r = client.get("/auth/sessions")
    assert r.status_code == 200
    assert len(r.json()) >= 2


# ─── DELETE /auth/sessions/{id} ───────────────────────────────────────────────

def test_revoke_other_session_returns_204(client):
    client.post("/auth/register", json={"email": "rev@test.com", "password": "pass123", "username": "rev_user"})
    client.post("/auth/login", json={"email": "rev@test.com", "password": "pass123"})
    # Second login creates another session
    client.post("/auth/login", json={"email": "rev@test.com", "password": "pass123"})

    sessions = client.get("/auth/sessions").json()
    other = next((s for s in sessions if not s["is_current"]), None)
    assert other is not None, "Expected at least one non-current session"

    r = client.delete(f"/auth/sessions/{other['id']}")
    assert r.status_code == 204

    remaining = client.get("/auth/sessions").json()
    ids = [s["id"] for s in remaining]
    assert other["id"] not in ids


def test_revoke_current_session_clears_cookie(client):
    client.post("/auth/register", json={"email": "revcurr@test.com", "password": "pass123", "username": "revcurr"})
    client.post("/auth/login", json={"email": "revcurr@test.com", "password": "pass123"})

    sessions = client.get("/auth/sessions").json()
    current = next(s for s in sessions if s["is_current"])

    r = client.delete(f"/auth/sessions/{current['id']}")
    assert r.status_code == 204
    # After revoking current session, /me should return 401
    assert client.get("/auth/me").status_code == 401


def test_revoke_nonexistent_session_returns_404(client):
    _register_login(client, "rev404@test.com", "pass123", "rev404_user")
    r = client.delete("/auth/sessions/99999")
    assert r.status_code == 404


def test_revoke_another_users_session_returns_404(client):
    """User cannot revoke another user's session — must appear as 404."""
    client.post("/auth/register", json={"email": "a@test.com", "password": "pass123", "username": "user_a"})
    r_a = client.post("/auth/login", json={"email": "a@test.com", "password": "pass123"})

    client.post("/auth/register", json={"email": "b@test.com", "password": "pass123", "username": "user_b"})
    r_b = client.post("/auth/login", json={"email": "b@test.com", "password": "pass123"})

    # Get B's session id while logged in as B
    sessions_b = client.get("/auth/sessions").json()
    session_b_id = sessions_b[0]["id"]

    # Log in as A
    client.post("/auth/login", json={"email": "a@test.com", "password": "pass123"})
    sessions_a = client.get("/auth/sessions").json()
    # Make sure we're looking at A's session now
    session_a = next(s for s in sessions_a if s["is_current"])

    # A tries to delete B's session id
    r = client.delete(f"/auth/sessions/{session_b_id}")
    # Either 404 (not found for this user) or different user entirely
    assert r.status_code == 404


def test_revoke_session_requires_auth(client):
    r = client.delete("/auth/sessions/1")
    assert r.status_code == 401


# ─── POST /auth/forgot-password ───────────────────────────────────────────────

def test_forgot_password_known_email_returns_token(client):
    client.post("/auth/register", json={"email": "forgot@test.com", "password": "pass123", "username": "forgot_user"})
    r = client.post("/auth/forgot-password", json={"email": "forgot@test.com"})
    assert r.status_code == 200
    data = r.json()
    assert "reset_token" in data
    assert data["reset_token"] is not None
    assert len(data["reset_token"]) > 10


def test_forgot_password_unknown_email_returns_generic(client):
    r = client.post("/auth/forgot-password", json={"email": "nobody@test.com"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("reset_token") is None


# ─── POST /auth/reset-password ────────────────────────────────────────────────

def test_reset_password_valid_token_succeeds(client):
    client.post("/auth/register", json={"email": "reset@test.com", "password": "oldpass", "username": "reset_user"})
    token = client.post("/auth/forgot-password", json={"email": "reset@test.com"}).json()["reset_token"]

    r = client.post("/auth/reset-password", json={"token": token, "new_password": "newpass456"})
    assert r.status_code == 200
    assert r.json()["detail"] == "Password reset"


def test_reset_password_allows_login_with_new_password(client):
    client.post("/auth/register", json={"email": "reset2@test.com", "password": "oldpass", "username": "reset_user2"})
    token = client.post("/auth/forgot-password", json={"email": "reset2@test.com"}).json()["reset_token"]
    client.post("/auth/reset-password", json={"token": token, "new_password": "newpass456"})

    r = client.post("/auth/login", json={"email": "reset2@test.com", "password": "newpass456"})
    assert r.status_code == 200


def test_reset_password_old_password_rejected_after_reset(client):
    client.post("/auth/register", json={"email": "reset3@test.com", "password": "oldpass", "username": "reset_user3"})
    token = client.post("/auth/forgot-password", json={"email": "reset3@test.com"}).json()["reset_token"]
    client.post("/auth/reset-password", json={"token": token, "new_password": "newpass456"})

    r = client.post("/auth/login", json={"email": "reset3@test.com", "password": "oldpass"})
    assert r.status_code == 401


def test_reset_password_token_can_only_be_used_once(client):
    client.post("/auth/register", json={"email": "reset4@test.com", "password": "oldpass", "username": "reset_user4"})
    token = client.post("/auth/forgot-password", json={"email": "reset4@test.com"}).json()["reset_token"]
    client.post("/auth/reset-password", json={"token": token, "new_password": "newpass456"})

    r = client.post("/auth/reset-password", json={"token": token, "new_password": "anotherpass"})
    assert r.status_code == 400
    assert "already used" in r.json()["detail"]


def test_reset_password_invalid_token_returns_400(client):
    r = client.post("/auth/reset-password", json={"token": "bad-token-xyz", "new_password": "newpass"})
    assert r.status_code == 400
    assert "Invalid reset token" in r.json()["detail"]


# ─── PUT /auth/password ───────────────────────────────────────────────────────

def test_change_password_succeeds_with_correct_current(client):
    _register_login(client, "chpw@test.com", "oldpass", "chpw_user")
    r = client.put("/auth/password", json={"current_password": "oldpass", "new_password": "newpass789"})
    assert r.status_code == 200
    assert r.json()["detail"] == "Password changed"


def test_change_password_allows_login_with_new(client):
    _register_login(client, "chpw2@test.com", "oldpass", "chpw_user2")
    client.put("/auth/password", json={"current_password": "oldpass", "new_password": "newpass789"})

    client.post("/auth/logout")
    r = client.post("/auth/login", json={"email": "chpw2@test.com", "password": "newpass789"})
    assert r.status_code == 200


def test_change_password_wrong_current_returns_400(client):
    _register_login(client, "chpw3@test.com", "pass123", "chpw_user3")
    r = client.put("/auth/password", json={"current_password": "wrongpass", "new_password": "newpass"})
    assert r.status_code == 400
    assert "incorrect" in r.json()["detail"]


def test_change_password_requires_auth(client):
    r = client.put("/auth/password", json={"current_password": "x", "new_password": "y"})
    assert r.status_code == 401
