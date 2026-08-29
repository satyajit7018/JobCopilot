/**
 * ==========================================================================
 * JobCopilot OS — Master Cockpit Frontend Logic
 * Reactive UI with WebSocket streaming, interactive Kanban, real-time
 * Knowledge Vault Q&A playground, Command Palette (Cmd+K), and Soundwave Studio.
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
  currentPipelineFilter: 'ALL',
  ws: null,
  activePendingHitl: null,
  activeOutreachPackage: null,
  activeOutreachTab: 'cover',
  isDiscovering: false
};

// UI Element Cache
const els = {
  navTabs: document.querySelectorAll('.nav-item'),
  viewPanels: document.querySelectorAll('.view-panel'),
  workerStatusText: document.getElementById('worker-status-text'),
  workerStatusDot: document.getElementById('worker-status-dot'),
  wsStatusText: document.getElementById('ws-status-text'),
  toastContainer: document.getElementById('toast-container'),

  // Telemetry HUD
  statTotalSourced: document.getElementById('stat-total-sourced'),
  statTotalApplied: document.getElementById('stat-total-applied'),
  statInterviews: document.getElementById('stat-interviews'),
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
  qRemotePref: document.getElementById('q-remote-pref'),
  qCurrentEmployer: document.getElementById('q-current-employer'),
  qWhyLooking: document.getElementById('q-why-looking'),
  screeningSlotsList: document.getElementById('screening-slots-review-list'),

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
  vaultTableBody: document.getElementById('vault-table-body'),
  vaultSearchInput: document.getElementById('vault-search-input'),
  playgroundInput: document.getElementById('playground-test-input'),
  playgroundConfidenceFill: document.getElementById('playground-confidence-fill'),
  playgroundResultBox: document.getElementById('playground-result-box'),
  playgroundSlotKey: document.getElementById('playground-slot-key'),
  playgroundScore: document.getElementById('playground-score'),
  playgroundResolvedText: document.getElementById('playground-resolved-text'),

  // Email Radar
  emailMessagesList: document.getElementById('email-messages-list'),

  // Interview Studio
  mockCompanyInput: document.getElementById('mock-company-input'),
  mockRoleInput: document.getElementById('mock-role-input'),
  mockInterviewContainer: document.getElementById('mock-interview-container'),
  interviewSoundwave: document.getElementById('interview-soundwave'),

  // Negotiation & ESOP
  negBaseSalary: document.getElementById('neg-base-salary'),
  negBonus: document.getElementById('neg-bonus'),
  negEquity: document.getElementById('neg-equity'),
  negRoleTitle: document.getElementById('neg-role-title'),
  negotiationResultsContainer: document.getElementById('negotiation-results-container'),
  esopOptionsCount: document.getElementById('esop-options-count'),
  esopTotalShares: document.getElementById('esop-total-shares'),
  esopValuationUsd: document.getElementById('esop-valuation-usd'),
  esopResultsContainer: document.getElementById('esop-results-container'),

  // Bot Logs Terminal
  botLogsContainer: document.getElementById('bot-logs-container'),

  // Command Palette
  cmdPaletteOverlay: document.getElementById('cmd-palette-overlay'),
  cmdPaletteInput: document.getElementById('cmd-palette-input'),
  cmdPaletteList: document.getElementById('cmd-palette-list'),

  // Modals
  hitlModal: document.getElementById('hitl-modal'),
  hitlCompanyTag: document.getElementById('hitl-company-tag'),
  hitlQuestionText: document.getElementById('hitl-question-text'),
  hitlUserAnswer: document.getElementById('hitl-user-answer'),
  hitlSaveVaultCheck: document.getElementById('hitl-save-vault-check'),
  btnHitlApprove: document.getElementById('btn-hitl-approve'),

  outreachModal: document.getElementById('outreach-modal'),
  outreachModalTitle: document.getElementById('outreach-modal-title'),
  outreachCoverLetterText: document.getElementById('outreach-cover-letter-text'),
  outreachLiText: document.getElementById('outreach-li-text'),
  outreachEmailText: document.getElementById('outreach-email-text')
};

// ==========================================================================
// Tab Navigation & View Management
// ==========================================================================
window.switchTab = function(viewName) {
  window.location.hash = viewName;
  els.navTabs.forEach(tab => {
    tab.classList.toggle('active', tab.dataset.view === viewName);
  });
  els.viewPanels.forEach(panel => {
    panel.classList.toggle('active', panel.id === `view-${viewName}`);
  });

  if (viewName === 'vault') {
    fetchVaultEntries();
  } else if (viewName === 'pipeline') {
    fetchJobsList();
    fetchFunnelMetrics();
  } else if (viewName === 'email') {
    fetchEmailMessages();
  }
};

els.navTabs.forEach(tab => {
  tab.addEventListener('click', () => window.switchTab(tab.dataset.view));
});

// Toast Notifications
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
  toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
  els.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Append Terminal Log
function appendTerminalLog(module, message, isError = false, isSuccess = false) {
  const now = new Date();
  const ts = `[${now.toTimeString().split(' ')[0]}]`;
  const div = document.createElement('div');
  div.className = 'log-entry';
  
  let msgClass = '';
  if (isError) msgClass = 'log-err';
  else if (isSuccess) msgClass = 'log-success';

  div.innerHTML = `
    <span class="log-ts">${ts}</span>
    <span class="log-mod">[${module.toUpperCase()}]</span>
    <span class="${msgClass}">${message}</span>
  `;
  els.botLogsContainer.appendChild(div);
  els.botLogsContainer.scrollTop = els.botLogsContainer.scrollHeight;
}

// ==========================================================================
// Command Palette (Cmd + K)
// ==========================================================================
window.toggleCmdPalette = function() {
  const isOpen = els.cmdPaletteOverlay.classList.toggle('active');
  if (isOpen) {
    els.cmdPaletteInput.value = '';
    els.cmdPaletteInput.focus();
  }
};

document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    window.toggleCmdPalette();
  } else if (e.key === 'Escape' && els.cmdPaletteOverlay.classList.contains('active')) {
    els.cmdPaletteOverlay.classList.remove('active');
  }
});

// ==========================================================================
// WebSocket Real-Time Streaming & Alerts
// ==========================================================================
function initWebSocket() {
  try {
    state.ws = new WebSocket(WS_URL);

    state.ws.onopen = () => {
      els.wsStatusText.textContent = 'Sync: Live';
      els.workerStatusText.textContent = 'Stealth Bot Ready';
      appendTerminalLog('WS', 'Connected to real-time telemetry streaming channel.', false, true);
    };

    state.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch (err) {
        console.error('WS Parse Error:', err);
      }
    };

    state.ws.onclose = () => {
      els.wsStatusText.textContent = 'Sync: Reconnecting...';
      setTimeout(initWebSocket, 3000);
    };
  } catch (err) {
    console.warn('WS not reachable in static mode');
  }
}

function handleWebSocketMessage(data) {
  if (data.type === 'BOT_LOG') {
    appendTerminalLog('BOT', data.message);
  } else if (data.type === 'DISCOVERY_COMPLETED') {
    showToast(`0-Day Discovery Complete! Found ${data.total_sourced} leads (${data.matched_and_saved} matched).`, 'success');
    fetchJobsList();
    fetchFunnelMetrics();
  } else if (data.type === 'HITL_REQUIRED') {
    triggerHitlModal(data.event);
  } else if (data.type === 'INBOUND_EMAIL') {
    showToast(`Recruiter email received from ${data.sender}: "${data.subject}"`, 'info');
    fetchEmailMessages();
  }
}

// ==========================================================================
// Multi-Currency Dynamic Salary Slider
// ==========================================================================
function updateSalaryEquivalents(lpa) {
  const baseInr = lpa * 100000;
  const usdAnnual = Math.round(baseInr / 83.5);
  const usdHourly = (usdAnnual / 2080).toFixed(2);
  const inrMonthly = Math.round(baseInr / 12);

  els.salaryDisplay.textContent = `${parseFloat(lpa).toFixed(1)} LPA`;
  els.eqInrLpa.textContent = `${parseFloat(lpa).toFixed(1)} LPA`;
  els.eqUsdAnnual.textContent = `$${usdAnnual.toLocaleString()}`;
  els.eqUsdHourly.textContent = `$${usdHourly}/hr`;
  els.eqInrMonthly.textContent = `₹${inrMonthly.toLocaleString()}`;
}

els.salarySlider.addEventListener('input', (e) => {
  updateSalaryEquivalents(e.target.value);
});

// ==========================================================================
// Stepper Wizard Navigation
// ==========================================================================
function goToWizardStep(step) {
  [els.wstep1, els.wstep2, els.wstep3, els.wstep4].forEach((s, idx) => {
    s.classList.toggle('active', idx + 1 === step);
    s.classList.toggle('completed', idx + 1 < step);
  });

  els.stepContent1.style.display = step === 1 ? 'block' : 'none';
  els.stepContent2.style.display = step === 2 ? 'block' : 'none';
  els.stepContent3.style.display = step === 3 ? 'block' : 'none';
  els.stepContent4.style.display = step === 4 ? 'block' : 'none';

  const badgeLabels = [
    'Step 1: Resume Ingestion',
    'Step 2: Recruiter Baseline',
    'Step 3: 14 Screening Slots',
    'Step 4: Autopilot Ready'
  ];
  els.currentStepBadge.textContent = badgeLabels[step - 1];
}

window.backToStep2 = () => goToWizardStep(2);
window.proceedToStep4 = () => goToWizardStep(4);

if (els.btnBackStep1) {
  els.btnBackStep1.addEventListener('click', () => goToWizardStep(1));
}

// ==========================================================================
// Resume Ingestion & Parsing
// ==========================================================================
['dragenter', 'dragover'].forEach(eventName => {
  els.resumeDropzone.addEventListener(eventName, (e) => {
    e.preventDefault();
    els.resumeDropzone.classList.add('dragover');
  });
});

['dragleave', 'drop'].forEach(eventName => {
  els.resumeDropzone.addEventListener(eventName, (e) => {
    e.preventDefault();
    els.resumeDropzone.classList.remove('dragover');
  });
});

els.resumeDropzone.addEventListener('drop', (e) => {
  if (e.dataTransfer.files.length) {
    handleFileUpload(e.dataTransfer.files[0]);
  }
});

els.resumeDropzone.addEventListener('click', () => els.resumeFileInput.click());

els.resumeFileInput.addEventListener('change', (e) => {
  if (e.target.files.length) {
    handleFileUpload(e.target.files[0]);
  }
});

els.btnParseResume.addEventListener('click', () => {
  const rawText = els.rawResumeText.value.trim();
  if (rawText) {
    handleRawTextParse(rawText);
  } else {
    showToast('Please upload a resume file or paste resume text.', 'error');
  }
});

async function handleFileUpload(file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('profile_id', 'default_user');

  try {
    showToast(`Parsing ${file.name} in < 150ms...`, 'info');
    appendTerminalLog('PARSER', `Ingesting ${file.name}...`);
    const res = await fetch(`${API_BASE}/upload-resume`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (data.status === 'success') {
      populateQuestionnaire(data.profile, data.prefilled_questionnaire);
      goToWizardStep(2);
      showToast('Resume parsed successfully! Review prefilled preferences.', 'success');
      appendTerminalLog('PARSER', `Profile extracted: ${data.profile.full_name} (${data.profile.skills.length} skills)`, false, true);
    } else {
      showToast(data.detail || 'Error parsing resume', 'error');
    }
  } catch (err) {
    showToast(`Failed to parse resume: ${err.message}`, 'error');
  }
}

async function handleRawTextParse(rawText) {
  const formData = new FormData();
  formData.append('raw_text', rawText);
  formData.append('profile_id', 'default_user');

  try {
    showToast('Parsing candidate text...', 'info');
    const res = await fetch(`${API_BASE}/upload-resume`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (data.status === 'success') {
      populateQuestionnaire(data.profile, data.prefilled_questionnaire);
      goToWizardStep(2);
      showToast('Profile parsed! Confirm your 8 baseline preferences.', 'success');
    }
  } catch (err) {
    showToast(`Parsing failed: ${err.message}`, 'error');
  }
}

function populateQuestionnaire(profile, prefilled) {
  state.currentProfile = profile;
  els.qFullName.value = prefilled.full_name || profile.full_name || '';
  els.qEmail.value = prefilled.email || profile.email || '';
  els.qPhone.value = prefilled.phone || profile.phone || '';
  els.qLocation.value = prefilled.location || profile.location || '';
  els.qNoticePeriod.value = prefilled.notice_period_days !== undefined ? String(prefilled.notice_period_days) : '0';
  els.qWorkAuth.value = prefilled.work_authorization || 'Citizen / Permanent Resident';
  els.qRemotePref.value = prefilled.remote_preference || 'Remote / Hybrid / On-site';
  els.qCurrentEmployer.value = prefilled.current_employer || '';
  els.qWhyLooking.value = prefilled.why_looking_for_role || '';

  const ctcMatch = (prefilled.expected_ctc || '').match(/[\d\.]+/);
  const lpaVal = ctcMatch ? parseFloat(ctcMatch[0]) : 15.0;
  els.salarySlider.value = lpaVal;
  updateSalaryEquivalents(lpaVal);
}

// Questionnaire Submit
els.questionnaireForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  const answers = {
    full_name: els.qFullName.value.trim(),
    email: els.qEmail.value.trim(),
    phone: els.qPhone.value.trim(),
    location: els.qLocation.value.trim(),
    expected_ctc: `${els.salarySlider.value} LPA`,
    notice_period_days: parseInt(els.qNoticePeriod.value, 10),
    work_authorization: els.qWorkAuth.value,
    remote_preference: els.qRemotePref.value,
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
      showToast('Preferences saved & 14 slots seeded into Knowledge Vault!', 'success');
      renderScreeningSlotsReview();
      goToWizardStep(3);
    }
  } catch (err) {
    showToast(`Error saving preferences: ${err.message}`, 'error');
  }
});

function renderScreeningSlotsReview() {
  const standardSlots = [
    { key: 'expected_ctc', name: 'Expected Compensation', val: `${els.salarySlider.value} LPA` },
    { key: 'notice_period_days', name: 'Notice Period', val: `${els.qNoticePeriod.value} days` },
    { key: 'work_authorization', name: 'Work Authorization', val: els.qWorkAuth.value },
    { key: 'remote_preference', name: 'Work Mode Preference', val: els.qRemotePref.value },
    { key: 'willing_to_relocate', name: 'Relocation Openness', val: 'Yes, open to relocation' },
    { key: 'why_looking_for_role', name: 'Career Motivation Essay', val: els.qWhyLooking.value || 'Seeking challenging technical growth' },
    { key: 'why_join_company', name: 'Why Company Essay', val: 'Excited about scaling high-performance systems' },
    { key: 'technical_achievement', name: 'Technical Project Link', val: 'Diagnostic AI with FastAPI & Sub-50ms latency' }
  ];

  els.screeningSlotsList.innerHTML = standardSlots.map(s => `
    <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 10px 12px;">
      <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--accent-cyan); font-family: 'JetBrains Mono', monospace;">
        <span>${s.key}</span>
        <span style="color: var(--accent-emerald);">✓ Indexed</span>
      </div>
      <div style="font-weight: 700; font-size: 12.5px; margin: 2px 0;">${s.name}</div>
      <div style="font-size: 12px; color: var(--text-secondary);">${s.val}</div>
    </div>
  `).join('');
}

// ==========================================================================
// 0-Day Job Pipeline & Interactive Kanban
// ==========================================================================
async function fetchJobsList() {
  try {
    const res = await fetch(`${API_BASE}/jobs`);
    const data = await res.json();
    state.jobsList = data.jobs || [];
    renderKanbanBoard();
  } catch (err) {
    console.error('Error fetching jobs:', err);
  }
}

async function triggerDiscoveryCycle() {
  if (state.isDiscovering) return;
  state.isDiscovering = true;
  showToast('Starting 0-day multi-source discovery cycle...', 'info');
  appendTerminalLog('DISCOVERY', 'Ingesting Greenhouse, Lever, Ashby, YC, HN boards concurrently...');

  try {
    const res = await fetch(`${API_BASE}/discovery/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    showToast(`Discovery completed! Sourced ${data.total_sourced} leads (${data.matched_and_saved} matched).`, 'success');
    appendTerminalLog('DISCOVERY', `Saved ${data.matched_and_saved} high-match opportunities to SQLite WAL.`, false, true);
    fetchJobsList();
    fetchFunnelMetrics();
  } catch (err) {
    showToast(`Discovery failed: ${err.message}`, 'error');
  } finally {
    state.isDiscovering = false;
  }
}

window.filterPipeline = function(filterType, element) {
  state.currentPipelineFilter = filterType;
  document.querySelectorAll('.filter-pill').forEach(btn => btn.classList.remove('active'));
  if (element) element.classList.add('active');
  renderKanbanBoard();
};

els.pipelineSearchInput.addEventListener('input', () => {
  renderKanbanBoard();
});

function renderKanbanBoard() {
  const query = (els.pipelineSearchInput.value || '').toLowerCase();
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

  els.countDiscovered.textContent = columns.discovered.length;
  els.countQueued.textContent = columns.queued.length;
  els.countSubmitted.textContent = columns.submitted.length;
  els.countInterview.textContent = columns.interview.length;
  els.countOffer.textContent = columns.offer.length;
  els.badgePipelineCount.textContent = filtered.length;

  els.cardsDiscovered.innerHTML = columns.discovered.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">No leads discovered.</p>';
  els.cardsQueued.innerHTML = columns.queued.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">Queue is empty.</p>';
  els.cardsSubmitted.innerHTML = columns.submitted.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">No applications submitted yet.</p>';
  els.cardsInterview.innerHTML = columns.interview.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">No active interviews.</p>';
  els.cardsOffer.innerHTML = columns.offer.map(j => renderJobCardHTML(j)).join('') || '<p style="color: var(--text-muted); font-size: 12px;">No offers recorded.</p>';
}

function renderJobCardHTML(job) {
  const matchPct = Math.round((job.match_score || 0) * 100);
  let matchBadgeClass = 'match-low';
  if (matchPct >= 80) matchBadgeClass = 'match-high';
  else if (matchPct >= 65) matchBadgeClass = 'match-mid';

  const platform = job.platform || 'Direct';
  const location = job.location || 'Remote';

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
    } else {
      showToast(data.message || 'Application error', 'error');
      appendTerminalLog('BOT', `Error: ${data.message}`, true);
    }
  } catch (err) {
    showToast(`Bot failed: ${err.message}`, 'error');
  }
};

// Generate Tailored Assets & Outreach
window.tailorJobAssets = async function(jobId) {
  showToast('Compiling pixel-perfect tailored PDF and outreach...', 'info');
  try {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/tailor`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    if (data.status === 'success') {
      state.activeOutreachPackage = data;
      els.outreachModalTitle.textContent = `${data.company} — ${data.title}`;
      els.outreachCoverLetterText.value = data.cover_letter;
      els.outreachLiText.value = data.outreach.linkedin_note;
      els.outreachEmailText.value = `${data.outreach.cold_email.subject}\n\n${data.outreach.cold_email.body}`;
      switchOutreachTab('cover');
      els.outreachModal.classList.add('active');
    }
  } catch (err) {
    showToast(`Tailoring failed: ${err.message}`, 'error');
  }
};

window.switchOutreachTab = function(tab) {
  state.activeOutreachTab = tab;
  ['cover', 'li', 'email'].forEach(t => {
    document.getElementById(`modal-tab-${t}`).classList.toggle('active', t === tab);
    document.getElementById(`modal-content-${t}`).style.display = t === tab ? 'block' : 'none';
  });
};

window.copyActiveOutreach = function() {
  let textToCopy = '';
  if (state.activeOutreachTab === 'cover') textToCopy = els.outreachCoverLetterText.value;
  else if (state.activeOutreachTab === 'li') textToCopy = els.outreachLiText.value;
  else if (state.activeOutreachTab === 'email') textToCopy = els.outreachEmailText.value;

  navigator.clipboard.writeText(textToCopy);
  showToast('Copied to clipboard!', 'success');
};

// ==========================================================================
// Knowledge Vault Studio & Live Q&A Playground
// ==========================================================================
async function fetchVaultEntries() {
  try {
    const res = await fetch(`${API_BASE}/vault`);
    const data = await res.json();
    state.vaultEntries = data.entries || [];
    els.badgeVaultCount.textContent = `${state.vaultEntries.length} Slots`;
    renderVaultTable();
  } catch (err) {
    console.error('Error fetching vault:', err);
  }
}

function renderVaultTable() {
  const query = (els.vaultSearchInput.value || '').toLowerCase();
  const filtered = state.vaultEntries.filter(e => 
    (e.slot_key + ' ' + e.question_pattern + ' ' + e.answer_template).toLowerCase().includes(query)
  );

  els.vaultTableBody.innerHTML = filtered.map(e => `
    <tr>
      <td>
        <span class="badge badge-info" style="font-family: 'JetBrains Mono', monospace;">${e.slot_key}</span>
        <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${e.slot_type}</div>
      </td>
      <td style="font-weight: 500; color: #f1f5f9;">${e.question_pattern}</td>
      <td style="font-size: 12.5px; color: var(--text-secondary);">${e.answer_template}</td>
      <td><span class="badge badge-low">${e.usage_count} uses</span></td>
    </tr>
  `).join('') || '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No vault slots matching query.</td></tr>';
}

els.vaultSearchInput.addEventListener('input', renderVaultTable);

window.testVaultQuestionMatch = async function() {
  const question = els.playgroundInput.value.trim();
  if (!question) {
    showToast('Enter a recruiter question to test.', 'error');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/vault/test-match`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: question, company: 'Stripe', role: 'Senior Backend Engineer' })
    });
    const data = await res.json();

    els.playgroundResultBox.style.display = 'block';
    els.playgroundSlotKey.textContent = `${data.slot_key} (${data.slot_type})`;
    els.playgroundScore.textContent = `${data.confidence_score}%`;
    els.playgroundConfidenceFill.style.width = `${data.confidence_score}%`;
    els.playgroundResolvedText.textContent = data.resolved_answer;

    if (data.is_matched) {
      showToast(`Matched slot: ${data.slot_key} (${data.confidence_score}% confidence)`, 'success');
    } else {
      showToast('Confidence below threshold (< 55%). Consider teaching this slot.', 'info');
    }
  } catch (err) {
    showToast(`Test match failed: ${err.message}`, 'error');
  }
};

window.openAddSlotModal = function() {
  const question = prompt('Enter recruiter question pattern:');
  if (!question) return;
  const answer = prompt('Enter answer template (can include {company}, {expected_ctc}):');
  if (!answer) return;

  fetch(`${API_BASE}/vault/learn`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question: question, answer: answer })
  }).then(() => {
    showToast('Slot indexed into Knowledge Vault!', 'success');
    fetchVaultEntries();
  });
};

// ==========================================================================
// Inbound Email Radar
// ==========================================================================
async function fetchEmailMessages() {
  try {
    const res = await fetch(`${API_BASE}/email/messages`);
    const data = await res.json();
    const messages = data.messages || [];
    
    els.emailMessagesList.innerHTML = messages.map(m => `
      <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 12px 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <div>
            <span style="font-weight: 700; color: #f1f5f9;">${m.sender}</span>
            <span style="font-size: 11px; color: var(--text-muted); margin-left: 8px;">${m.received_at || 'Just now'}</span>
          </div>
          <span class="badge ${m.intent === 'INTERVIEW_INVITE' ? 'badge-high' : 'badge-info'}">${m.intent || 'REPLY'}</span>
        </div>
        <div style="font-weight: 600; font-size: 13px; margin-bottom: 4px; color: var(--accent-cyan);">${m.subject}</div>
        <div style="font-size: 12.5px; color: var(--text-secondary);">${m.body_text}</div>
      </div>
    `).join('') || '<p style="color: var(--text-muted); font-size: 13px;">No inbound recruiter emails currently tracked.</p>';
  } catch (err) {
    console.error('Error fetching emails:', err);
  }
}

window.simulateTestEmail = async function() {
  try {
    const res = await fetch(`${API_BASE}/email/inbound`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sender: 'sarah.recruiter@stripe.com',
        subject: 'Invitation to Technical Screen — Senior Backend Engineer at Stripe',
        body_html: '<p>Hi Satyajit, we were very impressed with your application and would like to schedule a 30-min technical screen.</p><img src="https://tracking.stripe.com/pixel.gif"/>'
      })
    });
    const data = await res.json();
    showToast('Simulated email parsed and tracking pixels stripped!', 'success');
    fetchEmailMessages();
  } catch (err) {
    showToast(`Simulation failed: ${err.message}`, 'error');
  }
};

// ==========================================================================
// Mock Interview Studio & Soundwave
// ==========================================================================
window.loadMockDossierAndQuestions = async function() {
  const company = els.mockCompanyInput.value.trim() || 'Stripe';
  const role = els.mockRoleInput.value.trim() || 'Senior Software Engineer';

  els.interviewSoundwave.style.display = 'flex';
  showToast(`Generating engineering dossier & questions for ${company}...`, 'info');

  try {
    const [dossierRes, qRes] = await Promise.all([
      fetch(`${API_BASE}/interview/dossier?company=${encodeURIComponent(company)}&role=${encodeURIComponent(role)}`),
      fetch(`${API_BASE}/interview/questions?role=${encodeURIComponent(role)}`)
    ]);
    const dossierData = await dossierRes.json();
    const qData = await qRes.json();

    const dossier = dossierData.dossier || {};
    const questions = qData.questions || [];

    els.mockInterviewContainer.innerHTML = `
      <div style="background: rgba(10, 14, 24, 0.7); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 1.25rem; margin-bottom: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <h4 style="font-size: 15px; color: var(--accent-cyan);">🏛️ ${dossier.company} Engineering Topology</h4>
          <span class="badge badge-info">${dossier.role}</span>
        </div>
        <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 10px;">${dossier.engineering_focus}</p>
        <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px;">
          ${(dossier.likely_tech_stack || []).map(t => `<span class="badge badge-low">${t}</span>`).join('')}
        </div>
      </div>

      <div style="display: flex; flex-direction: column; gap: 1rem;">
        ${questions.map((q, idx) => `
          <div class="glass-card" style="margin-bottom: 0;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
              <span class="badge badge-high">${q.category}</span>
              <span class="badge badge-low">${q.difficulty}</span>
            </div>
            <div style="font-weight: 600; font-size: 14px; color: #f1f5f9; margin-bottom: 10px;">${q.question}</div>
            <textarea id="mock-ans-${idx}" class="form-textarea" rows="3" placeholder="Provide your technical answer..."></textarea>
            <div style="display: flex; justify-content: flex-end; margin-top: 8px;">
              <button class="btn btn-primary btn-sm" onclick="evaluateMockAnswer('${idx}', '${encodeURIComponent(q.question)}')">Evaluate Answer</button>
            </div>
            <div id="eval-result-${idx}" class="star-rubric-card" style="display: none;"></div>
          </div>
        `).join('')}
      </div>
    `;
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  } finally {
    els.interviewSoundwave.style.display = 'none';
  }
};

window.evaluateMockAnswer = async function(idx, encQuestion) {
  const question = decodeURIComponent(encQuestion);
  const answer = document.getElementById(`mock-ans-${idx}`).value.trim();
  const resultBox = document.getElementById(`eval-result-${idx}`);

  if (!answer) {
    showToast('Please type an answer before evaluating.', 'error');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/interview/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: question, answer: answer })
    });
    const data = await res.json();
    const ev = data.evaluation || {};

    resultBox.style.display = 'block';
    resultBox.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
        <span style="font-weight: 700; color: #f1f5f9;">STAR Rubric Score</span>
        <span style="font-size: 16px; font-weight: 800; color: var(--accent-emerald);">${ev.score}/100 (${ev.rating})</span>
      </div>
      <p style="font-size: 12.5px; color: var(--text-secondary); margin-bottom: 8px;">${ev.feedback}</p>
      <div style="display: flex; flex-wrap: wrap; gap: 4px;">
        ${(ev.covered_concepts || []).map(c => `<span class="badge badge-low" style="color: var(--accent-emerald);">✓ ${c}</span>`).join('')}
        ${(ev.missing_concepts || []).map(c => `<span class="badge badge-critical">✕ Missing: ${c}</span>`).join('')}
      </div>
    `;
  } catch (err) {
    showToast(`Evaluation error: ${err.message}`, 'error');
  }
};

// ==========================================================================
// Salary & Startup ESOP Modeler
// ==========================================================================
window.evaluateOfferCompensation = async function() {
  const base = parseFloat(els.negBaseSalary.value) || 0;
  const bonus = parseFloat(els.negBonus.value) || 0;
  const equity = parseFloat(els.negEquity.value) || 0;
  const role = els.negRoleTitle.value.trim();

  try {
    const res = await fetch(`${API_BASE}/negotiation/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ base_salary_lpa: base, bonus_lpa: bonus, equity_annual_lpa: equity, role_title: role })
    });
    const data = await res.json();
    const ev = data.evaluation || {};

    els.negotiationResultsContainer.innerHTML = `
      <div style="background: rgba(10, 14, 24, 0.7); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 1.25rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <span style="font-size: 16px; font-weight: 700; color: var(--accent-cyan);">Total Annual Comp: ${ev.total_annual_comp_lpa} LPA</span>
          <span class="badge badge-high">${ev.market_percentile_band}</span>
        </div>
        <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 12px;">${ev.negotiation_guidance}</p>
        <button class="btn btn-secondary btn-sm" onclick="generateCounterOfferScript('${role}', '${ev.total_annual_comp_lpa} LPA')">Generate Counter-Offer Email</button>
      </div>
    `;
  } catch (err) {
    showToast(`Evaluation failed: ${err.message}`, 'error');
  }
};

window.simulateEsopEquity = async function() {
  const options = parseInt(els.esopOptionsCount.value, 10) || 0;
  const totalShares = parseInt(els.esopTotalShares.value, 10) || 1;
  const valUsd = parseFloat(els.esopValuationUsd.value) || 0;

  try {
    const res = await fetch(`${API_BASE}/negotiation/equity`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ options_count: options, total_company_shares: totalShares, current_valuation_usd: valUsd })
    });
    const data = await res.json();
    const eq = data.equity_model || {};

    els.esopResultsContainer.innerHTML = `
      <div style="background: rgba(10, 14, 24, 0.7); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 1.25rem;">
        <div style="font-weight: 700; margin-bottom: 8px;">Ownership: ${eq.ownership_percentage}% (Current Value: $${(eq.current_estimated_value_usd || 0).toLocaleString()})</div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px;">
          ${(eq.exit_scenarios || []).map(s => `
            <div style="background: rgba(255, 255, 255, 0.03); border-radius: 6px; padding: 8px; text-align: center;">
              <div style="font-size: 11px; color: var(--accent-cyan); font-weight: 700;">${s.growth_multiple} Multiple</div>
              <div style="font-size: 14px; font-weight: 800; color: var(--accent-emerald); margin-top: 2px;">$${(s.projected_payout_usd || 0).toLocaleString()}</div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  } catch (err) {
    showToast(`Simulation failed: ${err.message}`, 'error');
  }
};

window.generateCounterOfferScript = async function(role, offeredTc) {
  try {
    const res = await fetch(`${API_BASE}/negotiation/counter-offer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        candidate_name: state.currentProfile ? state.currentProfile.full_name : 'Candidate',
        company_name: 'Target Company',
        role_title: role,
        offered_tc: offeredTc,
        desired_tc: `${(parseFloat(offeredTc) * 1.15).toFixed(1)} LPA`
      })
    });
    const data = await res.json();
    prompt('Copy your Anti-AI Counter-Offer script:', data.counter_offer_script);
  } catch (err) {
    showToast(`Script error: ${err.message}`, 'error');
  }
};

// ==========================================================================
// Funnel Analytics & Backups
// ==========================================================================
async function fetchFunnelMetrics() {
  try {
    const res = await fetch(`${API_BASE}/analytics/funnel`);
    const data = await res.json();
    const m = data.metrics || {};

    els.statTotalSourced.textContent = m.total_sourced || '0';
    els.statTotalApplied.textContent = m.total_applied || '0';
    els.statInterviews.textContent = m.interviews_count || '0';
    els.statResponseRate.textContent = `${m.response_rate_percent || 0.0}%`;
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
// Initialization on Load
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
  initWebSocket();
  fetchJobsList();
  fetchFunnelMetrics();
  fetchVaultEntries();
  updateSalaryEquivalents(15);

  const initialView = window.location.hash ? window.location.hash.replace('#', '') : 'onboarding';
  if (initialView && initialView !== 'onboarding') {
    window.switchTab(initialView);
  }
});
