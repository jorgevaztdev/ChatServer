"""Integration tests for Phase 3 — US-AUTH."""


def _reg(client, email="a@b.com", password="pass1234", username="alice"):
    return client.post("/auth/register", json={"email": email, "password": password, "username": username})


def _login(client, email="a@b.com", password="pass1234"):
    return client.post("/auth/login", json={"email": email, "password": password})


# ── register ──────────────────────────────────────────────────────────────────

def test_register_returns_201(client):
    res = _reg(client)
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == "alice"
    assert data["email"] == "a@b.com"
    assert "password" not in data
    assert "password_hash" not in data


def test_register_duplicate_email_returns_409(client):
    _reg(client)
    res = _reg(client, username="bob")
    assert res.status_code == 409
    assert "Email" in res.json()["detail"]


def test_register_duplicate_username_returns_409(client):
    _reg(client)
    res = _reg(client, email="other@b.com")
    assert res.status_code == 409
    assert "Username" in res.json()["detail"]


# ── login ─────────────────────────────────────────────────────────────────────

def test_login_valid_returns_200_and_cookie(client):
    _reg(client)
    res = _login(client)
    assert res.status_code == 200
    assert "access_token" in res.cookies
    assert res.json()["username"] == "alice"


def test_login_wrong_password_returns_401(client):
    _reg(client)
    res = _login(client, password="wrongpass")
    assert res.status_code == 401


def test_login_unknown_email_returns_401(client):
    res = _login(client, email="nobody@b.com")
    assert res.status_code == 401


# ── /auth/me ──────────────────────────────────────────────────────────────────

def test_me_returns_user_when_authenticated(client):
    _reg(client)
    _login(client)
    res = client.get("/auth/me")
    assert res.status_code == 200
    assert res.json()["username"] == "alice"


def test_me_returns_401_when_not_authenticated(client):
    res = client.get("/auth/me")
    assert res.status_code == 401


# ── logout ────────────────────────────────────────────────────────────────────

def test_logout_clears_cookie(client):
    _reg(client)
    _login(client)
    res = client.post("/auth/logout")
    assert res.status_code == 200
    # After logout, /auth/me must reject
    assert client.get("/auth/me").status_code == 401


def test_logout_only_current_session(client):
    _reg(client)
    # Session 1 — kept in `client` cookie jar
    _login(client)

    # Session 2 — separate client shares no cookies
    from fastapi.testclient import TestClient
    from src.main import app
    client2 = TestClient(app)
    client2.post("/auth/login", json={"email": "a@b.com", "password": "pass1234"})

    # Logout session 1
    client.post("/auth/logout")

    # Session 1 is dead
    assert client.get("/auth/me").status_code == 401
    # Session 2 still alive
    assert client2.get("/auth/me").status_code == 200


# ── delete account ────────────────────────────────────────────────────────────

def test_delete_account_returns_204(client):
    _reg(client)
    _login(client)
    res = client.delete("/auth/account")
    assert res.status_code == 204


def test_delete_account_login_fails_after(client):
    _reg(client)
    _login(client)
    client.delete("/auth/account")
    res = _login(client)
    assert res.status_code == 401


def test_delete_account_requires_auth(client):
    res = client.delete("/auth/account")
    assert res.status_code == 401
