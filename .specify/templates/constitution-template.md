# Online Chat Server Constitution

## Core Principles

### I. Classic Web Chat Paradigm
The application must represent a typical "classic web chat" experience. Navigation, room lists, contact lists, message history, notifications, and online presence indicators must be straightforward. We prioritize functional chat layouts over modern social network bloat or complex collaboration suite features.

### II. Multi-Session & Tab Reliability
The application must work flawlessly across multiple browser tabs and devices. A user is only "offline" when all tabs are closed; "AFK" triggers after 1 minute of inactivity across all open tabs. Login state persists across browser restarts, and logging out of one session must never unexpectedly terminate others.

### III. Immutable Data Control & Privacy
Data boundaries and lifecycles are strict. Usernames are unique and immutable. Deleting an account or a room cascades permanently, purging all associated messages, files, and images. File access is strictly tied to room membership—if a user is banned or loses access, they instantly lose access to all related files.

### IV. Scalability & Performance Limits
The system is built for moderate scale, strictly supporting up to 300 simultaneously connected users and 1,000 participants per room. Message delivery must occur within 3 seconds, and presence status updates must propagate in under 2 seconds. The UI must smoothly handle infinite scrolling for histories exceeding 10,000 messages.

### V. Federation & Extensibility (Advanced)
The architecture must transcend a single-server silo by supporting the Jabber protocol and server-to-server federation. The system must accommodate cross-server messaging traffic, support robust third-party Jabber client connections, and handle load testing across federated nodes.

## Architectural Constraints & Security

* **Storage Constraints:** Files must be stored on the local file system. Maximum file size is strictly capped at 20 MB, and maximum image size at 3 MB.
* **Security Standards:** Passwords must be stored securely in hashed form. No forced periodic password changes are required. Email verification is not required for onboarding.
* **Integrity:** System must preserve the strict consistency of room membership, room bans, file access rights, message history, and admin/owner permissions.

## Development Workflow & Deployment Standards

* **Containerization:** This is mandatory. The project MUST be universally buildable and runnable executing exactly `docker compose up` in the root repository folder.
* **Advanced Federation Testing:** Multi-server architectures must be fully orchestrated within the docker-compose setup. Load tests must explicitly verify 50+ clients on Server A communicating with 50+ clients on Server B.
* **UI/UX Acceptance:** Administrative actions must be implemented via modal dialogs. Standard chat behaviors like automatic scrolling to new messages (unless scrolled up to read history) must be implemented.

## Governance

This Constitution supersedes all other feature assumptions and serves as the ultimate source of truth for the Online Chat Server MVP. All pull requests and feature implementations must verify compliance with these explicit constraints. Features outside this specific scope (e.g., implementing read receipts, auto-logout due to inactivity, or cloud bucket storage) are strictly prohibited unless formally amended and documented here.

**Version**: 1.0.0 | **Ratified**: 2026-04-18 | **Last Amended**: 2026-04-18