// JobCopilot — Multi-Offer Comparison Matrix & Counter-Offer Generator:
// offer compensation evaluation, ESOP/equity simulation, multi-offer ranking,
// and advanced counter-offer script generation. Extracted from app.js (P1-6);
// classic script bundled after app.js (fully self-contained — no external refs
// to its internals; exposes only its window.* handlers).
// ==========================================================================
// Multi-Offer Comparison Matrix & Counter-Offer Generator
// ==========================================================================
function posNum(id, fallback = 0) {
  const el = document.getElementById(id);
  if (!el) return fallback;
  const v = parseFloat(el.value);
  return (Number.isFinite(v) && v >= 0) ? v : fallback;
}

window.runMultiOfferComparison = async function() {
  const o1 = {
    company: document.getElementById('offer1-comp')?.value || 'Stripe',
    base_lpa: posNum('offer1-base', 50),
    bonus_lpa: posNum('offer1-bonus', 10),
    equity_grant_total_lpa: posNum('offer1-equity', 60),
    sign_on_lpa: posNum('offer1-signon', 15),
    role_title: 'Senior Engineer'
  };
  const o2 = {
    company: document.getElementById('offer2-comp')?.value || 'Uber',
    base_lpa: posNum('offer2-base', 45),
    bonus_lpa: posNum('offer2-bonus', 8),
    equity_grant_total_lpa: posNum('offer2-equity', 80),
    sign_on_lpa: posNum('offer2-signon', 10),
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
          💡 <strong>Negotiation Strategy:</strong> ${escapeHTML(data.strategic_recommendation)}
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
          <button class="btn btn-secondary btn-sm" data-action="copyCounterEmail">Copy Email</button>
        </div>
        <textarea id="counter-email-box" class="form-textarea" rows="6" readonly style="font-size: 12.5px; margin-bottom: 12px;">${escapeHTML(scripts.negotiation_email || '')}</textarea>

        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <strong style="color: #fbbf24; font-size: 13.5px;">📞 Phone Negotiation Talking Points:</strong>
          <button class="btn btn-secondary btn-sm" data-action="copyCounterPhone">Copy Talking Points</button>
        </div>
        <textarea id="counter-phone-box" class="form-textarea" rows="5" readonly style="font-size: 12px; color: #cbd5e1;">${escapeHTML(scripts.phone_talking_points || '')}</textarea>
      </div>
    `;
    showToast('Executive negotiation package generated!', 'success');
    window.playProceduralChime('success');
  } catch (e) {
    container.innerHTML = '<div style="color: var(--text-muted);">Failed to generate counter script.</div>';
  }
};

window.evaluateOfferCompensation = async function() {
  const baseSalary = posNum('neg-base-salary', 35);
  const company = document.getElementById('neg-company-name')?.value || 'Target Company';
  const roleTitle = document.getElementById('neg-role-title')?.value || 'Senior Software Engineer';
  const container = document.getElementById('negotiation-results-container');
  if (!container) return;

  container.innerHTML = '<div style="color: var(--accent-cyan); font-size: 12.5px;">Benchmarking against Indian & Global compensation datasets...</div>';

  try {
    const res = await authFetch(`${API_BASE}/negotiation/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        base_salary_lpa: baseSalary,
        bonus_lpa: 0.0,
        equity_annual_lpa: 0.0,
        role_title: roleTitle
      })
    });
    const data = await res.json();
    const ev = data.evaluation || {};
    const recRange = ev.recommended_counter_range || (baseSalary > 0 ? ((baseSalary * 1.15).toFixed(1) + ' - ' + (baseSalary * 1.3).toFixed(1)) : '—');
    container.innerHTML = `
      <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-md); padding: 1.25rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <strong style="font-size: 14px; color: #34d399;">Offer Percentile: ${escapeHTML(ev.percentile || 'Top 15%')}</strong>
          <span class="badge badge-success">${escapeHTML(ev.verdict || 'Competitive')}</span>
        </div>
        <p style="font-size: 13px; color: #cbd5e1; margin-bottom: 10px;">${escapeHTML(ev.market_summary || ('Salary matches market benchmarks for ' + roleTitle))}</p>
        <div style="font-size: 12px; color: #94a3b8;">
          <strong>Target Counter Range:</strong> ₹${escapeHTML(recRange)} LPA
        </div>
      </div>
    `;
    showToast('Compensation benchmarking complete!', 'success');
    window.playProceduralChime('success');
  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-rose); font-size: 12px;">Evaluation failed: ${escapeHTML(err.message)}</div>`;
  }
};

window.simulateEsopEquity = async function() {
  const options = posNum('esop-options-count', 15000);
  const totalShares = posNum('esop-total-shares', 10000000);
  const valuation = posNum('esop-valuation-usd', 50000000);
  const container = document.getElementById('esop-results-container');
  if (!container) return;

  container.innerHTML = '<div style="color: var(--accent-cyan); font-size: 12.5px;">Simulating exit multiples & ownership dilution...</div>';

  try {
    const res = await authFetch(`${API_BASE}/negotiation/equity`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        options_count: options,
        total_company_shares: totalShares > 0 ? totalShares : 1,
        current_valuation_usd: valuation,
        strike_price: 0.0
      })
    });
    const data = await res.json();
    const eq = data.equity_model || {};
    const ownership = totalShares > 0 ? (options / totalShares) : 0;
    const pct = Number.isFinite(ownership) ? (ownership * 100).toFixed(4) : '0.0000';
    const currVal = Number.isFinite(ownership * valuation) ? Math.round(ownership * valuation).toLocaleString() : '0';

    const exit3x = Number.isFinite(ownership * valuation * 3) ? Math.round(ownership * valuation * 3).toLocaleString() : '0';
    const exit5x = Number.isFinite(ownership * valuation * 5) ? Math.round(ownership * valuation * 5).toLocaleString() : '0';

    container.innerHTML = `
      <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: var(--radius-md); padding: 1.25rem;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
          <strong style="color: #fbbf24; font-size: 14px;">Equity Ownership: ${pct}%</strong>
          <span style="font-size: 12px; color: #cbd5e1;">Current Value: $${currVal}</span>
        </div>
        <div style="font-size: 12px; color: #94a3b8; line-height: 1.5;">
          ${eq.scenarios ? Object.entries(eq.scenarios).map(([k, v]) => `<div>• <strong>${escapeHTML(k)}:</strong> $${escapeHTML(String(v))}</div>`).join('') : `<div>• Projected 3x Exit: $${exit3x}</div><div>• Projected 5x Exit: $${exit5x}</div>`}
        </div>
      </div>
    `;
    showToast('ESOP equity modeled!', 'success');
    window.playProceduralChime('success');
  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-rose); font-size: 12px;">ESOP simulation failed: ${escapeHTML(err.message)}</div>`;
  }
};
