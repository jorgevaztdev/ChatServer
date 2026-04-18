from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session
from src.models.base import SessionLocal
from src.models.user import User
from src.models.session import UserSession
from src.services.auth import decode_jwt


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_jwt(access_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id: int | None = payload.get("user_id")
    session_token: str | None = payload.get("session_token")
    if not user_id or not session_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    session = (
        db.query(UserSession)
        .filter(UserSession.user_id == user_id, UserSession.token == session_token)
        .first()
    )
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
