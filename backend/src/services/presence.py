"""T028 — Presence service."""
import asyncio
from src.services.websocket_hub import hub

_AFK_CHECK_INTERVAL = 10  # seconds — check for AFK transitions
_OFFLINE_GRACE = 5         # seconds — wait before declaring offline after disconnect

# Cache of last-broadcast status per user to avoid redundant broadcasts
_status_cache: dict[int, str] = {}


def update_activity(user_id: int, tab_id: str) -> None:
    hub.record_activity(user_id, tab_id)


def get_status(user_id: int) -> str:
    return hub.get_presence_status(user_id)


async def broadcast_status_change(user_id: int) -> None:
    new_status = get_status(user_id)
    if _status_cache.get(user_id) == new_status:
        return
    _status_cache[user_id] = new_status
    payload = {"type": "presence:update", "payload": {"user_id": user_id, "status": new_status}}
    await hub.broadcast_all(payload)


async def _offline_grace_task(user_id: int) -> None:
    """T030 — wait OFFLINE_GRACE seconds, then broadcast offline if still no tabs."""
    await asyncio.sleep(_OFFLINE_GRACE)
    if get_status(user_id) == "offline":
        await broadcast_status_change(user_id)


def schedule_offline_grace(user_id: int) -> None:
    asyncio.create_task(_offline_grace_task(user_id))


async def run_afk_checker() -> None:
    """Background task: detect AFK transitions for all connected users."""
    while True:
        await asyncio.sleep(_AFK_CHECK_INTERVAL)
        for uid in hub.all_connected_user_ids():
            await broadcast_status_change(uid)
