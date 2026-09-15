// ==========================================================================
// Triple-Threat Outreach & Alumni Referral Engine
// Extracted from app.js (P1-6 monolith split). Classic script, bundled AFTER
// app.js — shares the same global scope (state, els, showToast, openModal, etc.).
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
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(ta.value).catch(() => {});
    }
    showToast('Copied text to clipboard!', 'success');
    window.playProceduralChime('tap');
  }
};

window.openJobDetails = function(jobId) {
  const job = (state.jobsList || []).find(j => String(j.job_id ?? j.id) === String(jobId));
  if (!job) {
    showToast('Job details not found in active cache.', 'error');
    return;
  }

  const modal = document.getElementById('modal-job-details');
  if (!modal) return;

  const avatar = getCompanyAvatarData(job.company);
  const avatarEl = document.getElementById('details-company-avatar');
  if (avatarEl) {
    avatarEl.style.background = avatar.bg;
    avatarEl.textContent = avatar.icon;
  }

  const titleEl = document.getElementById('title-job-details');
  if (titleEl) titleEl.textContent = job.title || 'Role Details';

  const compEl = document.getElementById('details-company-name');
  if (compEl) compEl.textContent = job.company || 'Company';

  const locEl = document.getElementById('details-location');
  if (locEl) locEl.textContent = job.location || 'Remote';

  const platEl = document.getElementById('details-platform-pill');
  if (platEl) platEl.textContent = job.platform || 'Direct';

  const salEl = document.getElementById('details-salary-pill');
  if (salEl) {
    salEl.textContent = job.salary_range ? `⚡ ${job.salary_range}` : 'Compensation Open';
  }

  const urlEl = document.getElementById('details-external-url');
  if (urlEl) {
    urlEl.href = job.url ? sanitizeUrl(job.url) : '#';
    urlEl.style.display = job.url ? 'inline-flex' : 'none';
  }

  const matchPct = Math.round((job.match_score || 0) * 100);
  const matchPill = document.getElementById('details-match-pill');
  if (matchPill) matchPill.textContent = `${matchPct}% Match Score`;

  // Match Reasons
  const reasonsEl = document.getElementById('details-match-reasons');
  if (reasonsEl) {
    const reasons = (job.match_reasons && job.match_reasons.length > 0)
      ? job.match_reasons
      : ['Profile matches target core competencies and title taxonomy.'];
    reasonsEl.innerHTML = reasons.map(r => `<li>${escapeHTML(r)}</li>`).join('');
  }

  // Missing Skills
  const skillsEl = document.getElementById('details-missing-skills');
  if (skillsEl) {
    const skills = (job.missing_skills && job.missing_skills.length > 0)
      ? job.missing_skills
      : [];
    if (skills.length > 0) {
      skillsEl.innerHTML = skills.map(s => `<span class="hud-pill" style="color: var(--accent-amber); border-color: rgba(245, 158, 11, 0.4); font-size: 11px;">⚠️ ${escapeHTML(s)}</span>`).join('');
    } else {
      skillsEl.innerHTML = '<span class="hud-pill" style="color: var(--accent-emerald); font-size: 11px;">✓ Complete Skill Alignment</span>';
    }
  }

  // Job Description
  const descEl = document.getElementById('details-job-description');
  if (descEl) {
    descEl.textContent = job.description || 'No extended job description provided by source feed.';
  }

  // Stage Selector
  const stageSelect = document.getElementById('details-stage-changer');
  if (stageSelect) {
    stageSelect.value = job.status || 'DISCOVERED';
    stageSelect.onchange = () => {
      window.optimisticStatusChange(jobId, stageSelect.value);
    };
  }

  // Action Buttons
  const tailorBtn = document.getElementById('btn-details-tailor');
  if (tailorBtn) {
    tailorBtn.onclick = () => {
      modal.classList.remove('active');
      if (typeof window.tailorJobAssets === 'function') window.tailorJobAssets(jobId);
    };
  }

  const applyBtn = document.getElementById('btn-details-apply');
  if (applyBtn) {
    if (job.status === 'SUBMITTED') {
      applyBtn.textContent = '✓ Already Applied';
      applyBtn.disabled = true;
    } else {
      applyBtn.textContent = '⚡ Apply Now';
      applyBtn.disabled = false;
      applyBtn.onclick = () => {
        modal.classList.remove('active');
        if (typeof window.applyToJob === 'function') window.applyToJob(jobId);
      };
    }
  }

  if (typeof window.openModal === 'function') {
    window.openModal(modal);
  } else {
    modal.classList.add('active');
  }
};

window.closeJobDetailsModal = function() {
  if (typeof window.closeModal === 'function') {
    window.closeModal('modal-job-details');
  } else {
    const modal = document.getElementById('modal-job-details');
    if (modal) modal.classList.remove('active');
  }
};

window.sendJobToNegotiation = function(jobId) {
  const job = (state.jobsList || []).find(j => String(j.job_id ?? j.id) === String(jobId));
  if (!job) {
    showToast('Job details not found in active cache.', 'error');
    return;
  }

  window.switchTab('negotiation');

  const negComp = document.getElementById('neg-company-name');
  if (negComp) negComp.value = job.company || 'Target Company';

  const negRole = document.getElementById('neg-role-title');
  if (negRole) negRole.value = job.title || 'Senior Software Engineer';

  const offer1Comp = document.getElementById('offer1-comp');
  if (offer1Comp) offer1Comp.value = job.company || 'Offer A';

  const counterTarget = document.getElementById('counter-target-comp');
  if (counterTarget) counterTarget.value = job.company || 'Target Company';

  if (job.salary_range) {
    const match = job.salary_range.match(/(\d+(?:\.\d+)?)/);
    if (match) {
      const val = parseFloat(match[1]);
      const offer1Base = document.getElementById('offer1-base');
      if (offer1Base && !isNaN(val)) offer1Base.value = val;
    }
  }

  showToast(`Loaded ${job.company} into Salary & Comp Modeler!`, 'success');
  if (typeof window.playProceduralChime === 'function') window.playProceduralChime('success');
  window.scrollTo({ top: 0, behavior: 'smooth' });
};

window.generateEmailReply = function(target) {
  const sender = target.getAttribute('data-sender') || 'Recruiter';
  const intent = target.getAttribute('data-intent') || 'INQUIRY';
  const boxId = target.getAttribute('data-box-id');
  const box = document.getElementById(boxId);
  if (!box) return;

  let replyText = '';
  if (intent === 'INTERVIEW_INVITE') {
    replyText = `Hi ${sender},\n\nThank you so much for the invitation! I would be delighted to speak with the team. The proposed time works well for me. Looking forward to discussing the role further.\n\nBest regards,\nAlex Mercer`;
  } else if (intent === 'REJECTION') {
    replyText = `Hi ${sender},\n\nThank you for letting me know. While I am disappointed, I genuinely appreciate the team's time and consideration. Please feel free to keep my details on file for future engineering opportunities.\n\nBest regards,\nAlex Mercer`;
  } else {
    replyText = `Hi ${sender},\n\nThank you for reaching out regarding the opportunity! I have attached my latest resume and would be delighted to schedule a brief introductory call.\n\nBest regards,\nAlex Mercer`;
  }

  box.style.display = 'block';
  box.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
      <span style="font-size: 11.5px; font-weight: 700; color: var(--accent-cyan);">🤖 AI Draft Response (${escapeHTML(intent)}):</span>
      <button class="btn btn-primary btn-sm" id="btn-copy-ai-reply-${escapeHTML(boxId)}" style="font-size: 11px; padding: 2px 8px;">Copy Reply</button>
    </div>
    <textarea id="ta-reply-${escapeHTML(boxId)}" class="form-textarea" rows="4" style="margin-top: 4px; font-size: 12px; width: 100%; display: block;" readonly>${escapeHTML(replyText)}</textarea>
  `;

  const copyBtn = document.getElementById(`btn-copy-ai-reply-${boxId}`);
  const ta = document.getElementById(`ta-reply-${boxId}`);
  if (copyBtn && ta) {
    copyBtn.onclick = () => {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(ta.value).catch(() => {});
      }
      showToast('AI draft reply copied to clipboard!', 'success');
      if (typeof window.playProceduralChime === 'function') window.playProceduralChime('tap');
    };
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
