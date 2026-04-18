/**
 * T062 — Message input component.
 * Handles text input, reply-to preview, WS send with REST fallback.
 * Enter = send; Shift+Enter = newline.
 */

let _ws = null;
let _roomId = null;
let _replyTo = null;   // { id, sender_username, content }
let _onSendRest = null; // async fallback fn(content, reply_to_id)

const _input = () => document.getElementById('msg-input');
const _replyBar = () => document.getElementById('reply-bar');
const _replyLabel = () => document.getElementById('reply-label');

export function init({ ws, roomId, onSendRest }) {
  _ws = ws;
  _roomId = roomId;
  _onSendRest = onSendRest;

  const input = _input();
  if (!input) return;
  input.disabled = false;
  input.placeholder = 'Type a message… (Enter to send, Shift+Enter for newline)';

  // Ensure reply bar markup exists
  let bar = _replyBar();
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'reply-bar';
    bar.style.cssText = 'display:none;padding:4px 8px;background:#e8e8e8;border-top:1px solid #808080;font-size:11px;font-family:"JetBrains Mono",monospace;display:none;align-items:center;gap:8px;';
    bar.innerHTML = `<span id="reply-label" style="flex:1;color:#000080;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"></span>
      <button id="reply-cancel" style="background:none;border:none;cursor:pointer;font-size:14px;color:#808080;">✕</button>`;
    const inputBar = input.closest('.chat-input-bar') || input.parentElement;
    inputBar.parentElement.insertBefore(bar, inputBar);
    document.getElementById('reply-cancel').addEventListener('click', clearReplyTo);
  }

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      _send();
    }
  });
}

export function updateWs(ws) {
  _ws = ws;
}

export function setReplyTo(msg) {
  _replyTo = msg;
  const label = _replyLabel();
  const bar = _replyBar();
  if (label) label.textContent = `Replying to ${msg.sender_username}: ${msg.content.slice(0, 60)}`;
  if (bar) bar.style.display = 'flex';
  _input()?.focus();
}

export function clearReplyTo() {
  _replyTo = null;
  const bar = _replyBar();
  if (bar) bar.style.display = 'none';
}

export function startEdit(msg, onSubmit) {
  const input = _input();
  if (!input) return;
  const original = input.value;
  const originalReply = _replyTo;

  clearReplyTo();
  input.value = msg.content;
  input.focus();
  input.style.outline = '2px solid #17cfcf';

  const submit = async () => {
    const content = input.value.trim();
    if (content && content !== msg.content) {
      await onSubmit(content);
    }
    input.value = '';
    input.style.outline = '';
    input.removeEventListener('keydown', editKey);
  };

  const editKey = async e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      await submit();
    }
    if (e.key === 'Escape') {
      input.value = '';
      input.style.outline = '';
      input.removeEventListener('keydown', editKey);
      _replyTo = originalReply;
    }
  };

  input.addEventListener('keydown', editKey);
}

function _send() {
  const input = _input();
  if (!input) return;
  const content = input.value.trim();
  if (!content) return;

  const reply_to_id = _replyTo?.id ?? null;

  const wsOk = _ws && _ws.readyState === WebSocket.OPEN;
  if (wsOk) {
    _ws.send(JSON.stringify({ type: 'message:send', payload: { content, reply_to_id } }));
  } else if (_onSendRest) {
    _onSendRest(content, reply_to_id);
  }

  input.value = '';
  clearReplyTo();
}
