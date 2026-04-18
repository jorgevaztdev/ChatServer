"""T046-T049, T051 — Room moderation: admin message delete, room ban, promote."""
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_current_user
from src.models.attachment import Attachment
from src.models.message import Message
from src.models.room import Room, RoomBan, RoomMembership, RoomRole
from src.models.user import User

router = APIRouter()


def _get_room_or_404(room_id: int, db: Session) -> Room:
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


def _membership(room_id: int, user_id: int, db: Session) -> RoomMembership | None:
    return (
        db.query(RoomMembership)
        .filter(RoomMembership.room_id == room_id, RoomMembership.user_id == user_id)
        .first()
    )


def _is_admin_or_owner(room: Room, user: User, db: Session) -> bool:
    if room.owner_id == user.id:
        return True
    m = _membership(room.id, user.id, db)
    return m is not None and m.role == RoomRole.admin


def _require_admin_or_owner(room: Room, user: User, db: Session) -> None:
    if not _is_admin_or_owner(room, user, db):
        raise HTTPException(status_code=403, detail="Admin or owner required")


def _require_owner(room: Room, user: User) -> None:
    if room.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Owner only")


# ── T046: Admin delete message ────────────────────────────────────────────────

@router.delete("/rooms/{room_id}/messages/{msg_id}", status_code=204)
async def admin_delete_message(
    room_id: int,
    msg_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = _get_room_or_404(room_id, db)
    _require_admin_or_owner(room, current_user, db)

    msg = db.query(Message).filter(Message.id == msg_id, Message.room_id == room_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    attachment = db.query(Attachment).filter(Attachment.message_id == msg_id).first()
    if attachment:
        try:
            os.remove(attachment.stored_path)
        except OSError:
            pass

    db.delete(msg)
    db.commit()

    from src.services.websocket_hub import hub
    await hub.broadcast_room(room_id, {"type": "message:deleted", "payload": {"id": msg_id, "room_id": room_id}})


# ── T047: Ban user from room ──────────────────────────────────────────────────

@router.post("/rooms/{room_id}/ban/{user_id}", status_code=201)
async def ban_room_member(
    room_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = _get_room_or_404(room_id, db)
    _require_admin_or_owner(room, current_user, db)

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot ban yourself")
    if user_id == room.owner_id:
        raise HTTPException(status_code=403, detail="Cannot ban the room owner")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    existing_ban = (
        db.query(RoomBan)
        .filter(RoomBan.room_id == room_id, RoomBan.banned_user_id == user_id)
        .first()
    )
    if existing_ban:
        raise HTTPException(status_code=409, detail="User already banned from this room")

    membership = _membership(room_id, user_id, db)
    if membership:
        db.delete(membership)

    ban = RoomBan(room_id=room_id, banned_user_id=user_id, banned_by_id=current_user.id)
    db.add(ban)
    db.commit()

    from src.services.websocket_hub import hub
    await hub.broadcast_user(user_id, {"type": "room:banned", "payload": {"room_id": room_id}})

    return {
        "room_id": room_id,
        "banned_user_id": user_id,
        "banned_by_id": current_user.id,
    }


# ── T048: Unban user from room ────────────────────────────────────────────────

@router.delete("/rooms/{room_id}/ban/{user_id}", status_code=200)
def unban_room_member(
    room_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = _get_room_or_404(room_id, db)
    _require_admin_or_owner(room, current_user, db)

    ban = (
        db.query(RoomBan)
        .filter(RoomBan.room_id == room_id, RoomBan.banned_user_id == user_id)
        .first()
    )
    if not ban:
        raise HTTPException(status_code=404, detail="Ban not found")

    # If ban was placed by a different admin, only the owner may unban
    if ban.banned_by_id != current_user.id and room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner can lift bans placed by other admins")

    db.delete(ban)
    db.commit()
    return {"detail": "Unbanned"}


# ── T049: Promote / demote admin ──────────────────────────────────────────────

@router.post("/rooms/{room_id}/admins/{user_id}", status_code=200)
def promote_to_admin(
    room_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = _get_room_or_404(room_id, db)
    _require_owner(room, current_user)

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Owner is already the owner")

    m = _membership(room_id, user_id, db)
    if not m:
        raise HTTPException(status_code=404, detail="User is not a member")

    m.role = RoomRole.admin
    db.commit()
    return {"detail": "Promoted to admin"}


@router.delete("/rooms/{room_id}/admins/{user_id}", status_code=200)
def demote_admin(
    room_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = _get_room_or_404(room_id, db)
    _require_owner(room, current_user)

    if user_id == room.owner_id:
        raise HTTPException(status_code=400, detail="Cannot demote the owner")

    m = _membership(room_id, user_id, db)
    if not m:
        raise HTTPException(status_code=404, detail="User is not a member")
    if m.role != RoomRole.admin:
        raise HTTPException(status_code=400, detail="User is not an admin")

    m.role = RoomRole.member
    db.commit()
    return {"detail": "Demoted to member"}


# ── T051: List room bans ──────────────────────────────────────────────────────

@router.get("/rooms/{room_id}/bans")
def list_room_bans(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = _get_room_or_404(room_id, db)
    _require_admin_or_owner(room, current_user, db)

    rows = (
        db.query(RoomBan, User.username)
        .join(User, User.id == RoomBan.banned_user_id)
        .filter(RoomBan.room_id == room_id)
        .all()
    )
    return [
        {
            "banned_user_id": ban.banned_user_id,
            "username": username,
            "banned_by_id": ban.banned_by_id,
            "created_at": ban.created_at.isoformat(),
        }
        for ban, username in rows
    ]
