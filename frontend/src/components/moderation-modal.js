/**
 * T052 — Moderation modal: ban/kick/promote/delete actions for room admins/owners.
 * Triggered from the member list in main-chat. Injects its own modal DOM.
 */

const API = '';

async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `${res.status}`);
  return data;
}

export const moderationApi = {
  banMember:   (roomId, userId) => apiFetch(`/rooms/${roomId}/ban/${userId}`, { method: 'POST' }),
  unbanMember: (roomId, userId) => apiFetch(`/rooms/${roomId}/ban/${userId}`, { method: 'DELETE' }),
  listBans:    (roomId)         => apiFetch(`/rooms/${roomId}/bans`),
  promote:     (roomId, userId) => apiFetch(`/rooms/${roomId}/admins/${userId}`, { method: 'POST' }),
  demote:      (roomId, userId) => apiFetch(`/rooms/${roomId}/admins/${userId}`, { method: 'DELETE' }),
  deleteRoom:  (roomId)         => apiFetch(`/rooms/${roomId}`, { method: 'DELETE' }),
  kickMember:  (roomId, userId) => apiFetch(`/rooms/${roomId}/members/${userId}`, { method: 'DELETE' }),
};

// ── Shared modal DOM ──────────────────────────────────────────────────────────

let _overlay = null;

function _getOrCreateOverlay() {
  if (_overlay) return _overlay;

  _overlay = document.createElement('div');
  _overlay.id = 'mod-overlay';
  _overlay.style.cssText = [
    'position:fixed;inset:0;background:rgba(0,0,0,0.45);',
    'display:none;align-items:center;justify-content:center;z-index:9999;',
  ].join('');

  const win = document.createElement('div');
  win.id = 'mod-win';
  win.style.cssText = [
    'background:#DFDFDF;width:360px;display:flex;flex-direction:column;',
    'box-shadow:inset 2px 2px 0 #FFF,inset -2px -2px 0 #808080;',
  ].join('');
  win.innerHTML = `
    <div id="mod-titlebar" style="background:#000080;color:#fff;height:24px;display:flex;align-items:center;justify-content:space-between;padding:0 6px;user-select:none;">
      <span id="mod-title" style="font-size:13px;font-weight:700;">Moderation</span>
      <button id="mod-close" style="width:18px;height:16px;background:#DFDFDF;border:none;cursor:pointer;font-weight:bold;font-size:11px;box-shadow:inset 2px 2px 0 #FFF,inset -2px -2px 0 #808080;">X</button>
    </div>
    <div id="mod-body" style="padding:14px 16px;font-size:13px;font-family:'JetBrains Mono',monospace;"></div>
    <div id="mod-status" style="padding:0 16px 8px;font-size:11px;color:#800000;min-height:16px;font-family:monospace;"></div>
    <div id="mod-actions" style="display:flex;gap:6px;justify-content:flex-end;padding:8px 12px 10px;border-top:1px solid #808080;"></div>
  `;

  _overlay.appendChild(win);
  document.body.appendChild(_overlay);

  _overlay.addEventListener('click', e => {
    if (e.target === _overlay) _close();
  });
  win.querySelector('#mod-close').addEventListener('click', _close);

  return _overlay;
}

function _close() {
  if (_overlay) _overlay.style.display = 'none';
}

function _show(title, bodyHtml, actions) {
  const overlay = _getOrCreateOverlay();
  overlay.querySelector('#mod-title').textContent = title;
  overlay.querySelector('#mod-body').innerHTML = bodyHtml;
  overlay.querySelector('#mod-status').textContent = '';

  const actionsEl = overlay.querySelector('#mod-actions');
  actionsEl.innerHTML = '';

  const cancelBtn = _btn('Cancel', () => _close());
  actionsEl.appendChild(cancelBtn);

  actions.forEach(({ label, danger, onClick }) => {
    const b = _btn(label, onClick, danger);
    actionsEl.appendChild(b);
  });

  overlay.style.display = 'flex';
}

function _btn(label, onClick, danger = false) {
  const b = document.createElement('button');
  b.textContent = label;
  b.style.cssText = [
    'padding:3px 12px;background:#DFDFDF;border:none;cursor:pointer;font-size:12px;font-weight:600;',
    'box-shadow:inset 2px 2px 0 #FFF,inset -2px -2px 0 #808080;',
    danger ? 'color:#800000;' : '',
  ].join('');
  b.addEventListener('click', onClick);
  return b;
}

function _setStatus(msg, isError = true) {
  const el = _overlay?.querySelector('#mod-status');
  if (el) {
    el.textContent = msg;
    el.style.color = isError ? '#800000' : '#005000';
  }
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Open the moderation menu for a given room member.
 *
 * @param {object} opts
 * @param {number} opts.roomId       - current room ID
 * @param {number} opts.targetUserId - user to moderate
 * @param {string} opts.targetUsername
 * @param {string} opts.targetRole   - "member" | "admin"
 * @param {number} opts.currentUserId
 * @param {string} opts.currentRole  - "member" | "admin"  (of current user)
 * @param {boolean} opts.isOwner     - true if current user is room owner
 * @param {function} opts.onDone     - callback() after any successful action
 */
export function openMemberActions(opts) {
  const { roomId, targetUserId, targetUsername, targetRole, currentUserId, isOwner, onDone } = opts;

  if (targetUserId === currentUserId) return; // no self-moderation

  const actions = [];

  // Ban from room (admin or owner)
  actions.push({
    label: 'Ban from Room',
    danger: true,
    onClick: async () => {
      try {
        await moderationApi.banMember(roomId, targetUserId);
        _close();
        onDone?.('ban', targetUserId);
      } catch (e) {
        _setStatus(e.message);
      }
    },
  });

  // Promote / demote (owner only)
  if (isOwner) {
    if (targetRole === 'member') {
      actions.push({
        label: 'Promote to Admin',
        onClick: async () => {
          try {
            await moderationApi.promote(roomId, targetUserId);
            _close();
            onDone?.('promote', targetUserId);
          } catch (e) {
            _setStatus(e.message);
          }
        },
      });
    } else {
      actions.push({
        label: 'Demote to Member',
        onClick: async () => {
          try {
            await moderationApi.demote(roomId, targetUserId);
            _close();
            onDone?.('demote', targetUserId);
          } catch (e) {
            _setStatus(e.message);
          }
        },
      });
    }
  }

  _show(
    `Moderate: ${targetUsername}`,
    `<p>Target: <strong>${targetUsername}</strong> (${targetRole})</p><p style="color:#808080;font-size:11px;margin-top:6px;">Choose an action below.</p>`,
    actions,
  );
}

/**
 * Open the room delete confirmation dialog (owner only).
 *
 * @param {number} roomId
 * @param {string} roomName
 * @param {function} onDeleted - callback() after successful deletion
 */
export function openDeleteRoom(roomId, roomName, onDeleted) {
  _show(
    'Delete Room',
    `<p style="color:#800000;font-weight:700;">⚠ This cannot be undone!</p>
     <p style="margin-top:8px;">Delete <strong>${roomName}</strong>?<br/>All messages and files will be permanently removed.</p>`,
    [
      {
        label: 'Delete Room',
        danger: true,
        onClick: async () => {
          try {
            await moderationApi.deleteRoom(roomId);
            _close();
            onDeleted?.();
          } catch (e) {
            _setStatus(e.message);
          }
        },
      },
    ],
  );
}

/**
 * Open the ban list panel for a room.
 *
 * @param {number} roomId
 * @param {string} roomName
 * @param {function} onUnban - callback(userId) after unban
 */
export async function openBanList(roomId, roomName, onUnban) {
  let bans;
  try {
    bans = await moderationApi.listBans(roomId);
  } catch (e) {
    return;
  }

  const rows = bans.length === 0
    ? '<p style="color:#808080;">No users are banned from this room.</p>'
    : bans.map(b => `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
          <span>${b.username}</span>
          <button data-uid="${b.banned_user_id}" class="unban-btn" style="font-size:11px;padding:2px 8px;background:#DFDFDF;border:none;cursor:pointer;box-shadow:inset 2px 2px 0 #FFF,inset -2px -2px 0 #808080;">Unban</button>
        </div>`).join('');

  _show(`Room Bans — ${roomName}`, rows, []);

  _overlay.querySelectorAll('.unban-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const uid = Number(btn.dataset.uid);
      try {
        await moderationApi.unbanMember(roomId, uid);
        btn.closest('div').remove();
        onUnban?.(uid);
      } catch (e) {
        _setStatus(e.message);
      }
    });
  });
}
