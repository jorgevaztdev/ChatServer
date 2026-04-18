"""T037 — User-to-user banning (US-BAN)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from src.api.deps import get_db, get_current_user
from src.models.user import User
from src.models.social import Friendship, FriendshipStatus, UserBan

router = APIRouter(prefix="/bans", tags=["bans"])


def _existing_ban(db: Session, banner_id: int, banned_id: int) -> UserBan | None:
    return (
        db.query(UserBan)
        .filter(UserBan.banner_id == banner_id, UserBan.banned_id == banned_id)
        .first()
    )


# ── POST /bans/user/{user_id} ─────────────────────────────────────────────────

@router.post("/user/{user_id}", status_code=201)
def ban_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot ban yourself")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if _existing_ban(db, current_user.id, user_id):
        raise HTTPException(status_code=409, detail="Already banned")

    # Terminate friendship (either direction)
    friendship = (
        db.query(Friendship)
        .filter(
            or_(
                and_(Friendship.requester_id == current_user.id, Friendship.addressee_id == user_id),
                and_(Friendship.requester_id == user_id, Friendship.addressee_id == current_user.id),
            )
        )
        .first()
    )
    if friendship:
        db.delete(friendship)

    ban = UserBan(banner_id=current_user.id, banned_id=user_id)
    db.add(ban)
    db.commit()
    db.refresh(ban)

    return {
        "id": ban.id,
        "banned_user_id": user_id,
        "banned_username": target.username,
        "created_at": ban.created_at.isoformat(),
    }


# ── DELETE /bans/user/{user_id} — unban ───────────────────────────────────────

@router.delete("/user/{user_id}", status_code=200)
def unban_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ban = _existing_ban(db, current_user.id, user_id)
    if not ban:
        raise HTTPException(status_code=404, detail="Ban not found")

    db.delete(ban)
    db.commit()
    return {"detail": "User unbanned"}


# ── GET /bans — list own bans ─────────────────────────────────────────────────

@router.get("")
def list_bans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(UserBan, User.username)
        .join(User, User.id == UserBan.banned_id)
        .filter(UserBan.banner_id == current_user.id)
        .order_by(UserBan.created_at.desc())
        .all()
    )
    return [
        {
            "id": ban.id,
            "banned_user_id": ban.banned_id,
            "banned_username": username,
            "created_at": ban.created_at.isoformat(),
        }
        for ban, username in rows
    ]


# ── GET /bans/check/{user_id} — check if ban exists either direction ──────────

@router.get("/check/{user_id}")
def check_ban(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ban = (
        db.query(UserBan)
        .filter(
            or_(
                and_(UserBan.banner_id == current_user.id, UserBan.banned_id == user_id),
                and_(UserBan.banner_id == user_id, UserBan.banned_id == current_user.id),
            )
        )
        .first()
    )
    return {"banned": ban is not None, "you_banned_them": ban.banner_id == current_user.id if ban else False}
