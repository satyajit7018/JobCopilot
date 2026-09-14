// JobCopilot — Inbound Email Radar (Step 8 & 9): IMAP push-radar sync and
// rendering of detected recruiter emails. Extracted from app.js (P1-6);
// self-contained classic script bundled after app.js.
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

  els.emailRadarFeed.innerHTML = emails.map((m, idx) => {
    let badgeClass = 'badge-info';
    if (m.intent === 'INTERVIEW_INVITE') badgeClass = 'badge-low';
    if (m.intent === 'REJECTION') badgeClass = 'badge-critical';

    const matchLink = (m.body_text || '').match(/(https?:\/\/(?:meet\.google\.com|zoom\.us|teams\.microsoft\.com|calendly\.com)[^\s]+)/i);
    const rawMeetingUrl = matchLink ? matchLink[1] : null;
    const meetingUrl = rawMeetingUrl ? sanitizeUrl(rawMeetingUrl) : null;
    const boxId = `email-reply-box-${idx}`;

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

        <div style="display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap;">
          ${meetingUrl ? `
            <a href="${meetingUrl}" target="_blank" rel="noopener noreferrer" class="gmeet-btn" style="flex: 1; min-width: 160px;">
              <span>📹 Join Video Interview Meeting</span>
            </a>
          ` : ''}
          <button class="btn btn-secondary btn-sm" data-action="generateEmailReply" data-sender="${escapeHTML(m.sender || '')}" data-intent="${escapeHTML(m.intent || '')}" data-subject="${escapeHTML(m.subject || '')}" data-box-id="${boxId}" style="font-size: 11.5px; padding: 5px 10px;">
            <span>✉️ Quick AI Reply</span>
          </button>
          <button class="btn btn-secondary btn-sm" data-action="openLogCallModal" style="font-size: 11.5px; padding: 5px 10px;">
            <span>📞 Log Call / Update</span>
          </button>
        </div>
        <div id="${boxId}" style="display: none; margin-top: 8px; background: rgba(0,0,0,0.3); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 8px;"></div>
      </div>
    `;
  }).join('');
}
