from datetime import datetime
from fastapi import WebSocket

_AFK_SECONDS = 60


class ConnectionHub:
    def __init__(self) -> None:
        # user_id -> list of open WebSocket connections (one per tab)
        self._connections: dict[int, list[WebSocket]] = {}
        # room_id -> set of user_ids currently subscribed
        self._room_users: dict[int, set[int]] = {}
        # T027: presence — user_id -> {tab_id: last_activity}
        self._activity: dict[int, dict[str, datetime]] = {}
        # T059: offline queue — user_id -> last disconnect time
        self._last_disconnect: dict[int, datetime] = {}

    # ── connections ───────────────────────────────────────────────────────────

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        self._connections.setdefault(user_id, []).append(ws)

    async def disconnect(self, user_id: int, ws: WebSocket) -> None:
        conns = self._connections.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._connections.pop(user_id, None)

    def is_online(self, user_id: int) -> bool:
        return bool(self._connections.get(user_id))

    # ── rooms ─────────────────────────────────────────────────────────────────

    def join_room(self, room_id: int, user_id: int) -> None:
        self._room_users.setdefault(room_id, set()).add(user_id)

    def leave_room(self, room_id: int, user_id: int) -> None:
        self._room_users.get(room_id, set()).discard(user_id)

    # ── presence (T027) ───────────────────────────────────────────────────────

    def record_activity(self, user_id: int, tab_id: str) -> None:
        self._activity.setdefault(user_id, {})[tab_id] = datetime.utcnow()

    def remove_tab(self, user_id: int, tab_id: str) -> None:
        tabs = self._activity.get(user_id, {})
        tabs.pop(tab_id, None)
        if not tabs:
            self._activity.pop(user_id, None)

    def get_presence_status(self, user_id: int) -> str:
        tabs = self._activity.get(user_id, {})
        if not tabs:
            return "offline"
        now = datetime.utcnow()
        for ts in tabs.values():
            if (now - ts).total_seconds() < _AFK_SECONDS:
                return "online"
        return "AFK"

    def all_connected_user_ids(self) -> list[int]:
        return list(self._connections.keys())

    # ── offline queue (T059) ──────────────────────────────────────────────────

    def record_disconnect(self, user_id: int) -> None:
        self._last_disconnect[user_id] = datetime.utcnow()

    def get_last_disconnect(self, user_id: int) -> "datetime | None":
        return self._last_disconnect.get(user_id)

    # ── broadcast ─────────────────────────────────────────────────────────────

    async def broadcast_room(self, room_id: int, payload: dict) -> None:
        for uid in list(self._room_users.get(room_id, set())):
            await self.broadcast_user(uid, payload)

    async def broadcast_user(self, user_id: int, payload: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(user_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(user_id, ws)

    async def broadcast_all(self, payload: dict) -> None:
        for uid in self.all_connected_user_ids():
            await self.broadcast_user(uid, payload)


hub = ConnectionHub()
