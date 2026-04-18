# Online Chat Server Constitution

## Core Principles

### I. Classic Web Chat Paradigm
The application must represent a typical "classic web chat" experience. Navigation, room lists, contact lists, and message history should be straightforward and intuitive. We prioritize functional chat layouts (top menu, center messages, bottom input, sidebars for rooms/users) over modern social network bloat or complex collaboration suite features.

### II. Reliable Multi-Session Architecture
User presence and sessions must be rock-solid across multiple browser tabs and devices. A user is only "offline" when all tabs are closed; "AFK" triggers after 1 minute of inactivity across all open tabs. Login state must persist across browser restarts, and logging out of one session must never unexpectedly terminate others.

### III. Guaranteed Performance & Scale
The system is built for a moderate scale, strictly supporting up to 300 simultaneously connected users and single rooms with up to 1000 participants. Message delivery must be consistently fast (under 3 seconds), and presence status updates must propagate with low latency (under 2 seconds).

### IV. Immutable Data & Privacy Control
Data integrity and user boundaries are strict. Usernames are unique and immutable. Deleting an account or room cascades perfectly to delete all associated messages and files permanently. File access strictly mirrors room access—if a user loses access or is banned, they instantly lose access to all related files and history.

### V. Federation & Extensibility (Advanced)
The architecture must transcend a single server silo by supporting the Jabber protocol and server-to-server federation. The system must support scaling to multi-server environments, accommodating cross-server messaging traffic and robust third-party Jabber client connections.

## Epics and User Stories

This section houses the fundamental Epics that define our application features, formatted strictly as Jira-ready user stories.

**1. User Accounts and Authentication**
* **Registration:** Self-registration via unique email and immutable username. No email verification required. Passwords securely hashed.
* **Authentication:** Email/password sign-in. Independent session management. No automatic logout on inactivity.
* **Account Deletion:** Permanent purge of user profile, owned rooms, and associated files.

**2. Presence and Sessions**
* **Visibility:** Real-time Online, AFK, and Offline statuses with sub-2-second propagation.
* **Multi-Tab:** Presence intelligently aggregated across multiple tabs (active in any tab = Online).

**3. Contacts and Friends**
* **Management:** Two-way confirmed friend requests with optional text.
* **Moderation:** User-to-user blocking/banning, freezing existing history into read-only, and completely blocking new personal messages.

**4. Chat Rooms**
* **Creation & Discovery:** Public (cataloged) and Private (invite-only) rooms with unique names.
* **Hierarchy:** Strict Owner > Admin > Member hierarchy. Owners manage admins and the room lifecycle; Admins handle kicks, bans, and message deletion.

**5. Messaging and Attachments**
* **Rich Text:** Up to 3 KB text messages, UTF-8, multiline, emojis, and inline replies/quotes. Edits show an "edited" flag.
* **Files:** Arbitrary files (up to 20 MB) and images (up to 3 MB) stored on the local file system. Accessible only by current authorized participants. Infinite scroll for older history.

## Development Workflow & Architecture Standards

* **Containerization (Mandatory):** The project MUST be universally buildable and runnable using exactly `docker compose up` executed from the root repository folder.
* **Tech Stack Alignment:** Use a chosen tech stack with natively compatible Jabber libraries for federation. Custom file storage implementation must rely on the local file system, not cloud buckets.
* **Testing Gates:** All code must pass performance checks verifying sub-3-second delivery, infinite scrolling on 10,000+ message history, and load tests for federation traffic (simulating 50+ clients on Server A messaging Server B).

## Governance

This constitution serves as the ultimate source of truth for project requirements. All pull requests and feature implementations must be verified against these core principles and epics. Features outside this specific scope (e.g., forced periodic password changes, email verification) are explicitly prohibited unless formally amended. The deployment and testing standard (`docker compose up`) is non-negotiable.

**Version**: 1.0.0 | **Ratified**: 2026-04-18 | **Last Amended**: 2026-04-18