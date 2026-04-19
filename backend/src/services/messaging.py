"""T053 / T058 — Messaging service (room + DM)."""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from src.models.message import Message
from src.models.social import Friendship, FriendshipStatus, UserBan
from src.services.websocket_hub import hub

MAX_CONTENT_BYTES = 3072


def build_payload(msg: Message, sender_username: str, reply_to_content: str | None = None, attachment: dict | None = None) -> dict:
    return {
        "id": msg.id,
        "room_id": msg.room_id,
        "sender_id": msg.sender_id,
        "sender_username": sender_username,
        "content": msg.content,
        "reply_to_id": msg.reply_to_id,
        "reply_to_content": reply_to_content,
        "is_edited": msg.is_edited,
        "created_at": msg.created_at.isoformat(),
        "updated_at": msg.updated_at.isoformat(),
        "attachment": attachment,
    }


def _fetch_reply_content(db: Session, reply_to_id: int | None) -> str | None:
    if not reply_to_id:
        return None
    reply = db.query(Message).filter(Message.id == reply_to_id).first()
    return reply.content[:120] if reply else None


async def send_room_message(
    db: Session,
    room_id: int,
    sender_id: int,
    sender_username: str,
    content: str,
    reply_to_id: int | None = None,
) -> Message:
    if len(content.encode()) > MAX_CONTENT_BYTES:
        raise ValueError(f"Content exceeds {MAX_CONTENT_BYTES} bytes")

    msg = Message(
        room_id=room_id,
        sender_id=sender_id,
        content=content,
        reply_to_id=reply_to_id,
        updated_at=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    reply_content = _fetch_reply_content(db, reply_to_id)
    payload = {"type": "message:new", "payload": build_payload(msg, sender_username, reply_content)}
    await hub.broadcast_room(room_id, payload)
    return msg


async def send_dm(
    db: Session,
    sender_id: int,
    sender_username: str,
    recipient_id: int,
    content: str,
    reply_to_id: int | None = None,
) -> Message:
    if len(content.encode()) > MAX_CONTENT_BYTES:
        raise ValueError(f"Content exceeds {MAX_CONTENT_BYTES} bytes")

    friendship = (
        db.query(Friendship)
        .filter(
            Friendship.status == FriendshipStatus.accepted,
            or_(
                and_(Friendship.requester_id == sender_id, Friendship.addressee_id == recipient_id),
                and_(Friendship.requester_id == recipient_id, Friendship.addressee_id == sender_id),
            ),
        )
        .first()
    )
    if not friendship:
        raise PermissionError("Must be mutual friends to DM")

    ban = (
        db.query(UserBan)
        .filter(
            or_(
                and_(UserBan.banner_id == sender_id, UserBan.banned_id == recipient_id),
                and_(UserBan.banner_id == recipient_id, UserBan.banned_id == sender_id),
            )
        )
        .first()
    )
    if ban:
        raise PermissionError("Cannot DM — ban exists")

    msg = Message(
        room_id=None,
        sender_id=sender_id,
        recipient_id=recipient_id,
        content=content,
        reply_to_id=reply_to_id,
        updated_at=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    reply_content = _fetch_reply_content(db, reply_to_id)
    payload = {"type": "message:new", "payload": build_payload(msg, sender_username, reply_content)}
    await hub.broadcast_user(sender_id, payload)
    await hub.broadcast_user(recipient_id, payload)
    return msg
