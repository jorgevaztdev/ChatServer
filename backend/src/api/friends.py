"""T032–T035 — Friends / Contacts API (US-CONTACTS)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_current_user
from src.models.user import User
from src.models.social import Friendship, FriendshipStatus
from src.services.presence import get_status

router = APIRouter(prefix="/friends", tags=["friends"])


class FriendRequestBody(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    message: str | None = Field(default=None, max_length=256)


def _get_friendship(db: Session, user_a: int, user_b: int) -> Friendship | None:
    return (
        db.query(Friendship)
        .filter(
            (
                (Friendship.requester_id == user_a) & (Friendship.addressee_id == user_b)
            ) | (
                (Friendship.requester_id == user_b) & (Friendship.addressee_id == user_a)
            )
        )
        .first()
    )


# ── T032: POST /friends/request ───────────────────────────────────────────────

@router.post("/request", status_code=201)
def send_friend_request(
    body: FriendRequestBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = db.query(User).filter(User.username == body.username).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot add yourself")

    existing = _get_friendship(db, current_user.id, target.id)
    if existing:
        if existing.status == FriendshipStatus.accepted:
            raise HTTPException(status_code=409, detail="Already friends")
        raise HTTPException(status_code=409, detail="Request already exists")

    friendship = Friendship(
        requester_id=current_user.id,
        addressee_id=target.id,
        status=FriendshipStatus.pending,
    )
    db.add(friendship)
    db.commit()
    db.refresh(friendship)
    return {
        "id": friendship.id,
        "addressee": target.username,
        "status": friendship.status.value,
    }


# ── T033: POST /friends/accept/{requester_id} & DELETE /friends/{user_id} ────

@router.post("/accept/{requester_id}", status_code=200)
def accept_friend_request(
    requester_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    friendship = (
        db.query(Friendship)
        .filter(
            Friendship.requester_id == requester_id,
            Friendship.addressee_id == current_user.id,
            Friendship.status == FriendshipStatus.pending,
        )
        .first()
    )
    if not friendship:
        raise HTTPException(status_code=404, detail="Pending request not found")

    friendship.status = FriendshipStatus.accepted
    db.commit()
    return {"detail": "Friend request accepted"}


@router.delete("/decline/{requester_id}", status_code=200)
def decline_friend_request(
    requester_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    friendship = (
        db.query(Friendship)
        .filter(
            Friendship.requester_id == requester_id,
            Friendship.addressee_id == current_user.id,
            Friendship.status == FriendshipStatus.pending,
        )
        .first()
    )
    if not friendship:
        raise HTTPException(status_code=404, detail="Pending request not found")

    db.delete(friendship)
    db.commit()
    return {"detail": "Friend request declined"}


@router.delete("/{user_id}", status_code=200)
def remove_friend(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    friendship = _get_friendship(db, current_user.id, user_id)
    if not friendship or friendship.status != FriendshipStatus.accepted:
        raise HTTPException(status_code=404, detail="Friendship not found")

    db.delete(friendship)
    db.commit()
    return {"detail": "Friend removed"}


# ── T034: GET /friends — accepted friends with presence ──────────────────────

@router.get("")
def list_friends(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Friendship, User)
        .join(
            User,
            (
                (Friendship.requester_id == current_user.id) & (User.id == Friendship.addressee_id)
            ) | (
                (Friendship.addressee_id == current_user.id) & (User.id == Friendship.requester_id)
            ),
        )
        .filter(Friendship.status == FriendshipStatus.accepted)
        .all()
    )
    return [
        {
            "user_id": friend.id,
            "username": friend.username,
            "presence": get_status(friend.id),
            "friendship_id": f.id,
        }
        for f, friend in rows
    ]


# ── T035: GET /friends/requests — pending incoming requests ──────────────────

@router.get("/requests")
def list_pending_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Friendship, User)
        .join(User, User.id == Friendship.requester_id)
        .filter(
            Friendship.addressee_id == current_user.id,
            Friendship.status == FriendshipStatus.pending,
        )
        .all()
    )
    return [
        {
            "friendship_id": f.id,
            "requester_id": requester.id,
            "username": requester.username,
            "created_at": f.created_at.isoformat(),
        }
        for f, requester in rows
    ]
