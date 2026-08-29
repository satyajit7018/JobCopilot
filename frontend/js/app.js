/**
 * JobCopilot - Master Frontend Application Logic
 * Reactive UI handling Onboarding Wizard, Multi-Currency Slider,
 * Knowledge Vault, 0-Day Job Pipeline, Dynamic Tailored Resumes,
 * Triple-Threat Outreach, WebSockets, and Atomic HITL Approvals.
 */

const API_BASE = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
  ? `${window.location.origin}/api`
  : '/api';

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;

// Global State
const state = {
  currentProfile: null,
  vaultEntries: [],
  jobsList: [],
  ws: null,
  activePendingHitl: null,
  activeOutreachPackage: null,
  activeOutreachTab: 'cover'
};

// UI Elements
const els = {
  navTabs: document.querySelectorAll('.nav-tab'),
  viewPanels: document.querySelectorAll('.view-panel'),
  systemStatusText: document.getElementById('status-text'),
  
  // Wizard Elements
  wstep1: document.getElementById('wstep-1'),
  wstep2: document.getElementById('wstep-2'),
  wstep3: document.getElementById('wstep-3'),
  stepContent1: document.getElementById('step-content-1'),
  stepContent2: document.getElementById('step-content-2'),
  stepContent3: document.getElementById('step-content-3'),
  
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
  
  // Salary Slider
  salarySlider: document.getElementById('salary-slider'),
  salaryDisplay: document.getElementById('salary-display'),
  eqInrLpa: document.getElementById('eq-inr-lpa'),
  eqUsdAnnual: document.getElementById('eq-usd-annual'),
  eqUsdHourly: document.getElementById('eq-usd-hourly'),
  eqInrMonthly: document.getElementById('eq-inr-monthly'),
  eqEurAnnual: document.getElementById('eq-eur-annual'),
  
  // Vault
  vaultTableBody: document.getElementById('vault-table-body'),
  vaultSearchInput: document.getElementById('vault-search-input'),
  
  // Pipeline
  jobPipelineList: document.getElementById('job-pipeline-list'),
  btnStartAutopilot: document.getElementById('btn-start-autopilot'),
  
  // HITL Modal
  hitlModal: document.getElementById('hitl-modal'),
  hitlCompanyTag: document.getElementById('hitl-company-tag'),
  hitlQuestionText: document.getElementById('hitl-question-text'),
  hitlUserAnswer: document.getElementById('hitl-user-answer'),
  hitlSaveVaultCheck: document.getElementById('hitl-save-vault-check'),
  btnHitlApprove: document.getElementById('btn-hitl-approve'),
  
  // Outreach Modal
  outreachModal: document.getElementById('outreach-modal'),
  outreachModalTitle: document.getElementById('outreach-modal-title'),
  modalTabCover: document.getElementById('modal-tab-cover'),
  modalTabLi: document.getElementById('modal-tab-li'),
  modalTabEmail: document.getElementById('modal-tab-email'),
  modalContentCover: document.getElementById('modal-content-cover'),
  modalContentLi: document.getElementById('modal-content-li'),
  modalContentEmail: document.getElementById('modal-content-email'),
  outreachCoverLetterText: document.getElementById('outreach-cover-letter-text'),
  outreachLiText: document.getElementById('outreach-li-text'),
  outreachEmailText: document.getElementById('outreach-email-text'),
  btnCopyActiveOutreach: document.getElementById('btn-copy-active-outreach'),
  
  toastContainer: document.getElementById('toast-container')
};

// --- Tab Navigation ---
window.switchTab = function(viewName) {
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
  }
};

els.navTabs.forEach(tab => {
  tab.addEventListener('click', () => window.switchTab(tab.dataset.view));
});

// --- Toast Notifications ---
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

// --- Multi-Currency Salary Slider Calculation ---
function updateSalaryEquivalents(lpa) {
  const baseInr = lpa * 100000;
  const usdAnnual = Math.round(baseInr / 83.5);
  const usdHourly = (usdAnnual / 2080).toFixed(2);
  const inrMonthly = Math.round(baseInr / 12);
  const eurAnnual = Math.round(baseInr / 90.5);

  els.salaryDisplay.textContent = `${parseFloat(lpa).toFixed(1)} LPA`;
  els.eqInrLpa.textContent = `${parseFloat(lpa).toFixed(1)} LPA`;
  els.eqUsdAnnual.textContent = `$${usdAnnual.toLocaleString()}`;
  els.eqUsdHourly.textContent = `$${usdHourly}/hr`;
  els.eqInrMonthly.textContent = `₹${inrMonthly.toLocaleString()}`;
  els.eqEurAnnual.textContent = `€${eurAnnual.toLocaleString()}`;
}

els.salarySlider.addEventListener('input', (e) => {
  updateSalaryEquivalents(e.target.value);
});

// --- Wizard Step Management ---
function goToWizardStep(step) {
  els.wstep1.classList.toggle('active', step === 1);
  els.wstep1.classList.toggle('completed', step > 1);
  els.wstep2.classList.toggle('active', step === 2);
  els.wstep2.classList.toggle('completed', step > 2);
  els.wstep3.classList.toggle('active', step === 3);

  els.stepContent1.style.display = step === 1 ? 'block' : 'none';
  els.stepContent2.style.display = step === 2 ? 'block' : 'none';
  els.stepContent3.style.display = step === 3 ? 'block' : 'none';
}

if (els.btnBackStep1) {
  els.btnBackStep1.addEventListener('click', () => goToWizardStep(1));
}

// --- Dropzone & File Upload ---
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
    showToast(`Parsing ${file.name}...`, 'info');
    const res = await fetch(`${API_BASE}/upload-resume`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (data.status === 'success') {
      populateQuestionnaire(data.profile, data.prefilled_questionnaire);
      goToWizardStep(2);
      showToast('Resume parsed successfully! Review prefilled preferences.', 'success');
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
    showToast('Parsing resume text...', 'info');
    const res = await fetch(`${API_BASE}/upload-resume`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (data.status === 'success') {
      populateQuestionnaire(data.profile, data.prefilled_questionnaire);
      goToWizardStep(2);
      showToast('Profile extracted! Confirm your preferences.', 'success');
    } else {
      showToast(data.detail || 'Error parsing text', 'error');
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

// --- Submit Questionnaire ---
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
      body: JSON.stringify({
        profile_id: 'default_user',
        answers: answers
      })
    });
    const data = await res.json();
    if (data.status === 'success') {
      goToWizardStep(3);
      showToast('Preferences saved & Knowledge Vault seeded!', 'success');
    } else {
      showToast(data.detail || 'Failed to save questionnaire', 'error');
    }
  } catch (err) {
    showToast(`Error saving preferences: ${err.message}`, 'error');
  }
});

// --- Knowledge Vault Data Fetching ---
async function fetchVaultEntries() {
  try {
    const res = await fetch(`${API_BASE}/vault`);
    const data = await res.json();
    state.vaultEntries = data.entries || [];
    renderVaultTable(state.vaultEntries);
  } catch (err) {
    console.error('Failed to fetch vault entries:', err);
  }
}

function renderVaultTable(entries) {
  els.vaultTableBody.innerHTML = '';
  if (!entries.length) {
    els.vaultTableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">No vault entries yet. Upload your resume to seed the vault.</td></tr>`;
    return;
  }

  entries.forEach(entry => {
    const row = document.createElement('tr');
    const lastUsed = entry.last_used_at ? new Date(entry.last_used_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Never';
    row.innerHTML = `
      <td>
        <span class="slot-tag">${entry.slot_key}</span>
        <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 0.2rem;">${entry.slot_type}</div>
      </td>
      <td style="font-weight: 500;">${escapeHtml(entry.question_pattern)}</td>
      <td style="color: var(--text-secondary); max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
        ${escapeHtml(entry.answer_template)}
      </td>
      <td>
        <span style="font-weight: 700; color: #818cf8;">${entry.usage_count}</span>
      </td>
      <td style="color: var(--text-muted); font-size: 0.8rem;">${lastUsed}</td>
    `;
    els.vaultTableBody.appendChild(row);
  });
}

els.vaultSearchInput.addEventListener('input', (e) => {
  const query = e.target.value.toLowerCase();
  const filtered = state.vaultEntries.filter(entry =>
    entry.question_pattern.toLowerCase().includes(query) ||
    entry.slot_key.toLowerCase().includes(query) ||
    entry.answer_template.toLowerCase().includes(query)
  );
  renderVaultTable(filtered);
});

// --- Job Pipeline Data Fetching & Rendering ---
async function fetchJobsList() {
  try {
    const res = await fetch(`${API_BASE}/jobs`);
    const data = await res.json();
    state.jobsList = data.jobs || [];
    renderJobsList(state.jobsList);
  } catch (err) {
    console.error('Failed to fetch jobs:', err);
  }
}

function renderJobsList(jobs) {
  if (!els.jobPipelineList) return;
  els.jobPipelineList.innerHTML = '';

  if (!jobs.length) {
    els.jobPipelineList.innerHTML = `
      <div style="text-align: center; padding: 3rem 1rem; color: var(--text-muted);">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🔍</div>
        <p>No jobs discovered yet. Click <strong>Start Auto-Apply</strong> to run 0-day discovery across Greenhouse, Lever, Ashby, and YC!</p>
      </div>
    `;
    return;
  }

  const grid = document.createElement('div');
  grid.style.display = 'grid';
  grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(340px, 1fr))';
  grid.style.gap = '1.25rem';

  jobs.forEach(job => {
    const card = document.createElement('div');
    card.className = 'card';
    card.style.margin = '0';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.justifyContent = 'space-between';

    const matchPercent = Math.round(job.match_score * 100);
    const scoreColor = matchPercent >= 80 ? '#34d399' : matchPercent >= 60 ? '#818cf8' : '#f59e0b';
    const reasonsHtml = (job.match_reasons || []).slice(0, 2).map(r => `<div style="font-size: 0.75rem; color: var(--text-secondary);">• ${escapeHtml(r)}</div>`).join('');

    card.innerHTML = `
      <div>
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
          <span class="brand-badge">${escapeHtml(job.platform)}</span>
          <span style="font-weight: 700; font-size: 0.95rem; color: ${scoreColor}; background: rgba(255,255,255,0.05); padding: 0.2rem 0.6rem; border-radius: var(--radius-full); border: 1px solid ${scoreColor}44;">
            ${matchPercent}% Match
          </span>
        </div>
        <h3 style="font-size: 1.1rem; margin-bottom: 0.25rem;">${escapeHtml(job.title)}</h3>
        <div style="font-size: 0.85rem; font-weight: 600; color: #a5b4fc; margin-bottom: 0.5rem;">${escapeHtml(job.company)} • <span style="font-weight: 400; color: var(--text-muted);">${escapeHtml(job.location)}</span></div>
        ${job.salary_range ? `<div style="font-size: 0.8rem; color: #34d399; font-weight: 600; margin-bottom: 0.5rem;">💰 ${escapeHtml(job.salary_range)}</div>` : ''}
        <div style="margin-top: 0.5rem; background: rgba(0,0,0,0.2); padding: 0.5rem; border-radius: var(--radius-sm);">
          ${reasonsHtml}
        </div>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid var(--border-subtle); gap: 0.5rem;">
        <button class="btn btn-primary" onclick="openTailorModal('${job.job_id}')" style="padding: 0.4rem 0.75rem; font-size: 0.8rem; flex: 1;">
          🚀 Tailor &amp; Outreach
        </button>
        <a href="${job.url}" target="_blank" class="btn btn-secondary" style="padding: 0.4rem 0.75rem; font-size: 0.8rem;">View Post ➔</a>
      </div>
    `;
    grid.appendChild(card);
  });

  els.jobPipelineList.appendChild(grid);
}

if (els.btnStartAutopilot) {
  els.btnStartAutopilot.addEventListener('click', async () => {
    try {
      showToast('Triggering 0-day job discovery across Greenhouse, Lever, Ashby, YC & HN...', 'info');
      const res = await fetch(`${API_BASE}/discovery/run`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success') {
        showToast(`Discovery complete! Sourced ${data.total_sourced} jobs, matched & saved ${data.matched_and_saved}!`, 'success');
        fetchJobsList();
      } else {
        showToast(data.detail || 'Discovery error', 'error');
      }
    } catch (err) {
      showToast(`Discovery failed: ${err.message}`, 'error');
    }
  });
}

// --- Tailored Assets & Outreach Modal Actions ---
window.openTailorModal = async function(jobId) {
  try {
    showToast('Compiling tailored PDF resume and drafting outreach package...', 'info');
    const res = await fetch(`${API_BASE}/jobs/${jobId}/tailor`, { method: 'POST' });
    const data = await res.json();

    if (data.status === 'success') {
      state.activeOutreachPackage = data;
      els.outreachModalTitle.textContent = `${data.company} — ${data.title}`;
      els.outreachCoverLetterText.value = data.cover_letter || '';
      els.outreachLiText.value = data.outreach.linkedin_note || '';
      els.outreachEmailText.value = `Subject: ${data.outreach.cold_email.subject}\n\n${data.outreach.cold_email.body}`;
      
      switchOutreachTab('cover');
      els.outreachModal.classList.add('active');
      showToast('Tailored PDF resume & outreach package ready!', 'success');
    } else {
      showToast(data.detail || 'Failed to tailor assets', 'error');
    }
  } catch (err) {
    showToast(`Error tailoring assets: ${err.message}`, 'error');
  }
};

function switchOutreachTab(tabName) {
  state.activeOutreachTab = tabName;
  els.modalTabCover.classList.toggle('active', tabName === 'cover');
  els.modalTabLi.classList.toggle('active', tabName === 'li');
  els.modalTabEmail.classList.toggle('active', tabName === 'email');

  els.modalContentCover.style.display = tabName === 'cover' ? 'block' : 'none';
  els.modalContentLi.style.display = tabName === 'li' ? 'block' : 'none';
  els.modalContentEmail.style.display = tabName === 'email' ? 'block' : 'none';
}

if (els.modalTabCover) els.modalTabCover.addEventListener('click', () => switchOutreachTab('cover'));
if (els.modalTabLi) els.modalTabLi.addEventListener('click', () => switchOutreachTab('li'));
if (els.modalTabEmail) els.modalTabEmail.addEventListener('click', () => switchOutreachTab('email'));

if (els.btnCopyActiveOutreach) {
  els.btnCopyActiveOutreach.addEventListener('click', () => {
    let textToCopy = '';
    if (state.activeOutreachTab === 'cover') textToCopy = els.outreachCoverLetterText.value;
    else if (state.activeOutreachTab === 'li') textToCopy = els.outreachLiText.value;
    else if (state.activeOutreachTab === 'email') textToCopy = els.outreachEmailText.value;

    navigator.clipboard.writeText(textToCopy);
    showToast('Copied to clipboard!', 'success');
  });
}

function escapeHtml(str) {
  return (str || '').replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[m]));
}

// --- Real-Time WebSocket Connection ---
function initWebSocket() {
  try {
    state.ws = new WebSocket(WS_URL);

    state.ws.onopen = () => {
      els.systemStatusText.textContent = 'Engine Online';
    };

    state.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'HITL_REQUIRED') {
          showHitlModal(msg.event);
        } else if (msg.type === 'BOT_LOG') {
          appendBotLog(msg.message);
        } else if (msg.type === 'DISCOVERY_COMPLETED') {
          fetchJobsList();
        }
      } catch (e) {}
    };

    state.ws.onclose = () => {
      els.systemStatusText.textContent = 'Reconnecting...';
      setTimeout(initWebSocket, 3000);
    };
  } catch (e) {
    console.error('WebSocket connection error:', e);
  }
}

function appendBotLog(message) {
  const logContainer = document.getElementById('bot-logs-container');
  if (logContainer) {
    const time = new Date().toLocaleTimeString();
    const div = document.createElement('div');
    div.textContent = `[${time}] ${message}`;
    logContainer.appendChild(div);
    logContainer.scrollTop = logContainer.scrollHeight;
  }
}

// --- HITL Modal Handling ---
function showHitlModal(event) {
  state.activePendingHitl = event;
  els.hitlCompanyTag.textContent = event.company || 'Recruiter';
  els.hitlQuestionText.textContent = event.question_text;
  els.hitlUserAnswer.value = event.ai_suggested_draft || '';
  els.hitlModal.classList.add('active');
}

els.btnHitlApprove.addEventListener('click', async () => {
  if (!state.activePendingHitl) return;

  const answer = els.hitlUserAnswer.value.trim();
  const saveToVault = els.hitlSaveVaultCheck.checked;

  try {
    const res = await fetch(`${API_BASE}/hitl/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_id: state.activePendingHitl.event_id,
        user_answer: answer,
        save_to_vault: saveToVault
      })
    });
    const data = await res.json();
    if (data.status === 'success') {
      els.hitlModal.classList.remove('active');
      showToast('Answer submitted to bot & saved to vault!', 'success');
      state.activePendingHitl = null;
      fetchVaultEntries();
    }
  } catch (err) {
    showToast(`Error resolving HITL: ${err.message}`, 'error');
  }
});

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
  initWebSocket();
  updateSalaryEquivalents(15);
  fetchJobsList();
});
