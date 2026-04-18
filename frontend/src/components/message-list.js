/**
 * T061 — Message list component.
 * Renders messages oldest-first; supports infinite scroll (Intersection Observer);
 * reply-to quote blocks; "edited" badge; edit/delete actions for own messages.
 */

let _onLoadMore = null;      // callback(beforeId) for fetching older messages
let _currentUserId = null;
let _onEdit = null;          // callback(msg) to put message into edit mode
let _onDelete = null;        // callback(msg_id)

const _container = () => document.getElementById('messages');

const _esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');

function _ts(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function _buildCard(msg) {
  const isOwn = msg.sender_id === _currentUserId;
  const div = document.createElement('div');
  div.className = 'chat-msg';
  div.dataset.id = msg.id;

  let replyHtml = '';
  if (msg.reply_to_id && msg.reply_to_content) {
    replyHtml = `<div class="reply-quote">&gt; ${_esc(msg.reply_to_content)}</div>`;
  }

  const editedBadge = msg.is_edited ? '<span class="edited-badge">[edited]</span>' : '';
  const actions = isOwn
    ? `<span class="msg-actions">
        <button class="msg-action-btn edit-btn" title="Edit">✏</button>
        <button class="msg-action-btn del-btn" title="Delete">✕</button>
       </span>`
    : `<span class="msg-actions">
        <button class="msg-action-btn reply-btn" title="Reply">↩</button>
       </span>`;

  div.innerHTML = `
    ${replyHtml}
    <span class="ts">${_ts(msg.created_at)}</span>
    <span class="who">${_esc(msg.sender_username)}</span>
    <span class="msg-content">${_esc(msg.content)}</span>
    ${editedBadge}
    ${actions}
  `;

  if (isOwn) {
    div.querySelector('.edit-btn').addEventListener('click', () => _onEdit && _onEdit(msg));
    div.querySelector('.del-btn').addEventListener('click', () => _onDelete && _onDelete(msg.id));
  } else {
    div.querySelector('.reply-btn').addEventListener('click', () => {
      import('./message-input.js').then(m => m.setReplyTo(msg));
    });
  }

  return div;
}

// ── public API ────────────────────────────────────────────────────────────────

export function init({ currentUserId, onLoadMore, onEdit, onDelete }) {
  _currentUserId = currentUserId;
  _onLoadMore = onLoadMore;
  _onEdit = onEdit;
  _onDelete = onDelete;

  // Inject CSS if not present
  if (!document.getElementById('msg-list-styles')) {
    const style = document.createElement('style');
    style.id = 'msg-list-styles';
    style.textContent = `
      .reply-quote { border-left: 3px solid #808080; padding-left: 6px; color: #808080; font-size: 11px; margin-bottom: 2px; font-family: 'JetBrains Mono', monospace; }
      .edited-badge { color: #808080; font-size: 10px; font-style: italic; margin-left: 4px; }
      .msg-actions { opacity: 0; transition: opacity .15s; margin-left: 6px; }
      .chat-msg:hover .msg-actions { opacity: 1; }
      .msg-action-btn { background: none; border: 1px solid #808080; cursor: pointer; font-size: 11px; padding: 0 4px; margin-left: 2px; }
      .msg-action-btn:hover { background: #000080; color: #fff; border-color: #000080; }
    `;
    document.head.appendChild(style);
  }
}

/**
 * Render a batch of messages (oldest-first array) at the top of the list.
 * Returns the ID of the oldest message (for next cursor), or null.
 */
export function prependMessages(msgs) {
  const container = _container();
  if (!msgs.length) return null;

  const prevScrollHeight = container.scrollHeight;
  const prevScrollTop = container.scrollTop;

  // msgs from API come newest-first; reverse to get oldest-first
  const ordered = [...msgs].reverse();
  const fragment = document.createDocumentFragment();
  ordered.forEach(m => fragment.appendChild(_buildCard(m)));

  // sentinel must stay first child
  const sentinel = document.getElementById('scroll-sentinel');
  if (sentinel) {
    container.insertBefore(fragment, sentinel.nextSibling);
  } else {
    container.prepend(fragment);
  }

  // Restore scroll position after prepend
  container.scrollTop = container.scrollHeight - prevScrollHeight + prevScrollTop;
  return ordered[0].id;
}

/** Append a single new message at the bottom (live delivery). */
export function appendMessage(msg) {
  const container = _container();
  const atBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
  const existing = container.querySelector(`[data-id="${msg.id}"]`);
  if (existing) { updateMessage(msg); return; }

  container.appendChild(_buildCard(msg));
  if (atBottom) container.scrollTop = container.scrollHeight;
}

/** Update an existing message card (edit). */
export function updateMessage(msg) {
  const el = _container().querySelector(`[data-id="${msg.id}"]`);
  if (!el) return;
  const newCard = _buildCard(msg);
  el.replaceWith(newCard);
}

/** Remove a message card (delete). */
export function removeMessage(msgId) {
  _container().querySelector(`[data-id="${msgId}"]`)?.remove();
}

/** Clear all messages from the list. */
export function clearMessages() {
  const container = _container();
  container.innerHTML = '';
}

/** Attach Intersection Observer to the sentinel div for infinite scroll. */
export function attachSentinel(sentinel) {
  let loading = false;
  let oldestId = null;

  const observer = new IntersectionObserver(async ([entry]) => {
    if (!entry.isIntersecting || loading || !_onLoadMore) return;
    loading = true;
    const fetched = await _onLoadMore(oldestId);
    if (fetched && fetched.length) {
      const newOldest = prependMessages(fetched);
      if (newOldest !== null) oldestId = newOldest;
    }
    loading = false;
  }, { threshold: 0 });

  observer.observe(sentinel);
  return {
    setOldestId: id => { oldestId = id; },
    disconnect: () => observer.disconnect(),
  };
}
