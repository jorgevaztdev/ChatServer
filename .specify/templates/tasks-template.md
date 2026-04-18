---
description: "Task list for MVP Online Chat — Python 3.11 / FastAPI / SQLite / Docker"
---

# Tasks: MVP Online Chat

**Stack**: FastAPI + SQLAlchemy (backend) | HTML5 + Vanilla JS (frontend) | SQLite + Local FS (storage) | Docker Compose (deployment)
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/
**Path root**: `backend/src/` and `frontend/src/` as defined in plan.md
**Frontend mockups**: Every frontend task MUST be implemented to match the approved mockups in `screens/`. Read the relevant `.html` mockup file before writing any HTML/CSS/JS for that page or component.

| Screen | Mockup file |
|--------|-------------|
| Login | `screens/login.html` |
| Register | `screens/register.html` |
| Forgot password | `screens/forgot-password.html` |
| Main chat | `screens/main-chat.html` |
| Contacts & friends | `screens/contacts-friends.html` |
| Room management | `screens/room-management.html` |
| Admin dashboard | `screens/admin-ui-dashboard.html` |

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Safe to run in parallel — touches different files, no shared dependencies
- **[Story]**: Epic/story tag (e.g., US-AUTH, US-PRESENCE, US-ROOMS, US-MSG, US-FILES, US-JABBER)
- Tasks within a phase that are NOT marked [P] must run sequentially

---

## Phase 1: Setup

**Purpose**: Repository scaffold and Docker wiring — no story can start until this is done

- [ ] T001 Create directory tree: `backend/src/{models,services,api,storage}/`, `backend/tests/{unit,integration}/`, `frontend/src/{components,pages,services}/`
- [ ] T002 Create `backend/requirements.txt` with pinned versions: fastapi, uvicorn[standard], sqlalchemy, alembic, python-jose[cryptography], passlib[bcrypt], aiofiles, python-multipart, aioxmpp
- [ ] T003 [P] Create `backend/Dockerfile` — Python 3.11-slim, install requirements, expose port 8000
- [ ] T004 [P] Create `frontend/Dockerfile` — nginx:alpine serving `frontend/src/` as static files on port 80
- [ ] T005 Create root `docker-compose.yml` defining: `backend` service, `frontend` service, named volume `sqlite_data` mounted at `/data` in backend, named volume `media_data` mounted at `/media` in backend
- [ ] T006 [P] Create `backend/src/config.py` — reads env vars: `DATABASE_URL` (default `sqlite:////data/chat.db`), `MEDIA_DIR` (default `/media`), `JWT_SECRET`, `JWT_ALGORITHM` (default HS256)
- [ ] T007 [P] Create `backend/src/main.py` — FastAPI app instance, mounts routers, configures CORS, serves frontend static files in dev mode

**Checkpoint**: `docker-compose up` starts both containers without errors

---

## Phase 2: Foundational (Blocking — ALL stories depend on this)

**Purpose**: Database schema, auth primitives, WebSocket hub, and file handler that every story builds on

**CRITICAL**: No user-story phase can begin until T008–T019 are complete

- [ ] T008 Create `backend/src/models/base.py` — SQLAlchemy declarative base + `init_db()` that creates all tables on startup
- [ ] T009 [P] Create `backend/src/models/user.py` — `User` table: id, email (unique), username (unique, immutable), password_hash, created_at
- [ ] T010 [P] Create `backend/src/models/session.py` — `UserSession` table: id, user_id FK, token (unique), created_at
- [ ] T011 [P] Create `backend/src/models/room.py` — `Room` table: id, name (unique), description, is_private, owner_id FK, created_at; `RoomMembership` table: room_id FK, user_id FK, role enum(member|admin), joined_at; `RoomBan` table: room_id FK, banned_user_id FK, banned_by_id FK, created_at
- [ ] T012 [P] Create `backend/src/models/message.py` — `Message` table: id, room_id FK (nullable), sender_id FK, content (TEXT ≤ 3072 bytes enforced at service layer), reply_to_id FK (self-ref nullable), is_edited BOOL default false, created_at, updated_at
- [ ] T013 [P] Create `backend/src/models/attachment.py` — `Attachment` table: id, message_id FK, original_filename, stored_path, mime_type, size_bytes
- [ ] T014 [P] Create `backend/src/models/social.py` — `Friendship` table: id, requester_id FK, addressee_id FK, status enum(pending|accepted), created_at; `UserBan` table: id, banner_id FK, banned_id FK, created_at
- [ ] T015 Create `backend/src/services/auth.py` — `hash_password()`, `verify_password()`, `create_jwt()`, `decode_jwt()`, `get_current_user()` FastAPI dependency
- [ ] T016 Create `backend/src/services/websocket_hub.py` — `ConnectionHub` class: `connect(user_id, ws)`, `disconnect(user_id, ws)`, `broadcast_room(room_id, payload)`, `broadcast_user(user_id, payload)` — in-memory, supports multiple tabs per user
- [ ] T017 Create `backend/src/storage/file_handler.py` — `save_file(upload, media_dir) -> stored_path`: validates size (20 MB general / 3 MB image), preserves original filename with uuid prefix, writes to `MEDIA_DIR`
- [ ] T018 Create `backend/src/api/deps.py` — shared FastAPI dependencies: `get_db()` (SQLAlchemy session), `get_current_user()` (JWT cookie → User)
- [ ] T019 Create `backend/src/api/__init__.py` — APIRouter aggregating all sub-routers; wire into `main.py`

**Checkpoint**: `docker-compose up` → `GET /health` returns 200; SQLite tables exist in volume

---

## Phase 3: US-AUTH — User Accounts & Authentication (Priority: P1) 🎯 MVP

**Goal**: Users can register, log in (persistent session), log out, and delete their account

**Independent Test**: Register via UI → close and reopen browser → still logged in → delete account → confirm redirect to login

### Implementation

- [ ] T020 [US-AUTH] Create `backend/src/api/auth.py` — `POST /auth/register` (body: email, password, username → 201 User) with uniqueness validation for email and username
- [ ] T021 [US-AUTH] Create `backend/src/api/auth.py` — `POST /auth/login` (body: email, password → 200 + sets httpOnly JWT cookie; creates UserSession row)
- [ ] T022 [US-AUTH] Create `backend/src/api/auth.py` — `POST /auth/logout` (deletes current UserSession row, clears cookie — other sessions unaffected)
- [ ] T023 [US-AUTH] Create `backend/src/api/auth.py` — `DELETE /auth/account` (cascades: delete owned Rooms + their Messages/Attachments/files on disk; remove RoomMembership rows for non-owned rooms; delete UserSessions; delete User row)
- [ ] T024 [P] [US-AUTH] Create `frontend/src/pages/register.html` + `frontend/src/services/auth.js` — registration form calling `POST /auth/register`; redirect to login on success
- [ ] T025 [P] [US-AUTH] Create `frontend/src/pages/login.html` — login form calling `POST /auth/login`; redirect to main chat on success
- [ ] T026 [US-AUTH] Add "Delete account" button to profile UI (confirmation modal required before calling `DELETE /auth/account`)

**Checkpoint**: Register → login (persist across browser close) → logout → login again → delete account → confirm all owned rooms removed

---

## Phase 4: US-PRESENCE — Presence & Sessions (Priority: P1) 🎯 MVP

**Goal**: Online/AFK/offline status is visible to others and updates within 2 seconds

**Independent Test**: Open two tabs as User A while User B watches → go AFK on both tabs → both parties see AFK within 2s → close all tabs → User B sees offline within 2s

### Implementation

- [ ] T027 [US-PRESENCE] Add presence fields to `ConnectionHub`: track last-activity timestamp per (user_id, tab); compute aggregate status: online (any tab active), AFK (all tabs idle > 60s), offline (no tabs)
- [ ] T028 [US-PRESENCE] Create `backend/src/services/presence.py` — `update_activity(user_id, tab_id)`, `get_status(user_id) -> "online"|"AFK"|"offline"`, `broadcast_status_change(user_id)` via `ConnectionHub`
- [ ] T029 [US-PRESENCE] Add WebSocket endpoint `WS /ws/presence` — client sends `{type:"heartbeat", tab_id}` every 30s; server replies with own status and pushes `presence:update` events for followed users
- [ ] T030 [US-PRESENCE] Handle WebSocket disconnect in `ConnectionHub.disconnect()`: if last tab closes, broadcast `presence:update` with status=offline after 5s grace window
- [ ] T031 [P] [US-PRESENCE] Add presence indicators to `frontend/src/components/presence-dot.js` — renders colored dot (green=online, yellow=AFK, gray=offline); auto-updates on `presence:update` WebSocket event

**Checkpoint**: Status changes reflect for all viewers within 2 seconds; AFK triggers after 60s of no input; offline triggers when last tab closes

---

## Phase 5: US-CONTACTS — Contacts & Friend List (Priority: P2)

**Goal**: Users can add friends, accept/decline requests, remove friends, and initiate DMs only with mutual friends

**Independent Test**: User A sends request to User B → User B accepts → both see each other in friend list → User A removes User B → DM option disappears for both

### Implementation

- [ ] T032 [US-CONTACTS] Create `backend/src/api/friends.py` — `POST /friends/request` (body: username, optional message → creates Friendship row with status=pending)
- [ ] T033 [US-CONTACTS] Add to `backend/src/api/friends.py` — `POST /friends/accept/{requester_id}`, `DELETE /friends/{user_id}` (remove friendship, no DM allowed after)
- [ ] T034 [US-CONTACTS] Add to `backend/src/api/friends.py` — `GET /friends` → list of accepted friends with current presence status
- [ ] T035 [US-CONTACTS] Add to `backend/src/api/friends.py` — `GET /friends/requests` → list of pending incoming requests
- [ ] T036 [P] [US-CONTACTS] Create `frontend/src/pages/contacts.html` + `frontend/src/components/friend-list.js` — renders friend list with presence dots; "Add friend" search by username; accept/decline pending requests

**Checkpoint**: Full friend request flow works end-to-end; DM only accessible for mutual friends

---

## Phase 6: US-BAN — User-to-User Banning (Priority: P2)

**Goal**: Users can block unwanted contacts; banned users cannot message the banner; existing DM history becomes read-only

**Independent Test**: User A bans User B → User B's DM send button is disabled → existing messages are visible but frozen → User A's ban list shows User B

### Implementation

- [ ] T037 [US-BAN] Create `backend/src/api/bans.py` — `POST /bans/user/{user_id}` (creates UserBan row; terminates Friendship; existing DM messages remain but endpoint rejects new DM sends if either party has banned the other)
- [ ] T038 [US-BAN] Add to message send service: check UserBan table before persisting DM messages — return 403 if ban exists in either direction
- [ ] T039 [P] [US-BAN] Update `frontend/src/pages/contacts.html` — show "Ban" option in user context menu; display frozen/read-only indicator on DM thread when a ban exists

**Checkpoint**: Ban blocks new DMs in both directions; old history viewable but read-only; friendship terminated

---

## Phase 7: US-ROOMS — Chat Room Creation & Discovery (Priority: P1) 🎯 MVP

**Goal**: Users can create public and private rooms, browse the public catalog, join freely, and invite to private rooms

**Independent Test**: Create public room → appears in catalog → second user joins freely; Create private room → does NOT appear in catalog → invite second user → second user can join

### Implementation

- [ ] T040 [US-ROOMS] Create `backend/src/api/rooms.py` — `POST /rooms` (body: name, description, is_private → creates Room + RoomMembership with role=admin for creator/owner)
- [ ] T041 [US-ROOMS] Add to `backend/src/api/rooms.py` — `GET /rooms` → paginated list of public rooms with member count; `GET /rooms/search?q=` → search public rooms by name
- [ ] T042 [US-ROOMS] Add to `backend/src/api/rooms.py` — `POST /rooms/{id}/join` (adds RoomMembership for public rooms; 403 for private)
- [ ] T043 [US-ROOMS] Add to `backend/src/api/rooms.py` — `POST /rooms/{id}/invite` (admin/owner only; adds invited user's RoomMembership for private rooms)
- [ ] T044 [US-ROOMS] Add to `backend/src/api/rooms.py` — `POST /rooms/{id}/leave` (disabled/hidden for owner; removes RoomMembership for members)
- [ ] T045 [P] [US-ROOMS] Create `frontend/src/pages/room-catalog.html` + `frontend/src/components/room-list.js` — displays public rooms with join button; create-room modal (name, description, public/private toggle)

**Checkpoint**: Public room visible in catalog and freely joinable; private room invisible and invite-only; owner cannot leave

---

## Phase 8: US-MODERATION — Room Admin & Moderation (Priority: P2)

**Goal**: Admins can moderate messages and members; owner has full control including room deletion

**Independent Test**: Admin deletes a message → disappears for all users; Admin bans member → member immediately loses room access; Owner deletes room → all members redirected, data purged

### Implementation

- [ ] T046 [US-MODERATION] Create `backend/src/api/moderation.py` — `DELETE /rooms/{id}/messages/{msg_id}` (admin or owner only; deletes Message + Attachments + files on disk)
- [ ] T047 [US-MODERATION] Add to `backend/src/api/moderation.py` — `POST /rooms/{id}/ban/{user_id}` (admin or owner only; creates RoomBan, removes RoomMembership, pushes `room:banned` WebSocket event to target user)
- [ ] T048 [US-MODERATION] Add to `backend/src/api/moderation.py` — `DELETE /rooms/{id}/ban/{user_id}` (unban; owner only for admin-placed bans)
- [ ] T049 [US-MODERATION] Add to `backend/src/api/moderation.py` — `POST /rooms/{id}/admins/{user_id}` (owner only; sets RoomMembership.role=admin); `DELETE /rooms/{id}/admins/{user_id}` (owner only; demotes to member — cannot demote owner)
- [ ] T050 [US-MODERATION] Add to `backend/src/api/rooms.py` — `DELETE /rooms/{id}` (owner only; cascades: delete all Messages, Attachments, files on disk, RoomMemberships, RoomBans, then Room row)
- [ ] T051 [US-MODERATION] Add to `backend/src/api/moderation.py` — `GET /rooms/{id}/bans` (admin/owner; returns list of banned users with ban issuer)
- [ ] T052 [P] [US-MODERATION] Create `frontend/src/components/moderation-modal.js` — modal dialog for ban/remove/promote/delete actions triggered from right-click or gear icon in room member list

**Checkpoint**: Admin can ban/delete; owner can delete room; banned user immediately loses access; admin cannot demote owner

---

## Phase 9: US-MSG — Messaging (Priority: P1) 🎯 MVP

**Goal**: Users can send, edit, delete, and reply to messages in real time; offline messages are queued and delivered on reconnect; infinite scroll works for 10k+ history

**Independent Test**: Send message in room → appears for all members < 3s; edit message → "edited" tag appears; scroll to top of 10k+ thread → loads without freeze; disconnect and reconnect → missed messages delivered

### Implementation

- [ ] T053 [US-MSG] Create `backend/src/services/messaging.py` — `send_message(room_id, sender_id, content, reply_to_id)`: validates content ≤ 3072 bytes, persists Message, broadcasts `message:new` via `ConnectionHub`
- [ ] T054 [US-MSG] Add to `backend/src/api/rooms.py` — WebSocket endpoint `WS /ws/rooms/{id}`: on connect verify membership; relay `message:new`, `message:edited`, `message:deleted`, `presence:update` events to all room members
- [ ] T055 [US-MSG] Create `backend/src/api/messages.py` — `POST /rooms/{id}/messages` (REST fallback for send); `GET /rooms/{id}/messages?before=<cursor>&limit=50` (cursor pagination, newest-first)
- [ ] T056 [US-MSG] Add to `backend/src/api/messages.py` — `PUT /messages/{id}` (sender only; updates content, sets is_edited=true, updated_at=now; broadcasts `message:edited`)
- [ ] T057 [US-MSG] Add to `backend/src/api/messages.py` — `DELETE /messages/{id}` (sender or room admin/owner; deletes Message + Attachment + file on disk; broadcasts `message:deleted`)
- [ ] T058 [US-MSG] Add DM support to `backend/src/services/messaging.py` — same as room messages but room_id=null; sender/recipient must be mutual friends with no active ban; deliver via `ConnectionHub.broadcast_user()`
- [ ] T059 [US-MSG] Implement offline message queue: on WebSocket connect, query Messages created after user's last disconnect and push them in order before subscribing to live events
- [ ] T060 [P] [US-MSG] Create `frontend/src/pages/main-chat.html` — three-column layout: rooms/DMs sidebar | message pane with infinite scroll | members sidebar
- [ ] T061 [P] [US-MSG] Create `frontend/src/components/message-list.js` — renders messages chronologically; reply-to quote block; "edited" gray badge; Intersection Observer for infinite scroll trigger
- [ ] T062 [P] [US-MSG] Create `frontend/src/components/message-input.js` — text input (multiline), emoji picker, attach button, paste handler; submit via WebSocket `message:send` event; shows reply-to preview when replying

**Checkpoint**: Real-time send < 3s; edit shows badge; delete removes for all; offline queue delivers on reconnect; 10k+ scroll does not freeze

---

## Phase 10: US-FILES — File & Image Sharing (Priority: P2)

**Goal**: Users can upload and share images (≤ 3 MB) and files (≤ 20 MB) via button or paste; files are access-controlled per room/DM membership

**Independent Test**: Paste image into input → uploads and displays inline; upload 25 MB file → rejected with error; banned user's direct file URL → 403; original filename preserved in download

### Implementation

- [ ] T063 [US-FILES] Create `backend/src/api/files.py` — `POST /upload` (multipart/form-data: file + optional comment + room_id or dm_partner_id): calls `file_handler.save_file()`, creates Attachment + Message row, broadcasts `message:new` with attachment payload
- [ ] T064 [US-FILES] Add to `backend/src/api/files.py` — `GET /files/{attachment_id}`: verifies requesting user is current member of the room (or DM participant); streams file from `MEDIA_DIR`; returns 403 otherwise
- [ ] T065 [US-FILES] Enforce in `file_handler.save_file()`: reject if `image/*` MIME and size > 3 145 728 bytes (3 MB); reject any file > 20 971 520 bytes (20 MB); return 413 with descriptive error
- [ ] T066 [P] [US-FILES] Update `frontend/src/components/message-input.js` — add paste event listener for `ClipboardEvent.clipboardData.files`; add file picker `<input type="file">`; show upload progress bar; display optional comment field before submit
- [ ] T067 [P] [US-FILES] Update `frontend/src/components/message-list.js` — render image attachments inline with `<img>`; render non-image attachments as download link showing original filename and size

**Checkpoint**: Image paste works; 25 MB upload rejected; banned user gets 403 on direct file URL; original filename shown in download

---

## Phase 11: US-JABBER — Jabber Protocol & Server Federation (Priority: P3)

**Goal**: Third-party Jabber clients can connect; two server instances can federate messages; Admin UI shows connection/federation stats; entire setup runs via `docker-compose up`

**Independent Test**: Connect Gajim/Pidgin to the server → authenticate and send message → appears in web UI; Server A user messages Server B user → message delivered and displayed on both sides

### Implementation

- [ ] T068 [US-JABBER] Create `backend/src/services/jabber_server.py` — aioxmpp-based XMPP component: C2S (client-to-server) listener on port 5222; bridges incoming XMPP messages to internal `messaging.py` service
- [ ] T069 [US-JABBER] Add S2S (server-to-server) federation handler in `jabber_server.py` using aioxmpp federation primitives; route federated messages to destination rooms/users
- [ ] T070 [US-JABBER] Create `backend/src/api/admin.py` — `GET /admin/jabber/connections` (active C2S sessions count, client JIDs); `GET /admin/jabber/federation` (active S2S links, messages in/out per peer)
- [ ] T071 [P] [US-JABBER] Create `frontend/src/pages/admin-dashboard.html` — Jabber section: connection count widget, federation traffic table refreshed every 5s via `GET /admin/jabber/*`
- [ ] T072 Update root `docker-compose.yml` — add second backend service `backend_b` on different ports (8001, 5223) with its own volumes; configure S2S hostnames so both instances can federate

**Checkpoint**: Jabber client connects and sends messages visible in web UI; Server A ↔ Server B messages routed correctly; Admin dashboard shows live stats; `docker-compose up` starts everything

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Hardening and validation that spans all stories

- [ ] T073 [P] Add rate limiting to `POST /auth/login` (max 10 attempts/minute per IP) using a simple in-memory counter or Redis if available
- [ ] T074 [P] Add input sanitization middleware — strip HTML from all user-supplied text fields before persistence (XSS prevention)
- [ ] T075 [P] Add `GET /health` endpoint returning `{status: "ok", db: "ok", media_dir: "writable"}` — used by Docker healthcheck
- [ ] T076 Validate `docker-compose down && docker-compose up` — all messages, rooms, and files survive restart; confirm volumes are correctly named and mounted
- [ ] T077 [P] Create `backend/tests/integration/test_auth.py` — register, login, logout, delete account flow
- [ ] T078 [P] Create `backend/tests/integration/test_messaging.py` — send, edit, delete, reply, offline-queue delivery
- [ ] T079 [P] Create `backend/tests/integration/test_files.py` — upload, size rejection, access control for banned user
- [ ] T080 Run manual load test: 50 simultaneous WebSocket connections sending messages to one room; confirm all deliveries < 3s

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Requires Phase 1 — BLOCKS all story phases
- **Phases 3–11 (User Stories)**: All require Phase 2 completion; can proceed in parallel across teams
- **Phase 12 (Polish)**: Requires all desired story phases complete

### Story Priority Order (single developer)

P1 first (unblocks demo): Phase 3 (Auth) → Phase 4 (Presence) → Phase 7 (Rooms) → Phase 9 (Messaging)
P2 next (full product): Phase 5 (Contacts) → Phase 6 (Bans) → Phase 8 (Moderation) → Phase 10 (Files)
P3 last (advanced): Phase 11 (Jabber)

### Parallel Opportunities

- All Phase 1 tasks marked [P] can run in parallel
- All Phase 2 model tasks (T009–T014) can run in parallel
- After Phase 2: Phases 3–11 can be assigned to different developers in parallel
- Within each phase, tasks marked [P] touch different files and can run concurrently

---

## Notes

- `[P]` = safe to parallelize — different files, no shared write dependency
- `[US-*]` = story tag for traceability back to UserStories.md epics
- Every model must be registered in `base.py` metadata before `init_db()` is called
- WebSocket events use consistent payload shape: `{type: "<event>", payload: {...}}`
- All file deletes (message delete, room delete, account delete) MUST also remove the physical file from `MEDIA_DIR`
- Commit after each completed task or logical group; verify `docker-compose up` still works after each phase
