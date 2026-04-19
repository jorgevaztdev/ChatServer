"""Integration tests for Phase 10 — US-FILES (T063-T065)."""
import io
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


def _create_room(client, name):
    res = client.post("/rooms", json={"name": name})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _make_friends(ca, cb, uid_a):
    cb_user = cb.get("/auth/me").json()["username"]
    ca.post("/friends/request", json={"username": cb_user})
    cb.post(f"/friends/accept/{uid_a}")


def _small_png():
    """Valid 1x1 pixel PNG — 67 bytes, well under 3 MB."""
    return io.BytesIO(
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00'
        b'\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18'
        b'\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )


def _text_file(content=b"hello world"):
    return io.BytesIO(content)


# ── T063: POST /upload — room ────────────────────────────────────────────────

def test_upload_image_to_room_returns_201(client):
    _setup(client, "up1@t.com", "up1")
    room_id = _create_room(client, "up_room1")

    res = client.post("/upload",
        data={"room_id": str(room_id)},
        files={"file": ("test.png", _small_png(), "image/png")},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["attachment"] is not None
    assert body["attachment"]["mime_type"] == "image/png"
    assert body["attachment"]["url"].startswith("/files/")


def test_upload_text_file_to_room_with_comment(client):
    _setup(client, "up2@t.com", "up2")
    room_id = _create_room(client, "up_room2")

    res = client.post("/upload",
        data={"room_id": str(room_id), "comment": "see attached"},
        files={"file": ("notes.txt", _text_file(), "text/plain")},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["content"] == "see attached"
    assert body["attachment"]["original_filename"] == "notes.txt"


def test_upload_requires_room_or_dm(client):
    _setup(client, "up3@t.com", "up3")
    # Neither room_id nor dm_partner_id — should fail
    res = client.post("/upload",
        files={"file": ("f.txt", _text_file(), "text/plain")},
    )
    assert res.status_code == 400


def test_upload_both_room_and_dm_returns_400(client):
    uid_a = _setup(client, "up4a@t.com", "up4a")
    c2 = _mk(); uid_b = _setup(c2, "up4b@t.com", "up4b")
    room_id = _create_room(client, "up_room4")
    res = client.post("/upload",
        data={"room_id": str(room_id), "dm_partner_id": str(uid_b)},
        files={"file": ("f.txt", _text_file(), "text/plain")},
    )
    assert res.status_code == 400


def test_upload_nonmember_returns_403(client):
    _setup(client, "up5a@t.com", "up5a")
    c2 = _mk(); _setup(c2, "up5b@t.com", "up5b")
    room_id = _create_room(client, "up_room5")
    # c2 is not a member
    res = c2.post("/upload",
        data={"room_id": str(room_id)},
        files={"file": ("f.txt", _text_file(), "text/plain")},
    )
    assert res.status_code == 403


def test_upload_requires_auth(client):
    # Not logged in — get_current_user should return 401
    res = client.post("/upload",
        data={"room_id": "1"},
        files={"file": ("f.txt", _text_file(), "text/plain")},
    )
    assert res.status_code == 401


# ── T065: Size enforcement ────────────────────────────────────────────────────

def test_image_over_3mb_rejected(client):
    _setup(client, "sz1@t.com", "sz1")
    room_id = _create_room(client, "sz_room1")

    big_image = io.BytesIO(b'\x00' * (3 * 1024 * 1024 + 1))
    res = client.post("/upload",
        data={"room_id": str(room_id)},
        files={"file": ("big.png", big_image, "image/png")},
    )
    assert res.status_code == 413


def test_file_over_20mb_rejected(client):
    _setup(client, "sz2@t.com", "sz2")
    room_id = _create_room(client, "sz_room2")

    big_file = io.BytesIO(b'\x00' * (20 * 1024 * 1024 + 1))
    res = client.post("/upload",
        data={"room_id": str(room_id)},
        files={"file": ("big.bin", big_file, "application/octet-stream")},
    )
    assert res.status_code == 413


# ── T063: POST /upload — DM ──────────────────────────────────────────────────

def test_upload_dm_without_friendship_returns_403(client):
    _setup(client, "dm1a@t.com", "dm1a")
    c2 = _mk(); uid_b = _setup(c2, "dm1b@t.com", "dm1b")
    res = client.post("/upload",
        data={"dm_partner_id": str(uid_b)},
        files={"file": ("f.txt", _text_file(), "text/plain")},
    )
    assert res.status_code == 403


def test_upload_dm_with_friendship_returns_201(client):
    uid_a = _setup(client, "dm2a@t.com", "dm2a")
    c2 = _mk(); uid_b = _setup(c2, "dm2b@t.com", "dm2b")
    _make_friends(client, c2, uid_a)

    res = client.post("/upload",
        data={"dm_partner_id": str(uid_b)},
        files={"file": ("msg.txt", _text_file(b"hi there"), "text/plain")},
    )
    assert res.status_code == 201, res.text
    assert res.json()["attachment"]["original_filename"] == "msg.txt"


# ── T064: GET /files/{id} ─────────────────────────────────────────────────────

def test_download_room_file_as_member(client):
    _setup(client, "dl1@t.com", "dl1")
    room_id = _create_room(client, "dl_room1")

    up = client.post("/upload",
        data={"room_id": str(room_id)},
        files={"file": ("hello.txt", _text_file(b"hello file"), "text/plain")},
    )
    assert up.status_code == 201, up.text
    att_id = up.json()["attachment"]["id"]

    res = client.get(f"/files/{att_id}")
    assert res.status_code == 200
    assert res.content == b"hello file"


def test_download_room_file_as_nonmember_returns_403(client):
    _setup(client, "dl2a@t.com", "dl2a")
    c2 = _mk(); _setup(c2, "dl2b@t.com", "dl2b")
    room_id = _create_room(client, "dl_room2")

    up = client.post("/upload",
        data={"room_id": str(room_id)},
        files={"file": ("secret.txt", _text_file(b"secret"), "text/plain")},
    )
    att_id = up.json()["attachment"]["id"]

    res = c2.get(f"/files/{att_id}")
    assert res.status_code == 403


def test_download_nonexistent_returns_404(client):
    _setup(client, "dl3@t.com", "dl3")
    res = client.get("/files/99999")
    assert res.status_code == 404


def test_banned_room_member_cannot_download(client):
    _setup(client, "dl4a@t.com", "dl4a")
    c2 = _mk(); uid_b = _setup(c2, "dl4b@t.com", "dl4b")
    room_id = _create_room(client, "dl_room4")
    client.post(f"/rooms/{room_id}/invite", json={"username": "dl4b"})

    up = client.post("/upload",
        data={"room_id": str(room_id)},
        files={"file": ("doc.txt", _text_file(b"private"), "text/plain")},
    )
    att_id = up.json()["attachment"]["id"]

    # Ban c2 from room — removes membership
    client.post(f"/rooms/{room_id}/ban/{uid_b}")

    res = c2.get(f"/files/{att_id}")
    assert res.status_code == 403
