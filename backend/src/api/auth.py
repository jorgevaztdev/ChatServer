import os
import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_current_user
from src.config import MEDIA_DIR
from src.models.attachment import Attachment
from src.models.message import Message
from src.models.room import Room, RoomBan, RoomMembership
from src.models.session import UserSession
from src.models.user import User
from src.services.auth import create_jwt, decode_jwt, hash_password, verify_password

router = APIRouter()

_COOKIE = "access_token"
_COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1 year — persistent across browser restarts


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "email": current_user.email, "is_admin": current_user.is_admin}


class RegisterRequest(BaseModel):
    email: str
    password: str
    username: str


class LoginRequest(BaseModel):
    email: str
    password: str


# ── helpers ──────────────────────────────────────────────────────────────────

def _delete_attachment_files(message_id: int, db: Session) -> None:
    for att in db.query(Attachment).filter(Attachment.message_id == message_id).all():
        try:
            os.remove(att.stored_path)
        except FileNotFoundError:
            pass
        db.delete(att)


def _delete_room_cascade(room_id: int, db: Session) -> None:
    for msg in db.query(Message).filter(Message.room_id == room_id).all():
        _delete_attachment_files(msg.id, db)
        db.delete(msg)
    db.query(RoomMembership).filter(RoomMembership.room_id == room_id).delete()
    db.query(RoomBan).filter(RoomBan.room_id == room_id).delete()
    room = db.query(Room).filter(Room.id == room_id).first()
    if room:
        db.delete(room)


# ── T020: POST /auth/register ─────────────────────────────────────────────────

@router.post("/register", status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    user = User(
        email=body.email,
        username=body.username,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "email": user.email}


# ── T021: POST /auth/login ────────────────────────────────────────────────────

@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    session_token = str(uuid.uuid4())
    db.add(UserSession(user_id=user.id, token=session_token))
    db.commit()
    token = create_jwt({"user_id": user.id, "session_token": session_token})
    response.set_cookie(
        key=_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
    )
    return {"id": user.id, "username": user.username, "email": user.email}


# ── T022: POST /auth/logout ───────────────────────────────────────────────────

@router.post("/logout")
def logout(
    response: Response,
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if access_token:
        payload = decode_jwt(access_token)
        session_token = payload.get("session_token")
        if session_token:
            db.query(UserSession).filter(UserSession.token == session_token).delete()
            db.commit()
    response.delete_cookie(_COOKIE)
    return {"detail": "Logged out"}


# ── T023: DELETE /auth/account ────────────────────────────────────────────────

@router.delete("/account", status_code=204)
def delete_account(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id

    # Delete owned rooms (messages + attachments + files + memberships + bans)
    for room in db.query(Room).filter(Room.owner_id == uid).all():
        _delete_room_cascade(room.id, db)

    # Delete DM messages sent by user (room_id is null)
    for msg in db.query(Message).filter(Message.sender_id == uid, Message.room_id.is_(None)).all():
        _delete_attachment_files(msg.id, db)
        db.delete(msg)

    # Remove non-owned memberships
    db.query(RoomMembership).filter(RoomMembership.user_id == uid).delete()

    # Delete all sessions
    db.query(UserSession).filter(UserSession.user_id == uid).delete()

    db.delete(current_user)
    db.commit()
    response.delete_cookie(_COOKIE)
