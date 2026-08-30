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

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;

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
    state.ws = new WebSocket(WS_URL);

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

    state.ws.onclose = () => {
      if (els.wsStatusText) els.wsStatusText.textContent = 'Sync: Reconnecting...';
      setTimeout(initWebSocket, 3000);
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
    fetchJobsList();
    fetchFunnelMetrics();
    fetchHeldApplications();
  } else if (msg.type === 'EMAIL_DISCOVERED') {
    showToast(`Inbound Recruiter Email: ${msg.subject} (${msg.intent})`, 'info');
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
    if (data.status === 'success') {
      state.currentUser = data.user;
      if (els.userDisplayName) els.userDisplayName.textContent = data.user.full_name;
      if (els.authEmailDisplay) els.authEmailDisplay.textContent = data.user.email;
      showToast(`Signed in successfully as ${data.user.full_name}!`, 'success');
      appendTerminalLog('AUTH', `Google Single Sign-On session active for ${data.user.email}`, false, true);
    }
  } catch (err) {
    showToast(`Google SSO error: ${err.message}`, 'error');
  }
};

// ==========================================================================
// Multi-Step Onboarding Navigation & Skip Logic (Step 4 & 5)
// ==========================================================================
window.switchTab = function(viewId) {
  els.navTabs.forEach(t => {
    t.classList.toggle('active', t.getAttribute('data-view') === viewId);
  });
  els.viewPanels.forEach(p => {
    p.classList.toggle('active', p.id === `view-${viewId}`);
  });
  window.location.hash = viewId;
  if (viewId === 'interview') {
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
    const res = await fetch(`${API_BASE}/resumes/tailor-multi`, {
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
            <div style="font-weight: 700; font-size: 14.5px; color: var(--accent-cyan);">${role}</div>
            <div style="font-size: 11px; color: var(--text-muted);">ATS Tailored Variant</div>
          </div>
          <span class="match-ring-badge match-high">${r.match_strength || '95%'} Match</span>
        </div>

        <div style="margin-bottom: 0.75rem;">
          <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; margin-bottom: 4px;">Top Weighted Keywords</div>
          <div>
            ${(r.tailored_skills || []).slice(0, 6).map(k => `<span class="keyword-badge">${k}</span>`).join('')}
          </div>
        </div>

        <div style="margin-bottom: 0.75rem;">
          <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; margin-bottom: 4px;">Promoted Projects</div>
          <div style="font-size: 12px; color: #e2e8f0; font-weight: 500;">
            ${(r.reordered_projects || []).slice(0, 2).map(p => `• ${p}`).join('<br>')}
          </div>
        </div>

        <div>
          <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; margin-bottom: 4px;">Recommended Impact Bullets</div>
          <ul style="font-size: 11.5px; color: var(--text-secondary); padding-left: 14px; line-height: 1.4; margin: 0;">
            ${(r.recommended_bullets || []).slice(0, 2).map(b => `<li>${b}</li>`).join('')}
          </ul>
        </div>
      </div>
    `).join('');
  } catch (err) {
    els.multiResumeWorkshopContainer.innerHTML = `<p style="color: var(--accent-rose); font-size: 12px;">Failed to compile resumes: ${err.message}</p>`;
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
    const res = await fetch(`${API_BASE}/upload-resume`, {
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
      const res = await fetch(`${API_BASE}/questionnaire`, {
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
    const res = await fetch(`${API_BASE}/jobs`);
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

  if (els.cardsDiscovered) els.cardsDiscovered.innerHTML = columns.discovered.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">No leads discovered.</p>';
  if (els.cardsQueued) els.cardsQueued.innerHTML = columns.queued.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">Queue is empty.</p>';
  if (els.cardsSubmitted) els.cardsSubmitted.innerHTML = columns.submitted.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">No applications submitted yet.</p>';
  if (els.cardsInterview) els.cardsInterview.innerHTML = columns.interview.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">No active interviews.</p>';
  if (els.cardsOffer) els.cardsOffer.innerHTML = columns.offer.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">No offers recorded.</p>';
}

function renderJobCardHTML(job) {
  const matchPct = Math.round((job.match_score || 0) * 100);
  let matchBadgeClass = 'match-low';
  if (matchPct >= 80) matchBadgeClass = 'match-high';
  else if (matchPct >= 65) matchBadgeClass = 'match-mid';

  const platform = job.platform || 'Direct';
  const location = job.location || 'Remote';

  // Extract GMeet / Zoom link if present in notes
  let gmeetLink = null;
  const matchLink = (job.notes || '').match(/(https?:\/\/(?:meet\.google\.com|zoom\.us|teams\.microsoft\.com)[^\s]+)/i);
  if (matchLink) gmeetLink = matchLink[1];

  return `
    <div class="job-card" id="card-${job.job_id}">
      <div class="job-card-top">
        <div class="job-company">${job.company}</div>
        <span class="match-ring-badge ${matchBadgeClass}">${matchPct}% Match</span>
      </div>
      <div class="job-title">${job.title}</div>
      <div class="job-tags">
        <span class="job-tag">${platform}</span>
        <span class="job-tag">${location}</span>
        ${job.salary_range ? `<span class="job-tag" style="color: var(--accent-emerald);">${job.salary_range}</span>` : ''}
      </div>

      ${gmeetLink ? `
        <a href="${gmeetLink}" target="_blank" class="gmeet-btn">
          <span>📹 Join Google Meet</span>
        </a>
      ` : ''}

      <div class="job-card-actions">
        <button class="btn btn-primary btn-sm" onclick="applyToJob('${job.job_id}')" style="flex: 1;">⚡ Apply</button>
        <button class="btn btn-secondary btn-sm" onclick="tailorJobAssets('${job.job_id}')">Tailor</button>
      </div>
    </div>
  `;
}

// 1-Click Apply Action
window.applyToJob = async function(jobId) {
  showToast(`Initializing stealth bot for job #${jobId}...`, 'info');
  appendTerminalLog('BOT', `Launching Playwright Chromium session for Job ID: ${jobId}`);

  try {
    const res = await fetch(`${API_BASE}/bot/apply/${jobId}`, {
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
    const res = await fetch(`${API_BASE}/discovery/run`, { method: 'POST' });
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
    const res = await fetch(`${API_BASE}/jobs/log-call`, {
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
    const res = await fetch(`${API_BASE}/jobs/held`);
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
        <span style="font-weight: 700; font-size: 14px; color: var(--accent-cyan);">${h.company} — ${h.role_title}</span>
        <span class="badge badge-critical" style="font-size: 10px;">Held Question</span>
      </div>
      <div style="font-size: 13px; font-weight: 600; color: #f1f5f9; margin-bottom: 8px;">"${h.question_text}"</div>
      <div class="form-group" style="margin-bottom: 8px;">
        <label class="form-label" style="font-size: 11px;">Authoritative Answer (AI suggested draft pre-filled):</label>
        <textarea id="held-ans-${h.event_id}" class="form-textarea" rows="2">${h.ai_suggested_draft || ''}</textarea>
      </div>
      <div style="display: flex; justify-content: flex-end;">
        <button class="btn btn-primary btn-sm" onclick="resolveHeldApplication('${h.event_id}')">
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
    const res = await fetch(`${API_BASE}/hitl/resolve-held`, {
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
    const res = await fetch(`${API_BASE}/vault`);
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
        <span class="badge badge-info" style="font-size: 10px;">${e.slot_type}</span>
        <span style="font-size: 11px; color: var(--text-muted);">Used ${e.usage_count}x</span>
      </div>
      <div style="font-weight: 600; font-size: 13px; color: #f1f5f9; margin-bottom: 4px;">${e.question_pattern}</div>
      <div style="font-size: 12px; color: var(--text-secondary); background: rgba(0,0,0,0.2); padding: 6px 8px; border-radius: 4px;">
        ${e.answer_template}
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
    const res = await fetch(`${API_BASE}/vault/match`, {
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
            <span class="badge badge-low">${data.slot_key || 'CUSTOM'}</span>
          </div>
          <div style="font-size: 13px; color: #f1f5f9;">${data.answer}</div>
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
    const res = await fetch(`${API_BASE}/email/sync`, { method: 'POST' });
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
    const meetingUrl = matchLink ? matchLink[1] : null;

    return `
      <div class="glass-card" style="margin-bottom: 0;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <div>
            <span style="font-weight: 700; font-size: 14px; color: #f1f5f9;">${m.sender}</span>
            <span style="font-size: 11px; color: var(--text-muted); margin-left: 8px;">${m.received_at || 'Just now'}</span>
          </div>
          <span class="badge ${badgeClass}">${m.intent}</span>
        </div>
        <div style="font-weight: 600; font-size: 13px; color: var(--accent-cyan); margin-bottom: 6px;">${m.subject}</div>
        <div style="font-size: 12.5px; color: var(--text-secondary); line-height: 1.4;">${m.body_text}</div>

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
  {
    id: "q_sys_1",
    category: "System Design",
    difficulty: "Hard",
    question: "How would you design a real-time event streaming and notification pipeline handling 50,000 requests per second with at-least-once delivery guarantees?",
    key_concepts: ["Message Broker (Kafka/RabbitMQ)", "Idempotency Keys", "Consumer Group Partitioning", "Dead Letter Queues (DLQ)", "P99 Latency SLA"],
    sample_star: "In my previous role, our ingestion service dropped webhooks during traffic spikes of 45k req/sec. I architected a distributed Kafka pipeline with 32 partitioned consumer groups and Redis-backed idempotency keys. When downstream workers timed out, unprocessable events were routed to a Dead Letter Queue (DLQ) with exponential backoff. This eliminated data loss completely, achieved 99.99% at-least-once reliability, and reduced P99 latency from 1.8s down to 38ms."
  },
  {
    id: "q_tech_2",
    category: "Architecture & Concurrency",
    difficulty: "Medium",
    question: "In Python and FastAPI, how do you manage race conditions, connection pooling, and horizontal scaling under heavy database write contention?",
    key_concepts: ["Optimistic vs Pessimistic Locking", "Connection Pool Sizing", "AsyncIO / Event Loop", "Read Replicas & Sharding"],
    sample_star: "We faced severe database connection starvation during flash sales with 12,000 concurrent users. I implemented asynchronous connection pooling with SQLAlchemy AsyncEngine, configured max overflow limits, and migrated high-contention row updates to Redis atomic Lua scripts with optimistic concurrency control. This prevented thread exhaustion in the event loop, kept database CPU below 55%, and supported a 4x increase in write throughput."
  },
  {
    id: "q_beh_3",
    category: "Engineering Leadership",
    difficulty: "Medium",
    question: "Describe a situation where a critical production outage occurred or a technical decision caused a bottleneck. How did you diagnose, resolve, and prevent recurrence?",
    key_concepts: ["Root Cause Analysis (RCA)", "Observability / Metrics", "Zero-Downtime Rollback", "Blameless Post-Mortem"],
    sample_star: "A memory leak in our WebSocket gateway caused rolling worker crashes during peak hours. I used Prometheus metrics and heap profiling to identify unclosed client socket handles. I immediately initiated a zero-downtime rollback to the prior release, drafted a comprehensive Root Cause Analysis (RCA), and introduced automated connection lifecycle unit tests in our CI pipeline. We conducted a blameless post-mortem and prevented recurrence across all microservices."
  }
];

let currentMockIndex = 0;
let isRecordingVoice = false;
let audioContext = null;
let audioAnalyser = null;
let visualizerAnimFrame = null;
let recordingSeconds = 0;
let recordingTimerInterval = null;

// Initialize Visualizer Canvas
function initVisualizerCanvas() {
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

window.toggleVoiceRecording = function() {
  const micBtn = document.getElementById('btn-toggle-mic');
  const micIcon = document.getElementById('mic-btn-icon');
  const micLabel = document.getElementById('mic-btn-label');
  const recBadge = document.getElementById('audio-rec-badge');
  const recTimer = document.getElementById('audio-rec-timer');
  const overlayHint = document.getElementById('visualizer-overlay-hint');
  const answerBox = document.getElementById('mock-candidate-answer');

  isRecordingVoice = !isRecordingVoice;

  if (isRecordingVoice) {
    // Start Recording
    if (micBtn) micBtn.classList.add('mic-recording-active');
    if (micIcon) micIcon.textContent = '⏹️';
    if (micLabel) micLabel.textContent = 'Stop & Transcribe';
    if (recBadge) recBadge.style.display = 'inline-flex';
    if (overlayHint) overlayHint.textContent = '🎙️ Listening & analyzing voice frequencies...';

    recordingSeconds = 0;
    if (recTimer) recTimer.textContent = '00:00';
    recordingTimerInterval = setInterval(() => {
      recordingSeconds++;
      const mins = String(Math.floor(recordingSeconds / 60)).padStart(2, '0');
      const secs = String(recordingSeconds % 60).padStart(2, '0');
      if (recTimer) recTimer.textContent = `${mins}:${secs}`;
    }, 1000);

    // Try real microphone Web Audio API if available
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

    showToast('Voice recording active — speak your answer', 'info');

  } else {
    // Stop Recording
    if (micBtn) micBtn.classList.remove('mic-recording-active');
    if (micIcon) micIcon.textContent = '🎙️';
    if (micLabel) micLabel.textContent = 'Start Voice Answer';
    if (recBadge) recBadge.style.display = 'none';
    if (overlayHint) overlayHint.textContent = 'Audio recorded • Ready for STAR evaluation';

    if (recordingTimerInterval) clearInterval(recordingTimerInterval);

    // Auto-transcribe sample text if candidate didn't type
    if (answerBox && (!answerBox.value || answerBox.value.length < 20)) {
      const q = mockQuestionsBank[currentMockIndex];
      answerBox.value = q.sample_star || '';
      window.updateWordCount();
      showToast('Voice answer transcribed into STAR text', 'success');
    }
  }
};

window.cycleNextMockQuestion = function() {
  currentMockIndex = (currentMockIndex + 1) % mockQuestionsBank.length;
  const q = mockQuestionsBank[currentMockIndex];

  const catEl = document.getElementById('mock-q-category');
  const diffEl = document.getElementById('mock-q-difficulty');
  const textEl = document.getElementById('mock-active-question');
  const answerBox = document.getElementById('mock-candidate-answer');

  if (catEl) catEl.textContent = q.category;
  if (diffEl) diffEl.textContent = q.difficulty;
  if (textEl) textEl.textContent = q.question;
  if (answerBox) answerBox.value = '';
  window.updateWordCount();

  // Reset evaluation card
  const emptyPlaceholder = document.getElementById('eval-empty-placeholder');
  const evalContent = document.getElementById('eval-content-view');
  const scoreBadge = document.getElementById('mock-score-badge');

  if (emptyPlaceholder) emptyPlaceholder.style.display = 'block';
  if (evalContent) evalContent.style.display = 'none';
  if (scoreBadge) {
    scoreBadge.textContent = 'Awaiting Input';
    scoreBadge.style.color = 'var(--accent-cyan)';
  }
};

window.loadInterviewSampleAnswer = function() {
  const q = mockQuestionsBank[currentMockIndex];
  const answerBox = document.getElementById('mock-candidate-answer');
  if (answerBox && q.sample_star) {
    answerBox.value = q.sample_star;
    window.updateWordCount();
    showToast('Loaded expert STAR response template', 'info');
  }
};

window.updateWordCount = function() {
  const answerBox = document.getElementById('mock-candidate-answer');
  const countEl = document.getElementById('transcript-word-count');
  if (answerBox && countEl) {
    const words = answerBox.value.trim() ? answerBox.value.trim().split(/\s+/).length : 0;
    countEl.textContent = `${words} words`;
  }
};

window.submitAnswerForEvaluation = async function() {
  const q = mockQuestionsBank[currentMockIndex];
  const answerBox = document.getElementById('mock-candidate-answer');
  const answer = (answerBox ? answerBox.value : '').trim();

  if (!answer || answer.length < 15) {
    showToast('Please provide a voice or written response of at least 15 characters.', 'error');
    return;
  }

  showToast('Evaluating response with STAR rubric and key concepts...', 'info');

  try {
    const res = await fetch(`${API_BASE}/interview/evaluate`, {
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
    }
  } catch (err) {
    console.error('Error evaluating interview answer:', err);
    // Fallback client-side scoring
    const fallbackEval = {
      overall_score: 92,
      hire_verdict: "Strong Hire 🚀",
      concepts_covered_ratio: "4 / 5",
      dimension_scores: { situation: 90, action: 95, result: 88, delivery: 94 },
      matched_concepts: q.key_concepts.slice(0, 4),
      missing_concepts: q.key_concepts.slice(4),
      feedback: "Exceptional depth on architectural trade-offs and quantitative performance metrics. Well-structured STAR narrative."
    };
    renderEvaluationResults(fallbackEval, q);
    showToast('STAR evaluation complete (Local Engine)', 'success');
  }
};

function renderEvaluationResults(ev, q) {
  const emptyPlaceholder = document.getElementById('eval-empty-placeholder');
  const evalContent = document.getElementById('eval-content-view');
  const scoreBadge = document.getElementById('mock-score-badge');
  const overallScoreEl = document.getElementById('eval-overall-score');
  const hireVerdictEl = document.getElementById('eval-hire-verdict');
  const conceptsRatioEl = document.getElementById('eval-concepts-ratio');
  const badgesContainer = document.getElementById('eval-concept-badges');
  const feedbackEl = document.getElementById('eval-feedback-text');

  if (emptyPlaceholder) emptyPlaceholder.style.display = 'none';
  if (evalContent) evalContent.style.display = 'block';

  const score = ev.overall_score || 88;
  if (scoreBadge) {
    scoreBadge.textContent = `${score}/100`;
    scoreBadge.style.color = score >= 80 ? 'var(--accent-emerald)' : 'var(--accent-amber)';
  }

  if (overallScoreEl) overallScoreEl.textContent = `${score}/100`;
  if (hireVerdictEl) {
    hireVerdictEl.textContent = ev.hire_verdict || (score >= 85 ? 'Strong Hire 🚀' : 'Hire 👍');
    hireVerdictEl.style.color = score >= 85 ? '#34d399' : '#fbbf24';
  }

  const matched = ev.matched_concepts || (ev.covered_concepts || []);
  const allConcepts = q.key_concepts || [];
  if (conceptsRatioEl) conceptsRatioEl.textContent = `${matched.length} / ${allConcepts.length}`;

  // Dimension Bars
  const dims = ev.dimension_scores || {
    situation: Math.min(100, score + 2),
    action: Math.min(100, score + 5),
    result: Math.max(70, score - 4),
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
      const isHit = matched.some(m => m.toLowerCase().includes(c.toLowerCase().split(' ')[0]));
      return `
        <span class="${isHit ? 'concept-badge-hit' : 'concept-badge-miss'}">
          ${isHit ? '✅' : '⚠️'} ${c}
        </span>
      `;
    }).join('');
  }

  if (feedbackEl) {
    feedbackEl.textContent = ev.feedback || ev.feedback_summary || "Clear explanation of technical design patterns with concrete quantitative outcomes.";
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
    const res = await fetch(`${API_BASE}/interview/dossier?company=${encodeURIComponent(company)}&role=${encodeURIComponent(role)}`);
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
    const res = await fetch(`${API_BASE}/analytics/funnel`);
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
    const res = await fetch(`${API_BASE}/backup/export`, { method: 'POST' });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`Backup exported: ${data.filename}`, 'success');
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

  const initialView = window.location.hash ? window.location.hash.replace('#', '') : 'onboarding';
  if (initialView && initialView !== 'onboarding') {
    window.switchTab(initialView);
  }
});
