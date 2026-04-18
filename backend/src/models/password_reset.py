from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from .base import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Integer, default=0, nullable=False)  # 0=unused, 1=used
