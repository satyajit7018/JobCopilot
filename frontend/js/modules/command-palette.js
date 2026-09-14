// JobCopilot — Command Palette (Cmd/Ctrl + K)
// Extracted from app.js as the first step of the incremental modularization
// (P1-6). Loaded as a classic script AFTER app.js, so it shares the global
// lexical scope and can read app.js globals (state, els, escapeHTML,
// renderKanbanBoard, window.switchTab, …). Exposes window.toggleCmdPalette.
const PALETTE_COMMANDS = [
  { icon: '🎯', label: 'Jump to Job Pipeline',        key: 'P', run: () => window.switchTab('pipeline') },
  { icon: '⚡', label: 'Run 0-Day Discovery Cycle',   key: 'D', run: () => window.triggerDiscoveryCycle() },
  { icon: '🧠', label: 'Open Knowledge Vault',        key: 'V', run: () => window.switchTab('vault') },
  { icon: '🎙️', label: 'Open Mock Interview Studio',  key: 'I', run: () => window.switchTab('interview') },
  { icon: '💎', label: 'Salary & ESOP Modeler',       key: 'S', run: () => window.switchTab('negotiation') },
  { icon: '📧', label: 'Open Email Outreach',                    run: () => window.switchTab('email') },
  { icon: '🤖', label: 'Open Autopilot Bot',                     run: () => window.switchTab('bot') },
  { icon: '⚙️', label: 'Open Settings',                          run: () => window.switchTab('settings') },
  { icon: '🔒', label: 'Export Encrypted Backup',     key: 'B', run: () => window.exportEncryptedBackup && window.exportEncryptedBackup() },
];

let paletteActiveIndex = 0;

function buildPaletteItems(query) {
  const q = (query || '').trim().toLowerCase();
  const cmds = PALETTE_COMMANDS
    .filter(c => !q || c.label.toLowerCase().includes(q))
    .map(c => ({ type: 'cmd', icon: c.icon, label: c.label, badge: c.key || '', run: c.run }));

  let jobs = [];
  if (q.length >= 2 && Array.isArray(state.jobsList)) {
    jobs = state.jobsList
      .filter(j => ((j.company || '') + ' ' + (j.title || '')).toLowerCase().includes(q))
      .slice(0, 6)
      .map(j => ({
        type: 'job',
        icon: '💼',
        label: `${escapeHTML(j.company || 'Company')} — ${escapeHTML(j.title || 'Role')}`,
        badge: j.status || '',
        run: () => {
          window.switchTab('pipeline');
          if (els.pipelineSearchInput) {
            els.pipelineSearchInput.value = j.company || '';
          }
          renderKanbanBoard();
        }
      }));
  }
  return [...cmds, ...jobs];
}

function renderPaletteResults(query) {
  const list = document.getElementById('cmd-palette-list');
  if (!list) return;
  const items = buildPaletteItems(query);
  paletteActiveIndex = 0;
  if (!items.length) {
    list.innerHTML = '<div class="cmd-empty" style="padding: 16px; color: var(--text-muted); text-align: center; font-size: 13px;">No matches.</div>';
    list._items = [];
    return;
  }
  list._items = items;
  list.innerHTML = items.map((it, i) => `
    <div class="cmd-item ${i === 0 ? 'cmd-active' : ''}" data-palette-index="${i}">
      <span style="display: flex; align-items: center; gap: 8px;"><span>${it.icon}</span> <span>${it.label}</span></span>
      ${it.badge ? `<span class="cmd-k-badge">${escapeHTML(String(it.badge))}</span>` : ''}
    </div>`).join('');
}

function runPaletteItem(i) {
  const list = document.getElementById('cmd-palette-list');
  const item = list && list._items && list._items[i];
  if (!item) return;
  window.toggleCmdPalette(false);
  setTimeout(() => item.run(), 60);
}

window.toggleCmdPalette = function(forceOpen) {
  const overlay = document.getElementById('cmd-palette-overlay');
  if (!overlay) return;
  const isOpen = forceOpen !== undefined ? forceOpen : !overlay.classList.contains('active');
  overlay.classList.toggle('active', isOpen);
  if (isOpen) {
    const input = document.getElementById('cmd-palette-input');
    if (input) {
      input.value = '';
      input.focus();
    }
    renderPaletteResults('');
  }
};

document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    if (document.body.classList.contains('onboarding-mode')) return;
    window.toggleCmdPalette();
  }
});

function initPalette() {
  const input = document.getElementById('cmd-palette-input');
  const list = document.getElementById('cmd-palette-list');
  if (!input || !list) return;

  input.addEventListener('input', () => renderPaletteResults(input.value));

  input.addEventListener('keydown', (e) => {
    const items = list._items || [];
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      paletteActiveIndex = Math.min(paletteActiveIndex + 1, Math.max(0, items.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      paletteActiveIndex = Math.max(paletteActiveIndex - 1, 0);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      runPaletteItem(paletteActiveIndex);
      return;
    } else {
      return;
    }
    list.querySelectorAll('.cmd-item').forEach((el, i) =>
      el.classList.toggle('cmd-active', i === paletteActiveIndex));
    const active = list.querySelector('.cmd-active');
    if (active) active.scrollIntoView({ block: 'nearest' });
  });

  list.addEventListener('click', (e) => {
    const row = e.target.closest('[data-palette-index]');
    if (row) {
      runPaletteItem(parseInt(row.getAttribute('data-palette-index'), 10));
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPalette);
} else {
  initPalette();
}
