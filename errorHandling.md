# Error Handling Report — Phase 5 QA Run

**Date**: 2026-04-18  
**QA Engineer**: Claude (Senior QA Agent)  
**Scope**: Phase 5 US-CONTACTS + full integration regression

---

## Phase 5 Results: ALL PASS ✅

27/27 tests in `tests/integration/test_friends.py` passed.

| Task | Endpoint | Tests | Result |
|------|----------|-------|--------|
| T032 | `POST /friends/request` | 6 | ✅ PASS |
| T033 | `POST /friends/accept/{id}`, `DELETE /friends/{id}`, `DELETE /friends/decline/{id}` | 7 | ✅ PASS |
| T034 | `GET /friends` | 6 | ✅ PASS |
| T035 | `GET /friends/requests` | 5 | ✅ PASS |

---

## Pre-Existing Failure Found — FIXED ✅

### ERR-001 — `test_ws_room_send_message` hangs indefinitely

**Related Story**: Phase 9 — US-MSG (T054)  
**File**: `backend/tests/integration/test_messaging.py:230`  
**Status**: Pre-existing bug (not introduced by Phase 5)

#### Steps to reproduce

```bash
DATABASE_URL="sqlite:///./test_chat.db" python3 -m pytest tests/integration/test_messaging.py::test_ws_room_send_message -v
```

Test runs indefinitely — never exits.

#### Expected Result

Test completes in < 5s.  
`ws.receive_json()` returns `{"type": "message:new", "payload": {...}}` after client sends `{"type": "message:send", "payload": {"content": "hello ws"}}`.

#### Actual Result

`ws.receive_json()` in test thread blocks indefinitely. Test never completes.

#### Root Cause Analysis

`hub` (in `src/services/websocket_hub.py:94`) is a **module-level singleton**. Between test runs, stale entries accumulate in:
- `_connections: dict[int, list[WebSocket]]` — dead WebSocket objects from prior test clients
- `_room_users: dict[int, set[int]]` — orphaned room subscriptions

When `send_room_message()` calls `hub.broadcast_room(room_id, payload)`:
1. `broadcast_user()` iterates all WS in `_connections[user_id]`
2. If stale WS from a previous test is present, `ws.send_json()` raises an exception
3. The exception is caught silently and the stale WS is removed
4. The `message:new` payload is attempted on the stale socket, not the live one

If user_id from a prior test happens to collide with current test's user_id (e.g., both register first user in a fresh DB and get `id=1`), the stale connection can interfere with delivery.

Additionally: `hub.join_room(room_id, user_id)` adds user to room, but if `hub._room_users` already has that room from a prior test, the set may contain a stale user_id that maps to dead connections — causing `broadcast_room` to fail silently before reaching the active connection.

#### Minimal Reproduction

```python
# Test A runs: alice (id=1) connects to room 1
# hub._connections = {1: [dead_ws_A]}
# hub._room_users = {1: {1}}

# Test B runs: alice (id=1) connects to room 1  
# hub._connections = {1: [dead_ws_A, live_ws_B]}
# hub._room_users = {1: {1}}  (already there)

# broadcast_room(1, payload):
#   dead_ws_A.send_json() → Exception → removed
#   live_ws_B.send_json() → OK
# But: exception handling may short-circuit — needs verification
```

#### Fix Required

In `conftest.py`, reset hub state after each test:

```python
# backend/tests/integration/conftest.py

@pytest.fixture()
def client():
    from src.models import user, session, room, message, attachment, social  # noqa: F401
    from src.services.websocket_hub import hub
    Base.metadata.create_all(bind=_engine)
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=_engine)
    # ← ADD THIS: reset singleton between tests
    hub._connections.clear()
    hub._room_users.clear()
    hub._activity.clear()
    hub._last_disconnect.clear()
```

#### Affected Tests

All tests in `test_messaging.py` that use `client.websocket_connect()`:
- `test_ws_room_send_message` (confirmed hanging)
- `test_ws_room_empty_send_ignored` (likely affected)
- Any future WS tests

#### Fix Applied

`conftest.py` updated — hub state cleared after each test fixture:

```python
# After yield in client fixture:
hub._connections.clear()
hub._room_users.clear()
hub._activity.clear()
hub._last_disconnect.clear()
```

**Result**: All 83 integration tests pass after fix. `83 passed in 81.01s`

#### Priority

~~**P2** — blocks WS message tests; non-blocking for Phase 5 delivery.~~ **RESOLVED**

---

## Run Command (Phase 5 only, confirmed green)

```bash
cd backend
DATABASE_URL="sqlite:///./test_chat.db" python3 -m pytest tests/integration/test_friends.py -v
# 27 passed in 24.86s
```

## Warnings (non-blocking)

| Warning | Impact |
|---------|--------|
| `@app.on_event("startup")` deprecated | None — functional. Migrate to `lifespan=` context manager when convenient |
| `datetime.utcnow()` deprecated in Python 3.13 | None — functional. Replace with `datetime.now(datetime.UTC)` in models |
