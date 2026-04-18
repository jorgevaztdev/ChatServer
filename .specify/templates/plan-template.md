# Implementation Plan: [FEATURE]
**Branch**: `[MVP-online-chat]` | **Date**: 2026-04-18 | **Spec**: [constitution-v2.md]
**Input**: Feature specification from `/specs/MVP-online-chat/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Implementation of a classic web-based online chat application supporting public/private rooms, 1-on-1 messaging, presence tracking, and file sharing. The technical approach involves a containerized web architecture using SQLite for persistent data storage (mounted via Docker volumes to ensure data survives container restarts) and local file system storage for media attachments.

## Technical Context

**Language/Version**: Python 3.11 (Backend) / HTML5/JavaScript (Frontend)
**Primary Dependencies**: FastAPI (for WebSockets/REST), SQLAlchemy, aioxmpp (for Jabber federation)
**Storage**: SQLite (Database) and Local Filesystem (Attachments) - *Must be mapped to persistent Docker Volumes*
**Frontend mockups**: All frontend implementation MUST reproduce the approved mockups in `screens/`. Before planning or implementing any UI component or page, read the corresponding `.html` file in `screens/` to extract layout, styling, color palette, and interaction patterns.

| Screen | Mockup file |
|--------|-------------|
| Login | `screens/login.html` |
| Register | `screens/register.html` |
| Forgot password | `screens/forgot-password.html` |
| Main chat | `screens/main-chat.html` |
| Contacts & friends | `screens/contacts-friends.html` |
| Room management | `screens/room-management.html` |
| Admin dashboard | `screens/admin-ui-dashboard.html` |
**Testing**: pytest (Backend), Jest/Cypress (Frontend/E2E)
**Target Platform**: Linux server (Docker Container via `docker-compose up`)
**Project Type**: Web Application (Backend + Frontend)
**Performance Goals**: < 3s message delivery, < 2s presence updates, support for 10k+ message infinite scroll
**Constraints**: strictly max 20MB files, max 3MB images, single `docker-compose up` execution requirement
**Scale/Scope**: Up to 300 simultaneous users, 1000 participants per room, ~20 rooms/50 contacts per typical user

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Classic Web Chat Paradigm**: UI layout aligns with standard web chat requirements.
- [x] **II. Reliable Multi-Session Architecture**: Presence accurately tracks tab-level activity.
- [x] **III. Guaranteed Performance & Scale**: Architecture targets < 3s delivery and 300 concurrent users.
- [x] **IV. Immutable Data & Privacy Control**: Cascading deletes mapped out; SQLite structure prepared.
- [x] **V. Federation & Extensibility**: Jabber protocol library integrated into backend dependencies.

## Project Structure

### Documentation (this feature)

```text
specs/MVP-online-chat/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
Source Code (repository root)Plaintextbackend/
├── src/
│   ├── models/          # SQLAlchemy SQLite models
│   ├── services/        # Presence, Messaging, and Jabber logic
│   ├── api/             # REST endpoints and WebSocket routers
│   └── storage/         # Local file I/O handlers
└── tests/
    ├── integration/
    └── unit/

frontend/
├── src/
│   ├── components/      # Chat layout, sidebars, modals
│   ├── pages/           # Main chat interface, Admin dashboard
│   └── services/        # WebSocket client, API fetchers
└── tests/

docker-compose.yml       # Root compose file with SQLite and Media volumes defined
Structure Decision: Web Application structure was selected to cleanly separate the classic web chat UI from the WebSocket/REST API backend. Both will be orchestrated via a root docker-compose.yml that strictly defines the SQLite .db file and the media uploads directory as persistent Docker Volumes to ensure data survival.Complexity TrackingFill ONLY if Constitution Check has violations that must be justifiedViolationWhy NeededSimpler Alternative Rejected BecauseJabber Federation integrationExplicitly requested in RFP "Advanced Requirements"Single-server isolated chat rejected because the RFP mandates Jabber client support and multi-server federation load testing.Persistent Volume MappingEphemeral container storage leads to permanent data loss upon restartStoring SQLite directly "inside" the container without volumes rejected because chat history and files must remain persistently available for years (Section 3.3).