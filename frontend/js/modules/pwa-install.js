// JobCopilot — PWA & Android Installation Management: service worker
// registration, native install prompt capture/trigger, and mobile
// drawer/kanban/notification helpers. Extracted from app.js (P1-6);
// self-contained classic script bundled after app.js.
// ==========================================================================
// PWA & Android Installation Management
// ==========================================================================
let deferredInstallPrompt = null;

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then((reg) => {
        console.log('[JobCopilot PWA] ServiceWorker registered with scope:', reg.scope);
      })
      .catch((err) => {
        console.warn('[JobCopilot PWA] ServiceWorker registration failed:', err);
      });
  });
}

// Intercept Native Android PWA Install Event
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  console.log('[JobCopilot PWA] beforeinstallprompt event captured');
  const installBanner = document.getElementById('pwa-install-banner');
  if (installBanner) installBanner.style.display = 'block';
  const topInstallBtn = document.getElementById('btn-mobile-top-install');
  if (topInstallBtn) topInstallBtn.style.display = 'inline-flex';
});

window.addEventListener('appinstalled', () => {
  deferredInstallPrompt = null;
  showToast('🎉 JobCopilot successfully installed on your device!', 'success');
  const topInstallBtn = document.getElementById('btn-mobile-top-install');
  if (topInstallBtn) topInstallBtn.style.display = 'none';
  window.closeInstallModal();
});

window.openInstallModal = function() {
  const modal = document.getElementById('modal-install-app');
  if (modal) modal.style.display = 'flex';
};

window.closeInstallModal = function() {
  const modal = document.getElementById('modal-install-app');
  if (modal) modal.style.display = 'none';
};

window.triggerNativePWAInstall = async function() {
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    const { outcome } = await deferredInstallPrompt.userChoice;
    console.log(`[JobCopilot PWA] Install outcome: ${outcome}`);
    if (outcome === 'accepted') {
      showToast('Installing JobCopilot App...', 'success');
    }
    deferredInstallPrompt = null;
    window.closeInstallModal();
  } else {
    showToast('To install: Tap your browser menu (⋮) and choose "Install app" or "Add to Home Screen".', 'info');
  }
};

window.toggleMobileDrawer = function(forceOpen) {
  const drawer = document.getElementById('mobile-drawer');
  const overlay = document.getElementById('mobile-drawer-overlay');
  if (!drawer || !overlay) return;

  const isOpen = forceOpen !== undefined ? forceOpen : !drawer.classList.contains('active');
  drawer.classList.toggle('active', isOpen);
  overlay.classList.toggle('active', isOpen);
};

window.switchMobileKanbanStage = function(stage, btnElement) {
  const board = document.getElementById('kanban-board-container');
  if (!board) return;

  document.querySelectorAll('.mob-segment').forEach(btn => btn.classList.remove('active'));
  if (btnElement) btnElement.classList.add('active');

  if (stage === 'ALL') {
    board.removeAttribute('data-active-stage');
  } else {
    board.setAttribute('data-active-stage', stage);
  }
};

window.testMobileNotifications = async function() {
  if (!('Notification' in window)) {
    showToast('Notifications are not supported in this browser.', 'error');
    return;
  }
  const perm = await Notification.requestPermission();
  if (perm === 'granted') {
    showToast('🔔 Push Notifications Enabled!', 'success');
    if (navigator.serviceWorker && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({ type: 'TEST_NOTIFICATION' });
    }
    new Notification('JobCopilot Live Radar', {
      body: 'Recruiter radar is active and monitoring 0-day opportunities.',
      icon: '/icons/icon-192.png'
    });
  } else {
    showToast('Notification permission was denied.', 'warning');
  }
};
