// JobCopilot — Manual pipeline actions: Recruiter Direct Call Logger (Step 8)
// and the Held Applications Queue + 1-Click HITL Resolution (Steps 6 & 7).
// Extracted from app.js (P1-6); self-contained classic script bundled after
// app.js (exposes only its window.* handlers).
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
        <button class="btn btn-primary btn-sm" data-action="resolveHeldApplication" data-event-id="${escapeHTML(h.event_id || '')}">
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
