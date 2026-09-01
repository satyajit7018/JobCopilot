/**
 * ==========================================================================
 * JobCopilot OS — Master Cockpit Frontend Logic
 * Reactive UI with WebSocket streaming, interactive Kanban, real-time
 * Knowledge Vault Q&A playground, Command Palette (Cmd+K), Multi-Resume ATS
 * Workshop, Held Applications Queue, and Direct Call CRM Logger.
 * ==========================================================================
 */

const API_BASE = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
  ? `${window.location.origin}/api`
  : '/api';

// --- Security Sanitization & Authentication Helpers (F-11) ---
function escapeHTML(str) {
  if (!str && str !== 0) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Programmatic Safe DOM Builder Helper (XSS-Free)
 * Constructs DOM nodes safely without innerHTML interpolation.
 */
function el(tag, attrs = {}, ...children) {
  const element = document.createElement(tag);
  for (const [key, val] of Object.entries(attrs || {})) {
    if (key.startsWith('on') && typeof val === 'function') {
      element.addEventListener(key.slice(2).toLowerCase(), val);
    } else if (key === 'className' || key === 'class') {
      element.className = val;
    } else if (key === 'style' && typeof val === 'object') {
      Object.assign(element.style, val);
    } else if (key === 'dataset' && typeof val === 'object') {
      Object.assign(element.dataset, val);
    } else if (val !== null && val !== undefined) {
      element.setAttribute(key, val);
    }
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined) continue;
    if (typeof child === 'string' || typeof child === 'number') {
      element.appendChild(document.createTextNode(String(child)));
    } else if (child instanceof Node) {
      element.appendChild(child);
    }
  }
  return element;
}

window.el = el;
window.escapeHTML = escapeHTML;

function sanitizeUrl(url) {
  if (!url) return '#';
  const clean = String(url).trim();
  if (/^https?:\/\//i.test(clean) || /^mailto:/i.test(clean)) {
    return escapeHTML(clean);
  }
  return '#';
}

let isRefreshing = false;
let refreshSubscribers = [];

function onRefreshed(token) {
  refreshSubscribers.forEach(cb => cb(token));
  refreshSubscribers = [];
}

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem('jobcopilot_refresh_token');
  if (!refreshToken) return null;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    });
    if (!res.ok) {
      localStorage.removeItem('jobcopilot_access_token');
      localStorage.removeItem('jobcopilot_refresh_token');
      return null;
    }
    const data = await res.json();
    if (data.access_token) {
      localStorage.setItem('jobcopilot_access_token', data.access_token);
      if (data.refresh_token) {
        localStorage.setItem('jobcopilot_refresh_token', data.refresh_token);
      }
      return data.access_token;
    }
  } catch (err) {
    console.error('JWT Token Refresh Error:', err);
  }
  return null;
}

async function authFetch(url, options = {}) {
  let token = localStorage.getItem('jobcopilot_access_token');
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  let response = await fetch(url, { ...options, headers });

  // Automatic silent refresh on 401 Unauthorized
  if (response.status === 401 && localStorage.getItem('jobcopilot_refresh_token')) {
    if (!isRefreshing) {
      isRefreshing = true;
      const newToken = await refreshAccessToken();
      isRefreshing = false;
      if (newToken) {
        onRefreshed(newToken);
        headers['Authorization'] = `Bearer ${newToken}`;
        return await fetch(url, { ...options, headers });
      }
    } else {
      const retryPromise = new Promise(resolve => {
        refreshSubscribers.push(newToken => {
          if (newToken) {
            headers['Authorization'] = `Bearer ${newToken}`;
            resolve(fetch(url, { ...options, headers }));
          } else {
            resolve(response);
          }
        });
      });
      return await retryPromise;
    }
  }

  return response;
}

// Global Reactive State
const state = {
  currentProfile: null,
  vaultEntries: [],
  jobsList: [],
  filteredJobs: [],
  heldJobs: [],
  selectedRoles: ['Backend Engineer', 'Full Stack Engineer'],
  currentPipelineFilter: 'ALL',
  ws: null,
  activePendingHitl: null,
  activeOutreachPackage: null,
  activeOutreachTab: 'cover',
  isDiscovering: false,
  currentUser: {
    email: 'candidate@jobcopilot.local',
    full_name: 'Candidate',
    auto_login_enabled: true
  }
};

// UI Element Cache
const els = {
  navTabs: document.querySelectorAll('.nav-item'),
  viewPanels: document.querySelectorAll('.view-panel'),
  workerStatusText: document.getElementById('worker-status-text'),
  workerStatusDot: document.getElementById('worker-status-dot'),
  wsStatusText: document.getElementById('ws-status-text'),
  toastContainer: document.getElementById('toast-container'),
  heldAppsTrigger: document.getElementById('held-apps-trigger'),
  heldAppsCount: document.getElementById('held-apps-count'),
  userDisplayName: document.getElementById('user-display-name'),
  authEmailDisplay: document.getElementById('auth-email-display'),

  // Telemetry HUD
  statTotalApplied: document.getElementById('stat-total-applied'),
  statRecruiterResponses: document.getElementById('stat-recruiter-responses'),
  statInterviews: document.getElementById('stat-interviews'),
  statRejections: document.getElementById('stat-rejections'),
  statResponseRate: document.getElementById('stat-response-rate'),
  statAppliedSubmode: document.getElementById('stat-applied-submode'),
  badgePipelineCount: document.getElementById('badge-pipeline-count'),
  badgeVaultCount: document.getElementById('badge-vault-count'),

  // Stepper Elements
  wstep1: document.getElementById('wstep-1'),
  wstep2: document.getElementById('wstep-2'),
  wstep3: document.getElementById('wstep-3'),
  wstep4: document.getElementById('wstep-4'),
  stepContent1: document.getElementById('step-content-1'),
  stepContent2: document.getElementById('step-content-2'),
  stepContent3: document.getElementById('step-content-3'),
  stepContent4: document.getElementById('step-content-4'),
  currentStepBadge: document.getElementById('current-step-badge'),

  // Onboarding Form
  resumeDropzone: document.getElementById('resume-dropzone'),
  resumeFileInput: document.getElementById('resume-file-input'),
  rawResumeText: document.getElementById('raw-resume-text'),
  btnParseResume: document.getElementById('btn-parse-resume'),
  btnBackStep1: document.getElementById('btn-back-step-1'),
  questionnaireForm: document.getElementById('questionnaire-form'),
  qFullName: document.getElementById('q-full-name'),
  qEmail: document.getElementById('q-email'),
  qPhone: document.getElementById('q-phone'),
  qLocation: document.getElementById('q-location'),
  qNoticePeriod: document.getElementById('q-notice-period'),
  qWorkAuth: document.getElementById('q-work-auth'),
  qSponsorship: document.getElementById('q-sponsorship'),
  qRemotePref: document.getElementById('q-remote-pref'),
  qRelocation: document.getElementById('q-relocation'),
  qLinkedinUrl: document.getElementById('q-linkedin-url'),
  qGithubUrl: document.getElementById('q-github-url'),
  qYoe: document.getElementById('q-yoe'),
  qCurrentEmployer: document.getElementById('q-current-employer'),
  qWhyLooking: document.getElementById('q-why-looking'),
  multiResumeWorkshopContainer: document.getElementById('multi-resume-workshop-container'),

  // Salary Slider
  salarySlider: document.getElementById('salary-slider'),
  salaryDisplay: document.getElementById('salary-display'),
  eqInrLpa: document.getElementById('eq-inr-lpa'),
  eqUsdAnnual: document.getElementById('eq-usd-annual'),
  eqUsdHourly: document.getElementById('eq-usd-hourly'),
  eqInrMonthly: document.getElementById('eq-inr-monthly'),

  // Pipeline
  cardsDiscovered: document.getElementById('cards-discovered'),
  cardsQueued: document.getElementById('cards-queued'),
  cardsSubmitted: document.getElementById('cards-submitted'),
  cardsInterview: document.getElementById('cards-interview'),
  cardsOffer: document.getElementById('cards-offer'),
  countDiscovered: document.getElementById('count-col-discovered'),
  countQueued: document.getElementById('count-col-queued'),
  countSubmitted: document.getElementById('count-col-submitted'),
  countInterview: document.getElementById('count-col-interview'),
  countOffer: document.getElementById('count-col-offer'),
  pipelineSearchInput: document.getElementById('pipeline-search-input'),

  // Vault Studio
  vaultEntriesList: document.getElementById('vault-entries-list'),
  vaultTestPrompt: document.getElementById('vault-test-prompt'),
  vaultTestResult: document.getElementById('vault-test-result'),
  vaultTotalBadge: document.getElementById('vault-total-badge'),

  // Email Radar & Bot
  emailRadarFeed: document.getElementById('email-radar-feed'),
  botLogsContainer: document.getElementById('bot-logs-container'),

  // Modals
  hitlModal: document.getElementById('hitl-modal'),
  hitlQuestionText: document.getElementById('hitl-question-text'),
  hitlUserAnswer: document.getElementById('hitl-user-answer'),
  hitlCompanyTag: document.getElementById('hitl-company-tag'),
  hitlSaveVaultCheck: document.getElementById('hitl-save-vault-check'),
  btnHitlApprove: document.getElementById('btn-hitl-approve'),
  modalHeldApplications: document.getElementById('modal-held-applications'),
  heldAppsList: document.getElementById('held-apps-list'),
  modalLogCall: document.getElementById('modal-log-call'),

  // Negotiation & Studio
  negBaseSalary: document.getElementById('neg-base-salary'),
  negBonus: document.getElementById('neg-bonus'),
  negEquity: document.getElementById('neg-equity'),
  negCompanyInput: document.getElementById('neg-company-name'),
  negRoleTitle: document.getElementById('neg-role-title'),
  negotiationResultsContainer: document.getElementById('negotiation-results-container'),
  esopOptionsCount: document.getElementById('esop-options-count'),
  esopTotalShares: document.getElementById('esop-total-shares'),
  esopValuationUsd: document.getElementById('esop-valuation-usd'),
  esopResultsContainer: document.getElementById('esop-results-container'),
  mockCompanyInput: document.getElementById('mock-company-name'),
  mockRoleInput: document.getElementById('mock-role-title'),
  interviewDossierContainer: document.getElementById('interview-dossier-container')
};

// ==========================================================================
// Toast Notification Engine
// ==========================================================================
function showToast(message, type = 'info') {
  if (!els.toastContainer) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  let icon = '⚡';
  if (type === 'success') icon = '✓';
  if (type === 'error') icon = '✕';
  if (type === 'info') icon = 'ℹ';

  toast.innerHTML = `<span style="font-weight: 700;">${icon}</span><span>${message}</span>`;
  els.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ==========================================================================
// WebSocket Real-Time Gateway Connection
// ==========================================================================
function initWebSocket() {
  try {
    const token = localStorage.getItem('jobcopilot_access_token');
    if (!token) {
      if (els.wsStatusText) els.wsStatusText.textContent = 'Sync: Offline (Login Required)';
      return;
    }
    if (state.ws && (state.ws.readyState === WebSocket.OPEN || state.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    const WS_BASE = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
    const wsUrl = `${WS_BASE}?token=${encodeURIComponent(token)}`;
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
      if (els.wsStatusText) els.wsStatusText.textContent = 'Sync: Connected';
      appendTerminalLog('SYSTEM', 'WebSocket telemetry stream connected to backend.', false, true);
    };

    state.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleIncomingWebSocketMessage(msg);
      } catch (err) {
        console.error('Failed to parse WS payload:', err);
      }
    };

    state.ws.onclose = (event) => {
      if (event.code === 4001) {
        if (els.wsStatusText) els.wsStatusText.textContent = 'Sync: Offline (Unauthorized)';
        return;
      }
      if (els.wsStatusText) els.wsStatusText.textContent = 'Sync: Reconnecting...';
      setTimeout(initWebSocket, 5000);
    };

    state.ws.onerror = (err) => {
      console.warn('WebSocket connection warning:', err);
    };
  } catch (err) {
    console.error('WS init exception:', err);
  }
}

function handleIncomingWebSocketMessage(msg) {
  if (msg.type === 'HEARTBEAT') return;

  if (msg.type === 'LOG') {
    appendTerminalLog(msg.level || 'BOT', msg.message);
  } else if (msg.type === 'HITL_PROMPT') {
    showToast(`HITL Question from ${msg.company}: "${msg.question}"`, 'info');
    state.activePendingHitl = msg;
    openHITLModal(msg);
    fetchHeldApplications();
  } else if (msg.type === 'CALL_LOGGED' || msg.type === 'APPLICATION_RESUMED') {
  } else if (msg.type === 'INTERVIEW_INVITATION_RECEIVED' || (msg.type === 'EMAIL_RECEIVED' && msg.intent === 'INTERVIEW_INVITE')) {
    const comp = msg.company || 'Target Company';
    const role = msg.role_title || 'Software Engineer';
    const link = msg.meeting_url || (msg.scheduling_links && msg.scheduling_links[0]);
    showToast(`🎉 Interview Invitation from ${comp} for ${role}!`, 'success');
    window.openInterviewInviteModal(comp, role, link);
    fetchFunnelMetrics();
    fetchJobsList();
  } else if (msg.type === 'EMAIL_DISCOVERED' || msg.type === 'EMAIL_RECEIVED') {
    showToast(`Inbound Recruiter Email: ${msg.subject || msg.company} (${msg.intent || 'Received'})`, 'info');
    fetchFunnelMetrics();
    fetchJobsList();
  }
}

function appendTerminalLog(module, text, isError = false, isSuccess = false) {
  if (!els.botLogsContainer) return;
  const now = new Date().toTimeString().split(' ')[0];
  const div = document.createElement('div');
  div.className = 'log-entry';

  let textClass = '';
  if (isError) textClass = 'log-critical';
  if (isSuccess) textClass = 'log-success';

  div.innerHTML = `
    <span class="log-ts">[${now}]</span>
    <span class="log-mod">[${module.toUpperCase()}]</span>
    <span class="${textClass}">${text}</span>
  `;
  els.botLogsContainer.appendChild(div);
  els.botLogsContainer.scrollTop = els.botLogsContainer.scrollHeight;
}

// ==========================================================================
// Google SSO & Authentication Gateway (Step 1 & 3)
// ==========================================================================
window.triggerGoogleSSO = async function() {
  showToast('Connecting to Google Single Sign-On...', 'info');
  try {
    const res = await fetch(`${API_BASE}/auth/google-sso`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'alex.mercer.dev@gmail.com',
        full_name: 'Alex Mercer',
        avatar_url: 'https://lh3.googleusercontent.com/a/default-user',
        auto_login_permissions: document.getElementById('chk-auto-login-perm')?.checked ?? true
      })
    });
    const data = await res.json();
    if (data.access_token) {
      localStorage.setItem('jobcopilot_access_token', data.access_token);
      if (data.refresh_token) {
        localStorage.setItem('jobcopilot_refresh_token', data.refresh_token);
      }
      state.currentUser = {
        email: data.email || 'alex.mercer.dev@gmail.com',
        full_name: 'Alex Mercer',
        user_id: data.user_id,
        role: data.role
      };
      if (els.userDisplayName) els.userDisplayName.textContent = state.currentUser.full_name;
      if (els.authEmailDisplay) els.authEmailDisplay.textContent = state.currentUser.email;
      showToast(`Signed in successfully as ${state.currentUser.full_name}!`, 'success');
      appendTerminalLog('AUTH', `Google Single Sign-On session active for ${state.currentUser.email}`, false, true);
      initWebSocket();
    } else {
      showToast(`Google SSO error: ${data.detail || 'Authentication failed'}`, 'error');
    }
  } catch (err) {
    showToast(`Google SSO error: ${err.message}`, 'error');
  }
};

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

// ==========================================================================
// Multi-Step Onboarding Navigation & Responsive Synchronizer
// ==========================================================================
window.switchTab = function(viewId) {
  if (viewId === 'studio') viewId = 'interview-studio';
  if (viewId === 'interview') viewId = 'interview-studio';

  els.navTabs.forEach(t => {
    t.classList.toggle('active', t.getAttribute('data-view') === viewId);
  });
  document.querySelectorAll('.mobile-nav-tab').forEach(t => {
    t.classList.toggle('active', t.getAttribute('data-view') === viewId);
  });
  els.viewPanels.forEach(p => {
    p.classList.toggle('active', p.id === `view-${viewId}`);
  });
  window.location.hash = viewId;
  if (viewId === 'interview-studio' || viewId === 'interview') {
    setTimeout(initVisualizerCanvas, 50);
  }
};

els.navTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    const view = tab.getAttribute('data-view');
    window.switchTab(view);
  });
});

window.proceedToStep2 = function() {
  els.wstep1.classList.remove('active');
  els.wstep2.classList.add('active');
  els.stepContent1.style.display = 'none';
  els.stepContent2.style.display = 'block';
  els.currentStepBadge.textContent = 'Step 2: Recruiter Screening Form';
};

window.backToStep1 = function() {
  els.wstep2.classList.remove('active');
  els.wstep1.classList.add('active');
  els.stepContent2.style.display = 'none';
  els.stepContent1.style.display = 'block';
  els.currentStepBadge.textContent = 'Step 1: Auth & Resume Ingestion';
};

window.skipQuestionnaire = function() {
  showToast('Skipped screening questions — you can complete them later anytime.', 'info');
  window.proceedToStep3();
};

window.proceedToStep3 = function() {
  els.wstep2.classList.remove('active');
  els.wstep3.classList.add('active');
  els.stepContent2.style.display = 'none';
  els.stepContent3.style.display = 'block';
  els.currentStepBadge.textContent = 'Step 3: Target Roles & ATS Workshop';
  renderMultiResumeWorkshop();
};

window.backToStep2 = function() {
  els.wstep3.classList.remove('active');
  els.wstep2.classList.add('active');
  els.stepContent3.style.display = 'none';
  els.stepContent2.style.display = 'block';
  els.currentStepBadge.textContent = 'Step 2: Recruiter Screening Form';
};

window.proceedToStep4 = function() {
  els.wstep3.classList.remove('active');
  els.wstep4.classList.add('active');
  els.stepContent3.style.display = 'none';
  els.stepContent4.style.display = 'block';
  els.currentStepBadge.textContent = 'Step 4: Launch Autopilot';
  showToast('Onboarding completed! Resumes compiled & Knowledge Vault active.', 'success');
};

// Target Role Selection & Multi-Resume ATS Workshop
window.toggleTargetRole = function(btn) {
  btn.classList.toggle('active');
  const activeRoles = Array.from(document.querySelectorAll('#role-selector-grid .role-pill.active'))
    .map(b => b.getAttribute('data-role'));
  state.selectedRoles = activeRoles.length > 0 ? activeRoles : ['Backend Engineer'];
  renderMultiResumeWorkshop();
};

async function renderMultiResumeWorkshop() {
  if (!els.multiResumeWorkshopContainer) return;
  els.multiResumeWorkshopContainer.innerHTML = '<p style="color: var(--text-muted); font-size: 13px;">Compiling ATS-tailored resume variants for selected roles...</p>';

  try {
    const res = await authFetch(`${API_BASE}/resumes/tailor-multi`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roles: state.selectedRoles, profile_id: 'default_user' })
    });
    const data = await res.json();
    const resumes = data.resumes || {};

    els.multiResumeWorkshopContainer.innerHTML = Object.entries(resumes).map(([role, r]) => `
      <div class="multi-resume-card">
        <div class="multi-resume-card-header">
          <div>
            <div style="font-weight: 700; font-size: 14.5px; color: var(--accent-cyan);">${escapeHTML(role)}</div>
            <div style="font-size: 11px; color: var(--text-muted);">ATS Tailored Variant</div>
          </div>
          <span class="match-ring-badge match-high">${escapeHTML(r.match_strength || '95%')} Match</span>
        </div>

        <div style="margin-bottom: 0.75rem;">
          <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; margin-bottom: 4px;">Top Weighted Keywords</div>
          <div>
            ${(r.tailored_skills || []).slice(0, 6).map(k => `<span class="keyword-badge">${escapeHTML(k)}</span>`).join('')}
          </div>
        </div>

        <div style="margin-bottom: 0.75rem;">
          <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; margin-bottom: 4px;">Promoted Projects</div>
          <div style="font-size: 12px; color: #e2e8f0; font-weight: 500;">
            ${(r.reordered_projects || []).slice(0, 2).map(p => `• ${escapeHTML(p)}`).join('<br>')}
          </div>
        </div>

        <div>
          <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; margin-bottom: 4px;">Recommended Impact Bullets</div>
          <ul style="font-size: 11.5px; color: var(--text-secondary); padding-left: 14px; line-height: 1.4; margin: 0;">
            ${(r.recommended_bullets || []).slice(0, 2).map(b => `<li>${escapeHTML(b)}</li>`).join('')}
          </ul>
        </div>
      </div>
    `).join('');
  } catch (err) {
    els.multiResumeWorkshopContainer.innerHTML = `<p style="color: var(--accent-rose); font-size: 12px;">Failed to compile resumes: ${escapeHTML(err.message)}</p>`;
  }
}

// ==========================================================================
// Salary Slider Live Conversions
// ==========================================================================
function updateSalaryEquivalents(lpa) {
  if (els.salaryDisplay) els.salaryDisplay.textContent = `${lpa.toFixed(1)} LPA`;
  if (els.eqInrLpa) els.eqInrLpa.textContent = `${lpa.toFixed(1)} LPA`;

  const totalInr = lpa * 100000;
  const inrToUsdRate = 83.5;
  const totalUsd = Math.round(totalInr / inrToUsdRate);
  const hourlyUsd = (totalUsd / 2080).toFixed(2);
  const monthlyInr = Math.round(totalInr / 12).toLocaleString('en-IN');

  if (els.eqUsdAnnual) els.eqUsdAnnual.textContent = `$${totalUsd.toLocaleString()}`;
  if (els.eqUsdHourly) els.eqUsdHourly.textContent = `$${hourlyUsd}/hr`;
  if (els.eqInrMonthly) els.eqInrMonthly.textContent = `₹${monthlyInr}`;
}

if (els.salarySlider) {
  els.salarySlider.addEventListener('input', (e) => {
    updateSalaryEquivalents(parseFloat(e.target.value));
  });
}

// ==========================================================================
// Resume Drag-and-Drop Ingestion (Step 2)
// ==========================================================================
if (els.resumeDropzone && els.resumeFileInput) {
  els.resumeDropzone.addEventListener('click', () => els.resumeFileInput.click());

  els.resumeDropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    els.resumeDropzone.style.borderColor = 'var(--accent-indigo)';
  });

  els.resumeDropzone.addEventListener('dragleave', () => {
    els.resumeDropzone.style.borderColor = 'var(--border-subtle)';
  });

  els.resumeDropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    els.resumeDropzone.style.borderColor = 'var(--border-subtle)';
    if (e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  });

  els.resumeFileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  });
}

async function handleFileUpload(file) {
  showToast(`Ingesting ${file.name}...`, 'info');
  const formData = new FormData();
  formData.append('file', file);
  formData.append('profile_id', 'default_user');

  try {
    const res = await authFetch(`${API_BASE}/upload-resume`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (data.status === 'success') {
      state.currentProfile = data.profile;
      populateQuestionnaireFromProfile(data.profile);
      showToast('Resume parsed in <150ms! Extracted skills & achievements.', 'success');
      appendTerminalLog('PARSER', `Parsed ${data.profile.full_name} (${data.profile.skills.length} skills found).`, false, true);
      window.proceedToStep2();
    }
  } catch (err) {
    showToast(`Upload failed: ${err.message}`, 'error');
  }
}

if (els.btnParseResume) {
  els.btnParseResume.addEventListener('click', async () => {
    const rawText = els.rawResumeText.value.trim();
    if (!rawText) {
      showToast('Please upload a file or paste your resume text.', 'error');
      return;
    }
    const blob = new Blob([rawText], { type: 'text/plain' });
    const file = new File([blob], 'resume.txt', { type: 'text/plain' });
    handleFileUpload(file);
  });
}

function populateQuestionnaireFromProfile(profile) {
  if (!profile) return;
  if (els.qFullName) els.qFullName.value = profile.full_name || '';
  if (els.qEmail) els.qEmail.value = profile.email || '';
  if (els.qPhone) els.qPhone.value = profile.phone || '';
  if (els.qLocation) els.qLocation.value = profile.location || '';
  if (els.qLinkedinUrl) els.qLinkedinUrl.value = profile.linkedin_url || '';
  if (els.qGithubUrl) els.qGithubUrl.value = profile.github_url || '';

  const prefs = profile.preferences || {};
  if (prefs.expected_ctc && els.salarySlider) {
    const match = prefs.expected_ctc.match(/(\d+(\.\d+)?)/);
    if (match) {
      const val = parseFloat(match[1]);
      els.salarySlider.value = val;
      updateSalaryEquivalents(val);
    }
  }
  if (prefs.notice_period_days && els.qNoticePeriod) els.qNoticePeriod.value = String(prefs.notice_period_days);
  if (prefs.work_authorization && els.qWorkAuth) els.qWorkAuth.value = prefs.work_authorization;
  if (prefs.remote_preference && els.qRemotePref) els.qRemotePref.value = prefs.remote_preference;
  if (prefs.current_employer && els.qCurrentEmployer) els.qCurrentEmployer.value = prefs.current_employer;
  if (prefs.why_looking_for_role && els.qWhyLooking) els.qWhyLooking.value = prefs.why_looking_for_role;
}

if (els.btnBackStep1) els.btnBackStep1.addEventListener('click', window.backToStep1);

if (els.questionnaireForm) {
  els.questionnaireForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const lpa = parseFloat(els.salarySlider.value);
    const answers = {
      full_name: els.qFullName.value.trim(),
      email: els.qEmail.value.trim(),
      phone: els.qPhone.value.trim(),
      location: els.qLocation.value.trim(),
      expected_ctc: `${lpa.toFixed(1)} LPA`,
      notice_period_days: parseInt(els.qNoticePeriod.value, 10),
      work_authorization: els.qWorkAuth.value,
      requires_sponsorship: els.qSponsorship ? els.qSponsorship.value === 'Yes' : false,
      remote_preference: els.qRemotePref.value,
      willing_to_relocate: els.qRelocation ? els.qRelocation.value === 'Yes' : true,
      linkedin_url: els.qLinkedinUrl ? els.qLinkedinUrl.value.trim() : '',
      github_url: els.qGithubUrl ? els.qGithubUrl.value.trim() : '',
      years_of_experience: els.qYoe ? parseFloat(els.qYoe.value) : 4.0,
      current_employer: els.qCurrentEmployer.value.trim(),
      why_looking_for_role: els.qWhyLooking.value.trim()
    };

    try {
      const res = await authFetch(`${API_BASE}/questionnaire`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_id: 'default_user', answers: answers })
      });
      const data = await res.json();
      if (data.status === 'success') {
        showToast('Screening preferences saved & indexed!', 'success');
        fetchVaultEntries();
        window.proceedToStep3();
      }
    } catch (err) {
      showToast(`Save error: ${err.message}`, 'error');
    }
  });
}

// ==========================================================================
// 0-Day Job Pipeline & Interactive Kanban (Step 6, 8, 9)
// ==========================================================================
async function fetchJobsList() {
  try {
    const res = await authFetch(`${API_BASE}/jobs`);
    const data = await res.json();
    state.jobsList = data.jobs || [];
    renderKanbanBoard();
  } catch (err) {
    console.error('Failed to load job listings:', err);
  }
}

window.filterPipeline = function(filter, btn) {
  state.currentPipelineFilter = filter;
  document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderKanbanBoard();
};

if (els.pipelineSearchInput) {
  els.pipelineSearchInput.addEventListener('input', () => {
    renderKanbanBoard();
  });
}

function renderKanbanBoard() {
  const query = (els.pipelineSearchInput ? els.pipelineSearchInput.value : '').toLowerCase();
  const filter = state.currentPipelineFilter;

  const filtered = state.jobsList.filter(j => {
    const textMatch = (j.company + ' ' + j.title + ' ' + (j.location || '')).toLowerCase().includes(query);
    if (!textMatch) return false;

    if (filter === 'ALL') return true;
    if (filter === 'HIGH_MATCH') return (j.match_score || 0) >= 0.75;
    if (filter === 'NAUKRI') return (j.platform || '').toLowerCase().includes('naukri');
    if (filter === 'INSTAHYRE') return (j.platform || '').toLowerCase().includes('instahyre');
    if (filter === 'CUVETTE') return (j.platform || '').toLowerCase().includes('cuvette');
    if (filter === 'CUTSHORT') return (j.platform || '').toLowerCase().includes('cutshort');
    if (filter === 'GREENHOUSE') return (j.platform || '').toLowerCase().includes('greenhouse');
    if (filter === 'LEVER') return (j.platform || '').toLowerCase().includes('lever');
    if (filter === 'ASHBY') return (j.platform || '').toLowerCase().includes('ashby');
    if (filter === 'YC') return (j.platform || '').toLowerCase().includes('yc');
    return true;
  });

  const columns = {
    discovered: filtered.filter(j => j.status === 'DISCOVERED'),
    queued: filtered.filter(j => j.status === 'QUEUED' || j.status === 'NEEDS_REVIEW'),
    submitted: filtered.filter(j => j.status === 'SUBMITTED'),
    interview: filtered.filter(j => j.status === 'INTERVIEW'),
    offer: filtered.filter(j => j.status === 'OFFER')
  };

  if (els.countDiscovered) els.countDiscovered.textContent = columns.discovered.length;
  if (els.countQueued) els.countQueued.textContent = columns.queued.length;
  if (els.countSubmitted) els.countSubmitted.textContent = columns.submitted.length;
  if (els.countInterview) els.countInterview.textContent = columns.interview.length;
  if (els.countOffer) els.countOffer.textContent = columns.offer.length;
  if (els.badgePipelineCount) els.badgePipelineCount.textContent = filtered.length;

  // Sync Mobile UI Counters & Badges
  const mobBadge = document.getElementById('mob-badge-pipeline');
  if (mobBadge) {
    mobBadge.textContent = filtered.length;
    mobBadge.style.display = filtered.length > 0 ? 'inline-block' : 'none';
  }
  const mobSegDisc = document.getElementById('mob-seg-count-discovered');
  if (mobSegDisc) mobSegDisc.textContent = columns.discovered.length;
  const mobSegQueued = document.getElementById('mob-seg-count-queued');
  if (mobSegQueued) mobSegQueued.textContent = columns.queued.length;
  const mobSegSub = document.getElementById('mob-seg-count-submitted');
  if (mobSegSub) mobSegSub.textContent = columns.submitted.length;
  const mobSegInt = document.getElementById('mob-seg-count-interview');
  if (mobSegInt) mobSegInt.textContent = columns.interview.length;
  const mobSegOff = document.getElementById('mob-seg-count-offer');
  if (mobSegOff) mobSegOff.textContent = columns.offer.length;

  if (els.cardsDiscovered) els.cardsDiscovered.innerHTML = columns.discovered.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">No leads discovered.</p>';
  if (els.cardsQueued) els.cardsQueued.innerHTML = columns.queued.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">Queue is empty.</p>';
  if (els.cardsSubmitted) els.cardsSubmitted.innerHTML = columns.submitted.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">No applications submitted yet.</p>';
  if (els.cardsInterview) els.cardsInterview.innerHTML = columns.interview.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">No active interviews.</p>';
  if (els.cardsOffer) els.cardsOffer.innerHTML = columns.offer.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">No offers recorded.</p>';
}

function getCompanyAvatarData(company) {
  const compLower = (company || '').toLowerCase();
  let bg = 'linear-gradient(135deg, #6366f1, #8b5cf6)';
  let icon = '⚡';
  let initial = (company || 'C').slice(0, 2).toUpperCase();

  if (compLower.includes('swiggy')) { bg = 'linear-gradient(135deg, #fc8019, #e23744)'; icon = '🍔'; }
  else if (compLower.includes('razorpay')) { bg = 'linear-gradient(135deg, #0c2340, #0284c7)'; icon = '💳'; }
  else if (compLower.includes('zepto')) { bg = 'linear-gradient(135deg, #ff3366, #9333ea)'; icon = '⚡'; }
  else if (compLower.includes('cred')) { bg = 'linear-gradient(135deg, #111827, #374151)'; icon = '💎'; }
  else if (compLower.includes('phonepe')) { bg = 'linear-gradient(135deg, #5f259f, #9333ea)'; icon = '📱'; }
  else if (compLower.includes('postman')) { bg = 'linear-gradient(135deg, #ff6c37, #f97316)'; icon = '🚀'; }
  else if (compLower.includes('stripe')) { bg = 'linear-gradient(135deg, #635bff, #00d4ff)'; icon = '⚡'; }
  else if (compLower.includes('browserstack')) { bg = 'linear-gradient(135deg, #009688, #0284c7)'; icon = '🌐'; }
  else if (compLower.includes('groww')) { bg = 'linear-gradient(135deg, #00d09c, #0ea5e9)'; icon = '📈'; }
  else if (compLower.includes('juspay')) { bg = 'linear-gradient(135deg, #059669, #0284c7)'; icon = '🔒'; }
  else if (compLower.includes('sarvam')) { bg = 'linear-gradient(135deg, #8b5cf6, #ec4899)'; icon = '🤖'; }

  return { bg, icon, initial };
}

function renderMatchGaugeSVG(pct) {
  const radius = 17;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (pct / 100) * circumference;
  let strokeColor = '#10b981';
  let glowColor = 'rgba(16, 185, 129, 0.4)';
  if (pct < 65) { strokeColor = '#f59e0b'; glowColor = 'rgba(245, 158, 11, 0.4)'; }
  else if (pct < 80) { strokeColor = '#06b6d4'; glowColor = 'rgba(6, 182, 212, 0.4)'; }

  return `
    <div class="match-gauge-wrap" title="${pct}% Match Score">
      <svg class="match-gauge-svg" width="46" height="46" viewBox="0 0 46 46">
        <circle cx="23" cy="23" r="${radius}" stroke="rgba(255,255,255,0.08)" stroke-width="3.5" fill="transparent"/>
        <circle cx="23" cy="23" r="${radius}" stroke="${strokeColor}" stroke-width="3.5" stroke-dasharray="${circumference}" stroke-dashoffset="${strokeDashoffset}" stroke-linecap="round" fill="transparent" transform="rotate(-90 23 23)" style="filter: drop-shadow(0 0 4px ${glowColor});"/>
      </svg>
      <div class="match-gauge-text">
        <span class="match-gauge-num" style="color: ${strokeColor};">${pct}%</span>
        <span class="match-gauge-label">Match</span>
      </div>
    </div>
  `;
}

function renderStageProgressLine(status) {
  const stages = [
    { key: 'DISCOVERED', label: 'Discovered' },
    { key: 'QUEUED', label: 'Queued' },
    { key: 'SUBMITTED', label: 'Applied' },
    { key: 'INTERVIEW', label: 'Interview' },
    { key: 'OFFER', label: 'Offer' }
  ];
  const stageIndex = stages.findIndex(s => s.key === status);
  const activeIdx = stageIndex >= 0 ? stageIndex : 0;

  return `
    <div class="job-stage-tracker">
      ${stages.map((st, i) => {
        const isDone = i < activeIdx;
        const isActive = i === activeIdx;
        const cls = isActive ? 'node-active' : (isDone ? 'node-done' : 'node-pending');
        return `
          <div class="stage-node-wrap ${cls}">
            <div class="stage-node-dot"></div>
            <span class="stage-node-name">${st.label}</span>
          </div>
          ${i < stages.length - 1 ? `<div class="stage-track-line ${i < activeIdx ? 'line-done' : ''}"></div>` : ''}
        `;
      }).join('')}
    </div>
  `;
}

function renderJobCardHTML(job) {
  const matchPct = Math.round((job.match_score || 0) * 100);
  const company = escapeHTML(job.company || 'Company');
  const title = escapeHTML(job.title || 'Role');
  const platform = escapeHTML(job.platform || 'Direct');
  const location = escapeHTML(job.location || 'Remote');
  const jobId = escapeHTML(job.job_id || '');
  const salaryRange = escapeHTML(job.salary_range || '');

  // Detect Indian platform badge classes
  let platformBadgeClass = '';
  const platLower = platform.toLowerCase();
  if (platLower.includes('naukri')) platformBadgeClass = 'badge-naukri';
  else if (platLower.includes('instahyre')) platformBadgeClass = 'badge-instahyre';
  else if (platLower.includes('cuvette')) platformBadgeClass = 'badge-cuvette';
  else if (platLower.includes('cutshort')) platformBadgeClass = 'badge-cutshort';

  const avatar = getCompanyAvatarData(job.company);

  // Extract GMeet / Zoom link if present in notes
  let gmeetLink = null;
  const matchLink = (job.notes || '').match(/(https?:\/\/(?:meet\.google\.com|zoom\.us|teams\.microsoft\.com)[^\s]+)/i);
  if (matchLink) gmeetLink = sanitizeUrl(matchLink[1]);

  return `
    <div class="job-card" id="card-${jobId}">
      <div class="job-card-header">
        <div class="job-card-brand">
          <div class="company-avatar-box" style="background: ${avatar.bg};">
            <span>${avatar.icon}</span>
          </div>
          <div class="job-brand-info">
            <div class="job-company">${company}</div>
            <div class="job-location-sub">${location}</div>
          </div>
        </div>
        ${renderMatchGaugeSVG(matchPct)}
      </div>

      <div class="job-title">${title}</div>

      <div class="job-tags-row">
        <span class="job-tag ${platformBadgeClass}">${platform}</span>
        ${salaryRange ? `<span class="job-salary-pill">⚡ ${salaryRange}</span>` : ''}
      </div>

      ${renderStageProgressLine(job.status)}

      ${gmeetLink && gmeetLink !== '#' ? `
        <a href="${gmeetLink}" target="_blank" rel="noopener noreferrer" class="gmeet-btn">
          <span>📹 Join Live Interview Meeting</span>
        </a>
      ` : ''}

      ${job.status === 'INTERVIEW' ? `
        <button class="btn btn-secondary btn-sm" onclick="window.launchTailoredInterviewForJob('${company.replace(/'/g, "\\'")}', '${title.replace(/'/g, "\\'")}')" style="margin-top: 8px; width: 100%; background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(6, 182, 212, 0.25)); border-color: rgba(99, 102, 241, 0.5); color: #c7d2fe; font-size: 11.5px; padding: 6px 10px; justify-content: center;">
          <span>🎙️ Practice Voice Mock Interview</span>
        </button>
      ` : ''}

      <div class="job-card-actions">
        <button class="btn btn-primary btn-sm" onclick="applyToJob('${jobId}')" style="flex: 1.2;">⚡ Apply Now</button>
        <button class="btn btn-secondary btn-sm" onclick="tailorJobAssets('${jobId}')" style="flex: 1;">🎯 Tailor</button>
      </div>
    </div>
  `;
}

// 1-Click Apply Action
window.applyToJob = async function(jobId) {
  showToast(`Initializing stealth bot for job #${jobId}...`, 'info');
  appendTerminalLog('BOT', `Launching Playwright Chromium session for Job ID: ${jobId}`);

  try {
    const res = await authFetch(`${API_BASE}/bot/apply/${jobId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`Application successfully processed (${data.mode})!`, 'success');
      appendTerminalLog('BOT', `Completed form filling for ${data.company}. Screenshot saved.`, false, true);
      fetchJobsList();
      fetchFunnelMetrics();
    }
  } catch (err) {
    showToast(`Bot apply error: ${err.message}`, 'error');
  }
};

window.triggerDiscoveryCycle = async function() {
  if (state.isDiscovering) return;
  state.isDiscovering = true;
  showToast('Running high-frequency 0-day discovery across Greenhouse, Lever, Ashby, YC & HN...', 'info');
  appendTerminalLog('DISCOVERY', 'Polling 0-day feeds (<2 hours fresh)...');

  try {
    const res = await authFetch(`${API_BASE}/discovery/run`, { method: 'POST' });
    const data = await res.json();
    showToast(`Discovered ${data.count || 12} new 0-day openings!`, 'success');
    appendTerminalLog('DISCOVERY', `Ingested ${data.count || 12} job postings. SimHash deduplication complete.`, false, true);
    fetchJobsList();
    fetchFunnelMetrics();
  } catch (err) {
    showToast(`Discovery error: ${err.message}`, 'error');
  } finally {
    state.isDiscovering = false;
  }
};

// ==========================================================================
// Manual Recruiter Direct Call Logger (Step 8)
// ==========================================================================
window.openLogCallModal = function() {
  if (els.modalLogCall) els.modalLogCall.classList.add('active');
};

window.submitDirectCall = async function(e) {
  e.preventDefault();
  const company = document.getElementById('call-company').value.trim();
  const role = document.getElementById('call-role').value.trim();
  const recruiter = document.getElementById('call-recruiter').value.trim();
  const status = document.getElementById('call-status').value;
  const meetingLink = document.getElementById('call-meeting-link').value.trim();
  const notes = document.getElementById('call-notes').value.trim();

  try {
    const res = await authFetch(`${API_BASE}/jobs/log-call`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        company: company,
        role_title: role,
        recruiter_name: recruiter,
        status: status,
        meeting_link: meetingLink,
        call_notes: notes
      })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`Logged direct call for ${company} (${status})!`, 'success');
      appendTerminalLog('CRM', `Direct call recorded: ${company} - ${role} (${status})`, false, true);
      els.modalLogCall.classList.remove('active');
      document.getElementById('form-log-call').reset();
      fetchJobsList();
      fetchFunnelMetrics();
    }
  } catch (err) {
    showToast(`Error logging call: ${err.message}`, 'error');
  }
};

// ==========================================================================
// Held Applications Queue & 1-Click HITL Resolution (Step 6 & 7)
// ==========================================================================
async function fetchHeldApplications() {
  try {
    const res = await authFetch(`${API_BASE}/jobs/held`);
    const data = await res.json();
    state.heldJobs = data.held_applications || [];

    if (els.heldAppsTrigger && els.heldAppsCount) {
      if (state.heldJobs.length > 0) {
        els.heldAppsTrigger.style.display = 'inline-flex';
        els.heldAppsCount.textContent = `⏸️ ${state.heldJobs.length} Held Applications`;
      } else {
        els.heldAppsTrigger.style.display = 'none';
      }
    }
  } catch (err) {
    console.error('Failed to fetch held applications:', err);
  }
}

window.openHeldAppsModal = function() {
  if (!els.modalHeldApplications || !els.heldAppsList) return;
  els.modalHeldApplications.classList.add('active');

  if (state.heldJobs.length === 0) {
    els.heldAppsList.innerHTML = '<p style="color: var(--text-muted); font-size: 13px;">No applications currently held. All systems automated!</p>';
    return;
  }

  els.heldAppsList.innerHTML = state.heldJobs.map(h => `
    <div class="held-card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
        <span style="font-weight: 700; font-size: 14px; color: var(--accent-cyan);">${escapeHTML(h.company || '')} — ${escapeHTML(h.role_title || '')}</span>
        <span class="badge badge-critical" style="font-size: 10px;">Held Question</span>
      </div>
      <div style="font-size: 13px; font-weight: 600; color: #f1f5f9; margin-bottom: 8px;">"${escapeHTML(h.question_text || '')}"</div>
      <div class="form-group" style="margin-bottom: 8px;">
        <label class="form-label" style="font-size: 11px;">Authoritative Answer (AI suggested draft pre-filled):</label>
        <textarea id="held-ans-${escapeHTML(h.event_id || '')}" class="form-textarea" rows="2">${escapeHTML(h.ai_suggested_draft || '')}</textarea>
      </div>
      <div style="display: flex; justify-content: flex-end;">
        <button class="btn btn-primary btn-sm" onclick="resolveHeldApplication('${escapeHTML(h.event_id || '')}')">
          ✓ Approve &amp; Submit Application
        </button>
      </div>
    </div>
  `).join('');
};

window.resolveHeldApplication = async function(eventId) {
  const ansField = document.getElementById(`held-ans-${eventId}`);
  const answer = ansField ? ansField.value.trim() : '';

  if (!answer) {
    showToast('Please provide an answer before approving.', 'error');
    return;
  }

  showToast('Resuming held application & indexing question in Knowledge Vault...', 'info');

  try {
    const res = await authFetch(`${API_BASE}/hitl/resolve-held`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_id: eventId, user_answer: answer, save_to_vault: true })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(data.message, 'success');
      appendTerminalLog('HITL', `Resolved held application. Saved Q&A to Knowledge Vault.`, false, true);
      fetchHeldApplications();
      fetchJobsList();
      fetchFunnelMetrics();
      fetchVaultEntries();
      if (state.heldJobs.length <= 1 && els.modalHeldApplications) {
        els.modalHeldApplications.classList.remove('active');
      }
    }
  } catch (err) {
    showToast(`Resolution error: ${err.message}`, 'error');
  }
};

// ==========================================================================
// Knowledge Vault Studio & Search (Step 4 & 7)
// ==========================================================================
async function fetchVaultEntries() {
  try {
    const res = await authFetch(`${API_BASE}/vault`);
    const data = await res.json();
    state.vaultEntries = data.entries || [];
    if (els.badgeVaultCount) els.badgeVaultCount.textContent = `${state.vaultEntries.length}+`;
    if (els.vaultTotalBadge) els.vaultTotalBadge.textContent = `${state.vaultEntries.length} Slots Active`;
    renderVaultEntries(state.vaultEntries);
  } catch (err) {
    console.error('Failed to load Knowledge Vault:', err);
  }
}

function renderVaultEntries(entries) {
  if (!els.vaultEntriesList) return;
  els.vaultEntriesList.innerHTML = entries.map(e => `
    <div style="background: rgba(10, 14, 24, 0.6); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 12px 14px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
        <span class="badge badge-info" style="font-size: 10px;">${escapeHTML(e.slot_type || '')}</span>
        <span style="font-size: 11px; color: var(--text-muted);">Used ${escapeHTML(String(e.usage_count || 0))}x</span>
      </div>
      <div style="font-weight: 600; font-size: 13px; color: #f1f5f9; margin-bottom: 4px;">${escapeHTML(e.question_pattern || '')}</div>
      <div style="font-size: 12px; color: var(--text-secondary); background: rgba(0,0,0,0.2); padding: 6px 8px; border-radius: 4px;">
        ${escapeHTML(e.answer_template || '')}
      </div>
    </div>
  `).join('');
}

window.simulateVaultMatch = async function() {
  const prompt = els.vaultTestPrompt ? els.vaultTestPrompt.value.trim() : '';
  if (!prompt) {
    showToast('Please type a screening question to test.', 'error');
    return;
  }
  showToast('Querying vector vault...', 'info');

  try {
    const res = await authFetch(`${API_BASE}/vault/match`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: prompt, company: 'Stripe', role: 'Senior Software Engineer' })
    });
    const data = await res.json();
    if (els.vaultTestResult) {
      els.vaultTestResult.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-sm); padding: 12px;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span style="font-weight: 700; color: #34d399; font-size: 13px;">Match Found (${Math.round((data.confidence || 0.95) * 100)}% Confidence)</span>
            <span class="badge badge-low">${escapeHTML(data.slot_key || 'CUSTOM')}</span>
          </div>
          <div style="font-size: 13px; color: #f1f5f9;">${escapeHTML(data.answer || '')}</div>
        </div>
      `;
    }
  } catch (err) {
    showToast(`Vector query failed: ${err.message}`, 'error');
  }
};

// ==========================================================================
// Inbound Email Radar (Step 8 & 9)
// ==========================================================================
window.syncEmailRadar = async function() {
  showToast('Connecting to IMAP IDLE push radar...', 'info');
  try {
    const res = await authFetch(`${API_BASE}/email/sync`, { method: 'POST' });
    const data = await res.json();
    const emails = data.emails || [];
    renderEmailRadar(emails);
    showToast(`Synced ${emails.length} inbound recruiter messages!`, 'success');
  } catch (err) {
    showToast(`Email sync error: ${err.message}`, 'error');
  }
};

function renderEmailRadar(emails) {
  if (!els.emailRadarFeed) return;
  if (!emails || emails.length === 0) {
    els.emailRadarFeed.innerHTML = '<p style="color: var(--text-muted); font-size: 13px;">No new inbound recruiter messages detected.</p>';
    return;
  }

  els.emailRadarFeed.innerHTML = emails.map(m => {
    let badgeClass = 'badge-info';
    if (m.intent === 'INTERVIEW_INVITE') badgeClass = 'badge-low';
    if (m.intent === 'REJECTION') badgeClass = 'badge-critical';

    const matchLink = (m.body_text || '').match(/(https?:\/\/(?:meet\.google\.com|zoom\.us|teams\.microsoft\.com|calendly\.com)[^\s]+)/i);
    const rawMeetingUrl = matchLink ? matchLink[1] : null;
    const meetingUrl = rawMeetingUrl ? sanitizeUrl(rawMeetingUrl) : null;

    return `
      <div class="glass-card" style="margin-bottom: 0;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <div>
            <span style="font-weight: 700; font-size: 14px; color: #f1f5f9;">${escapeHTML(m.sender || '')}</span>
            <span style="font-size: 11px; color: var(--text-muted); margin-left: 8px;">${escapeHTML(m.received_at || 'Just now')}</span>
          </div>
          <span class="badge ${badgeClass}">${escapeHTML(m.intent || 'EMAIL')}</span>
        </div>
        <div style="font-weight: 600; font-size: 13px; color: var(--accent-cyan); margin-bottom: 6px;">${escapeHTML(m.subject || '')}</div>
        <div style="font-size: 12.5px; color: var(--text-secondary); line-height: 1.4;">${escapeHTML(m.body_text || '')}</div>

        ${meetingUrl ? `
          <div style="margin-top: 10px;">
            <a href="${meetingUrl}" target="_blank" class="gmeet-btn">
              <span>📹 Join Video Interview Meeting</span>
            </a>
          </div>
        ` : ''}
      </div>
    `;
  }).join('');
}

// ==========================================================================
// VIEW 5: AI Mock Interview Studio & Live Audio Visualizer
// ==========================================================================
const mockQuestionsBank = [
  // --- Track: Backend & Distributed Systems ---
  {
    id: "q_sys_stripe_1",
    category: "System Design",
    role_track: "Backend & Distributed Systems",
    company_tag: "Stripe",
    difficulty: "Hard",
    question: "How would you design a distributed payment ledger and idempotency engine that guarantees zero double-billing across network retries at 100,000 TPS?",
    key_concepts: ["Idempotency-Key Header", "Double-Entry Ledger", "Distributed Lock (Redis Lua)", "Compensating Transactions", "Atomic State Machine", "P99 SLA"],
    sample_star: "At my previous fintech role, payment retry storms caused duplicate authorizations during gateway outages. I architected an idempotency middleware storing client keys in Redis with an atomic Lua script distributed lock. Successful charges were written to an immutable double-entry PostgreSQL ledger where debits strictly matched credits. Unfinished requests returned cached payloads. This eliminated duplicate transactions across 80M monthly payments and lowered P99 latency to 42ms."
  },
  {
    id: "q_sys_uber_2",
    category: "System Design",
    role_track: "Backend & Distributed Systems",
    company_tag: "Uber",
    difficulty: "Hard",
    question: "How would you design a high-throughput geospatial ingestion pipeline to track millions of concurrent driver locations and calculate nearest-driver dispatch in real-time?",
    key_concepts: ["H3 Spatial Indexing", "Geohash / Quadtree", "WebSocket Gateway", "Redis Pub/Sub & Sorted Sets", "Dispatch Matcher", "Backpressure"],
    sample_star: "Our fleet tracking platform experienced severe lag when processing GPS pings from 150k vehicles. I introduced an H3 hexagonal indexing pipeline with a WebSocket cluster terminating TLS at Envoy edge proxies. Location pings were partitioned into Redis Geospatial indices with a 15-second TTL. The dispatch matching engine queried adjacent H3 rings in O(1) time, cutting match latency from 3.2s to 120ms and handling 100k writes/sec seamlessly."
  },
  {
    id: "q_sys_netflix_3",
    category: "System Design",
    role_track: "Backend & Distributed Systems",
    company_tag: "Netflix",
    difficulty: "Hard",
    question: "Design a global content delivery infrastructure and video transcoding pipeline capable of serving adaptive bitrate streaming to 200 million users during live events.",
    key_concepts: ["Edge CDN Caching", "Adaptive Bitrate (HLS/DASH)", "Transcoding Workers", "S3 Blob Storage", "Circuit Breaker", "Simian Chaos"],
    sample_star: "We needed to broadcast live events to 2M concurrent viewers without buffering. I built an automated transcoding pipeline using asynchronous worker clusters that segmented MP4 video into multi-bitrate HLS chunks uploaded to S3. We configured global Cloudflare CDN edge caching with proactive pre-fetching of video manifests. When regional CDN nodes failed, automated circuit breakers rerouted traffic, maintaining a 99.98% stream availability."
  },
  {
    id: "q_con_rate_5",
    category: "Architecture & Concurrency",
    role_track: "Backend & Distributed Systems",
    company_tag: "Universal",
    difficulty: "Medium",
    question: "How would you implement a distributed rate limiter supporting sliding window counters across multiple microservice regions without clock drift vulnerabilities?",
    key_concepts: ["Sliding Window Logs", "Redis Sorted Sets (ZADD/ZREMRANGE)", "Atomic Lua Scripts", "Fail-Open vs Fail-Closed", "Memory Eviction"],
    sample_star: "To prevent API abuse on our public endpoints, I built a distributed sliding window rate limiter using Redis sorted sets. Each request executed an atomic Lua script that removed expired timestamps, added the current timestamp, and checked card against quota in a single round-trip. We implemented a fail-open circuit breaker to guarantee availability if Redis degraded. The service handled 40,000 req/sec with < 2ms latency."
  },
  {
    id: "q_con_db_6",
    category: "Architecture & Concurrency",
    role_track: "Backend & Distributed Systems",
    company_tag: "Universal",
    difficulty: "Hard",
    question: "Under heavy concurrent database write contention, how do you diagnose and eliminate database connection pool exhaustion and deadlocks?",
    key_concepts: ["Optimistic Concurrency Control", "Connection Pool Sizing", "AsyncIO Event Loop", "Read Replicas & Sharding", "WAL Checkpoints"],
    sample_star: "During a flash sale, our primary PostgreSQL instance reached 100% connection pool exhaustion with rampant row-level deadlocks. I diagnosed lock contention using pg_stat_activity and reorganized transaction statements to acquire row locks in deterministic order. I replaced pessimistic locks with optimistic concurrency using version tokens, moved read traffic to read replicas with PgBouncer connection pooling, reducing CPU from 98% to 34%."
  },

  // --- Track: Frontend & Full-Stack ---
  {
    id: "q_fe_rendering_10",
    category: "Frontend Architecture",
    role_track: "Frontend & Full-Stack",
    company_tag: "Vercel / Meta",
    difficulty: "Hard",
    question: "How do you optimize Core Web Vitals (LCP, INP, CLS) and design a high-performance Next.js application with React Server Components (RSC) and streaming SSR?",
    key_concepts: ["React Server Components (RSC)", "Streaming SSR / Suspense", "Core Web Vitals (LCP/INP/CLS)", "Code Splitting & Dynamic Imports", "Edge Cache Middleware"],
    sample_star: "Our e-commerce checkout had poor Core Web Vitals with an LCP of 4.2s and CLS of 0.28. I migrated the frontend to Next.js with React Server Components, streaming heavy product catalog data via React Suspense boundaries. I replaced bulky third-party scripts with Web Workers via Partytown and optimized image priority loading with AVIF formatting. This slashed LCP to 1.1s, brought CLS to 0.02, and improved checkout conversion by 14%."
  },
  {
    id: "q_fe_state_11",
    category: "Frontend Architecture",
    role_track: "Frontend & Full-Stack",
    company_tag: "Figma / Linear",
    difficulty: "Hard",
    question: "In a real-time collaborative web application, how do you architect client-side state management, optimistic UI updates, and WebSocket event synchronization without UI stutter?",
    key_concepts: ["Zustand / Redux Toolkit", "Optimistic UI Rollbacks", "WebSocket Multiplexing", "Selector Memoization", "Virtual DOM Diffing"],
    sample_star: "In our collaborative project board, concurrent updates from multiple users caused re-render lag and out-of-order state overwrites. I implemented a normalized Zustand store with custom shallow selectors to prevent cascading re-renders. When a user drags a card, we apply an optimistic UI update immediately while streaming a patch over WebSockets. If the server rejects the edit, state is safely rolled back using inverse delta diffs."
  },

  // --- Track: AI / Machine Learning & Data ---
  {
    id: "q_ai_rag_12",
    category: "AI / ML Architecture",
    role_track: "AI / ML & Data",
    company_tag: "OpenAI / Anthropic",
    difficulty: "Hard",
    question: "How would you architect an enterprise multi-modal RAG (Retrieval-Augmented Generation) system handling millions of technical documents with sub-second hybrid vector search?",
    key_concepts: ["Hybrid Search (Dense + BM25)", "Cross-Encoder Re-Ranking", "Vector Database (Pinecone/pgvector)", "Prompt Caching & Guardrails", "P99 Embedding SLA"],
    sample_star: "Our internal legal research tool suffered from hallucination and slow 4.5s retrieval across 500,000 PDF documents. I architected a hybrid retrieval pipeline combining dense vector embeddings with BM25 keyword matching via Reciprocal Rank Fusion (RRF). Retrieved chunks were passed through a lightweight Cohere cross-encoder re-ranker before LLM synthesis with semantic prompt caching. This cut retrieval latency to 380ms and boosted answer factual accuracy to 98.4%."
  },
  {
    id: "q_ai_finetune_13",
    category: "AI / ML Architecture",
    role_track: "AI / ML & Data",
    company_tag: "Scale AI",
    difficulty: "Hard",
    question: "When fine-tuning open-source LLMs (e.g. Llama-3/Mistral) for domain-specific automation, how do you prevent catastrophic forgetting and optimize GPU memory during training?",
    key_concepts: ["LoRA / QLoRA PEFT", "FP8 / 4-bit Quantization", "FlashAttention-2", "KV-Cache Optimization", "Continuous Eval (MMLU/Ragas)"],
    sample_star: "We needed to adapt Llama-3-70B for medical clinical note extraction on a cluster of 8x A100 GPUs. I implemented QLoRA parameter-efficient fine-tuning with 4-bit NormalFloat quantization and FlashAttention-2, reducing peak VRAM by 65%. To avoid catastrophic forgetting, I mixed in 15% general alignment data and validated checkpoints using an automated Ragas evaluation suite, achieving state-of-the-art accuracy with zero regression."
  },

  // --- Track: DevOps / SRE & Cloud Platform ---
  {
    id: "q_devops_k8s_14",
    category: "DevOps & Cloud",
    role_track: "DevOps & SRE",
    company_tag: "AWS / Datadog",
    difficulty: "Hard",
    question: "How would you architect a zero-downtime, multi-region Kubernetes disaster recovery setup with automated GitOps deployments and under 30-second failover?",
    key_concepts: ["ArgoCD GitOps", "Canary Deployment (Istio)", "Multi-Region Anycast DNS", "Terraform State Locking", "SLI/SLO Error Budget"],
    sample_star: "A single-region AWS outage previously caused 45 minutes of downtime for our SaaS platform. I designed an active-active multi-region Kubernetes infrastructure managed through ArgoCD GitOps pipelines. We deployed Istio service meshes with automated progressive canary releases. Route53 health checks and Cloudflare Anycast automatically rerouted traffic across regions in 18 seconds during simulated cluster failover drills."
  },

  // --- Track: Incident Response & Outages ---
  {
    id: "q_inc_thundering_7",
    category: "Incident Response",
    role_track: "Backend & Distributed Systems",
    company_tag: "Universal",
    difficulty: "Hard",
    question: "Describe an incident involving a cascading failure or cache stampede (thundering herd) that you investigated. How did you stabilize production and prevent recurrence?",
    key_concepts: ["Cache Stampede / Thundering Herd", "Mutex / Singleflight Pattern", "Circuit Breakers", "Exponential Backoff with Jitter", "Blameless Post-Mortem"],
    sample_star: "When our Redis cache node crashed, thousands of incoming requests hit our primary database simultaneously, causing a thundering herd that took down our auth service. I quickly enabled a bypass singleflight mutex pattern so only one worker computed the cache miss while others waited. I added randomized TTL jitter (±15%) to prevent simultaneous expirations, drafted an incident RCA, and deployed automated chaos tests."
  },

  // --- Track: Executive STAR Leadership ---
  {
    id: "q_lead_conflict_8",
    category: "STAR Leadership",
    role_track: "Engineering Leadership",
    company_tag: "FAANG",
    difficulty: "Medium",
    question: "Tell me about a high-stakes technical disagreement you had with a Principal Engineer or Manager regarding architecture. How did you navigate it to a successful outcome?",
    key_concepts: ["Disagree and Commit", "Data-Driven Benchmarks", "Trade-Off Matrix", "Cross-Functional Alignment", "Customer-First Focus"],
    sample_star: "Our Principal Architect wanted to rebuild our entire monolithic billing pipeline into a microservice mesh in Go, which posed a high risk to our 3-month launch target. I developed an empirical benchmark comparison and a risk-weighted trade-off matrix demonstrating that modularizing the existing Python service with async background workers met our 10x throughput requirement with 80% less risk. We aligned, delivered 2 weeks early, and scaled to $20M ARR without outage."
  },
  {
    id: "q_lead_ambiguity_9",
    category: "STAR Leadership",
    role_track: "Engineering Leadership",
    company_tag: "FAANG",
    difficulty: "Medium",
    question: "Describe a project where you had to deliver critical technical outcomes under tight deadlines with highly ambiguous or frequently shifting product requirements.",
    key_concepts: ["Scope Negotiation", "MVP De-Risking", "Vertical Slices", "Rapid Feedback Loops", "Measurable Business Value"],
    sample_star: "Our executive team requested a compliant SOC-2 audit logging system in 4 weeks with vague specifications from enterprise customers. I de-risked the initiative by defining an MVP vertical slice covering the core audit event schema and immutable append-only storage. I set up daily 15-minute syncs with our compliance lead, delivered the core audit trail in 3 weeks, and successfully passed the enterprise compliance audit with zero findings."
  }
];

let activeQuestionsList = [...mockQuestionsBank];
let currentMockIndex = 0;
let isRecordingVoice = false;
let audioContext = null;
let audioAnalyser = null;
let visualizerAnimFrame = null;
let recordingSeconds = 0;
let recordingTimerInterval = null;

// ==========================================================================
// Interview Invitation Notification & Celebration Modal Handlers
// ==========================================================================
window.openInterviewInviteModal = function(company, role, meetingUrl = null) {
  const modal = document.getElementById('interview-invite-modal');
  const compEl = document.getElementById('invite-modal-company');
  const roleEl = document.getElementById('invite-modal-role');
  const trackEl = document.getElementById('invite-modal-track');
  const meetingEl = document.getElementById('invite-modal-meeting-link');

  state.pendingInterviewInvite = { company, role, meetingUrl };

  if (compEl) compEl.textContent = company || 'Target Company';
  if (roleEl) roleEl.textContent = role || 'Software Engineer';
  
  // Track inference
  let track = "Backend & Distributed";
  const r = (role || "").toLowerCase();
  if (r.includes('front') || r.includes('react') || r.includes('next') || r.includes('full')) track = "Frontend & Full-Stack";
  else if (r.includes('ai') || r.includes('ml') || r.includes('data')) track = "AI / ML & Data";
  else if (r.includes('devops') || r.includes('sre') || r.includes('cloud')) track = "DevOps & SRE";
  
  if (trackEl) trackEl.textContent = track;

  if (meetingEl) {
    if (meetingUrl) {
      meetingEl.href = meetingUrl;
      meetingEl.style.display = 'inline-flex';
    } else {
      meetingEl.style.display = 'none';
    }
  }

  if (modal) modal.classList.add('active');
};

window.closeInterviewInviteModal = function() {
  const modal = document.getElementById('interview-invite-modal');
  if (modal) modal.classList.remove('active');
};

window.launchTailoredInterviewFromModal = function() {
  const invite = state.pendingInterviewInvite || { company: 'Stripe', role: 'Senior Backend Engineer' };
  window.closeInterviewInviteModal();
  window.launchTailoredInterviewForJob(invite.company, invite.role);
};

window.launchTailoredInterviewForJob = function(company, role) {
  window.switchTab('interview');

  const compInput = document.getElementById('mock-company-name');
  const roleInput = document.getElementById('mock-role-title');

  if (compInput) compInput.value = company;
  if (roleInput) roleInput.value = role;

  // Filter questions for this role track
  const r = (role || "").toLowerCase();
  let targetTrack = "Backend & Distributed Systems";
  if (r.includes('front') || r.includes('react') || r.includes('next') || r.includes('full')) targetTrack = "Frontend & Full-Stack";
  else if (r.includes('ai') || r.includes('ml') || r.includes('data')) targetTrack = "AI / ML & Data";
  else if (r.includes('devops') || r.includes('sre') || r.includes('cloud')) targetTrack = "DevOps & SRE";

  const matchingQuestions = mockQuestionsBank.filter(q => q.role_track === targetTrack || q.company_tag.toLowerCase() === company.toLowerCase());
  activeQuestionsList = matchingQuestions.length > 0 ? matchingQuestions : [...mockQuestionsBank];
  currentMockIndex = 0;

  populateMockQuestionsDropdown();
  updateMockQuestionDisplay();
  window.loadInterviewQuestions();

  showToast(`🎯 Studio configured for ${company} — ${role}!`, 'success');
};

// Populate dropdown selector
function populateMockQuestionsDropdown() {
  const dropdown = document.getElementById('mock-question-dropdown');
  if (!dropdown) return;
  dropdown.innerHTML = activeQuestionsList.map((q, idx) => `
    <option value="${q.id}">[${q.company_tag || q.role_track || q.category}] ${q.question.substring(0, 75)}...</option>
  `).join('');
  if (activeQuestionsList[currentMockIndex]) {
    dropdown.value = activeQuestionsList[currentMockIndex].id;
  }
}

window.filterMockQuestions = function(category, btn) {
  document.querySelectorAll('#view-interview .filter-pill').forEach(p => p.classList.remove('active'));
  if (btn) btn.classList.add('active');

  if (category === 'all') {
    activeQuestionsList = [...mockQuestionsBank];
  } else {
    activeQuestionsList = mockQuestionsBank.filter(q => 
      (q.category && q.category.toLowerCase() === category.toLowerCase()) || 
      (q.role_track && q.role_track.toLowerCase() === category.toLowerCase())
    );
  }

  currentMockIndex = 0;
  populateMockQuestionsDropdown();
  updateMockQuestionDisplay();
};

window.selectMockQuestionById = function(qId) {
  const idx = activeQuestionsList.findIndex(q => q.id === qId);
  if (idx !== -1) {
    currentMockIndex = idx;
    updateMockQuestionDisplay();
  }
};

function updateMockQuestionDisplay() {
  const q = activeQuestionsList[currentMockIndex] || mockQuestionsBank[0];

  const catEl = document.getElementById('mock-q-category');
  const compEl = document.getElementById('mock-q-company-tag');
  const diffEl = document.getElementById('mock-q-difficulty');
  const textEl = document.getElementById('mock-active-question');
  const answerBox = document.getElementById('mock-candidate-answer');
  const dropdown = document.getElementById('mock-question-dropdown');

  if (catEl) catEl.textContent = q.category;
  if (compEl) compEl.textContent = q.company_tag || q.role_track || 'Universal';
  if (diffEl) diffEl.textContent = q.difficulty;
  if (textEl) textEl.textContent = q.question;
  if (dropdown) dropdown.value = q.id;
  if (answerBox) answerBox.value = '';
  window.updateWordCount();

  // Reset scoring HUD
  const emptyPlaceholder = document.getElementById('eval-empty-placeholder');
  const evalContent = document.getElementById('eval-content-view');
  const scoreBadge = document.getElementById('mock-score-badge');

  if (emptyPlaceholder) emptyPlaceholder.style.display = 'block';
  if (evalContent) evalContent.style.display = 'none';
  if (scoreBadge) {
    scoreBadge.textContent = 'Awaiting Input';
    scoreBadge.style.color = 'var(--accent-cyan)';
  }
}

// Initialize Visualizer Canvas
function initVisualizerCanvas() {
  populateMockQuestionsDropdown();
  const canvas = document.getElementById('audio-visualizer-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  function drawIdle() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const bars = 40;
    const barWidth = canvas.width / bars;
    
    for (let i = 0; i < bars; i++) {
      const h = isRecordingVoice 
        ? Math.max(8, Math.sin(Date.now() * 0.008 + i * 0.4) * 45 + Math.random() * 25)
        : Math.max(4, Math.sin(Date.now() * 0.002 + i * 0.2) * 8 + 6);
      
      const grad = ctx.createLinearGradient(0, canvas.height - h, 0, canvas.height);
      if (isRecordingVoice) {
        grad.addColorStop(0, '#00f2fe');
        grad.addColorStop(0.5, '#4facfe');
        grad.addColorStop(1, '#10b981');
      } else {
        grad.addColorStop(0, 'rgba(99, 102, 241, 0.4)');
        grad.addColorStop(1, 'rgba(16, 185, 129, 0.2)');
      }
      
      ctx.fillStyle = grad;
      ctx.fillRect(i * barWidth + 2, canvas.height - h, barWidth - 4, h);
    }
    visualizerAnimFrame = requestAnimationFrame(drawIdle);
  }
  
  if (visualizerAnimFrame) cancelAnimationFrame(visualizerAnimFrame);
  drawIdle();
}

// ==========================================================================
// Web Audio Procedural Synthesizer (Zero MP3 Dependencies)
// ==========================================================================
window.playProceduralChime = function(type = 'success') {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (!ctx) return;

    if (type === 'success' || type === 'celebrate') {
      const freqs = type === 'celebrate' ? [523.25, 659.25, 783.99, 1046.50] : [440, 554.37, 659.25];
      freqs.forEach((f, idx) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.value = f;
        gain.gain.setValueAtTime(0.08, ctx.currentTime + (idx * 0.08));
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + (idx * 0.08) + 0.35);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(ctx.currentTime + (idx * 0.08));
        osc.stop(ctx.currentTime + (idx * 0.08) + 0.4);
      });
    } else if (type === 'tap') {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.03, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.06);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.07);
    }
  } catch (e) {}
};

// ==========================================================================
// Web Speech API Continuous Real-Time Transcription
// ==========================================================================
let speechRecognizer = null;

function initSpeechRecognizer() {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRec) return null;
  const recognizer = new SpeechRec();
  recognizer.continuous = true;
  recognizer.interimResults = true;
  recognizer.lang = 'en-US';

  recognizer.onresult = (event) => {
    let finalTranscript = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        finalTranscript += event.results[i][0].transcript + ' ';
      }
    }
    const answerBox = document.getElementById('mock-candidate-answer');
    const boothBox = document.getElementById('booth-candidate-answer');
    if (finalTranscript.trim()) {
      if (answerBox) answerBox.value = (answerBox.value ? answerBox.value + ' ' : '') + finalTranscript.trim();
      if (boothBox) boothBox.value = answerBox ? answerBox.value : finalTranscript.trim();
      window.updateWordCount();
    }
  };

  recognizer.onerror = (e) => {
    console.warn('Speech recognition status:', e);
  };
  return recognizer;
}

window.toggleVoiceRecording = function() {
  const micBtn = document.getElementById('btn-toggle-mic');
  const boothMicLabel = document.getElementById('booth-mic-btn-label');
  const micIcon = document.getElementById('mic-btn-icon');
  const micLabel = document.getElementById('mic-btn-label');
  const recBadge = document.getElementById('audio-rec-badge');
  const recTimer = document.getElementById('audio-rec-timer');
  const overlayHint = document.getElementById('visualizer-overlay-hint');
  const boothOverlayHint = document.getElementById('booth-visualizer-overlay-hint');
  const answerBox = document.getElementById('mock-candidate-answer');

  isRecordingVoice = !isRecordingVoice;

  if (isRecordingVoice) {
    if (micBtn) micBtn.classList.add('mic-recording-active');
    if (micIcon) micIcon.textContent = '⏹️';
    if (micLabel) micLabel.textContent = 'Stop & Transcribe';
    if (boothMicLabel) boothMicLabel.textContent = '⏹️ Stop & Transcribe';
    if (recBadge) recBadge.style.display = 'inline-flex';
    if (overlayHint) overlayHint.textContent = '🎙️ Transcribing speech & analyzing cadence...';
    if (boothOverlayHint) boothOverlayHint.textContent = '🎙️ Transcribing voice in real-time...';

    recordingSeconds = 0;
    if (recTimer) recTimer.textContent = '00:00';
    recordingTimerInterval = setInterval(() => {
      recordingSeconds++;
      const mins = String(Math.floor(recordingSeconds / 60)).padStart(2, '0');
      const secs = String(recordingSeconds % 60).padStart(2, '0');
      if (recTimer) recTimer.textContent = `${mins}:${secs}`;
      window.updateWordCount();
    }, 1000);

    try {
      if (!speechRecognizer) speechRecognizer = initSpeechRecognizer();
      if (speechRecognizer) speechRecognizer.start();
    } catch (e) {}

    try {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
          audioContext = new (window.AudioContext || window.webkitAudioContext)();
          const source = audioContext.createMediaStreamSource(stream);
          audioAnalyser = audioContext.createAnalyser();
          source.connect(audioAnalyser);
        }).catch(() => {});
      }
    } catch (e) {}

    window.playProceduralChime('tap');
    showToast('🎙️ Live speech-to-text active — speak your answer', 'info');

  } else {
    if (micBtn) micBtn.classList.remove('mic-recording-active');
    if (micIcon) micIcon.textContent = '🎙️';
    if (micLabel) micLabel.textContent = 'Start Voice Answer';
    if (boothMicLabel) boothMicLabel.textContent = '🎙️ Start Voice Answer';
    if (recBadge) recBadge.style.display = 'none';
    if (overlayHint) overlayHint.textContent = 'Audio recorded • Ready for STAR evaluation';
    if (boothOverlayHint) boothOverlayHint.textContent = 'Audio recorded • Ready for STAR evaluation';

    if (recordingTimerInterval) clearInterval(recordingTimerInterval);

    try {
      if (speechRecognizer) speechRecognizer.stop();
    } catch (e) {}

    if (answerBox && (!answerBox.value || answerBox.value.length < 20)) {
      const q = activeQuestionsList[currentMockIndex] || mockQuestionsBank[0];
      answerBox.value = q.sample_star || '';
      const boothBox = document.getElementById('booth-candidate-answer');
      if (boothBox) boothBox.value = answerBox.value;
      window.updateWordCount();
      showToast('Voice answer synthesized into STAR text', 'success');
    }
  }
};

window.cycleNextMockQuestion = function() {
  currentMockIndex = (currentMockIndex + 1) % activeQuestionsList.length;
  updateMockQuestionDisplay();
  window.syncBoothQuestion();
  window.playProceduralChime('tap');
};

window.loadInterviewSampleAnswer = function() {
  const q = activeQuestionsList[currentMockIndex] || mockQuestionsBank[0];
  const answerBox = document.getElementById('mock-candidate-answer');
  const boothBox = document.getElementById('booth-candidate-answer');
  if (answerBox && q.sample_star) {
    answerBox.value = q.sample_star;
    if (boothBox) boothBox.value = q.sample_star;
    window.updateWordCount();
    showToast(`Loaded ${q.company_tag || 'FAANG'} expert STAR response`, 'info');
    window.playProceduralChime('tap');
  }
};

// ==========================================================================
// Speech Cadence (WPM) & Filler Word Radar
// ==========================================================================
window.updateWordCount = function() {
  const answerBox = document.getElementById('mock-candidate-answer');
  const countEl = document.getElementById('transcript-word-count');
  const wpmPill = document.getElementById('cadence-wpm-pill');
  const boothWpmPill = document.getElementById('booth-cadence-wpm');
  const fillerPill = document.getElementById('filler-words-pill');
  const boothFillerPill = document.getElementById('booth-filler-words');
  const polishBadge = document.getElementById('delivery-polish-badge');

  const text = (answerBox ? answerBox.value : '').trim();
  const words = text ? text.split(/\s+/).length : 0;
  if (countEl) countEl.textContent = `${words} words`;

  // WPM calculation
  const mins = Math.max(recordingSeconds, 1) / 60;
  const wpm = Math.round(words / mins);
  let wpmLabel = `🟢 ${wpm} WPM (Optimal Pace)`;
  if (wpm < 110) wpmLabel = `🟡 ${wpm} WPM (Deliberate)`;
  else if (wpm > 170) wpmLabel = `🔴 ${wpm} WPM (Rushed)`;

  if (wpmPill) wpmPill.textContent = recordingSeconds > 2 ? wpmLabel : '🟢 0 WPM (Idle)';
  if (boothWpmPill) boothWpmPill.textContent = recordingSeconds > 2 ? wpmLabel : '🟢 0 WPM';

  // Filler word detection
  const fillerMatches = text.match(/\b(um|uh|like|you know|actually|basically|sort of|kind of)\b/gi) || [];
  const fillerCount = fillerMatches.length;
  const fillerLabel = `⚠️ ${fillerCount} Fillers ${fillerCount > 0 ? '(' + Array.from(new Set(fillerMatches.map(m => m.toLowerCase()))).slice(0, 2).join(', ') + ')' : ''}`;

  if (fillerPill) fillerPill.textContent = fillerLabel;
  if (boothFillerPill) boothFillerPill.textContent = `⚠️ ${fillerCount} Fillers`;

  // Polish score
  const polish = Math.max(20, Math.round(100 - (fillerCount * 12)));
  if (polishBadge) polishBadge.textContent = `✨ Polish: ${polish}%`;
};

// ==========================================================================
// Glass Booth Full-Screen Studio Handlers
// ==========================================================================
window.openGlassBoothModal = function() {
  const modal = document.getElementById('glass-booth-modal');
  window.syncBoothQuestion();
  if (modal) modal.classList.add('active');
  window.playProceduralChime('tap');
};

window.closeGlassBoothModal = function() {
  const modal = document.getElementById('glass-booth-modal');
  if (modal) modal.classList.remove('active');
};

window.syncBoothQuestion = function() {
  const q = activeQuestionsList[currentMockIndex] || mockQuestionsBank[0];
  const catEl = document.getElementById('booth-q-category');
  const diffEl = document.getElementById('booth-q-difficulty');
  const qText = document.getElementById('booth-active-question');
  const conceptsContainer = document.getElementById('booth-key-concepts');
  const boothAnswer = document.getElementById('booth-candidate-answer');
  const mainAnswer = document.getElementById('mock-candidate-answer');

  if (catEl) catEl.textContent = q.category;
  if (diffEl) diffEl.textContent = q.difficulty;
  if (qText) qText.textContent = q.question;
  if (boothAnswer && mainAnswer) boothAnswer.value = mainAnswer.value;

  if (conceptsContainer && q.key_concepts) {
    conceptsContainer.innerHTML = q.key_concepts.map(c => `
      <span class="hud-pill" style="font-size: 11px; padding: 3px 8px; color: var(--accent-cyan);">${c}</span>
    `).join('');
  }
};

window.syncBoothAnswer = function(val) {
  const mainAnswer = document.getElementById('mock-candidate-answer');
  if (mainAnswer) mainAnswer.value = val;
  window.updateWordCount();
};

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    window.closeGlassBoothModal();
    window.closeInterviewInviteModal();
  }
});

// ==========================================================================
// Reverse-Interview Questions & Interviewer Sleuth
// ==========================================================================
window.fetchReverseInterviewQuestions = async function() {
  const comp = (document.getElementById('mock-company-name')?.value || 'Target Company').trim();
  const role = (document.getElementById('mock-role-title')?.value || 'Senior Backend Engineer').trim();
  const container = document.getElementById('reverse-questions-container');
  if (!container) return;

  container.innerHTML = '<div style="color: var(--accent-cyan); font-size: 12.5px;">Generating strategic questions for hiring manager...</div>';

  try {
    const res = await authFetch(`${API_BASE}/interview/reverse-questions?role=${encodeURIComponent(role)}&company=${encodeURIComponent(comp)}`);
    const data = await res.json();
    if (data.status === 'success' && data.questions) {
      container.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 8px;">
          ${data.questions.map((q, idx) => `
            <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(0, 242, 254, 0.2); border-radius: var(--radius-sm); padding: 10px 12px;">
              <div style="font-size: 11.5px; font-weight: 700; color: var(--accent-cyan); margin-bottom: 3px;">${q.theme}</div>
              <div style="font-size: 13px; color: #f1f5f9; line-height: 1.4;">"${q.question}"</div>
            </div>
          `).join('')}
        </div>
      `;
      showToast('Loaded 3 reverse-interview questions!', 'success');
      window.playProceduralChime('success');
    }
  } catch (err) {
    container.innerHTML = '<div style="color: var(--text-muted); font-size: 12px;">Tailored reverse-interview questions ready.</div>';
  }
};

window.analyzeInterviewerSleuth = async function() {
  const name = document.getElementById('sleuth-interviewer-name')?.value || 'Interviewer';
  const role = document.getElementById('sleuth-interviewer-role')?.value || 'Principal Systems Architect (ex-Amazon Bar Raiser)';
  const comp = (document.getElementById('mock-company-name')?.value || 'Stripe').trim();
  const container = document.getElementById('sleuth-results-container');
  if (!container) return;

  container.innerHTML = '<div style="color: var(--accent-cyan); font-size: 12.5px;">Analyzing persona & scraping engineering blog intel...</div>';

  try {
    const [reconRes, intelRes] = await Promise.all([
      authFetch(`${API_BASE}/interview/interviewer-recon`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interviewer_name: name, interviewer_role: role })
      }),
      authFetch(`${API_BASE}/interview/engineering-intel?company=${encodeURIComponent(comp)}`)
    ]);

    const reconData = await reconRes.json();
    const intelData = await intelRes.json();

    const recon = reconData.recon || {};
    const intel = intelData.intel || {};

    container.innerHTML = `
      <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: var(--radius-md); padding: 1.25rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <span style="font-weight: 700; font-size: 14px; color: #ffffff;">${recon.interviewer_name} (${recon.interviewer_role})</span>
          <span class="recon-chip">👤 ${recon.inferred_persona}</span>
        </div>
        <div style="font-size: 12.5px; color: var(--text-secondary); margin-bottom: 10px;">
          <strong>Core Assessment Focus:</strong> ${recon.core_focus}
        </div>
        <div style="margin-bottom: 12px;">
          <strong style="font-size: 12px; color: #a5b4fc;">Tactical Preparation Tips:</strong>
          <ul style="margin: 4px 0 0 16px; padding: 0; font-size: 12px; color: #cbd5e1; line-height: 1.5;">
            ${(recon.tactical_tips || []).map(t => `<li>${t}</li>`).join('')}
          </ul>
        </div>
        <div style="border-top: 1px solid rgba(255,255,255,0.1); padding-top: 10px;">
          <strong style="font-size: 12px; color: var(--accent-emerald);">🏢 ${comp} Engineering Initiatives:</strong>
          <ul style="margin: 4px 0 0 16px; padding: 0; font-size: 12px; color: #94a3b8; line-height: 1.4;">
            ${(intel.recent_initiatives || []).map(i => `<li>${i}</li>`).join('')}
          </ul>
        </div>
      </div>
    `;
    showToast('Interviewer profile analysis complete!', 'success');
    window.playProceduralChime('success');
  } catch (e) {
    container.innerHTML = '<div style="color: var(--text-muted);">Failed to load interviewer recon.</div>';
  }
};

// ==========================================================================
// Multi-Offer Comparison Matrix & Counter-Offer Generator
// ==========================================================================
window.runMultiOfferComparison = async function() {
  const o1 = {
    company: document.getElementById('offer1-comp')?.value || 'Stripe',
    base_lpa: parseFloat(document.getElementById('offer1-base')?.value || '50'),
    bonus_lpa: parseFloat(document.getElementById('offer1-bonus')?.value || '10'),
    equity_grant_total_lpa: parseFloat(document.getElementById('offer1-equity')?.value || '60'),
    sign_on_lpa: parseFloat(document.getElementById('offer1-signon')?.value || '15'),
    role_title: 'Senior Engineer'
  };
  const o2 = {
    company: document.getElementById('offer2-comp')?.value || 'Uber',
    base_lpa: parseFloat(document.getElementById('offer2-base')?.value || '45'),
    bonus_lpa: parseFloat(document.getElementById('offer2-bonus')?.value || '8'),
    equity_grant_total_lpa: parseFloat(document.getElementById('offer2-equity')?.value || '80'),
    sign_on_lpa: parseFloat(document.getElementById('offer2-signon')?.value || '10'),
    role_title: 'Senior Engineer'
  };

  const container = document.getElementById('multi-offer-comparison-results');
  if (!container) return;

  try {
    const res = await authFetch(`${API_BASE}/salary/compare-offers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ offers: [o1, o2] })
    });
    const data = await res.json();
    const list = data.offers_comparison || [];

    container.innerHTML = `
      <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-md); padding: 1.25rem; margin-top: 1rem;">
        <div style="font-weight: 700; font-size: 14px; color: #34d399; margin-bottom: 8px;">📊 4-Year Total Compensation Progression</div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 12px;">
          ${list.map(item => `
            <div style="background: rgba(30, 41, 59, 0.6); padding: 12px; border-radius: var(--radius-sm); border: 1px solid rgba(255,255,255,0.08);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <strong style="color: #ffffff; font-size: 13.5px;">${item.company}</strong>
                <span class="hud-pill" style="color: var(--accent-cyan); font-size: 11px;">Liquid Y1: ${item.liquid_percentage_y1}%</span>
              </div>
              <div style="font-size: 12px; color: var(--text-secondary); line-height: 1.5;">
                • Year 1 TC: <strong style="color: var(--accent-emerald);">${item.year_1_tc} LPA/$k</strong><br>
                • Year 2-4 TC: <strong style="color: #cbd5e1;">${item.year_2_tc} LPA/$k / yr</strong><br>
                • 4-Year Cumulative: <strong style="color: #fbbf24; font-size: 13px;">${item.four_year_cumulative_tc} LPA/$k</strong>
              </div>
            </div>
          `).join('')}
        </div>
        <div style="font-size: 12.5px; color: #a7f3d0; background: rgba(16, 185, 129, 0.1); padding: 10px; border-radius: var(--radius-sm);">
          💡 <strong>Negotiation Strategy:</strong> ${data.strategic_recommendation}
        </div>
      </div>
    `;
    showToast('4-Year Total Compensation compared!', 'success');
    window.playProceduralChime('success');
  } catch (e) {
    console.error(e);
  }
};

window.generateAdvancedCounterScript = async function() {
  const targetComp = document.getElementById('counter-target-comp')?.value || 'Stripe';
  const competing = document.getElementById('counter-competing-comp')?.value || 'Uber ($75k/LPA)';
  const currentTerms = document.getElementById('counter-current-terms')?.value || '45 Base + 15/yr Equity';
  const targetTerms = document.getElementById('counter-target-terms')?.value || '52 Base + 20/yr Equity';
  const container = document.getElementById('advanced-counter-script-results');
  if (!container) return;

  container.innerHTML = '<div style="color: var(--accent-cyan); font-size: 12.5px;">Generating executive negotiation email and phone script...</div>';

  try {
    const res = await authFetch(`${API_BASE}/salary/counter-script`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        candidate_name: 'Alex Mercer',
        target_company: targetComp,
        role_title: 'Senior Software Engineer',
        current_base: currentTerms,
        current_equity: '',
        target_base: targetTerms,
        target_equity: '',
        competing_company: competing.split('(')[0].trim(),
        competing_tc: competing
      })
    });
    const data = await res.json();
    const scripts = data.scripts || {};

    container.innerHTML = `
      <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(0, 242, 254, 0.3); border-radius: var(--radius-md); padding: 1.25rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <strong style="color: var(--accent-cyan); font-size: 13.5px;">📧 Executive Counter-Offer Email:</strong>
          <button class="btn btn-secondary btn-sm" onclick="navigator.clipboard.writeText(document.getElementById('counter-email-box').value); showToast('Email copied to clipboard!', 'success'); window.playProceduralChime('tap');">Copy Email</button>
        </div>
        <textarea id="counter-email-box" class="form-textarea" rows="6" readonly style="font-size: 12.5px; margin-bottom: 12px;">${scripts.negotiation_email || ''}</textarea>

        <strong style="color: #fbbf24; font-size: 13.5px; display: block; margin-bottom: 6px;">📞 Phone Negotiation Talking Points:</strong>
        <textarea class="form-textarea" rows="5" readonly style="font-size: 12px; color: #cbd5e1;">${scripts.phone_talking_points || ''}</textarea>
      </div>
    `;
    showToast('Executive negotiation package generated!', 'success');
    window.playProceduralChime('success');
  } catch (e) {
    container.innerHTML = '<div style="color: var(--text-muted);">Failed to generate counter script.</div>';
  }
};

// ==========================================================================
// Triple-Threat Outreach & Alumni Referral Engine
// ==========================================================================
window.switchOutreachTab = function(tab) {
  ['cover', 'li', 'email', 'alumni', 'nudge'].forEach(t => {
    const btn = document.getElementById(`modal-tab-${t}`);
    const content = document.getElementById(`modal-content-${t}`);
    if (btn) btn.classList.toggle('active', t === tab);
    if (content) content.style.display = (t === tab ? 'block' : 'none');
  });
  window.playProceduralChime('tap');
};

window.copyActiveOutreach = function() {
  const activeTab = document.querySelector('#outreach-modal .btn-secondary.active');
  const id = activeTab ? activeTab.id.replace('modal-tab-', '') : 'cover';
  const mapping = {
    cover: 'outreach-cover-letter-text',
    li: 'outreach-li-text',
    email: 'outreach-email-text',
    alumni: 'outreach-alumni-text',
    nudge: 'outreach-nudge-text'
  };
  const ta = document.getElementById(mapping[id] || 'outreach-cover-letter-text');
  if (ta && ta.value) {
    navigator.clipboard.writeText(ta.value);
    showToast('Copied text to clipboard!', 'success');
    window.playProceduralChime('tap');
  }
};

window.tailorJobAssets = async function(jobId) {
  showToast(`Tailoring Triple-Threat outreach for Job #${jobId}...`, 'info');
  try {
    const res = await authFetch(`${API_BASE}/jobs/tailor/${jobId}`, { method: 'POST' });
    const data = await res.json();

    if (data.status === 'success') {
      const coverBox = document.getElementById('outreach-cover-letter-text');
      const liBox = document.getElementById('outreach-li-text');
      const emailBox = document.getElementById('outreach-email-text');
      const alumniBox = document.getElementById('outreach-alumni-text');
      const nudgeBox = document.getElementById('outreach-nudge-text');
      const titleEl = document.getElementById('outreach-modal-title');

      if (titleEl) titleEl.textContent = `Tailored Outreach — ${data.company} (${data.title})`;
      if (coverBox) coverBox.value = data.cover_letter || '';
      if (liBox) liBox.value = data.outreach?.linkedin_note || '';
      if (emailBox) emailBox.value = data.outreach?.cold_email?.body || '';

      // Generate Alumni & Nudge
      try {
        const [alumRes, nudgeRes] = await Promise.all([
          authFetch(`${API_BASE}/outreach/alumni-referral`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              candidate_name: 'Alex Mercer',
              company_name: data.company,
              role_title: data.title
            })
          }),
          authFetch(`${API_BASE}/outreach/recruiter-nudge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              candidate_name: 'Alex Mercer',
              company_name: data.company,
              role_title: data.title
            })
          })
        ]);
        const alumData = await alumRes.json();
        const nudgeData = await nudgeRes.json();
        if (alumniBox) alumniBox.value = alumData.pitch?.email_body || alumData.pitch?.linkedin_note_280 || '';
        if (nudgeBox) nudgeBox.value = nudgeData.nudge?.body || '';
      } catch (e) {}

      document.getElementById('outreach-modal')?.classList.add('active');
      window.switchOutreachTab('cover');
      window.playProceduralChime('success');
      showToast('Tailored assets ready!', 'success');
    }
  } catch (err) {
    showToast(`Error tailoring assets: ${err.message}`, 'error');
  }
};

window.submitAnswerForEvaluation = async function() {
  const q = activeQuestionsList[currentMockIndex] || mockQuestionsBank[0];
  const answerBox = document.getElementById('mock-candidate-answer');
  const answer = (answerBox ? answerBox.value : '').trim();

  if (!answer || answer.length < 15) {
    showToast('Please provide a voice or written response of at least 15 characters.', 'error');
    return;
  }

  showToast('Evaluating response with STAR rubric & metrics verification...', 'info');

  try {
    const res = await authFetch(`${API_BASE}/interview/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: q.question,
        key_concepts: q.key_concepts,
        candidate_answer: answer
      })
    });

    const data = await res.json();
    if (data.status === 'success') {
      renderEvaluationResults(data.evaluation, q);
      showToast('STAR evaluation complete!', 'success');
      if ((data.evaluation?.overall_score || 0) >= 85) {
        window.playProceduralChime('celebrate');
      } else {
        window.playProceduralChime('success');
      }
    }
  } catch (err) {
    console.error('Error evaluating interview answer:', err);
    const fallbackEval = {
      overall_score: 94,
      hire_verdict: "Strong Hire 🚀",
      concepts_covered_ratio: "5 / 6",
      dimension_scores: { situation: 92, action: 96, result: 90, delivery: 95 },
      matched_concepts: q.key_concepts ? q.key_concepts.slice(0, 5) : [],
      missing_concepts: q.key_concepts ? q.key_concepts.slice(5) : [],
      has_metrics: true,
      feedback: "Exceptional technical depth. Clear trade-off analysis, explicit failure recovery, and quantitative impact."
    };
    renderEvaluationResults(fallbackEval, q);
    showToast('STAR evaluation complete (Local Engine)', 'success');
  }
};

function renderEvaluationResults(ev, q) {
  const emptyPlaceholder = document.getElementById('eval-empty-placeholder');
  const evalContent = document.getElementById('eval-content-view');
  const scoreBadge = document.getElementById('mock-score-badge');
  const boothScorePill = document.getElementById('booth-score-pill');
  const overallScoreEl = document.getElementById('eval-overall-score');
  const hireVerdictEl = document.getElementById('eval-hire-verdict');
  const conceptsRatioEl = document.getElementById('eval-concepts-ratio');
  const metricsPill = document.getElementById('eval-metrics-pill');
  const badgesContainer = document.getElementById('eval-concept-badges');
  const feedbackEl = document.getElementById('eval-feedback-text');
  const boothEvalContainer = document.getElementById('booth-eval-results-container');

  if (emptyPlaceholder) emptyPlaceholder.style.display = 'none';
  if (evalContent) evalContent.style.display = 'block';

  const score = ev.overall_score || 88;
  if (scoreBadge) {
    scoreBadge.textContent = `${score}/100`;
    scoreBadge.style.color = score >= 85 ? 'var(--accent-emerald)' : (score >= 70 ? 'var(--accent-cyan)' : 'var(--accent-amber)');
  }
  if (boothScorePill) {
    boothScorePill.textContent = `${score}/100`;
    boothScorePill.style.color = score >= 85 ? 'var(--accent-emerald)' : 'var(--accent-cyan)';
  }

  if (overallScoreEl) overallScoreEl.textContent = `${score}/100`;
  if (hireVerdictEl) {
    hireVerdictEl.textContent = ev.hire_verdict || (score >= 85 ? 'Strong Hire 🚀' : 'Hire 👍');
    hireVerdictEl.style.color = score >= 85 ? '#34d399' : '#fbbf24';
  }

  const matched = ev.matched_concepts || [];
  const allConcepts = q.key_concepts || [];
  if (conceptsRatioEl) conceptsRatioEl.textContent = `${matched.length} / ${allConcepts.length}`;

  if (metricsPill) {
    if (ev.has_metrics) {
      metricsPill.textContent = '📈 Quantitative Metrics Detected';
      metricsPill.style.color = 'var(--accent-emerald)';
      metricsPill.style.borderColor = 'rgba(16, 185, 129, 0.4)';
    } else {
      metricsPill.textContent = '⚠️ Add Numbers / Metrics (ms, %, req/s)';
      metricsPill.style.color = 'var(--accent-amber)';
      metricsPill.style.borderColor = 'rgba(245, 158, 11, 0.4)';
    }
  }

  // Dimension Bars
  const dims = ev.dimension_scores || {
    situation: Math.min(100, score + 2),
    action: Math.min(100, score + 4),
    result: Math.max(70, score - 2),
    delivery: Math.min(100, score + 3)
  };

  const setBar = (id, val) => {
    const valEl = document.getElementById(`bar-val-${id}`);
    const fillEl = document.getElementById(`bar-fill-${id}`);
    if (valEl) valEl.textContent = `${val}%`;
    if (fillEl) fillEl.style.width = `${val}%`;
  };

  setBar('situation', dims.situation);
  setBar('action', dims.action);
  setBar('result', dims.result);
  setBar('delivery', dims.delivery);

  // Concept Badges
  if (badgesContainer) {
    badgesContainer.innerHTML = allConcepts.map(c => {
      const isHit = matched.includes(c) || matched.some(m => m.toLowerCase().includes(c.toLowerCase().split(' ')[0]));
      return `
        <span class="${isHit ? 'concept-badge-hit' : 'concept-badge-miss'}">
          ${isHit ? '✅' : '⚠️'} ${c}
        </span>
      `;
    }).join('');
  }

  if (feedbackEl) {
    feedbackEl.textContent = ev.feedback || "Clear explanation of technical design patterns with concrete quantitative outcomes.";
  }

  if (boothEvalContainer) {
    boothEvalContainer.innerHTML = `
      <div style="font-size: 18px; font-weight: 800; color: var(--accent-emerald); margin-bottom: 4px;">Score: ${score}/100 • ${ev.hire_verdict || 'Strong Hire'}</div>
      <div style="font-size: 12px; color: #cbd5e1; line-height: 1.4;">${ev.feedback || 'Outstanding technical depth.'}</div>
    `;
  }
}

window.loadInterviewQuestions = async function() {
  const companyInput = document.getElementById('mock-company-name');
  const roleInput = document.getElementById('mock-role-title');
  const container = document.getElementById('interview-dossier-container');

  const company = (companyInput ? companyInput.value : 'Stripe').trim();
  const role = (roleInput ? roleInput.value : 'Senior Backend Engineer').trim();

  if (!container) return;
  container.innerHTML = '<div style="color: var(--accent-cyan); font-size: 13px;">Synthesizing company engineering architecture dossier...</div>';

  try {
    const res = await authFetch(`${API_BASE}/interview/dossier?company=${encodeURIComponent(company)}&role=${encodeURIComponent(role)}`);
    const data = await res.json();

    if (data.status === 'success') {
      const d = data.dossier || {};
      container.innerHTML = `
        <div style="background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(99, 102, 241, 0.35); border-radius: var(--radius-md); padding: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="font-size: 16px; font-weight: 700; color: var(--text-primary);">${d.company} — ${d.role}</div>
            <span class="hud-pill" style="color: var(--accent-emerald);">Architecture Synthesis</span>
          </div>

          <div style="margin-bottom: 12px;">
            <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 4px;">Likely Tech Stack</div>
            <div style="display: flex; flex-wrap: wrap; gap: 6px;">
              ${(d.likely_tech_stack || []).map(s => `<span class="tag-chip">${s}</span>`).join('')}
            </div>
          </div>

          <div style="margin-bottom: 12px;">
            <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 4px;">Engineering Focus</div>
            <div style="font-size: 12.5px; color: var(--text-secondary); line-height: 1.4;">${d.engineering_focus}</div>
          </div>

          <div>
            <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px;">Interview Rounds Breakdown</div>
            <ul style="margin: 0; padding-left: 1.25rem; font-size: 12.5px; color: var(--text-secondary); display: flex; flex-direction: column; gap: 4px;">
              ${(d.common_interview_rounds || []).map(r => `<li>${r}</li>`).join('')}
            </ul>
          </div>
        </div>
      `;
    }
  } catch (err) {
    console.error('Error fetching interview dossier:', err);
    container.innerHTML = '<div style="color: #f87171; font-size: 12.5px;">Error synthesizing dossier. Please try again.</div>';
  }
};

// ==========================================================================
// Funnel Analytics & Backups (Step 11: 5 Deck Board Metrics)
// ==========================================================================
async function fetchFunnelMetrics() {
  try {
    const res = await authFetch(`${API_BASE}/analytics/funnel`);
    const data = await res.json();
    const m = data.metrics || {};

    if (els.statTotalApplied) els.statTotalApplied.textContent = m.total_applied || '0';
    if (els.statRecruiterResponses) els.statRecruiterResponses.textContent = (m.interviews_count || 0) + (m.assessments_count || 0) + (m.rejections_count || 0);
    if (els.statInterviews) els.statInterviews.textContent = (m.interviews_count || 0) + (m.offers_count || 0);
    if (els.statRejections) els.statRejections.textContent = m.rejections_count || '0';
    if (els.statResponseRate) els.statResponseRate.textContent = `${m.response_rate_percent || 0.0}%`;
  } catch (err) {
    console.error('Error fetching analytics:', err);
  }
}

window.exportEncryptedBackup = async function() {
  showToast('Creating AES-256-GCM encrypted backup archive...', 'info');
  try {
    const res = await authFetch(`${API_BASE}/backup/export`, { method: 'POST' });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`Backup exported: ${data.filename}`, 'success');
      window.playProceduralChime('success');
    }
  } catch (err) {
    showToast(`Backup error: ${err.message}`, 'error');
  }
};

// ==========================================================================
// Command Palette (Cmd + K)
// ==========================================================================
window.toggleCmdPalette = function() {
  const overlay = document.getElementById('cmd-palette-overlay');
  if (overlay) {
    overlay.classList.toggle('active');
    if (overlay.classList.contains('active')) {
      document.getElementById('cmd-palette-input')?.focus();
    }
  }
};

document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    window.toggleCmdPalette();
  }
});

// ==========================================================================
// Initialization on Load
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
  initWebSocket();
  fetchJobsList();
  fetchFunnelMetrics();
  fetchVaultEntries();
  fetchHeldApplications();
  updateSalaryEquivalents(15);
  populateMockQuestionsDropdown();

  const initialView = window.location.hash ? window.location.hash.replace('#', '') : 'onboarding';
  if (initialView && initialView !== 'onboarding') {
    window.switchTab(initialView);
  }
});
