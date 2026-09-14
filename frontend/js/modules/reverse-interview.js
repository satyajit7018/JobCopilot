// JobCopilot — Reverse-Interview Questions & Interviewer Sleuth: generates
// smart questions to ask, and recon on the interviewer. Extracted from app.js
// (P1-6); self-contained classic script bundled after app.js.
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
    container.innerHTML = '<div class="empty-state-text">Tailored reverse-interview questions ready.</div>';
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
