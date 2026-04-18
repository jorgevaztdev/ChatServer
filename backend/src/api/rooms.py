"""T040–T044 — Room CRUD, discovery, join, invite, leave."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.api.deps import get_db, get_current_user
from src.models.user import User
from src.models.room import Room, RoomMembership, RoomBan, RoomRole

router = APIRouter()


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str | None = None
    is_private: bool = False


class InviteBody(BaseModel):
    username: str


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


def _require_admin(room: Room, user: User, db: Session) -> RoomMembership:
    m = _membership(room.id, user.id, db)
    if not m or m.role not in (RoomRole.admin, RoomRole.admin):
        if room.owner_id != user.id and (not m or m.role != RoomRole.admin):
            raise HTTPException(status_code=403, detail="Admin or owner required")
    return m


# ── T040: Create room ─────────────────────────────────────────────────────────

@router.post("/rooms", status_code=201)
def create_room(
    body: RoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(Room).filter(Room.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Room name already taken")

    room = Room(
        name=body.name,
        description=body.description,
        is_private=body.is_private,
        owner_id=current_user.id,
    )
    db.add(room)
    db.flush()

    membership = RoomMembership(
        room_id=room.id,
        user_id=current_user.id,
        role=RoomRole.admin,
    )
    db.add(membership)
    db.commit()
    db.refresh(room)

    return {
        "id": room.id,
        "name": room.name,
        "description": room.description,
        "is_private": room.is_private,
        "owner_id": room.owner_id,
        "created_at": room.created_at.isoformat(),
    }


# ── T041: List + search public rooms ─────────────────────────────────────────

@router.get("/rooms")
def list_rooms(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * limit
    member_count_sq = (
        db.query(RoomMembership.room_id, func.count().label("member_count"))
        .group_by(RoomMembership.room_id)
        .subquery()
    )
    rows = (
        db.query(Room, member_count_sq.c.member_count)
        .outerjoin(member_count_sq, Room.id == member_count_sq.c.room_id)
        .filter(Room.is_private == False)  # noqa: E712
        .order_by(Room.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "is_private": r.is_private,
            "owner_id": r.owner_id,
            "member_count": cnt or 0,
            "created_at": r.created_at.isoformat(),
        }
        for r, cnt in rows
    ]


@router.get("/rooms/search")
def search_rooms(
    q: str = Query(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rooms = (
        db.query(Room)
        .filter(Room.is_private == False, Room.name.ilike(f"%{q}%"))  # noqa: E712
        .order_by(Room.name)
        .limit(50)
        .all()
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "is_private": r.is_private,
            "owner_id": r.owner_id,
            "created_at": r.created_at.isoformat(),
        }
        for r in rooms
    ]


# ── T042: Join public room ────────────────────────────────────────────────────

@router.post("/rooms/{room_id}/join", status_code=200)
def join_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = _get_room_or_404(room_id, db)
    if room.is_private:
        raise HTTPException(status_code=403, detail="Private room requires invite")

    ban = (
        db.query(RoomBan)
        .filter(RoomBan.room_id == room_id, RoomBan.banned_user_id == current_user.id)
        .first()
    )
    if ban:
        raise HTTPException(status_code=403, detail="You are banned from this room")

    existing = _membership(room_id, current_user.id, db)
    if existing:
        return {"detail": "Already a member"}

    db.add(RoomMembership(room_id=room_id, user_id=current_user.id, role=RoomRole.member))
    db.commit()
    return {"detail": "Joined"}


# ── T043: Invite to private room (admin/owner only) ───────────────────────────

@router.post("/rooms/{room_id}/invite", status_code=200)
def invite_to_room(
    room_id: int,
    body: InviteBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = _get_room_or_404(room_id, db)
    m = _membership(room_id, current_user.id, db)
    if room.owner_id != current_user.id and (not m or m.role != RoomRole.admin):
        raise HTTPException(status_code=403, detail="Admin or owner required")

    target = db.query(User).filter(User.username == body.username).first()  # type: ignore[attr-defined]
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    ban = (
        db.query(RoomBan)
        .filter(RoomBan.room_id == room_id, RoomBan.banned_user_id == target.id)
        .first()
    )
    if ban:
        raise HTTPException(status_code=403, detail="User is banned from this room")

    existing = _membership(room_id, target.id, db)
    if existing:
        return {"detail": "Already a member"}

    db.add(RoomMembership(room_id=room_id, user_id=target.id, role=RoomRole.member))
    db.commit()
    return {"detail": "Invited"}


# ── T044: Leave room (not for owner) ─────────────────────────────────────────

@router.post("/rooms/{room_id}/leave", status_code=200)
def leave_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = _get_room_or_404(room_id, db)
    if room.owner_id == current_user.id:
        raise HTTPException(status_code=403, detail="Owner cannot leave — delete the room instead")

    m = _membership(room_id, current_user.id, db)
    if not m:
        raise HTTPException(status_code=404, detail="Not a member")

    db.delete(m)
    db.commit()
    return {"detail": "Left"}


# ── GET /rooms/{id}/members ───────────────────────────────────────────────────

@router.get("/rooms/{room_id}/members")
def list_members(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = _get_room_or_404(room_id, db)
    if room.is_private:
        m = _membership(room_id, current_user.id, db)
        if not m:
            raise HTTPException(status_code=403, detail="Private room")

    rows = (
        db.query(RoomMembership, User.username)
        .join(User, User.id == RoomMembership.user_id)
        .filter(RoomMembership.room_id == room_id)
        .all()
    )
    from src.services.websocket_hub import hub
    return [
        {
            "user_id": m.user_id,
            "username": username,
            "role": m.role.value,
            "online": hub.is_online(m.user_id),
        }
        for m, username in rows
    ]


# ── GET /rooms/{id} — room detail ─────────────────────────────────────────────

@router.get("/rooms/{room_id}")
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = _get_room_or_404(room_id, db)
    if room.is_private:
        m = _membership(room_id, current_user.id, db)
        if not m:
            raise HTTPException(status_code=403, detail="Private room")

    member_count = db.query(RoomMembership).filter(RoomMembership.room_id == room_id).count()
    return {
        "id": room.id,
        "name": room.name,
        "description": room.description,
        "is_private": room.is_private,
        "owner_id": room.owner_id,
        "member_count": member_count,
        "created_at": room.created_at.isoformat(),
    }
