/**
 * Full "Manage Room" modal — matches wireframe with tabs:
 * Members | Admins | Banned | Invitations | Settings
 *
 * Also exports quick-action helpers used from the member list.
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
  banMember:    (roomId, userId) => apiFetch(`/rooms/${roomId}/ban/${userId}`, { method: 'POST' }),
  unbanMember:  (roomId, userId) => apiFetch(`/rooms/${roomId}/ban/${userId}`, { method: 'DELETE' }),
  listBans:     (roomId)         => apiFetch(`/rooms/${roomId}/bans`),
  promote:      (roomId, userId) => apiFetch(`/rooms/${roomId}/admins/${userId}`, { method: 'POST' }),
  demote:       (roomId, userId) => apiFetch(`/rooms/${roomId}/admins/${userId}`, { method: 'DELETE' }),
  deleteRoom:   (roomId)         => apiFetch(`/rooms/${roomId}`, { method: 'DELETE' }),
  updateRoom:   (roomId, body)   => apiFetch(`/rooms/${roomId}`, { method: 'PUT', body: JSON.stringify(body) }),
  invite:       (roomId, username) => apiFetch(`/rooms/${roomId}/invite`, { method: 'POST', body: JSON.stringify({ username }) }),
  listMembers:  (roomId)         => apiFetch(`/rooms/${roomId}/members`),
  // "Remove from room" = ban per spec §2.4.8
  kickMember:   (roomId, userId) => apiFetch(`/rooms/${roomId}/ban/${userId}`, { method: 'POST' }),
};

// ── Overlay singleton ─────────────────────────────────────────────────────────

let _modal = null;

function _ensureModal() {
  if (_modal) return _modal;

  const overlay = document.createElement('div');
  overlay.id = 'mgmt-overlay';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);display:none;align-items:center;justify-content:center;z-index:9999;';

  overlay.innerHTML = `
    <div id="mgmt-win" style="width:600px;max-height:90vh;background:#DFDFDF;display:flex;flex-direction:column;box-shadow:inset 2px 2px 0 #FFF,inset -2px -2px 0 #808080;">
      <div id="mgmt-titlebar" style="background:#000080;color:#fff;height:26px;display:flex;align-items:center;justify-content:space-between;padding:0 8px;user-select:none;flex-shrink:0;">
        <span id="mgmt-title" style="font-size:13px;font-weight:700;font-family:'JetBrains Mono',monospace;">Manage Room</span>
        <button id="mgmt-close" style="width:18px;height:16px;background:#DFDFDF;border:none;cursor:pointer;font-weight:bold;font-size:11px;box-shadow:inset 2px 2px 0 #FFF,inset -2px -2px 0 #808080;">X</button>
      </div>

      <div id="mgmt-tabs" style="display:flex;border-bottom:2px solid #808080;flex-shrink:0;background:#DFDFDF;">
        ${['Members','Admins','Banned','Invitations','Settings'].map((t,i) =>
          `<button class="mgmt-tab" data-tab="${t.toLowerCase()}" style="padding:4px 14px;background:${i===0?'#fff':'#DFDFDF'};border:none;border-right:1px solid #808080;cursor:pointer;font-size:12px;font-family:'JetBrains Mono',monospace;${i===0?'box-shadow:inset 2px 2px 0 #FFF;':''}font-weight:${i===0?'700':'400'};">${t}</button>`
        ).join('')}
      </div>

      <div id="mgmt-body" style="flex:1;overflow-y:auto;padding:12px;font-size:12px;font-family:'JetBrains Mono',monospace;min-height:200px;"></div>

      <div id="mgmt-status" style="padding:4px 12px;font-size:11px;color:#800000;font-family:monospace;min-height:18px;flex-shrink:0;"></div>
    </div>
  `;

  document.body.appendChild(overlay);
  _modal = overlay;

  overlay.addEventListener('click', e => { if (e.target === overlay) _closeModal(); });
  overlay.querySelector('#mgmt-close').addEventListener('click', _closeModal);

  overlay.querySelectorAll('.mgmt-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      overlay.querySelectorAll('.mgmt-tab').forEach(b => {
        b.style.background = '#DFDFDF';
        b.style.fontWeight = '400';
        b.style.boxShadow = '';
      });
      btn.style.background = '#fff';
      btn.style.fontWeight = '700';
      btn.style.boxShadow = 'inset 2px 2px 0 #FFF';
      _renderTab(btn.dataset.tab);
    });
  });

  return overlay;
}

// ── State ─────────────────────────────────────────────────────────────────────

let _state = { roomId: null, roomName: '', ownerId: null, currentUserId: null, isOwner: false, onDone: null };

function _setStatus(msg, isErr = true) {
  const el = _modal?.querySelector('#mgmt-status');
  if (el) { el.textContent = msg; el.style.color = isErr ? '#800000' : '#005000'; }
}

function _btn(label, onClick, danger = false, small = true) {
  const b = document.createElement('button');
  b.textContent = label;
  b.style.cssText = `padding:${small?'1px 8px':'3px 14px'};background:#DFDFDF;border:none;cursor:pointer;font-size:11px;` +
    `box-shadow:inset 2px 2px 0 #FFF,inset -2px -2px 0 #808080;${danger?'color:#800000;':''}margin-left:4px;font-family:'JetBrains Mono',monospace;`;
  b.addEventListener('click', onClick);
  return b;
}

function _table(cols, rows) {
  const t = document.createElement('table');
  t.style.cssText = 'width:100%;border-collapse:collapse;font-size:11px;';
  const thead = t.createTHead();
  const hrow = thead.insertRow();
  cols.forEach(c => {
    const th = document.createElement('th');
    th.textContent = c;
    th.style.cssText = 'text-align:left;padding:3px 6px;border-bottom:2px solid #808080;background:#DFDFDF;';
    hrow.appendChild(th);
  });
  const tbody = t.createTBody();
  rows.forEach(r => {
    const tr = tbody.insertRow();
    tr.style.borderBottom = '1px solid #e0e0e0';
    r.forEach((cell, i) => {
      const td = tr.insertCell();
      td.style.padding = '3px 6px';
      if (typeof cell === 'string' || typeof cell === 'number') {
        td.textContent = cell;
      } else {
        td.appendChild(cell);
      }
    });
  });
  return t;
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

async function _renderTab(tab) {
  const body = _modal.querySelector('#mgmt-body');
  body.innerHTML = '<div style="color:#808080;">Loading…</div>';
  _setStatus('');
  try {
    switch (tab) {
      case 'members':     await _tabMembers(body); break;
      case 'admins':      await _tabAdmins(body);  break;
      case 'banned':      await _tabBanned(body);  break;
      case 'invitations': await _tabInvite(body);  break;
      case 'settings':    await _tabSettings(body); break;
    }
  } catch(e) {
    body.innerHTML = `<div style="color:#800000;">Error: ${e.message}</div>`;
  }
}

async function _tabMembers(body) {
  const members = await moderationApi.listMembers(_state.roomId);
  body.innerHTML = '';

  const search = document.createElement('input');
  search.placeholder = 'Search member…';
  search.style.cssText = 'width:100%;height:24px;padding:0 6px;border:none;box-shadow:inset 2px 2px 0 #808080,inset -2px -2px 0 #fff;margin-bottom:8px;font-size:11px;font-family:inherit;background:#fff;outline:none;';
  body.appendChild(search);

  const wrap = document.createElement('div');
  body.appendChild(wrap);

  const render = (filter = '') => {
    wrap.innerHTML = '';
    const filtered = members.filter(m => m.username.toLowerCase().includes(filter.toLowerCase()));
    if (!filtered.length) { wrap.innerHTML = '<div style="color:#808080;">No members found.</div>'; return; }

    const rows = filtered.map(m => {
      const isOwner = m.user_id === _state.ownerId;
      const isSelf = m.user_id === _state.currentUserId;
      const roleLabel = isOwner ? 'Owner' : m.role === 'admin' ? 'Admin' : 'Member';
      const statusDot = `<span style="width:7px;height:7px;border-radius:50%;background:${m.online?'#008000':'#808080'};display:inline-block;margin-right:4px;"></span>`;

      const actionsCell = document.createElement('div');
      actionsCell.style.display = 'flex';
      actionsCell.style.flexWrap = 'wrap';
      actionsCell.style.gap = '2px';

      if (!isSelf && (_state.isOwner || !isOwner)) {
        // Make/Remove admin (owner only)
        if (_state.isOwner && !isOwner) {
          if (m.role === 'admin') {
            actionsCell.appendChild(_btn('Remove admin', async () => {
              try { await moderationApi.demote(_state.roomId, m.user_id); _state.onDone?.(); await _tabMembers(body); }
              catch(e) { _setStatus(e.message); }
            }));
          } else {
            actionsCell.appendChild(_btn('Make admin', async () => {
              try { await moderationApi.promote(_state.roomId, m.user_id); _state.onDone?.(); await _tabMembers(body); }
              catch(e) { _setStatus(e.message); }
            }));
          }
        }
        // Ban (admin or owner, not on owner)
        if (!isOwner) {
          actionsCell.appendChild(_btn('Ban', async () => {
            try { await moderationApi.banMember(_state.roomId, m.user_id); _state.onDone?.(); await _tabMembers(body); }
            catch(e) { _setStatus(e.message); }
          }, true));
          actionsCell.appendChild(_btn('Remove', async () => {
            try { await moderationApi.kickMember(_state.roomId, m.user_id); _state.onDone?.(); await _tabMembers(body); }
            catch(e) { _setStatus(e.message); }
          }, true));
        }
      }

      const nameCell = document.createElement('span');
      nameCell.innerHTML = statusDot + m.username;
      return [nameCell, m.online ? 'online' : 'offline', roleLabel, actionsCell];
    });

    wrap.appendChild(_table(['Username','Status','Role','Actions'], rows));
  };

  search.addEventListener('input', () => render(search.value));
  render();
}

async function _tabAdmins(body) {
  const members = await moderationApi.listMembers(_state.roomId);
  const admins = members.filter(m => m.role === 'admin' || m.user_id === _state.ownerId);
  body.innerHTML = '';

  if (!admins.length) { body.innerHTML = '<div style="color:#808080;">No admins.</div>'; return; }

  const rows = admins.map(m => {
    const isOwner = m.user_id === _state.ownerId;
    const actCell = document.createElement('span');
    if (isOwner) {
      actCell.textContent = 'Owner (cannot remove)';
      actCell.style.color = '#808080';
    } else if (_state.isOwner) {
      actCell.appendChild(_btn('Remove admin', async () => {
        try { await moderationApi.demote(_state.roomId, m.user_id); _state.onDone?.(); await _tabAdmins(body); }
        catch(e) { _setStatus(e.message); }
      }));
    }
    return [m.username, isOwner ? 'Owner' : 'Admin', actCell];
  });

  body.appendChild(_table(['Username','Role','Action'], rows));
}

async function _tabBanned(body) {
  const bans = await moderationApi.listBans(_state.roomId);
  body.innerHTML = '';

  if (!bans.length) { body.innerHTML = '<div style="color:#808080;">No users are banned.</div>'; return; }

  const rows = bans.map(b => {
    const actCell = document.createElement('span');
    actCell.appendChild(_btn('Unban', async () => {
      try { await moderationApi.unbanMember(_state.roomId, b.banned_user_id); _state.onDone?.(); await _tabBanned(body); }
      catch(e) { _setStatus(e.message); }
    }));
    return [b.username, `user #${b.banned_by_id}`, new Date(b.created_at).toLocaleString(), actCell];
  });

  body.appendChild(_table(['Username','Banned by','Date','Action'], rows));
}

async function _tabInvite(body) {
  body.innerHTML = '';
  const row = document.createElement('div');
  row.style.cssText = 'display:flex;gap:6px;align-items:center;margin-bottom:10px;';

  const inp = document.createElement('input');
  inp.placeholder = 'Username to invite…';
  inp.style.cssText = 'flex:1;height:24px;padding:0 6px;border:none;box-shadow:inset 2px 2px 0 #808080,inset -2px -2px 0 #fff;font-size:11px;font-family:inherit;background:#fff;outline:none;';

  const sendBtn = _btn('Send invite', async () => {
    const uname = inp.value.trim();
    if (!uname) return;
    try {
      await moderationApi.invite(_state.roomId, uname);
      inp.value = '';
      _setStatus('Invited ' + uname, false);
    } catch(e) { _setStatus(e.message); }
  }, false, false);

  row.appendChild(inp);
  row.appendChild(sendBtn);
  body.appendChild(row);
  body.innerHTML += '<div style="color:#808080;font-size:11px;">Invite users to this private room by username.</div>';
  body.insertBefore(row, body.firstChild);

  inp.addEventListener('keydown', e => {
    if (e.key === 'Enter') sendBtn.click();
  });
}

async function _tabSettings(body) {
  const res = await fetch(`/rooms/${_state.roomId}`, { credentials: 'include' });
  const room = await res.json();
  body.innerHTML = '';

  const fld = (label, id, val, type = 'text') => {
    const wrap = document.createElement('div');
    wrap.style.marginBottom = '10px';
    wrap.innerHTML = `<div style="font-weight:700;margin-bottom:3px;">${label}</div>
      <input id="${id}" type="${type}" value="${(val||'').replace(/"/g,'&quot;')}"
        style="width:100%;height:26px;padding:0 6px;border:none;box-shadow:inset 2px 2px 0 #808080,inset -2px -2px 0 #fff;font-size:12px;font-family:'JetBrains Mono',monospace;background:#fff;outline:none;"/>`;
    return wrap;
  };

  body.appendChild(fld('Room Name', 'st-name', room.name));
  body.appendChild(fld('Description', 'st-desc', room.description || ''));

  const privRow = document.createElement('div');
  privRow.style.marginBottom = '12px';
  privRow.innerHTML = `<label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
    <input type="checkbox" id="st-private" style="width:14px;height:14px;" ${room.is_private?'checked':''}/> Private (invite-only)
  </label>`;
  body.appendChild(privRow);

  const saveBtn = _btn('Save changes', async () => {
    const name = body.querySelector('#st-name').value.trim();
    const description = body.querySelector('#st-desc').value.trim() || null;
    const is_private = body.querySelector('#st-private').checked;
    if (!name) { _setStatus('Name required.'); return; }
    try {
      await moderationApi.updateRoom(_state.roomId, { name, description, is_private });
      _state.onDone?.();
      _setStatus('Saved.', false);
    } catch(e) { _setStatus(e.message); }
  }, false, false);
  saveBtn.style.marginRight = '8px';

  const dangerDiv = document.createElement('div');
  dangerDiv.style.cssText = 'margin-top:24px;border-top:2px solid #808080;padding-top:10px;';
  const delBtn = _btn('Delete Room', async () => {
    if (!confirm(`Delete "${room.name}" permanently? All messages and files will be lost.`)) return;
    try {
      await moderationApi.deleteRoom(_state.roomId);
      _closeModal();
      _state.onDone?.('deleted');
    } catch(e) { _setStatus(e.message); }
  }, true, false);

  const footer = document.createElement('div');
  footer.appendChild(saveBtn);
  body.appendChild(footer);
  dangerDiv.innerHTML = '<div style="color:#800000;font-weight:700;margin-bottom:6px;">⚠ Danger Zone</div>';
  dangerDiv.appendChild(delBtn);
  body.appendChild(dangerDiv);
}

// ── Public API ────────────────────────────────────────────────────────────────

function _closeModal() {
  if (_modal) _modal.style.display = 'none';
}

/**
 * Open the full Manage Room modal.
 * @param {object} opts
 * @param {number}   opts.roomId
 * @param {string}   opts.roomName
 * @param {number}   opts.ownerId
 * @param {number}   opts.currentUserId
 * @param {boolean}  opts.isOwner
 * @param {function} opts.onDone - called after any successful action
 */
export function openRoomManagement({ roomId, roomName, ownerId, currentUserId, isOwner, onDone }) {
  _state = { roomId, roomName, ownerId, currentUserId, isOwner, onDone };
  const overlay = _ensureModal();
  overlay.querySelector('#mgmt-title').textContent = `Manage Room: #${roomName}`;
  overlay.style.display = 'flex';

  // Reset to Members tab
  overlay.querySelectorAll('.mgmt-tab').forEach((b, i) => {
    b.style.background = i === 0 ? '#fff' : '#DFDFDF';
    b.style.fontWeight = i === 0 ? '700' : '400';
    b.style.boxShadow = i === 0 ? 'inset 2px 2px 0 #FFF' : '';
  });
  _renderTab('members');
}

/** Quick-action: just ban a member (no full modal). */
export async function quickBan(roomId, userId, onDone) {
  try { await moderationApi.banMember(roomId, userId); onDone?.(); }
  catch(e) { alert(e.message); }
}

/** Quick-action: show delete room confirm. */
export function quickDeleteRoom(roomId, roomName, onDeleted) {
  if (!confirm(`Delete "${roomName}" permanently? All messages and files will be lost.`)) return;
  moderationApi.deleteRoom(roomId)
    .then(() => onDeleted?.())
    .catch(e => alert(e.message));
}
