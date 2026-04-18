# Feature Specification: [FEATURE NAME]

**Feature Branch**: `[###-feature-name]`
**Created**: [DATE]
**Status**: Draft
**Input**: User description: "$ARGUMENTS"

## Technical Context

**Stack**: Python 3.11 (FastAPI + SQLAlchemy) / HTML5 + Vanilla JS
**Transport**: WebSockets (real-time) + REST (CRUD)
**Storage**: SQLite at `backend/data/chat.db` (Docker volume) + local filesystem at `backend/media/` (Docker volume)
**Auth**: JWT (httpOnly cookie, no expiry unless explicit logout)
**Deployment**: Single `docker-compose up` — both services must start cleanly from root `docker-compose.yml`
**Performance constraints**: < 3s message delivery, < 2s presence propagation, 10k+ message infinite scroll
**Scale constraints**: 300 simultaneous users, 1000 participants/room, max 20MB files / 3MB images
**Path conventions**: `backend/src/` (models, services, api, storage), `frontend/src/` (components, pages, services)
**Frontend mockups**: All UI work MUST match the approved mockups in `screens/`. Reference the corresponding `.html` file for each page before implementing any frontend component or page.

| Screen | Mockup file |
|--------|-------------|
| Login | `screens/login.html` |
| Register | `screens/register.html` |
| Forgot password | `screens/forgot-password.html` |
| Main chat | `screens/main-chat.html` |
| Contacts & friends | `screens/contacts-friends.html` |
| Room management | `screens/room-management.html` |
| Admin dashboard | `screens/admin-ui-dashboard.html` |

## Constitution Check

*Re-verify these before finalizing the spec.*

- [ ] **I. Classic Web Chat Paradigm**: UI layout matches standard chat conventions (sidebar + message pane + input bar)
- [ ] **II. Reliable Multi-Session Architecture**: Presence is tab-level, not device-level
- [ ] **III. Guaranteed Performance & Scale**: Feature does not break < 3s delivery or 300-user ceiling
- [ ] **IV. Immutable Data & Privacy Control**: Cascading deletes are defined for all owner relationships
- [ ] **V. Federation & Extensibility**: Jabber-facing endpoints remain unaffected (or are documented if changed)

## User Scenarios & Testing *(mandatory)*

<!--
  Stories must be PRIORITIZED as independent vertical slices.
  P1 = must-have for any usable MVP; P2 = important but deferrable; P3 = advanced/optional.
  Each story must be testable standalone via `docker-compose up` on the local dev machine.
-->

### User Story 1 - [Brief Title] (Priority: P1)

[Describe this user journey in plain language — who does what and why]

**Why this priority**: [Value delivered and why it blocks or enables other stories]

**Independent Test**: [Exact action sequence to verify: e.g., "Register → Login → perform X → assert Y visible in UI"]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]
2. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 2 - [Brief Title] (Priority: P2)

[Describe this user journey in plain language]

**Why this priority**: [Value delivered]

**Independent Test**: [Exact action sequence to verify independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 3 - [Brief Title] (Priority: P3)

[Describe this user journey in plain language]

**Why this priority**: [Value delivered]

**Independent Test**: [Exact action sequence to verify independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

- What happens when a user submits text > 3 KB?
- What happens when a file upload exceeds the 20 MB / 3 MB limit?
- What happens when a banned user attempts to access a room via direct URL?
- What happens when the WebSocket connection drops mid-send?
- How does presence behave when the browser crashes (no clean disconnect)?
- What happens when two tabs are open and one goes AFK but the other stays active?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST [specific backend capability with HTTP method and path, e.g., "expose POST /auth/register accepting {email, password, username}"]
- **FR-002**: System MUST [WebSocket event, e.g., "broadcast presence:update within 2s of tab activity change"]
- **FR-003**: Users MUST be able to [UI interaction, e.g., "trigger file upload via paste or button click"]
- **FR-004**: System MUST [persistence rule, e.g., "store messages in SQLite with created_at and is_edited flags"]
- **FR-005**: System MUST [access control rule, e.g., "reject file access requests from users not in the room"]

### Non-Functional Requirements

- **NFR-001**: All WebSocket message round-trips MUST complete in < 3 seconds under normal load
- **NFR-002**: Presence state changes MUST propagate to all observers in < 2 seconds
- **NFR-003**: Message history endpoints MUST support cursor-based pagination for 10k+ message threads
- **NFR-004**: File uploads MUST be rejected server-side if image > 3 MB or any file > 20 MB
- **NFR-005**: All data MUST survive `docker-compose down && docker-compose up` (volumes must be mapped)

### Key Entities *(include if feature involves data)*

- **User**: email (unique), username (unique, immutable), password_hash, created_at
- **Session**: user_id FK, token, created_at — one row per active browser tab/login
- **Room**: name (unique), description, is_private, owner_id FK, created_at
- **RoomMembership**: room_id FK, user_id FK, role (member | admin), joined_at
- **RoomBan**: room_id FK, banned_user_id FK, banned_by_id FK, created_at
- **Message**: room_id FK (nullable for DMs), sender_id FK, content (≤ 3 KB), reply_to_id FK (nullable), is_edited, created_at, updated_at
- **Attachment**: message_id FK, original_filename, stored_path, mime_type, size_bytes
- **Friendship**: requester_id FK, addressee_id FK, status (pending | accepted), created_at
- **UserBan**: banner_id FK, banned_id FK, created_at

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: [Specific measurable outcome tied to a user story, e.g., "User can register and send a message within 60 seconds of first visit"]
- **SC-002**: Message delivery latency is < 3s measured end-to-end via WebSocket under 50 concurrent connections
- **SC-003**: Presence status updates (online → AFK → offline) are visible to other users within 2 seconds
- **SC-004**: Infinite scroll loads previous messages without UI freeze on a thread with 10,000+ messages
- **SC-005**: `docker-compose down && docker-compose up` preserves all messages, rooms, and uploaded files

## Assumptions

- Mobile support is out of scope; desktop browser (Chrome/Firefox latest) is the target
- No email verification is required to complete registration
- Authentication uses JWT stored in httpOnly cookies; no OAuth or SSO providers
- The SQLite `.db` file is mapped to a named Docker volume defined in the root `docker-compose.yml`
- The media upload directory is mapped to a separate named Docker volume in the root `docker-compose.yml`
- Frontend is served as static HTML/JS from the backend container or a dedicated nginx container
- No CDN or object storage; all files are stored on the local filesystem inside the Docker volume
- [Add feature-specific assumptions here]
