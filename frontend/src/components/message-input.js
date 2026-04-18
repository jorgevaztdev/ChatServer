/**
 * T062 / T066 — Message input component.
 * Handles text input, reply-to preview, WS send with REST fallback,
 * file attach button, paste-to-upload, and upload progress.
 * Enter = send; Shift+Enter = newline.
 */

let _ws = null;
let _roomId = null;
let _replyTo = null;
let _onSendRest = null;
let _pendingFile = null; // { file: File }

const _input      = () => document.getElementById('msg-input');
const _replyBar   = () => document.getElementById('reply-bar');
const _replyLabel = () => document.getElementById('reply-label');
const _fileBar    = () => document.getElementById('file-preview-bar');
const _fileInput  = () => document.getElementById('file-attach-input');

export function init({ ws, roomId, onSendRest }) {
  _ws = ws;
  _roomId = roomId;
  _onSendRest = onSendRest;

  const input = _input();
  if (!input) return;
  input.disabled = false;
  input.placeholder = 'Type a message… (Enter to send, Shift+Enter for newline)';

  const inputBar = input.closest('.chat-input-bar') || input.parentElement;

  // ── Reply bar ──────────────────────────────────────────────────────────────
  let bar = _replyBar();
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'reply-bar';
    bar.style.cssText = 'display:none;padding:4px 8px;background:#e8e8e8;border-top:1px solid #808080;font-size:11px;font-family:"JetBrains Mono",monospace;align-items:center;gap:8px;';
    bar.innerHTML = `<span id="reply-label" style="flex:1;color:#000080;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"></span>
      <button id="reply-cancel" style="background:none;border:none;cursor:pointer;font-size:14px;color:#808080;">✕</button>`;
    inputBar.parentElement.insertBefore(bar, inputBar);
    document.getElementById('reply-cancel').addEventListener('click', clearReplyTo);
  }

  // ── File preview bar ───────────────────────────────────────────────────────
  if (!_fileBar()) {
    const fb = document.createElement('div');
    fb.id = 'file-preview-bar';
    fb.style.cssText = 'display:none;padding:4px 8px;background:#ffffcc;border-top:1px solid #808080;font-size:11px;font-family:"JetBrains Mono",monospace;align-items:center;gap:6px;flex-wrap:wrap;';
    fb.innerHTML = `
      <span id="file-preview-name" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#000080;"></span>
      <input id="file-comment-input" type="text" placeholder="Optional comment…"
        style="width:160px;height:22px;padding:0 4px;border:none;box-shadow:inset 2px 2px 0 #808080,inset -2px -2px 0 #fff;font-size:11px;font-family:inherit;background:#fff;"/>
      <button id="file-send-btn" style="padding:2px 10px;background:#DFDFDF;border:none;cursor:pointer;font-size:11px;box-shadow:inset 2px 2px 0 #fff,inset -2px -2px 0 #808080;">Send</button>
      <button id="file-cancel-btn" style="background:none;border:none;cursor:pointer;font-size:13px;color:#808080;">✕</button>
      <div id="upload-progress-wrap" style="width:100%;display:none;">
        <div id="upload-progress-bar" style="height:4px;background:#000080;width:0%;transition:width .2s;"></div>
      </div>`;
    inputBar.parentElement.insertBefore(fb, inputBar);

    document.getElementById('file-cancel-btn').addEventListener('click', _clearFile);
    document.getElementById('file-send-btn').addEventListener('click', _sendFile);
  }

  // ── Hidden file input ──────────────────────────────────────────────────────
  if (!_fileInput()) {
    const fi = document.createElement('input');
    fi.id = 'file-attach-input';
    fi.type = 'file';
    fi.style.display = 'none';
    fi.accept = '*/*';
    fi.addEventListener('change', () => {
      if (fi.files[0]) _showFilePreview(fi.files[0]);
      fi.value = '';
    });
    document.body.appendChild(fi);
  }

  // ── Attach button ──────────────────────────────────────────────────────────
  if (!document.getElementById('file-attach-btn')) {
    const attachBtn = document.createElement('button');
    attachBtn.id = 'file-attach-btn';
    attachBtn.title = 'Attach file';
    attachBtn.textContent = '📎';
    attachBtn.style.cssText = 'height:36px;padding:0 8px;background:#DFDFDF;box-shadow:inset 2px 2px 0 #fff,inset -2px -2px 0 #808080;border:none;cursor:pointer;font-size:16px;flex-shrink:0;';
    attachBtn.addEventListener('click', () => _fileInput()?.click());
    inputBar.insertBefore(attachBtn, input.nextSibling);
  }

  // ── Paste handler ──────────────────────────────────────────────────────────
  input.addEventListener('paste', e => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.kind === 'file') {
        e.preventDefault();
        _showFilePreview(item.getAsFile());
        break;
      }
    }
  });

  // ── Text send ─────────────────────────────────────────────────────────────
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

// ── File upload helpers ───────────────────────────────────────────────────────

function _showFilePreview(file) {
  _pendingFile = { file };
  const fb = _fileBar();
  if (!fb) return;
  document.getElementById('file-preview-name').textContent = `📎 ${file.name} (${Math.round(file.size / 1024)} KB)`;
  document.getElementById('file-comment-input').value = '';
  document.getElementById('upload-progress-wrap').style.display = 'none';
  document.getElementById('upload-progress-bar').style.width = '0%';
  fb.style.display = 'flex';
}

function _clearFile() {
  _pendingFile = null;
  const fb = _fileBar();
  if (fb) fb.style.display = 'none';
}

async function _sendFile() {
  if (!_pendingFile || !_roomId) return;

  const { file } = _pendingFile;
  const comment = document.getElementById('file-comment-input')?.value.trim() || '';
  const sendBtn = document.getElementById('file-send-btn');
  const progressWrap = document.getElementById('upload-progress-wrap');
  const progressBar = document.getElementById('upload-progress-bar');

  sendBtn.disabled = true;
  progressWrap.style.display = 'block';

  const fd = new FormData();
  fd.append('file', file);
  fd.append('comment', comment);
  fd.append('room_id', String(_roomId));

  await new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload');
    xhr.withCredentials = true;
    xhr.upload.onprogress = e => {
      if (e.lengthComputable) {
        progressBar.style.width = `${Math.round((e.loaded / e.total) * 100)}%`;
      }
    };
    xhr.onload = () => {
      if (xhr.status === 201) {
        resolve();
      } else {
        const msg = JSON.parse(xhr.responseText)?.detail || xhr.status;
        reject(new Error(msg));
      }
    };
    xhr.onerror = () => reject(new Error('Upload failed'));
    xhr.send(fd);
  }).catch(err => {
    document.getElementById('file-preview-name').textContent = `Error: ${err.message}`;
    sendBtn.disabled = false;
    return;
  });

  sendBtn.disabled = false;
  _clearFile();
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
