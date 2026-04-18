/**
 * T031 — Presence indicators.
 * Usage:
 *   import { presenceManager, createPresenceDot } from './presence-dot.js';
 *   presenceManager.connect();
 *   const { element } = createPresenceDot(userId, presenceManager);
 *   someParent.appendChild(element);
 */

const _STATUS_COLOR = { online: '#008000', AFK: '#FFD700', offline: '#808080' };
const _HEARTBEAT_MS = 30_000;
const _RECONNECT_MS = 3_000;

export class PresenceManager {
  constructor() {
    this._ws = null;
    this._tabId = crypto.randomUUID();
    this._statuses = new Map();           // user_id -> status string
    this._listeners = new Map();          // user_id -> Set<callback>
    this._heartbeatTimer = null;
  }

  connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    this._ws = new WebSocket(`${proto}://${location.host}/ws/presence`);

    this._ws.addEventListener('open', () => {
      this._sendHeartbeat();
      this._heartbeatTimer = setInterval(() => this._sendHeartbeat(), _HEARTBEAT_MS);
    });

    this._ws.addEventListener('message', (e) => {
      let msg;
      try { msg = JSON.parse(e.data); } catch { return; }
      if (msg.type === 'presence:update') {
        const { user_id, status } = msg.payload;
        this._statuses.set(user_id, status);
        this._notify(user_id, status);
      }
    });

    this._ws.addEventListener('close', () => {
      clearInterval(this._heartbeatTimer);
      setTimeout(() => this.connect(), _RECONNECT_MS);
    });
  }

  disconnect() {
    clearInterval(this._heartbeatTimer);
    this._ws?.close();
  }

  getStatus(userId) {
    return this._statuses.get(userId) ?? 'offline';
  }

  subscribe(userId, callback) {
    if (!this._listeners.has(userId)) this._listeners.set(userId, new Set());
    this._listeners.get(userId).add(callback);
    // Fire immediately with cached status
    const cached = this._statuses.get(userId);
    if (cached !== undefined) callback(cached);
  }

  unsubscribe(userId, callback) {
    this._listeners.get(userId)?.delete(callback);
  }

  _sendHeartbeat() {
    if (this._ws?.readyState === WebSocket.OPEN) {
      this._ws.send(JSON.stringify({ type: 'heartbeat', tab_id: this._tabId }));
    }
  }

  _notify(userId, status) {
    this._listeners.get(userId)?.forEach(cb => cb(status));
  }
}

/**
 * Create a presence dot DOM element for a given userId.
 * Returns { element, destroy } — call destroy() when removing from DOM.
 */
export function createPresenceDot(userId, manager) {
  const dot = document.createElement('span');
  dot.style.cssText =
    'display:inline-block;width:9px;height:9px;border-radius:50%;flex-shrink:0;transition:background-color .3s;';

  function update(status) {
    dot.style.backgroundColor = _STATUS_COLOR[status] ?? _STATUS_COLOR.offline;
    dot.title = status;
  }

  update(manager.getStatus(userId));
  manager.subscribe(userId, update);

  return {
    element: dot,
    destroy: () => manager.unsubscribe(userId, update),
  };
}

export const presenceManager = new PresenceManager();
