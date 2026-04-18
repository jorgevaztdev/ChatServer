/**
 * T045 — Room list component.
 * Renders public rooms from GET /rooms; supports search via GET /rooms/search.
 * Call roomList.load() on init; roomList.search(q) for search.
 */

const _container = () => document.getElementById('room-list-container');
const _status = () => document.getElementById('status-bar');
const _countSeg = () => document.getElementById('count-seg');

function _roomCard(room) {
  const item = document.createElement('div');
  item.className = 'room-item';
  item.innerHTML = `
    <div class="room-icon">${room.name[0].toUpperCase()}</div>
    <div class="room-info">
      <div class="room-name">${_esc(room.name)}</div>
      <div class="room-desc">${_esc(room.description || 'No description')}</div>
    </div>
    <div class="room-meta">
      <span class="room-count">${room.member_count ?? '?'} member${room.member_count === 1 ? '' : 's'}</span>
      <button class="btn btn-join" data-id="${room.id}">Join</button>
    </div>
  `;
  item.querySelector('.btn-join').addEventListener('click', () => _join(room.id, room.name));
  return item;
}

function _esc(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function _join(roomId, roomName) {
  const res = await fetch(`/rooms/${roomId}/join`, { method: 'POST' });
  const data = await res.json().catch(() => ({}));
  if (res.ok) {
    _status().textContent = `Joined ${roomName}!`;
    // brief highlight then navigate to chat
    setTimeout(() => { location.href = `main-chat.html?room=${roomId}`; }, 600);
  } else {
    _status().textContent = data.detail || 'Failed to join room.';
  }
}

function _render(rooms) {
  const container = _container();
  container.innerHTML = '';
  if (!rooms.length) {
    container.innerHTML = '<div class="empty-state">No rooms found.</div>';
    _countSeg().textContent = '0 rooms';
    return;
  }
  rooms.forEach(r => container.appendChild(_roomCard(r)));
  _countSeg().textContent = `${rooms.length} room${rooms.length === 1 ? '' : 's'}`;
}

async function load() {
  _status().textContent = 'Loading rooms...';
  const res = await fetch('/rooms').catch(() => null);
  if (!res || !res.ok) {
    _status().textContent = 'Failed to load rooms.';
    return;
  }
  const rooms = await res.json();
  _render(rooms);
  _status().textContent = `${rooms.length} public room${rooms.length === 1 ? '' : 's'} available`;
}

async function search(q) {
  _status().textContent = q ? `Searching for "${q}"...` : 'Loading rooms...';
  const url = q ? `/rooms/search?q=${encodeURIComponent(q)}` : '/rooms';
  const res = await fetch(url).catch(() => null);
  if (!res || !res.ok) {
    _status().textContent = 'Search failed.';
    return;
  }
  const rooms = await res.json();
  _render(rooms);
  _status().textContent = q
    ? `${rooms.length} result${rooms.length === 1 ? '' : 's'} for "${q}"`
    : `${rooms.length} public room${rooms.length === 1 ? '' : 's'} available`;
}

export const roomList = { load, search };
