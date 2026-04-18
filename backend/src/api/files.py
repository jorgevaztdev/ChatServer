"""T063 / T064 — File upload and retrieval endpoints."""
import os
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_current_user
from src.config import MEDIA_DIR
from src.models.attachment import Attachment
from src.models.message import Message
from src.models.room import RoomBan, RoomMembership
from src.models.social import Friendship, FriendshipStatus, UserBan
from src.models.user import User
from src.services.messaging import build_payload
from src.services.websocket_hub import hub
from src.storage.file_handler import save_file

router = APIRouter()


# ── T063: POST /upload ────────────────────────────────────────────────────────

@router.post("/upload", status_code=201)
async def upload_file(
    file: UploadFile,
    comment: str = Form(default=""),
    room_id: int | None = Form(default=None),
    dm_partner_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Exactly one of room_id or dm_partner_id must be provided
    if (room_id is None) == (dm_partner_id is None):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of room_id or dm_partner_id",
        )

    if room_id is not None:
        # Check membership
        membership = (
            db.query(RoomMembership)
            .filter(RoomMembership.room_id == room_id, RoomMembership.user_id == current_user.id)
            .first()
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this room")

        # Check room ban
        room_ban = (
            db.query(RoomBan)
            .filter(RoomBan.room_id == room_id, RoomBan.banned_user_id == current_user.id)
            .first()
        )
        if room_ban:
            raise HTTPException(status_code=403, detail="You are banned from this room")

    else:
        # DM: check accepted friendship in either direction
        friendship = (
            db.query(Friendship)
            .filter(
                Friendship.status == FriendshipStatus.accepted,
                or_(
                    and_(
                        Friendship.requester_id == current_user.id,
                        Friendship.addressee_id == dm_partner_id,
                    ),
                    and_(
                        Friendship.requester_id == dm_partner_id,
                        Friendship.addressee_id == current_user.id,
                    ),
                ),
            )
            .first()
        )
        if not friendship:
            raise HTTPException(status_code=403, detail="Must be mutual friends to share files")

        # Check user ban in either direction
        ban = (
            db.query(UserBan)
            .filter(
                or_(
                    and_(UserBan.banner_id == current_user.id, UserBan.banned_id == dm_partner_id),
                    and_(UserBan.banner_id == dm_partner_id, UserBan.banned_id == current_user.id),
                )
            )
            .first()
        )
        if ban:
            raise HTTPException(status_code=403, detail="Cannot share files — ban exists")

    # Save file to disk
    stored_path = await save_file(file, MEDIA_DIR)
    file_size = os.path.getsize(stored_path)

    # Create Message
    msg = Message(
        room_id=room_id,
        sender_id=current_user.id,
        content=comment,
        updated_at=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Create Attachment
    att = Attachment(
        message_id=msg.id,
        original_filename=file.filename or "file",
        stored_path=stored_path,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=file_size,
    )
    db.add(att)
    db.commit()
    db.refresh(att)

    attachment_dict = {
        "id": att.id,
        "original_filename": att.original_filename,
        "mime_type": att.mime_type,
        "size_bytes": att.size_bytes,
        "url": f"/files/{att.id}",
    }

    payload = {
        "type": "message:new",
        "payload": build_payload(msg, current_user.username, attachment=attachment_dict),
    }

    if room_id is not None:
        await hub.broadcast_room(room_id, payload)
    else:
        await hub.broadcast_user(current_user.id, payload)
        await hub.broadcast_user(dm_partner_id, payload)

    return build_payload(msg, current_user.username, attachment=attachment_dict)


# ── T064: GET /files/{attachment_id} ─────────────────────────────────────────

@router.get("/files/{attachment_id}")
def download_file(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    att = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    msg = db.query(Message).filter(Message.id == att.message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Associated message not found")

    if msg.room_id is not None:
        # Check room membership
        membership = (
            db.query(RoomMembership)
            .filter(RoomMembership.room_id == msg.room_id, RoomMembership.user_id == current_user.id)
            .first()
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this room")
    else:
        # DM: current user must be sender or have a friendship (any status) with sender
        is_sender = current_user.id == msg.sender_id
        friendship = (
            db.query(Friendship)
            .filter(
                or_(
                    and_(
                        Friendship.requester_id == current_user.id,
                        Friendship.addressee_id == msg.sender_id,
                    ),
                    and_(
                        Friendship.requester_id == msg.sender_id,
                        Friendship.addressee_id == current_user.id,
                    ),
                )
            )
            .first()
        )
        if not is_sender and not friendship:
            raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(att.stored_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        att.stored_path,
        media_type=att.mime_type,
        filename=att.original_filename,
    )
