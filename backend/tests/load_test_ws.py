"""T080 — Load test: 50 simultaneous WebSocket connections to one room.

Usage (from backend container or host with websockets installed):
    python tests/load_test_ws.py [BASE_URL]

Default BASE_URL: http://localhost:8000
Requires: websockets, httpx (both available in backend deps via uvicorn[standard])
"""
import asyncio
import json
import sys
import time
import httpx
import websockets

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
WS_BASE = BASE.replace("http://", "ws://").replace("https://", "wss://")

N_CLIENTS = 50
ROOM_NAME = "loadtest_room"
PASSWORD = "loadpass"


async def register_and_login(idx: int) -> tuple[str, str]:
    """Register user, login, return (cookie_header, user_id)."""
    email = f"lt_{idx}@t.com"
    username = f"lt_{idx}"
    async with httpx.AsyncClient(base_url=BASE) as c:
        await c.post("/auth/register", json={"email": email, "password": PASSWORD, "username": username})
        r = await c.post("/auth/login", json={"email": email, "password": PASSWORD})
        cookie = r.headers.get("set-cookie", "")
        token = ""
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith("access_token="):
                token = part
                break
        me = await c.get("/auth/me")
        uid = me.json().get("id", 0)
    return token, str(uid)


async def create_room_and_join(owner_cookie: str) -> int:
    """Owner creates room; returns room_id."""
    async with httpx.AsyncClient(base_url=BASE, headers={"Cookie": owner_cookie}) as c:
        r = await c.post("/rooms", json={"name": ROOM_NAME, "is_private": False})
        if r.status_code == 409:
            rooms = await c.get("/rooms/search", params={"q": ROOM_NAME})
            return rooms.json()["results"][0]["id"]
        return r.json()["id"]


async def join_room(cookie: str, room_id: int) -> None:
    async with httpx.AsyncClient(base_url=BASE, headers={"Cookie": cookie}) as c:
        await c.post(f"/rooms/{room_id}/join")


async def ws_client(idx: int, cookie: str, room_id: int, results: list) -> None:
    uri = f"{WS_BASE}/ws/rooms/{room_id}"
    start = time.monotonic()
    received = 0
    try:
        async with websockets.connect(uri, extra_headers={"Cookie": cookie}, open_timeout=10) as ws:
            connect_ms = round((time.monotonic() - start) * 1000)
            # Wait for room:joined
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if msg.get("type") == "room:joined":
                # Send one message
                await ws.send(json.dumps({"type": "message:send", "payload": {"content": f"load_{idx}"}}))
                # Wait for echo back (message:new)
                echo = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if echo.get("type") == "message:new":
                    received += 1
            results.append({"idx": idx, "connect_ms": connect_ms, "ok": received > 0})
    except Exception as e:
        results.append({"idx": idx, "connect_ms": -1, "ok": False, "err": str(e)})


async def main():
    print(f"Target: {BASE}  Clients: {N_CLIENTS}")

    # Setup users
    print("Registering users...")
    coros = [register_and_login(i) for i in range(N_CLIENTS)]
    users = await asyncio.gather(*coros)
    cookies = [u[0] for u in users]

    # Create room with first user
    room_id = await create_room_and_join(cookies[0])
    print(f"Room ID: {room_id}")

    # Join room (all users)
    await asyncio.gather(*[join_room(c, room_id) for c in cookies])
    print("All users joined. Opening WS connections...")

    results: list[dict] = []
    t0 = time.monotonic()
    await asyncio.gather(*[ws_client(i, cookies[i], room_id, results) for i in range(N_CLIENTS)])
    elapsed = round((time.monotonic() - t0) * 1000)

    ok = sum(1 for r in results if r["ok"])
    fail = N_CLIENTS - ok
    connect_times = [r["connect_ms"] for r in results if r["connect_ms"] >= 0]
    avg_ms = round(sum(connect_times) / len(connect_times)) if connect_times else -1

    print(f"\n{'='*50}")
    print(f"Results: {ok}/{N_CLIENTS} OK  |  {fail} failed")
    print(f"Total wall time: {elapsed} ms")
    print(f"Avg connect time: {avg_ms} ms")
    if fail:
        print("\nFailed clients:")
        for r in results:
            if not r["ok"]:
                print(f"  [{r['idx']}] err={r.get('err', 'unknown')}")
    print(f"{'='*50}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
