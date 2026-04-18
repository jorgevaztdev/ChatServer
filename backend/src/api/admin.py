"""Admin endpoints — XMPP monitoring + user management (admin only)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_admin_user
from src.models.user import User
from src.services.jabber_server import get_c2s_sessions, get_s2s_links

router = APIRouter()


# ── XMPP monitoring ───────────────────────────────────────────────────────────

@router.get("/admin/jabber/connections")
def jabber_connections(current_user: User = Depends(get_admin_user)) -> list[dict]:
    return get_c2s_sessions()


@router.get("/admin/jabber/federation")
def jabber_federation(current_user: User = Depends(get_admin_user)) -> list[dict]:
    return get_s2s_links()


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/admin/stats")
def admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    from src.models.room import Room
    from src.models.message import Message

    return {
        "total_users": db.query(User).count(),
        "total_admins": db.query(User).filter(User.is_admin == True).count(),  # noqa: E712
        "total_rooms": db.query(Room).count(),
        "total_messages": db.query(Message).count(),
    }


# ── User management ───────────────────────────────────────────────────────────

@router.get("/admin/users")
def list_users(
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    offset = (page - 1) * limit
    query = db.query(User)
    if q:
        like = f"%{q}%"
        query = query.filter(
            User.username.ilike(like) | User.email.ilike(like)
        )
    total = query.count()
    users = query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "is_admin": u.is_admin,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
    }


@router.delete("/admin/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()


@router.post("/admin/users/{user_id}/promote", status_code=200)
def promote_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=409, detail="Already an admin")
    user.is_admin = True
    db.commit()
    return {"detail": "Promoted to admin", "user_id": user_id}


@router.delete("/admin/users/{user_id}/promote", status_code=200)
def demote_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_admin:
        raise HTTPException(status_code=409, detail="User is not an admin")
    user.is_admin = False
    db.commit()
    return {"detail": "Demoted from admin", "user_id": user_id}
