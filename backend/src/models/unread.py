from sqlalchemy import Column, Integer, ForeignKey
from .base import Base


class UserRoomRead(Base):
    __tablename__ = "user_room_reads"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True)
    last_read_message_id = Column(Integer, nullable=False, default=0)


class UserDmRead(Base):
    __tablename__ = "user_dm_reads"
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    partner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    last_read_message_id = Column(Integer, nullable=False, default=0)
