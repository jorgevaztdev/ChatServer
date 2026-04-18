Here are the Jira-ready user stories based on the RFP you provided. I have organized them logically by feature areas (Epics) so you can easily copy and paste them into your backlog. 

***

### Epic: User Accounts and Authentication

**As a new User I want to register for an account So That I can access the chat application.**
**Acceptance Criteria**
* The registration form must include Email, Password, and Username.
* Email must be unique across the system.
* Username must be unique across the system.
* Username cannot be changed after registration (immutable).
* The user is not required to verify their email to complete registration.
* Passwords must be stored securely in hashed form.

**Testing Cases and Edge cases**
* *Test Case 1:* User registers with a valid, unique email and username. Expect successful creation.
* *Test Case 2:* User attempts to register with an already existing email. Expect validation error.
* *Edge Case 1:* User attempts to change their username post-registration through UI or API. Expect failure/rejection.
* *Edge Case 2:* User submits very long strings for the username. (Requires defining max length in UI, but must handle gracefully).

**Definition of Done**
* Code peer-reviewed and merged.
* Unit and integration tests passed.
* Feature deployed to the staging environment.
* Verified working via `docker compose up`.

---

**As a registered User I want to sign in and out of my account So That I can securely access my chats and protect my session.**
**Acceptance Criteria**
* User can log in using their email and password.
* Login state must persist across browser close and reopen.
* User can sign out, which terminates the current browser session only.
* Active sessions on other browsers/devices are not affected by logging out of the current one.
* No automatic logout due to inactivity is enforced.

**Testing Cases and Edge cases**
* *Test Case 1:* User logs in, closes the browser, reopens the browser, and navigates to the app. Expect user to remain logged in.
* *Test Case 2:* User logs in on Browser A and Browser B. User logs out on Browser A. Expect Browser B to remain logged in.
* *Edge Case 1:* User attempts brute-force login. (While not explicitly in RFP, system should handle gracefully or fail standard auth tests).

**Definition of Done**
* Code peer-reviewed and merged.
* Unit and integration tests passed.
* Feature deployed to the staging environment.
* Verified working via `docker compose up`.

---

**As a registered User I want to delete my account So That my data and the rooms I own are removed from the system.**
**Acceptance Criteria**
* A "Delete account" action is available in the UI.
* Deleting an account removes the user's profile and terminates their active sessions.
* Only chat rooms owned by the deleted user are deleted.
* All messages, files, and images within the deleted rooms are permanently deleted.
* The deleted user is removed from membership in all other rooms they did not own.

**Testing Cases and Edge cases**
* *Test Case 1:* User deletes account. Expect their profile, owned rooms, and associated files to be purged.
* *Test Case 2:* User deletes account. Expect them to be removed from the member list of a public room they joined.
* *Edge Case 1:* An admin of a room (but not owner) deletes their account. The room must remain intact.

**Definition of Done**
* Code peer-reviewed and merged.
* Unit and integration tests passed.
* Feature deployed to the staging environment.
* Verified working via `docker compose up`.

***

### Epic: Presence and Sessions

**As a User I want my online presence to be visible to others So That my contacts know when I am available to chat.**
**Acceptance Criteria**
* The system supports three statuses: online, AFK, and offline.
* Presence updates propagate with a latency below 2 seconds.
* A user is "online" if active in at least one browser tab.
* A user becomes "AFK" only if they have not interacted with *any* open browser tab for more than 1 minute.
* A user becomes "offline" only when all browser tabs running the app are closed or offloaded by the browser.

**Testing Cases and Edge cases**
* *Test Case 1:* User opens a tab, interacts. Status shows "online". Waits 61 seconds with no interaction. Status shows "AFK".
* *Test Case 2:* User opens two tabs. Tab A is idle for 2 minutes. Tab B is actively used. Status shows "online".
* *Edge Case 1:* Browser suddenly crashes or loses network. Status should eventually default to offline.

**Definition of Done**
* Code peer-reviewed and merged.
* Unit and integration tests passed.
* Feature deployed to the staging environment.
* Verified working via `docker compose up`.

***

### Epic: Contacts and Friends

**As a User I want to manage my friend list So That I can easily see and send personal messages to people I know.**
**Acceptance Criteria**
* User has a personal contact/friend list.
* User can send a friend request by searching a username or from a chat room's user list.
* Friend requests can include optional text.
* Adding a friend requires the recipient's confirmation.
* User can remove someone from their friend list.
* Personal messaging is strictly restricted to confirmed friends who have not banned each other.

**Testing Cases and Edge cases**
* *Test Case 1:* User A sends a request to User B. User B accepts. They can now send personal messages.
* *Test Case 2:* User A removes User B from friends. Both users lose the ability to send new personal messages to each other.
* *Edge Case 1:* User tries to send a friend request to a user who doesn't exist. Expect error message.

**Definition of Done**
* Code peer-reviewed and merged.
* Unit and integration tests passed.
* Feature deployed to the staging environment.
* Verified working via `docker compose up`.

---

**As a User I want to ban another user So That I can block unwanted interactions.**
**Acceptance Criteria**
* A user can apply a user-to-user ban.
* The banned user cannot contact the banner in any way.
* New personal messaging is blocked immediately.
* Existing personal message history remains visible but becomes read-only/frozen.
* The friend relationship is terminated.

**Testing Cases and Edge cases**
* *Test Case 1:* User A bans User B. User B attempts to message User A. Expect message to fail/be blocked.
* *Test Case 2:* User A views past chat history with banned User B. Expect UI to show history as read-only.
* *Edge Case 1:* Both users ban each other simultaneously. System must enforce the read-only state and block all messaging.

**Definition of Done**
* Code peer-reviewed and merged.
* Unit and integration tests passed.
* Feature deployed to the staging environment.
* Verified working via `docker compose up`.

***

### Epic: Chat Rooms

**As a User I want to create and manage chat rooms So That I can facilitate group discussions.**
**Acceptance Criteria**
* Any registered user can create a room with a unique name, description, and visibility (public or private).
* The creator is designated as the "owner" and an "admin".
* The owner cannot leave their own room, they can only delete it.
* Public rooms are listed in a searchable catalog and can be joined freely.
* Private rooms are hidden from the catalog and require an invitation to join.

**Testing Cases and Edge cases**
* *Test Case 1:* User creates a public room. Expect it to appear in the public catalog and allow others to join.
* *Test Case 2:* User attempts to create a room with an already existing room name. Expect validation error.
* *Edge Case 1:* The owner attempts to click "Leave Room". The action is hidden or disabled.

**Definition of Done**
* Code peer-reviewed and merged.
* Unit and integration tests passed.
* Feature deployed to the staging environment.
* Verified working via `docker compose up`.

---

**As a Room Admin I want to moderate my chat room So That I can maintain a safe and orderly environment.**
**Acceptance Criteria**
* Admins can delete messages, remove members, and ban/unban members from the room.
* Banning a user removes them from the room and prevents rejoining.
* If a user is banned/removed, they lose access to the room UI, message history, files, and images.
* Admins can view the banned users list and see who issued the ban.
* The Room Owner can do all admin actions, plus remove other admins, remove any member, and delete the room completely.
* Admin actions are executed via modal dialogs in the UI.

**Testing Cases and Edge cases**
* *Test Case 1:* Admin bans a user. Expect the user to immediately lose access to the room's chat and file history.
* *Test Case 2:* Owner attempts to revoke Admin status from another Admin. Expect success.
* *Edge Case 1:* An Admin attempts to revoke the Owner's admin status. Expect failure/action disabled.

**Definition of Done**
* Code peer-reviewed and merged.
* Unit and integration tests passed.
* Feature deployed to the staging environment.
* Verified working via `docker compose up`.

***

### Epic: Messaging & Attachments

**As a User I want to send, edit, and view messages So That I can communicate effectively.**
**Acceptance Criteria**
* Messages can contain plain text, multiline text, and emojis.
* Users can reply to specific messages (replied message must be visually outlined/quoted).
* Maximum text size per message is 3 KB (UTF-8 supported).
* Users can edit their own messages; edited messages must display a gray "edited" indicator.
* Users can delete their own messages.
* Messages must be delivered within 3 seconds of sending.
* Messages are stored persistently, displayed chronologically, and support infinite scroll for history.
* Messages sent to offline users are delivered when they next connect.

**Testing Cases and Edge cases**
* *Test Case 1:* User edits a message. Expect the text to update for all users and the "edited" tag to appear.
* *Test Case 2:* User scrolls to the top of a chat with 10,000+ messages. Expect infinite scroll to load older messages smoothly without crashing.
* *Edge Case 1:* User pastes exactly 3.1 KB of text. Expect the UI or server to reject the message due to size limits.

**Definition of Done**
* Code peer-reviewed and merged.
* Unit and integration tests passed.
* Feature deployed to the staging environment.
* Verified working via `docker compose up`.

---

**As a User I want to share files and images in chats So That I can collaborate and share media.**
**Acceptance Criteria**
* Users can upload images (max 3 MB) and arbitrary files (max 20 MB).
* Uploads can be triggered via a button or copy-and-paste.
* Original file names must be preserved, and users can add an optional comment.
* Files are stored on the local file system.
* Files and images are only accessible to current members of the room or personal chat.
* If a user uploaded a file and later loses access to the room, the file remains stored but the original uploader can no longer manage or view it.

**Testing Cases and Edge cases**
* *Test Case 1:* User pastes an image into the chat input. Expect it to upload and display in the chat.
* *Test Case 2:* User attempts to upload a 25 MB PDF. Expect the upload to be rejected based on the 20 MB limit.
* *Edge Case 1:* User uploads a file, then gets banned from the room. The file must remain in the room for other users, but the banned user cannot access it via direct link.

**Definition of Done**
* Code peer-reviewed and merged.
* Unit and integration tests passed.
* Feature deployed to the staging environment.
* Verified working via `docker compose up`.

***

### Epic: Advanced & Infrastructure

**As a System Administrator I want to support Jabber protocol and server federation So That clients can connect via alternative protocols and communicate across different servers.**
**Acceptance Criteria**
* The server supports Jabber protocol client connections.
* The system supports federation (messaging between servers).
* A specific Jabber dashboard is added to the Admin UI, showing a Connection Dashboard and Federation traffic info/statistics.
* The setup is completely runnable via `docker compose up`.
* The system can handle load testing with 50+ clients on Server A communicating with 50+ clients on Server B.

**Testing Cases and Edge cases**
* *Test Case 1:* User connects to the chat using a third-party Jabber client. Expect successful authentication and message sending.
* *Test Case 2:* Server A user sends a message to Server B user. Expect successful delivery and display on Server B.
* *Edge Case 1:* Network interruption between Server A and Server B during federation load test. System must handle dropped messages gracefully per the chosen Jabber library's capabilities.

**Definition of Done**
* Code peer-reviewed and merged.
* Load test completed and documented.
* Unit and integration tests passed.
* Multi-server architecture configured in docker compose.
* Verified working via `docker compose up` in the root repository.