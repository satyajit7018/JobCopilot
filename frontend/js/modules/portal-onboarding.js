// JobCopilot — Portal Connection State Machine & Onboarding: portal card
// rendering, connect/toggle handlers, and post-onboarding pipeline routing.
// Extracted from app.js (P1-6); self-contained classic script bundled after
// app.js.

// ==========================================================================
// Portal Connection State Machine & Onboarding
// ==========================================================================
const PORTAL_DEFS = [
  { id: 'linkedin',  icon: '💼', name: 'LinkedIn Jobs',              desc: 'Easy Apply bot & InMail Radar for 800M+ professionals.' },
  { id: 'naukri',    icon: '🇮🇳', name: 'Naukri.com',                 desc: "India's #1 tech hiring portal — 0-day openings from Swiggy, Zepto, PhonePe." },
  { id: 'instahyre', icon: '🎯', name: 'Instahyre & Cutshort',       desc: 'AI-curated tech candidate matching with direct recruiter connections.' },
  { id: 'ats',       icon: '🏢', name: 'Greenhouse, Lever & Ashby',  desc: 'Direct enterprise ATS career feeds (Stripe, Figma, Uber).' },
  { id: 'cuvette',   icon: '🚀', name: 'Cuvette & YC Startups',      desc: 'High-growth startups & seed-stage openings from Y Combinator network.' },
  { id: 'indeed',    icon: '🌍', name: 'Indeed & Wellfound',          desc: 'Global remote & startup tech jobs across 60+ countries.' }
];

function renderPortalCards() {
  const grid = document.getElementById('portals-grid');
  if (grid) {
    grid.innerHTML = PORTAL_DEFS.map(p => {
      const isConn = state.connectedPortals[p.id];
      return `
        <div class="portal-card ${isConn ? 'connected' : ''}" data-portal-id="${p.id}"
             data-action="togglePortalConnection" data-portal="${p.id}">
          <div class="portal-card-top">
            <div style="display: flex; align-items: center; gap: 10px;">
              <span class="portal-icon">${p.icon}</span>
              <span class="portal-name">${p.name}</span>
            </div>
            <span class="portal-status ${isConn ? 'connected' : 'ready'}" id="portal-status-${p.id}">
              ${isConn ? '✓ Connected' : 'Ready to Connect'}
            </span>
          </div>
          <div class="portal-desc">${p.desc}</div>
        </div>`;
    }).join('');
  }

  const settingsStatus = document.getElementById('settings-portals-status');
  if (settingsStatus) {
    settingsStatus.innerHTML = PORTAL_DEFS.map(p => {
      const isConn = state.connectedPortals[p.id];
      return `
        <div style="padding: 8px 12px; border-radius: var(--radius-sm); background: ${isConn ? 'rgba(16, 185, 129, 0.1)' : 'rgba(255, 255, 255, 0.04)'}; border: 1px solid ${isConn ? 'rgba(16, 185, 129, 0.3)' : 'var(--border-subtle)'}; display: flex; align-items: center; gap: 8px;">
          <span>${p.icon}</span>
          <span style="font-size: 12px; font-weight: 600; color: ${isConn ? 'var(--accent-emerald)' : 'var(--text-muted)'};">${p.name}</span>
        </div>`;
    }).join('');
  }
  if (typeof window.updatePortalCtaButton === 'function') window.updatePortalCtaButton();
}

window.updatePortalCtaButton = function() {
  const textEl = document.getElementById('btn-continue-cockpit-text');
  if (!textEl) return;
  const connectedCount = Object.values(state.connectedPortals || {}).filter(Boolean).length;
  if (connectedCount === 6) {
    textEl.textContent = 'Continue with All 6 Portals ➔';
  } else if (connectedCount > 0) {
    textEl.textContent = `Continue with ${connectedCount} Connected Portal${connectedCount > 1 ? 's' : ''} ➔`;
  } else {
    textEl.textContent = 'Continue to Main Cockpit ➔';
  }
};

window.togglePortalConnection = function(target) {
  const portalId = (typeof target === 'string') ? target : target?.getAttribute?.('data-portal') || target?.closest?.('[data-portal]')?.getAttribute('data-portal');
  if (!portalId || !state.connectedPortals.hasOwnProperty(portalId)) return;

  state.connectedPortals[portalId] = !state.connectedPortals[portalId];
  try {
    localStorage.setItem('jobcopilot_connected_portals', JSON.stringify(state.connectedPortals));
  } catch (_) {}

  const card = document.querySelector(`.portal-card[data-portal-id="${portalId}"]`);
  const badge = document.getElementById(`portal-status-${portalId}`);
  if (card) card.classList.toggle('connected', state.connectedPortals[portalId]);
  if (badge) {
    badge.className = `portal-status ${state.connectedPortals[portalId] ? 'connected' : 'ready'}`;
    badge.textContent = state.connectedPortals[portalId] ? '✓ Connected' : 'Ready to Connect';
  }

  // Update dynamic CTA button copy
  window.updatePortalCtaButton();

  // Update Settings badges if Settings view is loaded
  const settingsStatus = document.getElementById('settings-portals-status');
  if (settingsStatus) renderPortalCards();

  if (state.connectedPortals[portalId]) {
    showToast(`${PORTAL_DEFS.find(p => p.id === portalId)?.name || portalId} connected!`, 'success');
    if (typeof window.playProceduralChime === 'function') window.playProceduralChime('success');
  }
};

window.connectAllPortals = function() {
  Object.keys(state.connectedPortals).forEach(id => {
    state.connectedPortals[id] = true;
  });
  try {
    localStorage.setItem('jobcopilot_connected_portals', JSON.stringify(state.connectedPortals));
  } catch (_) {}
  renderPortalCards();
  window.updatePortalCtaButton();
  showToast('All 6 job portals connected! Ready to discover openings.', 'success');
  if (typeof window.playProceduralChime === 'function') window.playProceduralChime('success');
};

window.completePortalOnboarding = function() {
  localStorage.setItem('jobcopilot_portals_configured', 'true');
  try {
    localStorage.setItem('jobcopilot_connected_portals', JSON.stringify(state.connectedPortals));
  } catch (_) {}

  const connectedPortalsList = PORTAL_DEFS.filter(p => state.connectedPortals[p.id]);
  const hasConnected = connectedPortalsList.length > 0;

  // Auto-select "⭐ My Portals" filter if portals are connected
  if (hasConnected) {
    state.currentPipelineFilter = 'CONNECTED';
    document.querySelectorAll('.filter-pill').forEach(p => {
      p.classList.toggle('active', p.getAttribute('data-filter') === 'CONNECTED');
    });
  } else {
    state.currentPipelineFilter = 'ALL';
    document.querySelectorAll('.filter-pill').forEach(p => {
      p.classList.toggle('active', p.getAttribute('data-filter') === 'ALL');
    });
  }

  window.switchTab('pipeline');
  renderKanbanBoard(); // filter pill was toggled programmatically above — re-render to match

  // Trigger welcome banner if not previously dismissed
  const isDismissed = localStorage.getItem('jobcopilot_welcome_banner_dismissed') === 'true';
  const banner = document.getElementById('pipeline-welcome-banner');
  if (banner && !isDismissed) {
    const summaryEl = document.getElementById('welcome-banner-portals-summary');
    if (summaryEl) {
      const namesStr = hasConnected
        ? connectedPortalsList.map(p => p.name).join(', ')
        : 'your chosen sources';
      summaryEl.innerHTML = `Actively monitoring <strong>${escapeHTML(namesStr)}</strong>. <a href="#" data-action="switchTab" data-tab="onboarding" class="welcome-banner-link">Upload your resume</a> anytime in Profile &amp; Resume to calibrate 95%+ precision match scoring.`;
    }
    banner.style.display = 'flex';
  }

  showToast('Welcome to your cockpit! Pipeline is ready for 0-day discovery.', 'success');
};

window.dismissWelcomeBanner = function() {
  const banner = document.getElementById('pipeline-welcome-banner');
  if (banner) banner.style.display = 'none';
  try {
    localStorage.setItem('jobcopilot_welcome_banner_dismissed', 'true');
  } catch (_) {}
};
