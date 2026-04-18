import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.main import app
from src.models.base import Base
from src.api.deps import get_db

_HERE = os.path.dirname(os.path.abspath(__file__))
_TEST_DB_PATH = os.path.join(_HERE, "test_chat.db")
_TEST_DB = f"sqlite:///{_TEST_DB_PATH}"
_engine = create_engine(_TEST_DB, connect_args={"check_same_thread": False})


@event.listens_for(_engine, "connect")
def _fk_on(conn, _):
    conn.execute("PRAGMA foreign_keys=ON")


_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(tmp_path):
    import src.config as cfg
    import src.api.files as files_api
    import src.models.base as model_base

    original_media = cfg.MEDIA_DIR
    original_api   = files_api.MEDIA_DIR
    original_engine = model_base.engine
    original_session_local = model_base.SessionLocal

    cfg.MEDIA_DIR       = str(tmp_path)
    files_api.MEDIA_DIR = str(tmp_path)
    model_base.engine        = _engine
    model_base.SessionLocal  = _Session

    from src.models import user, session, room, message, attachment, social, password_reset, unread  # noqa: F401
    from src.services.websocket_hub import hub
    Base.metadata.create_all(bind=_engine)
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=_engine)
    hub._connections.clear()
    hub._room_users.clear()
    hub._activity.clear()
    hub._last_disconnect.clear()

    cfg.MEDIA_DIR            = original_media
    files_api.MEDIA_DIR      = original_api
    model_base.engine        = original_engine
    model_base.SessionLocal  = original_session_local


@pytest.fixture()
def registered(client):
    """Return client with a registered + logged-in user."""
    client.post("/auth/register", json={"email": "alice@test.com", "password": "pass123", "username": "alice"})
    client.post("/auth/login", json={"email": "alice@test.com", "password": "pass123"})
    return client
