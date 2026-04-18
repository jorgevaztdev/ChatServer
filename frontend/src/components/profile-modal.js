import { logout, deleteAccount } from '../services/auth.js';

// Injects profile modal into document.body. Call open() to show.
export function createProfileModal(user) {
  const overlay = document.createElement('div');
  overlay.id = 'profile-modal-overlay';
  overlay.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-40 hidden';
  overlay.innerHTML = `
    <div class="w-[340px] bg-[#DFDFDF] border border-black flex flex-col" style="box-shadow:inset 2px 2px 0 #fff,inset -2px -2px 0 #808080">
      <!-- Title bar -->
      <div class="bg-[#000080] h-7 flex items-center justify-between px-2 select-none">
        <span class="text-white font-bold text-[13px] font-['IBM_Plex_Sans',sans-serif]">User Profile</span>
        <button id="profile-close-btn" class="w-5 h-5 bg-[#DFDFDF] flex items-center justify-center text-xs font-bold" style="box-shadow:inset 2px 2px 0 #fff,inset -2px -2px 0 #808080">✕</button>
      </div>
      <!-- Content -->
      <div class="p-4 flex flex-col gap-4 font-['IBM_Plex_Sans',sans-serif]">
        <div class="text-[13px]">
          <span class="font-semibold">Username:</span> <span id="profile-username" class="font-mono">${user?.username ?? ''}</span>
        </div>
        <div class="text-[13px]">
          <span class="font-semibold">Email:</span> <span id="profile-email" class="font-mono">${user?.email ?? ''}</span>
        </div>
        <hr class="border-t border-[#808080]"/>
        <button id="profile-logout-btn" class="text-[13px] font-semibold px-4 py-1 bg-[#DFDFDF] border border-black text-left" style="box-shadow:inset 2px 2px 0 #fff,inset -2px -2px 0 #808080">
          Log Out
        </button>
        <button id="profile-delete-btn" class="text-[13px] font-semibold px-4 py-1 bg-[#DFDFDF] border border-black text-left text-red-700" style="box-shadow:inset 2px 2px 0 #fff,inset -2px -2px 0 #808080">
          Delete Account…
        </button>
      </div>
    </div>
    <!-- Confirm delete dialog (hidden by default) -->
    <div id="confirm-delete-overlay" class="fixed inset-0 z-60 flex items-center justify-center bg-black bg-opacity-50 hidden">
      <div class="w-[320px] bg-[#DFDFDF] border border-black flex flex-col" style="box-shadow:inset 2px 2px 0 #fff,inset -2px -2px 0 #808080">
        <div class="bg-[#000080] h-7 flex items-center px-2">
          <span class="text-white font-bold text-[13px]">Confirm Deletion</span>
        </div>
        <div class="p-4 flex flex-col gap-4 font-['IBM_Plex_Sans',sans-serif]">
          <p class="text-[13px]">Permanently delete your account and all owned rooms? This cannot be undone.</p>
          <div class="flex justify-end gap-2">
            <button id="confirm-cancel-btn" class="px-5 py-1 text-[13px] font-semibold bg-[#DFDFDF] border border-black" style="box-shadow:inset 2px 2px 0 #fff,inset -2px -2px 0 #808080">Cancel</button>
            <button id="confirm-delete-ok-btn" class="px-5 py-1 text-[13px] font-semibold bg-[#DFDFDF] border border-black text-red-700" style="box-shadow:inset 2px 2px 0 #fff,inset -2px -2px 0 #808080">Delete</button>
          </div>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  const confirmOverlay = overlay.querySelector('#confirm-delete-overlay');

  overlay.querySelector('#profile-close-btn').addEventListener('click', close);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });

  overlay.querySelector('#profile-logout-btn').addEventListener('click', async () => {
    await logout();
    window.location.href = '/login.html';
  });

  overlay.querySelector('#profile-delete-btn').addEventListener('click', () => {
    confirmOverlay.classList.remove('hidden');
  });

  overlay.querySelector('#confirm-cancel-btn').addEventListener('click', () => {
    confirmOverlay.classList.add('hidden');
  });

  overlay.querySelector('#confirm-delete-ok-btn').addEventListener('click', async () => {
    try {
      await deleteAccount();
      window.location.href = '/login.html';
    } catch {
      alert('Failed to delete account. Try again.');
      confirmOverlay.classList.add('hidden');
    }
  });

  function open() { overlay.classList.remove('hidden'); }
  function close() { overlay.classList.add('hidden'); confirmOverlay.classList.add('hidden'); }

  return { open, close };
}
