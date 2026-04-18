"""T029 / T030 / T054 — WebSocket endpoints (presence + room messaging)."""
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.models.session import UserSession
from src.models.room import RoomMembership
from src.models.message import Message
from src.models.unread import UserRoomRead
from src.models.user import User
from src.services.auth import decode_jwt
from src.services.websocket_hub import hub
from src.services import presence as presence_svc
from src.services.messaging import send_room_message, build_payload

router = APIRouter()


async def _auth_ws(ws: WebSocket, db: Session) -> int | None:
    token = ws.cookies.get("access_token")
    if not token:
        return None
    payload = decode_jwt(token)
    user_id: int | None = payload.get("user_id")
    session_token: str | None = payload.get("session_token")
    if not user_id or not session_token:
        return None
    session = db.query(UserSession).filter(UserSession.token == session_token).first()
    return user_id if session else None


@router.websocket("/ws/presence")
async def ws_presence(ws: WebSocket, db: Session = Depends(get_db)):
    user_id = await _auth_ws(ws, db)
    if user_id is None:
        await ws.close(code=4001)
        return

    tab_id = str(uuid.uuid4())
    await ws.accept()
    await hub.connect(user_id, ws)
    presence_svc.update_activity(user_id, tab_id)
    # Send ack to caller first, then broadcast to others
    await ws.send_json({
        "type": "presence:ack",
        "payload": {"status": presence_svc.get_status(user_id), "tab_id": tab_id},
    })
    await presence_svc.broadcast_status_change(user_id)

    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "heartbeat":
                tid = data.get("tab_id", tab_id)
                presence_svc.update_activity(user_id, tid)
                await ws.send_json({
                    "type": "presence:ack",
                    "payload": {"status": presence_svc.get_status(user_id)},
                })
    except WebSocketDisconnect:
        await hub.disconnect(user_id, ws)
        hub.remove_tab(user_id, tab_id)
        if not hub.is_online(user_id):
            hub.record_disconnect(user_id)
        # T030: grace window before broadcasting offline
        presence_svc.schedule_offline_grace(user_id)


# ── T054: Room WebSocket ──────────────────────────────────────────────────────

@router.websocket("/ws/rooms/{room_id}")
async def ws_room(room_id: int, ws: WebSocket, db: Session = Depends(get_db)):
    user_id = await _auth_ws(ws, db)
    if user_id is None:
        await ws.close(code=4001)
        return

    membership = (
        db.query(RoomMembership)
        .filter(RoomMembership.room_id == room_id, RoomMembership.user_id == user_id)
        .first()
    )
    if not membership:
        await ws.close(code=4003)
        return

    await ws.accept()
    await hub.connect(user_id, ws)   # register so broadcast_user can reach this socket
    hub.join_room(room_id, user_id)

    # T059: push messages missed since last disconnect
    since = hub.get_last_disconnect(user_id)
    if since:
        missed = (
            db.query(Message, User.username)
            .join(User, User.id == Message.sender_id)
            .filter(Message.room_id == room_id, Message.created_at > since)
            .order_by(Message.created_at.asc())
            .all()
        )
        for msg, username in missed:
            await ws.send_json({
                "type": "message:new",
                "payload": build_payload(msg, username),
            })

    await ws.send_json({"type": "room:joined", "payload": {"room_id": room_id}})

    # Auto-mark room as read on connect
    latest_msg = (
        db.query(Message)
        .filter(Message.room_id == room_id)
        .order_by(Message.id.desc())
        .first()
    )
    latest_id = latest_msg.id if latest_msg else 0
    read_row = (
        db.query(UserRoomRead)
        .filter(UserRoomRead.user_id == user_id, UserRoomRead.room_id == room_id)
        .first()
    )
    if read_row:
        read_row.last_read_message_id = latest_id
    else:
        db.add(UserRoomRead(user_id=user_id, room_id=room_id, last_read_message_id=latest_id))
    db.commit()

    user = db.query(User).filter(User.id == user_id).first()
    username = user.username if user else "unknown"

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "message:send":
                p = data.get("payload", {})
                content = (p.get("content") or "").strip()
                if content:
                    try:
                        await send_room_message(
                            db, room_id, user_id, username, content, p.get("reply_to_id")
                        )
                    except ValueError as exc:
                        await ws.send_json({"type": "error", "payload": {"detail": str(exc)}})

            elif msg_type == "heartbeat":
                tab_id = data.get("tab_id", "room")
                presence_svc.update_activity(user_id, tab_id)

    except WebSocketDisconnect:
        hub.leave_room(room_id, user_id)
        await hub.disconnect(user_id, ws)
        if not hub.is_online(user_id):
            hub.record_disconnect(user_id)
