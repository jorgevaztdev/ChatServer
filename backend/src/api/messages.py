"""T055-T058 — Message REST endpoints (send, list, edit, delete, DM)."""
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_current_user
from src.models.attachment import Attachment
from src.models.message import Message
from src.models.room import RoomBan, RoomMembership, RoomRole
from src.models.user import User
from src.services.messaging import MAX_CONTENT_BYTES, build_payload, send_dm, send_room_message

router = APIRouter()


class SendBody(BaseModel):
    content: str = Field(min_length=1)
    reply_to_id: int | None = None


class EditBody(BaseModel):
    content: str = Field(min_length=1)


class DmBody(BaseModel):
    content: str = Field(min_length=1)
    reply_to_id: int | None = None


# ── helpers ───────────────────────────────────────────────────────────────────

def _serialize(msg: Message, username: str, reply_content: str | None = None) -> dict:
    return build_payload(msg, username, reply_content)


def _get_sender_username(msg: Message, db: Session) -> str:
    user = db.query(User).filter(User.id == msg.sender_id).first()
    return user.username if user else "deleted"


def _reply_content(db: Session, reply_to_id: int | None) -> str | None:
    if not reply_to_id:
        return None
    m = db.query(Message).filter(Message.id == reply_to_id).first()
    return m.content[:120] if m else None


def _require_membership(room_id: int, user_id: int, db: Session) -> RoomMembership:
    m = (
        db.query(RoomMembership)
        .filter(RoomMembership.room_id == room_id, RoomMembership.user_id == user_id)
        .first()
    )
    if not m:
        raise HTTPException(status_code=403, detail="Not a member")
    return m


# ── T055: REST send + paginated history ──────────────────────────────────────

@router.post("/rooms/{room_id}/messages", status_code=201)
async def post_room_message(
    room_id: int,
    body: SendBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_membership(room_id, current_user.id, db)

    ban = (
        db.query(RoomBan)
        .filter(RoomBan.room_id == room_id, RoomBan.banned_user_id == current_user.id)
        .first()
    )
    if ban:
        raise HTTPException(status_code=403, detail="You are banned from this room")

    if len(body.content.encode()) > MAX_CONTENT_BYTES:
        raise HTTPException(status_code=422, detail=f"Content exceeds {MAX_CONTENT_BYTES} bytes")

    try:
        msg = await send_room_message(
            db, room_id, current_user.id, current_user.username, body.content, body.reply_to_id
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return _serialize(msg, current_user.username, _reply_content(db, body.reply_to_id))


@router.get("/rooms/{room_id}/messages")
def list_room_messages(
    room_id: int,
    before: int | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_membership(room_id, current_user.id, db)

    query = (
        db.query(Message, User.username)
        .join(User, User.id == Message.sender_id)
        .filter(Message.room_id == room_id)
    )
    if before is not None:
        query = query.filter(Message.id < before)

    rows = query.order_by(Message.id.desc()).limit(limit).all()

    result = []
    for msg, username in rows:
        rc = _reply_content(db, msg.reply_to_id)
        result.append(_serialize(msg, username, rc))
    return result


# ── T056: Edit message ────────────────────────────────────────────────────────

@router.put("/messages/{msg_id}", status_code=200)
async def edit_message(
    msg_id: int,
    body: EditBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msg = db.query(Message).filter(Message.id == msg_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot edit another user's message")
    if len(body.content.encode()) > MAX_CONTENT_BYTES:
        raise HTTPException(status_code=422, detail=f"Content exceeds {MAX_CONTENT_BYTES} bytes")

    msg.content = body.content
    msg.is_edited = True
    msg.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)

    rc = _reply_content(db, msg.reply_to_id)
    payload = {"type": "message:edited", "payload": _serialize(msg, current_user.username, rc)}

    from src.services.websocket_hub import hub
    if msg.room_id:
        await hub.broadcast_room(msg.room_id, payload)
    else:
        await hub.broadcast_user(msg.sender_id, payload)

    return _serialize(msg, current_user.username, rc)


# ── T057: Delete message ──────────────────────────────────────────────────────

@router.delete("/messages/{msg_id}", status_code=204)
async def delete_message(
    msg_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msg = db.query(Message).filter(Message.id == msg_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    is_sender = msg.sender_id == current_user.id
    is_room_mod = False
    if msg.room_id:
        m = (
            db.query(RoomMembership)
            .filter(RoomMembership.room_id == msg.room_id, RoomMembership.user_id == current_user.id)
            .first()
        )
        if m and m.role == RoomRole.admin:
            is_room_mod = True
        from src.models.room import Room
        room = db.query(Room).filter(Room.id == msg.room_id).first()
        if room and room.owner_id == current_user.id:
            is_room_mod = True

    if not is_sender and not is_room_mod:
        raise HTTPException(status_code=403, detail="Cannot delete this message")

    room_id = msg.room_id
    sender_id = msg.sender_id

    attachment = db.query(Attachment).filter(Attachment.message_id == msg_id).first()
    if attachment:
        try:
            os.remove(attachment.stored_path)
        except OSError:
            pass

    db.delete(msg)
    db.commit()

    from src.services.websocket_hub import hub
    del_payload = {"type": "message:deleted", "payload": {"id": msg_id, "room_id": room_id}}
    if room_id:
        await hub.broadcast_room(room_id, del_payload)
    else:
        await hub.broadcast_user(sender_id, del_payload)
        await hub.broadcast_user(current_user.id, del_payload)


# ── T058: DM send ─────────────────────────────────────────────────────────────

@router.post("/dms/{recipient_id}/messages", status_code=201)
async def send_dm_message(
    recipient_id: int,
    body: DmBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recipient = db.query(User).filter(User.id == recipient_id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    if recipient_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot DM yourself")

    try:
        msg = await send_dm(
            db, current_user.id, current_user.username, recipient_id, body.content, body.reply_to_id
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return _serialize(msg, current_user.username, _reply_content(db, body.reply_to_id))
