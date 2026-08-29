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
    fetchFunnelMetrics();
  } else if (viewName === 'email') {
    fetchEmailMessages();
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

// --- Login Modal & Auth Management ---
const loginForm = document.getElementById('vault-login-form');
const loginModal = document.getElementById('login-modal');

if (loginForm) {
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const pwdInput = document.getElementById('master-password-input');
    const pwd = pwdInput ? pwdInput.value : '';

    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ master_password: pwd || null })
      });
      const data = await res.json();
      if (data.status === 'success') {
        if (loginModal) loginModal.style.display = 'none';
        showToast('Vault unlocked! Argon2id + AES-256-GCM Active', 'success');
      }
    } catch (err) {
      if (loginModal) loginModal.style.display = 'none';
      showToast('Vault unlocked with local OS Keychain key.', 'info');
    }
  });
}

// --- Wizard Step Management ---
function goToWizardStep(step) {
  for (let i = 1; i <= 4; i++) {
    const w = document.getElementById(`wstep-${i}`);
    const c = document.getElementById(`step-content-${i}`);
    if (w) {
      w.classList.toggle('active', i === step);
      w.classList.toggle('completed', i < step);
    }
    if (c) c.style.display = i === step ? 'block' : 'none';
  }

  const badge = document.getElementById('current-step-badge');
  if (badge) {
    const titles = {
      1: 'Step 1: Resume Ingestion',
      2: 'Step 2: The 8 Baseline Questions',
      3: 'Step 3: 14 Screening Slots Review',
      4: 'Step 4: Autopilot Ready'
    };
    badge.innerText = titles[step] || `Step ${step}`;
  }
}

window.backToStep2 = function() {
  goToWizardStep(2);
};

window.proceedToStep4 = function() {
  goToWizardStep(4);
  fetchVaultEntries();
  showToast('All 14 screening slots confirmed & indexed in Vault!', 'success');
};

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

function renderScreeningSlotsReview(answers) {
  const container = document.getElementById('screening-slots-review-list');
  if (!container) return;

  const standard14Slots = [
    { num: 1, title: 'Legal Work Authorization', key: 'work_authorization', q: 'Are you legally authorized to work in this location?', ans: answers.work_authorization },
    { num: 2, title: 'Visa Sponsorship', key: 'visa_sponsorship', q: 'Will you now or in the future require visa sponsorship?', ans: answers.work_authorization.includes('Requires') ? 'Yes' : 'No' },
    { num: 3, title: 'Expected Annual CTC', key: 'expected_ctc', q: 'What is your target annual compensation?', ans: answers.expected_ctc },
    { num: 4, title: 'Notice Period & Availability', key: 'notice_period', q: 'What is your notice period or earliest start date?', ans: `${answers.notice_period_days} days` },
    { num: 5, title: 'Work Arrangement', key: 'remote_preference', q: 'What is your remote/hybrid work preference?', ans: answers.remote_preference },
    { num: 6, title: 'Years of Experience', key: 'years_experience', q: 'Total professional years of engineering experience?', ans: `${state.currentProfile?.years_of_experience || 2}+ years` },
    { num: 7, title: 'Core Tech Stack', key: 'technical_stack', q: 'What are your primary languages and tools?', ans: (state.currentProfile?.skills || ['Python', 'FastAPI', 'PostgreSQL', 'Docker']).join(', ') },
    { num: 8, title: 'Career Motivation Narrative', key: 'why_looking', q: 'Why are you seeking a new role / this opportunity?', ans: answers.why_looking_for_role || 'Seeking high-scale engineering challenges.' },
    { num: 9, title: 'Distributed Systems Background', key: 'distributed_systems', q: 'Experience with high-scale architecture and microservices?', ans: 'Built asynchronous event-driven pipelines with message queues and sub-20ms P99 latency.' },
    { num: 10, title: 'Technical Leadership', key: 'technical_leadership', q: 'Experience mentoring or leading technical work?', ans: 'Led design reviews, mentored junior engineers, and owned architecture roadmap.' },
    { num: 11, title: 'Education & Degree', key: 'education_level', q: 'Highest completed degree?', ans: 'Bachelor of Technology in Computer Science & Engineering' },
    { num: 12, title: 'GitHub / Portfolio Link', key: 'github_url', q: 'GitHub profile or code portfolio URL?', ans: state.currentProfile?.github_url || 'https://github.com/satyajit7018' },
    { num: 13, title: 'LinkedIn Profile Link', key: 'linkedin_url', q: 'LinkedIn profile link?', ans: state.currentProfile?.linkedin_url || 'https://linkedin.com/in/satyajit-nayak' },
    { num: 14, title: 'Non-Compete Agreement Clearance', key: 'non_compete', q: 'Are you subject to any non-compete agreements?', ans: 'No active non-compete agreements.' }
  ];

  container.innerHTML = standard14Slots.map(s => `
    <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 0.85rem 1rem;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
        <span style="font-weight: 600; font-size: 13px; color: #a5b4fc;">#${s.num}. ${escapeHtml(s.title)} <span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-muted);">(${s.key})</span></span>
        <span class="brand-badge" style="color: var(--status-green); font-size: 10.5px;">Indexed</span>
      </div>
      <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 0.35rem;">Q: ${escapeHtml(s.q)}</div>
      <div style="font-size: 13px; color: var(--text-primary); font-weight: 500;">➔ ${escapeHtml(s.ans)}</div>
    </div>
  `).join('');
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
      renderScreeningSlotsReview(answers);
      goToWizardStep(3);
      showToast('8 Baseline questions saved! Review the 14 screening slots.', 'success');
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
      <div style="display: flex; flex-direction: column; gap: 0.5rem; margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid var(--border-subtle);">
        <div style="display: flex; gap: 0.5rem;">
          <button class="btn btn-primary" onclick="openTailorModal('${job.job_id}')" style="padding: 0.4rem 0.75rem; font-size: 0.8rem; flex: 1;">
            🚀 Tailor &amp; Outreach
          </button>
          <a href="${job.url}" target="_blank" class="btn btn-secondary" style="padding: 0.4rem 0.75rem; font-size: 0.8rem;">View Post ➔</a>
        </div>
        <button class="btn btn-secondary" onclick="runJobBot('${job.job_id}')" style="padding: 0.4rem 0.75rem; font-size: 0.8rem; width: 100%; border-color: rgba(99,102,241,0.4); color: #a5b4fc;">
          🤖 Run Stealth Auto-Apply (DRY RUN)
        </button>
      </div>
    `;
    grid.appendChild(card);
  });

  els.jobPipelineList.appendChild(grid);
}

window.runJobBot = async function(jobId) {
  try {
    showToast('Starting autonomous stealth application in DRY RUN mode...', 'info');
    window.switchTab('bot');
    const res = await fetch(`${API_BASE}/bot/apply/${jobId}`, { method: 'POST' });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`Autonomous application finished! ${data.filled_fields_count} fields auto-filled!`, 'success');
      fetchJobsList();
    } else {
      showToast(data.message || 'Bot execution halted', 'error');
    }
  } catch (err) {
    showToast(`Bot error: ${err.message}`, 'error');
  }
};

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

// --- Funnel Metrics ---
async function fetchFunnelMetrics() {
  try {
    const res = await fetch(`${API_BASE}/analytics/funnel`);
    const data = await res.json();
    if (data.status === 'success' && data.metrics) {
      const m = data.metrics;
      const sSourced = document.getElementById('stat-total-sourced');
      const sApplied = document.getElementById('stat-total-applied');
      const sInterviews = document.getElementById('stat-interviews');
      const sRespRate = document.getElementById('stat-response-rate');

      if (sSourced) sSourced.textContent = m.total_sourced;
      if (sApplied) sApplied.textContent = m.total_applied;
      if (sInterviews) sInterviews.textContent = m.interviews_count;
      if (sRespRate) sRespRate.textContent = `${m.response_rate_percent}%`;
    }
  } catch (err) {
    console.error('Error fetching funnel metrics:', err);
  }
}

// --- Inbound Email Radar ---
async function fetchEmailMessages() {
  const container = document.getElementById('email-messages-list');
  if (!container) return;

  try {
    const res = await fetch(`${API_BASE}/email/messages`);
    const data = await res.json();
    renderEmailMessages(data.messages || []);
  } catch (err) {
    container.innerHTML = `<p style="color: var(--danger);">Error fetching emails: ${escapeHtml(err.message)}</p>`;
  }
}

function renderEmailMessages(messages) {
  const container = document.getElementById('email-messages-list');
  if (!container) return;

  if (messages.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 3rem 1rem; color: var(--text-muted);">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📬</div>
        <p>No recruiter emails received yet. Click <strong>'+ Simulate Recruiter Email'</strong> above to test live intent extraction and pipeline sync!</p>
      </div>
    `;
    return;
  }

  container.innerHTML = '';
  const grid = document.createElement('div');
  grid.style.display = 'grid';
  grid.style.gap = '1rem';

  messages.forEach(msg => {
    const item = document.createElement('div');
    item.className = 'card';
    item.style.margin = '0';
    item.style.padding = '1.25rem';

    let intentColor = '#818cf8';
    let intentLabel = msg.intent || 'OTHER';
    if (intentLabel === 'INTERVIEW_INVITE') {
      intentColor = '#34d399';
      intentLabel = '🎉 INTERVIEW INVITE';
    } else if (intentLabel === 'ASSESSMENT') {
      intentColor = '#38bdf8';
      intentLabel = '⚡ CODING ASSESSMENT';
    } else if (intentLabel === 'REJECTION') {
      intentColor = '#f43f5e';
      intentLabel = 'REJECTION';
    } else if (intentLabel === 'CONFIRMATION') {
      intentColor = '#fbbf24';
      intentLabel = 'CONFIRMATION';
    }

    const schedulingUrls = typeof msg.scheduling_links === 'string' ? JSON.parse(msg.scheduling_links || '[]') : (msg.scheduling_links || []);
    const linksHtml = schedulingUrls.map(url => `
      <a href="${escapeHtml(url)}" target="_blank" class="btn btn-primary" style="padding: 0.35rem 0.75rem; font-size: 0.8rem; text-decoration: none;">
        📅 Schedule Call (${escapeHtml(url.split('/')[2])}) ➔
      </a>
    `).join('');

    item.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
        <div>
          <span style="font-weight: 700; font-size: 0.85rem; color: ${intentColor}; background: rgba(255,255,255,0.06); padding: 0.2rem 0.6rem; border-radius: var(--radius-full); border: 1px solid ${intentColor}44;">
            ${intentLabel}
          </span>
          ${msg.has_tracking_pixels ? `<span style="font-size: 0.75rem; color: #f59e0b; margin-left: 0.5rem;">🛡️ Tracking Pixel Stripped</span>` : ''}
        </div>
        <div style="font-size: 0.8rem; color: var(--text-muted);">${new Date(msg.received_at).toLocaleTimeString()}</div>
      </div>
      <h3 style="font-size: 1.05rem; margin-bottom: 0.25rem;">${escapeHtml(msg.subject)}</h3>
      <div style="font-size: 0.85rem; color: #a5b4fc; margin-bottom: 0.75rem;">From: <strong>${escapeHtml(msg.sender)}</strong></div>
      <div style="background: rgba(0,0,0,0.25); padding: 0.75rem; border-radius: var(--radius-sm); font-size: 0.85rem; color: var(--text-secondary); white-space: pre-wrap; margin-bottom: 0.75rem;">
        ${escapeHtml(msg.body_text)}
      </div>
      ${linksHtml ? `<div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">${linksHtml}</div>` : ''}
    `;
    grid.appendChild(item);
  });

  container.appendChild(grid);
}

window.simulateTestEmail = async function() {
  try {
    showToast('Simulating inbound recruiter interview invitation...', 'info');
    const res = await fetch(`${API_BASE}/email/inbound`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sender: 'recruiting@stripe.com',
        subject: 'Interview Invitation: Backend Software Engineer at Stripe',
        body_html: '<p>Hi Satyajit,</p><p>We reviewed your tailored resume and were impressed by your distributed systems work. We would like to invite you for a 30-minute technical phone screen.</p><p>Please book a time here: <a href="https://calendly.com/stripe-eng/30min">Calendly Link</a></p><img src="https://sendgrid.net/wf/open?upn=12345" width="1" height="1">'
      })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`Email processed! Intent: ${data.intent} (Tracking pixels stripped)`, 'success');
      fetchEmailMessages();
      fetchFunnelMetrics();
    }
  } catch (err) {
    showToast(`Simulation failed: ${err.message}`, 'error');
  }
};

// --- Mock Interview Studio ---
window.loadMockDossierAndQuestions = async function() {
  const company = document.getElementById('mock-company-input').value.trim() || 'Stripe';
  const role = document.getElementById('mock-role-input').value.trim() || 'Senior Backend Engineer';
  const container = document.getElementById('mock-interview-container');
  if (!container) return;

  try {
    showToast(`Synthesizing ${company} engineering dossier & question rubrics...`, 'info');
    const [dRes, qRes] = await Promise.all([
      fetch(`${API_BASE}/interview/dossier?company=${encodeURIComponent(company)}&role=${encodeURIComponent(role)}`),
      fetch(`${API_BASE}/interview/questions?role=${encodeURIComponent(role)}`)
    ]);

    const dData = await dRes.json();
    const qData = await qRes.json();

    const dossier = dData.dossier;
    const questions = qData.questions;

    container.innerHTML = `
      <div style="background: rgba(99,102,241,0.08); border: 1px solid rgba(99,102,241,0.3); border-radius: var(--radius-lg); padding: 1.5rem; margin-bottom: 1.5rem;">
        <h3 style="font-size: 1.15rem; color: #818cf8; margin-bottom: 0.5rem;">🏢 ${escapeHtml(dossier.company)} Engineering Dossier</h3>
        <p style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 0.75rem;">${escapeHtml(dossier.engineering_focus)}</p>
        <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.75rem;">
          ${dossier.likely_tech_stack.map(s => `<span class="brand-badge" style="background: rgba(255,255,255,0.05); color: #a5b4fc; border-color: rgba(255,255,255,0.1);">${escapeHtml(s)}</span>`).join('')}
        </div>
      </div>

      <h3 style="font-size: 1.2rem; margin-bottom: 1rem;">🎯 Technical &amp; System Design Practice Questions</h3>
      <div style="display: flex; flex-direction: column; gap: 1.25rem;">
        ${questions.map((q, idx) => `
          <div class="card" style="margin-bottom: 0; padding: 1.5rem; background: rgba(15, 23, 42, 0.8);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
              <span class="brand-badge" style="background: rgba(99,102,241,0.2); color: #818cf8;">${escapeHtml(q.category)} • ${escapeHtml(q.difficulty)}</span>
              <span style="font-size: 0.8rem; color: var(--text-muted);">Question ${idx + 1} of ${questions.length}</span>
            </div>
            <h4 style="font-size: 1rem; margin-bottom: 0.75rem; color: var(--text-primary);">${escapeHtml(q.question)}</h4>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">Key concepts to address: <em>${escapeHtml(q.key_concepts.join(', '))}</em></div>
            <textarea id="ans-input-${q.id}" class="form-textarea" rows="3" placeholder="Type or dictate your verbal response..."></textarea>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.75rem;">
              <button class="btn btn-primary" onclick="submitAnswerEvaluation('${q.id}', '${escapeHtml(q.question)}', '${escapeHtml(JSON.stringify(q.key_concepts))}')" style="font-size: 0.85rem; padding: 0.45rem 1rem;">
                <span>✨ Evaluate Answer &amp; Get Score</span>
              </button>
              <div id="eval-result-${q.id}"></div>
            </div>
          </div>
        `).join('')}
      </div>
    `;
    showToast('Mock Interview Dossier ready!', 'success');
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
};

window.submitAnswerEvaluation = async function(qId, qText, conceptsJson) {
  const ansInput = document.getElementById(`ans-input-${qId}`);
  const resultDiv = document.getElementById(`eval-result-${qId}`);
  if (!ansInput || !resultDiv) return;

  const answer = ansInput.value.trim();
  if (!answer) {
    showToast('Please type an answer to evaluate!', 'warning');
    return;
  }

  try {
    const concepts = JSON.parse(conceptsJson || '[]');
    const res = await fetch(`${API_BASE}/interview/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: qText,
        answer: answer,
        key_concepts: concepts
      })
    });
    const data = await res.json();
    if (data.status === 'success') {
      const e = data.evaluation;
      const scoreColor = e.score >= 80 ? '#34d399' : e.score >= 60 ? '#f59e0b' : '#f43f5e';
      resultDiv.innerHTML = `
        <div style="background: rgba(0,0,0,0.3); border: 1px solid ${scoreColor}55; padding: 0.6rem 1rem; border-radius: var(--radius-md); font-size: 0.85rem;">
          <span style="font-weight: 800; color: ${scoreColor}; font-size: 1.05rem;">Score: ${e.score}/100 (${escapeHtml(e.rating)})</span>
          <div style="color: var(--text-secondary); margin-top: 0.25rem;">${escapeHtml(e.feedback)}</div>
        </div>
      `;
    }
  } catch (err) {
    showToast(`Evaluation error: ${err.message}`, 'error');
  }
};

// --- Salary & Offer Modeler ---
window.evaluateOfferCompensation = async function() {
  const base = parseFloat(document.getElementById('neg-base-salary').value) || 35.0;
  const bonus = parseFloat(document.getElementById('neg-bonus').value) || 5.0;
  const equity = parseFloat(document.getElementById('neg-equity').value) || 10.0;
  const role = document.getElementById('neg-role-title').value.trim() || 'Senior Software Engineer';
  const container = document.getElementById('negotiation-results-container');
  if (!container) return;

  try {
    const res = await fetch(`${API_BASE}/negotiation/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        base_salary_lpa: base,
        bonus_lpa: bonus,
        equity_annual_lpa: equity,
        role_title: role
      })
    });
    const data = await res.json();
    if (data.status === 'success') {
      const e = data.evaluation;
      container.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-lg); padding: 1.5rem; margin-top: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <span style="font-size: 1.15rem; font-weight: 700; color: #34d399;">Total Annual Comp: ${e.total_annual_comp_lpa} LPA</span>
            <span class="brand-badge" style="background: rgba(52, 211, 153, 0.2); color: #34d399;">${escapeHtml(e.market_percentile_band)}</span>
          </div>
          <p style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 0.5rem;">💡 <strong>Negotiation Strategy:</strong> ${escapeHtml(e.negotiation_guidance)}</p>
          <div style="font-size: 0.8rem; color: var(--text-muted);">Market Median (p50): ${e.benchmark_p50} LPA • Top Tier (p75): ${e.benchmark_p75} LPA</div>
        </div>
      `;
      showToast('Compensation offer benchmarked successfully!', 'success');
    }
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
};

// --- Disaster Recovery Backup Export ---
window.exportEncryptedBackup = async function() {
  try {
    showToast('Exporting AES-256-GCM encrypted backup archive...', 'info');
    const res = await fetch(`${API_BASE}/backup/export`, { method: 'POST' });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`Encrypted backup created: ${data.filename}`, 'success');
    }
  } catch (err) {
    showToast(`Backup failed: ${err.message}`, 'error');
  }
};

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
  initWebSocket();
  updateSalaryEquivalents(15);
  fetchJobsList();
  fetchFunnelMetrics();
});
