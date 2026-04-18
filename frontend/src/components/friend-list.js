/**
 * T036 — Friend list component with presence dots.
 * Handles: friend list, pending requests, add-friend form.
 */

import { presenceManager, createPresenceDot } from './presence-dot.js';

const API = '';

// ── API helpers ───────────────────────────────────────────────────────────────

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

export const friendsApi = {
  list:    ()            => apiFetch('/friends'),
  requests:()            => apiFetch('/friends/requests'),
  request: (username, message) =>
    apiFetch('/friends/request', { method: 'POST', body: JSON.stringify({ username, message }) }),
  accept:  (requesterId) => apiFetch(`/friends/accept/${requesterId}`, { method: 'POST' }),
  decline: (requesterId) => apiFetch(`/friends/decline/${requesterId}`, { method: 'DELETE' }),
  remove:  (userId)      => apiFetch(`/friends/${userId}`, { method: 'DELETE' }),
};

export const bansApi = {
  list:  ()       => apiFetch('/bans'),
  ban:   (userId) => apiFetch(`/bans/user/${userId}`, { method: 'POST' }),
  unban: (userId) => apiFetch(`/bans/user/${userId}`, { method: 'DELETE' }),
  check: (userId) => apiFetch(`/bans/check/${userId}`),
};

// ── FriendList component ──────────────────────────────────────────────────────

export class FriendList {
  /**
   * @param {HTMLElement} listEl     - container for friend rows
   * @param {HTMLElement} countEl    - element showing total friend count
   * @param {HTMLElement} onlineEl   - element showing online friend count
   */
  constructor(listEl, countEl, onlineEl) {
    this._list    = listEl;
    this._count   = countEl;
    this._online  = onlineEl;
    this._dots    = [];   // { destroy } references for cleanup
    this._friends = [];
    this._selected = null;
  }

  async refresh() {
    this._friends = await friendsApi.list();
    this._render();
  }

  _render() {
    // Cleanup previous presence subscriptions
    this._dots.forEach(d => d.destroy());
    this._dots = [];
    this._list.innerHTML = '';

    this._friends.forEach(f => {
      const row = document.createElement('div');
      row.className = 'friend-row';
      row.dataset.userId = f.user_id;

      const left = document.createElement('div');
      left.className = 'friend-row__left';

      const avatar = document.createElement('div');
      avatar.className = 'friend-row__avatar';
      avatar.textContent = f.username[0].toUpperCase();

      const name = document.createElement('span');
      name.className = 'friend-row__name';
      name.textContent = f.username;

      const dotSlot = document.createElement('span');
      const { element: dot, destroy } = createPresenceDot(f.user_id, presenceManager);
      dotSlot.appendChild(dot);
      this._dots.push({ destroy });

      left.appendChild(avatar);
      left.appendChild(dotSlot);
      left.appendChild(name);

      const statusLabel = document.createElement('span');
      statusLabel.className = 'friend-row__status';
      statusLabel.textContent = f.presence;
      presenceManager.subscribe(f.user_id, s => {
        statusLabel.textContent = s;
        this._updateCounts();
      });

      row.appendChild(left);
      row.appendChild(statusLabel);

      row.addEventListener('click', () => this._select(row, f));
      this._list.appendChild(row);
    });

    this._updateCounts();
  }

  _select(row, friend) {
    this._list.querySelectorAll('.friend-row--selected')
      .forEach(r => r.classList.remove('friend-row--selected'));
    row.classList.add('friend-row--selected');
    this._selected = friend;
    this._list.dispatchEvent(new CustomEvent('friend:select', { detail: friend, bubbles: true }));
  }

  _updateCounts() {
    if (this._count) this._count.textContent = `Total: ${this._friends.length} Friends`;
    if (this._online) {
      const onlineCount = this._friends.filter(
        f => presenceManager.getStatus(f.user_id) === 'online'
      ).length;
      this._online.textContent = `Online: ${onlineCount}`;
    }
  }

  getSelected() { return this._selected; }

  destroy() {
    this._dots.forEach(d => d.destroy());
    this._dots = [];
  }
}

// ── PendingRequestsList component ─────────────────────────────────────────────

export class PendingRequestsList {
  /**
   * @param {HTMLElement} incomingEl  - container for incoming request rows
   * @param {function}    onAccept    - callback(requesterId)
   * @param {function}    onDecline   - callback(requesterId)
   */
  constructor(incomingEl, onAccept, onDecline) {
    this._el       = incomingEl;
    this._onAccept  = onAccept;
    this._onDecline = onDecline;
  }

  async refresh() {
    const requests = await friendsApi.requests();
    this._render(requests);
  }

  _render(requests) {
    this._el.innerHTML = '';

    if (requests.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'requests__empty';
      empty.textContent = 'No pending requests.';
      this._el.appendChild(empty);
      return;
    }

    requests.forEach(r => {
      const item = document.createElement('div');
      item.className = 'request-item';

      const nameEl = document.createElement('div');
      nameEl.className = 'request-item__name';
      nameEl.textContent = r.username;

      const actions = document.createElement('div');
      actions.className = 'request-item__actions';

      const acceptBtn = document.createElement('button');
      acceptBtn.className = 'btn-os btn-os--sm';
      acceptBtn.textContent = 'Accept';
      acceptBtn.addEventListener('click', () => this._onAccept(r.requester_id));

      const declineBtn = document.createElement('button');
      declineBtn.className = 'btn-os btn-os--sm';
      declineBtn.textContent = 'Decline';
      declineBtn.addEventListener('click', () => this._onDecline(r.requester_id));

      actions.appendChild(acceptBtn);
      actions.appendChild(declineBtn);
      item.appendChild(nameEl);
      item.appendChild(actions);
      this._el.appendChild(item);
    });
  }
}

// ── AddFriendForm component ───────────────────────────────────────────────────

export class AddFriendForm {
  /**
   * @param {HTMLFormElement} formEl  - the add-friend form element
   * @param {HTMLElement}     statusEl - status/error message element
   * @param {function}        onSuccess - callback() called after successful request
   */
  constructor(formEl, statusEl, onSuccess) {
    this._form     = formEl;
    this._status   = statusEl;
    this._onSuccess = onSuccess;

    formEl.addEventListener('submit', e => {
      e.preventDefault();
      this._submit();
    });
  }

  async _submit() {
    const username = this._form.elements['username'].value.trim();
    const message  = this._form.elements['message']?.value.trim() || null;

    if (!username) return;

    this._setStatus('');
    try {
      await friendsApi.request(username, message);
      this._form.reset();
      this._setStatus('Request sent!', false);
      this._onSuccess();
    } catch (err) {
      this._setStatus(err.message, true);
    }
  }

  _setStatus(msg, isError = false) {
    if (!this._status) return;
    this._status.textContent = msg;
    this._status.className = isError ? 'form-status form-status--error' : 'form-status';
  }
}
