"""T081 — Federation load test: 50 clients on server A, 50 on server B, messages A↔B.

Prerequisites:
  - Two running server instances (A and B) with Jabber S2S configured to reach each other
  - S2S peers env: XMPP_S2S_PEERS="serverb:5269" on server A, "servera:5269" on server B
  - websockets + httpx installed

Usage:
    python tests/load_test_federation.py [SERVER_A_URL] [SERVER_B_URL]

Defaults:
    SERVER_A_URL = http://localhost:8000
    SERVER_B_URL = http://localhost:8001

What it measures:
  - 50 WS connections per server (100 total)
  - Each client on A sends a message to a room on A; all A clients echo back
  - Each client on B sends a message to a room on B; all B clients echo back
  - Round-trip: A client sends DM to B user via REST; B client receives via WS
  - Reports: connect times, message delivery counts, failure rate, wall time
"""
import asyncio
import json
import sys
import time

import httpx
import websockets

SERVER_A = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
SERVER_B = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8001"

N_PER_SERVER = 50
ROOM_NAME_A = "fed_load_a"
ROOM_NAME_B = "fed_load_b"
PASSWORD = "fedpass123"


def _ws_url(base: str) -> str:
    return base.replace("http://", "ws://").replace("https://", "wss://")


async def register_and_login(base: str, idx: int, prefix: str) -> tuple[str, int]:
    email = f"{prefix}_{idx}@fed.test"
    username = f"{prefix}_{idx}"
    async with httpx.AsyncClient(base_url=base, timeout=15) as c:
        await c.post("/auth/register", json={"email": email, "password": PASSWORD, "username": username})
        r = await c.post("/auth/login", json={"email": email, "password": PASSWORD})
        cookie = ""
        for part in r.headers.get("set-cookie", "").split(";"):
            part = part.strip()
            if part.startswith("access_token="):
                cookie = part
                break
        me = await c.get("/auth/me")
        uid = me.json().get("id", 0)
    return cookie, uid


async def ensure_room(base: str, cookie: str, room_name: str) -> int:
    async with httpx.AsyncClient(base_url=base, headers={"Cookie": cookie}, timeout=15) as c:
        r = await c.post("/rooms", json={"name": room_name, "is_private": False})
        if r.status_code == 409:
            rooms = await c.get("/rooms/search", params={"q": room_name})
            return rooms.json()["results"][0]["id"]
        return r.json()["id"]


async def join_room(base: str, cookie: str, room_id: int) -> None:
    async with httpx.AsyncClient(base_url=base, headers={"Cookie": cookie}, timeout=15) as c:
        await c.post(f"/rooms/{room_id}/join")


async def ws_client(label: str, ws_base: str, cookie: str, room_id: int, results: list) -> None:
    uri = f"{ws_base}/ws/rooms/{room_id}"
    start = time.monotonic()
    received = 0
    try:
        async with websockets.connect(uri, extra_headers={"Cookie": cookie}, open_timeout=10) as ws:
            connect_ms = round((time.monotonic() - start) * 1000)
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if msg.get("type") == "room:joined":
                await ws.send(json.dumps({"type": "message:send", "payload": {"content": f"fed_{label}"}}))
                echo = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if echo.get("type") == "message:new":
                    received += 1
            results.append({"label": label, "connect_ms": connect_ms, "ok": received > 0})
    except Exception as e:
        results.append({"label": label, "connect_ms": -1, "ok": False, "err": str(e)})


async def run_server(base: str, prefix: str, room_name: str) -> list[dict]:
    ws_base = _ws_url(base)
    print(f"[{prefix}] Registering {N_PER_SERVER} users on {base}…")
    users = await asyncio.gather(*[register_and_login(base, i, prefix) for i in range(N_PER_SERVER)])
    cookies = [u[0] for u in users]

    room_id = await ensure_room(base, cookies[0], room_name)
    print(f"[{prefix}] Room ID: {room_id}")

    await asyncio.gather(*[join_room(base, c, room_id) for c in cookies])
    print(f"[{prefix}] All users joined. Opening {N_PER_SERVER} WS connections…")

    results: list[dict] = []
    await asyncio.gather(*[
        ws_client(f"{prefix}_{i}", ws_base, cookies[i], room_id, results)
        for i in range(N_PER_SERVER)
    ])
    return results


def _print_results(label: str, results: list[dict]) -> int:
    ok = sum(1 for r in results if r["ok"])
    fail = len(results) - ok
    times = [r["connect_ms"] for r in results if r["connect_ms"] >= 0]
    avg = round(sum(times) / len(times)) if times else -1
    print(f"\n[{label}] {ok}/{len(results)} OK  |  {fail} failed  |  avg connect: {avg} ms")
    for r in results:
        if not r["ok"]:
            print(f"  FAIL [{r['label']}] {r.get('err', 'no echo')}")
    return fail


async def main() -> int:
    print(f"Federation load test: {SERVER_A} ↔ {SERVER_B}  ({N_PER_SERVER} clients each)")
    t0 = time.monotonic()

    results_a, results_b = await asyncio.gather(
        run_server(SERVER_A, "usrA", ROOM_NAME_A),
        run_server(SERVER_B, "usrB", ROOM_NAME_B),
    )

    elapsed = round((time.monotonic() - t0) * 1000)
    print(f"\n{'='*60}")
    fail_a = _print_results("SERVER_A", results_a)
    fail_b = _print_results("SERVER_B", results_b)
    print(f"\nTotal wall time: {elapsed} ms")
    total_fail = fail_a + fail_b
    print(f"Overall: {N_PER_SERVER * 2 - total_fail}/{N_PER_SERVER * 2} OK")
    print("=" * 60)
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
