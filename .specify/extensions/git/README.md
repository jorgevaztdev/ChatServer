# Git Branching Workflow Extension

Git repository initialization, feature branch creation, numbering (sequential/timestamp), validation, remote detection, and auto-commit for Spec Kit.

## Overview

This extension provides Git operations as an optional, self-contained module. It manages:

- **Repository initialization** with configurable commit messages
- **Feature branch creation** with sequential (`001-feature-name`) or timestamp (`20260319-143022-feature-name`) numbering
- **Branch validation** to ensure branches follow naming conventions
- **Git remote detection** for GitHub integration (e.g., issue creation)
- **Auto-commit** after core commands (configurable per-command with custom messages)

## Commands

| Command | Description |
|---------|-------------|
| `speckit.git.initialize` | Initialize a Git repository with a configurable commit message |
| `speckit.git.feature` | Create a feature branch with sequential or timestamp numbering |
| `speckit.git.validate` | Validate current branch follows feature branch naming conventions |
| `speckit.git.remote` | Detect Git remote URL for GitHub integration |
| `speckit.git.commit` | Auto-commit changes (configurable per-command enable/disable and messages) |

## Hooks

| Event | Command | Optional | Description |
|-------|---------|----------|-------------|
| `before_constitution` | `speckit.git.initialize` | No | Init git repo before constitution |
| `before_specify` | `speckit.git.feature` | No | Create feature branch before specification |
| `before_clarify` | `speckit.git.commit` | Yes | Commit outstanding changes before clarification |
| `before_plan` | `speckit.git.commit` | Yes | Commit outstanding changes before planning |
| `before_tasks` | `speckit.git.commit` | Yes | Commit outstanding changes before task generation |
| `before_implement` | `speckit.git.commit` | Yes | Commit outstanding changes before implementation |
| `before_checklist` | `speckit.git.commit` | Yes | Commit outstanding changes before checklist |
| `before_analyze` | `speckit.git.commit` | Yes | Commit outstanding changes before analysis |
| `before_taskstoissues` | `speckit.git.commit` | Yes | Commit outstanding changes before issue sync |
| `after_constitution` | `speckit.git.commit` | Yes | Auto-commit after constitution update |
| `after_specify` | `speckit.git.commit` | Yes | Auto-commit after specification |
| `after_clarify` | `speckit.git.commit` | Yes | Auto-commit after clarification |
| `after_plan` | `speckit.git.commit` | Yes | Auto-commit after planning |
| `after_tasks` | `speckit.git.commit` | Yes | Auto-commit after task generation |
| `after_implement` | `speckit.git.commit` | Yes | Auto-commit after implementation |
| `after_checklist` | `speckit.git.commit` | Yes | Auto-commit after checklist |
| `after_analyze` | `speckit.git.commit` | Yes | Auto-commit after analysis |
| `after_taskstoissues` | `speckit.git.commit` | Yes | Auto-commit after issue sync |

## Configuration

Configuration is stored in `.specify/extensions/git/git-config.yml`:

```yaml
# Branch numbering strategy: "sequential" or "timestamp"
branch_numbering: sequential

# Custom commit message for git init
init_commit_message: "[Spec Kit] Initial commit"

# Auto-commit per command (all disabled by default)
# Example: enable auto-commit after specify
auto_commit:
  default: false
  after_specify:
    enabled: true
    message: "[Spec Kit] Add specification"
```

## Installation

```bash
# Install the bundled git extension (no network required)
specify extension add git
```

## Disabling

```bash
# Disable the git extension (spec creation continues without branching)
specify extension disable git

# Re-enable it
specify extension enable git
```

## Graceful Degradation

When Git is not installed or the directory is not a Git repository:
- Spec directories are still created under `specs/`
- Branch creation is skipped with a warning
- Branch validation is skipped with a warning
- Remote detection returns empty results

## Scripts

The extension bundles cross-platform scripts:

- `scripts/bash/create-new-feature.sh` — Bash implementation
- `scripts/bash/git-common.sh` — Shared Git utilities (Bash)
- `scripts/powershell/create-new-feature.ps1` — PowerShell implementation
- `scripts/powershell/git-common.ps1` — Shared Git utilities (PowerShell)

## Gap Fixes Applied (2026-04-19)

Post-review gap analysis against `2026_04_18_AI_herders_jam_-_requirements_v3.docx` identified and resolved the following:

| Gap | File(s) Changed | Status |
|-----|----------------|--------|
| AFK presence color missing in member sidebar | `backend/src/api/rooms.py`, `frontend/src/pages/main-chat.html` | ✅ Fixed — `presence_status` now returned from `/rooms/{id}/members`; member sidebar and DM list show gold for AFK |
| AFK presence color missing in DM list | `frontend/src/pages/main-chat.html` | ✅ Fixed — `f.presence === 'AFK'` maps to `#FFD700` |
| Jabber C2S/S2S error tracking absent | `backend/src/services/jabber_server.py` | ✅ Fixed — `errors` counter on C2S sessions and S2S links; incremented on handler exceptions |
| Admin dashboard: no auto-refresh for XMPP section | `frontend/src/pages/admin-dashboard.html` | ✅ Fixed — 10s polling when XMPP tab active; clears on tab switch |
| Admin dashboard: no error count or uptime in Jabber view | `frontend/src/pages/admin-dashboard.html` | ✅ Fixed — error column in federation table; uptime (seconds) in C2S terminal |
| Presence test coverage insufficient (no AFK/multi-tab/offline) | `backend/tests/integration/test_presence.py` | ✅ Fixed — 5 new tests: offline-after-disconnect, status string values, unknown user, AFK via stale activity, multi-tab aggregation |
| Jabber federation load test missing | `backend/tests/load_test_federation.py` | ✅ Fixed — new script: 50 clients × 2 servers, concurrent, reports per-server and overall results |

### Round 2 Gap Fixes (2026-04-19)

Second review pass found additional gaps:

| Gap | File(s) Changed | Status |
|-----|----------------|--------|
| No password length/format validation on register | `backend/src/api/auth.py` | ✅ Fixed — `RegisterRequest.password` requires `min_length=8`, email requires RFC pattern, username `1-32` chars alphanumeric |
| No password min_length on change/reset endpoints | `backend/src/api/auth.py` | ✅ Fixed — `ChangePasswordRequest` and `ResetPasswordRequest.new_password` require `min_length=8` |
| Room capacity limit (1000 members) not enforced | `backend/src/api/rooms.py` | ✅ Fixed — `join_room` and `invite_to_room` count members before inserting; 400 at ≥1000 |
| Room search has no pagination (hard limit 50) | `backend/src/api/rooms.py`, `frontend/src/components/room-list.js`, `tests/load_test_ws.py`, `tests/load_test_federation.py` | ✅ Fixed — `/rooms/search` now accepts `offset`/`limit` params; returns `{total, offset, limit, results}`; frontend and load tests updated |

### Round 3 Gap Fixes (2026-04-19)

Third review pass and verification run identified and resolved the following:

| Gap | File(s) Changed | Status |
|-----|----------------|--------|
| `Message.recipient_id` column absent from DB model | `backend/src/models/message.py` | ✅ Fixed — added `recipient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)` |
| `send_dm` did not persist `recipient_id` on Message | `backend/src/services/messaging.py` | ✅ Fixed — `Message(recipient_id=recipient_id, ...)` now set; DM history queries now return correct results |
| All integration test passwords too short after min_length=8 enforcement | `backend/tests/integration/` (all test files), `backend/tests/load_test_ws.py` | ✅ Fixed — passwords updated from `"pass123"` / `"pass"` / `"oldpass"` / `"newpass"` to 8+ char equivalents across all test files |
| `test_search_rooms` expected array; got paginated dict | `backend/tests/integration/test_rooms.py` | ✅ Fixed — test now indexes `res.json()["results"]` |
| `test_afk_status_on_heartbeat_with_stale_activity` used float timestamp; hub stores `datetime` | `backend/tests/integration/test_presence.py` | ✅ Fixed — backdated with `datetime.utcnow() - timedelta(seconds=61)` |

**Final verification: 191/191 integration tests passing (2026-04-19).**
