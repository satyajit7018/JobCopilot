# Implementation Plan — Command Palette + Optimistic UI/Undo

Two self-contained features. Do them in separate branches/PRs. All paths are relative to `frontend/`.

---

## FEATURE 1 — Make the Command Palette actually work

**Status: ~60% already exists.** The overlay, CSS, `Cmd/Ctrl+K` toggle, and 6 static commands are built. You're adding: live search, keyboard navigation, and searching real jobs.

### Files touched
- `js/app.js`
- `index.html` (tiny — one attribute + one empty container, optional)

### Step 1.1 — Fix the toggle bug (do this first, it's a real bug)
`window.toggleCmdPalette` at **app.js:2685** ignores its argument. `toggleCmdPalette(false)` called from the Escape handler (app.js:3754) and dispatcher (app.js:2728) will *open* the palette when it's closed. Replace with:

```js
window.toggleCmdPalette = function(forceOpen) {
  const overlay = document.getElementById('cmd-palette-overlay');
  if (!overlay) return;
  const isOpen = forceOpen !== undefined ? forceOpen : !overlay.classList.contains('active');
  overlay.classList.toggle('active', isOpen);
  if (isOpen) {
    const input = document.getElementById('cmd-palette-input');
    if (input) { input.value = ''; input.focus(); }
    renderPaletteResults('');        // reset list every open (Step 1.3)
  }
};
```

### Step 1.2 — Define commands as data (not hardcoded HTML)
Right above `toggleCmdPalette`, add a command registry. Each item = label + the action it triggers. Reuse the existing `switchTab`/`triggerDiscoveryCycle`/etc. functions — no new backend work.

```js
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
```

### Step 1.3 — Render results (static commands + live job search)
Add a render function. Jobs come from `state.jobsList` (already in memory — no fetch needed). Selecting a job jumps to the pipeline and scrolls/opens it.

```js
let paletteActiveIndex = 0;

function buildPaletteItems(query) {
  const q = query.trim().toLowerCase();
  const cmds = PALETTE_COMMANDS
    .filter(c => !q || c.label.toLowerCase().includes(q))
    .map(c => ({ type: 'cmd', icon: c.icon, label: c.label, badge: c.key || '', run: c.run }));

  let jobs = [];
  if (q.length >= 2 && Array.isArray(state.jobsList)) {
    jobs = state.jobsList
      .filter(j => (j.company + ' ' + j.title).toLowerCase().includes(q))
      .slice(0, 6)
      .map(j => ({
        type: 'job', icon: '💼',
        label: `${escapeHTML(j.company)} — ${escapeHTML(j.title)}`,
        badge: j.status || '',
        run: () => { window.switchTab('pipeline');
                     if (els.pipelineSearchInput) { els.pipelineSearchInput.value = j.company; }
                     renderKanbanBoard(); }
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
    list.innerHTML = '<div class="cmd-empty" style="padding:16px;color:var(--text-muted);">No matches.</div>';
    list._items = [];
    return;
  }
  list._items = items;   // stash for Enter/arrow handlers
  list.innerHTML = items.map((it, i) => `
    <div class="cmd-item ${i === 0 ? 'cmd-active' : ''}" data-palette-index="${i}">
      <span>${it.icon} ${it.label}</span>
      ${it.badge ? `<span class="cmd-k-badge">${escapeHTML(String(it.badge))}</span>` : ''}
    </div>`).join('');
}

function runPaletteItem(i) {
  const list = document.getElementById('cmd-palette-list');
  const item = list && list._items && list._items[i];
  if (!item) return;
  window.toggleCmdPalette(false);
  setTimeout(() => item.run(), 60);   // let overlay close first
}
```

> Note: this replaces the hardcoded `<div class="cmd-item">` list in **index.html:1472–1497** with a single empty `<div class="cmd-palette-list" id="cmd-palette-list"></div>`. The list is now rendered by JS.

### Step 1.4 — Wire input + keyboard nav
Add near your other init/listeners (e.g. after the `Cmd+K` listener at app.js:2700):

```js
(function initPalette() {
  const input = document.getElementById('cmd-palette-input');
  const list  = document.getElementById('cmd-palette-list');
  if (!input || !list) return;

  input.addEventListener('input', () => renderPaletteResults(input.value));

  input.addEventListener('keydown', (e) => {
    const items = list._items || [];
    if (e.key === 'ArrowDown') { e.preventDefault(); paletteActiveIndex = Math.min(paletteActiveIndex + 1, items.length - 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); paletteActiveIndex = Math.max(paletteActiveIndex - 1, 0); }
    else if (e.key === 'Enter') { e.preventDefault(); runPaletteItem(paletteActiveIndex); return; }
    else return;
    list.querySelectorAll('.cmd-item').forEach((el, i) =>
      el.classList.toggle('cmd-active', i === paletteActiveIndex));
    const active = list.querySelector('.cmd-active');
    if (active) active.scrollIntoView({ block: 'nearest' });
  });

  // click a result
  list.addEventListener('click', (e) => {
    const row = e.target.closest('[data-palette-index]');
    if (row) runPaletteItem(parseInt(row.getAttribute('data-palette-index'), 10));
  });
})();
```

### Step 1.5 — CSS for the active row
Add to `css/style.css` near the `.cmd-item` rules (~line 1347):

```css
.cmd-item.cmd-active { background: rgba(99,102,241,0.18); }
.cmd-item { cursor: pointer; }
```

### Step 1.6 — Verify
- `Cmd/Ctrl+K` opens, input auto-focused, empty query shows all commands.
- Type `pipe` → filters to Pipeline command. Type a real company name (≥2 chars) → job rows appear.
- ↑/↓ moves highlight, Enter runs it, palette closes and navigates.
- Press Escape while a modal is open (palette closed) → palette does NOT pop open (the Step 1.1 bug fix).
- Mobile 375px: the `.cmd-k-trigger` in the topbar (index.html:189) still opens it.

---

## FEATURE 2 — Optimistic UI + Undo on pipeline actions

**Core idea:** `state.jobsList` is the single client-side source of truth; `renderKanbanBoard()` redraws from it. Today mutations call the API, wait, then `fetchJobsList()` (full refetch). Instead: **mutate `state.jobsList` locally + re-render immediately**, fire the API in the background, and **roll back + toast on failure**. Add an **Undo** affordance to the success toast.

### Files touched
- `js/app.js`

### Step 2.1 — Upgrade `showToast` to support an action button
Current `showToast` (app.js:288) has no action support. Add an optional 3rd arg:

```js
function showToast(message, type = 'info', action = null) {
  if (!els.toastContainer) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  let icon = '⚡';
  if (type === 'success') icon = '✓';
  if (type === 'error') icon = '✕';
  if (type === 'info') icon = 'ℹ';

  toast.innerHTML = `<span style="font-weight:700;">${icon}</span><span>${message}</span>`;
  if (action && action.label) {
    const btn = document.createElement('button');
    btn.className = 'toast-action-btn';
    btn.textContent = action.label;
    btn.onclick = () => { action.onClick(); toast.remove(); };
    toast.appendChild(btn);
  }
  els.toastContainer.appendChild(toast);

  const ttl = action ? 6000 : 4000;   // give people time to hit Undo
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, ttl);
}
```
CSS for the button (style.css, near toast styles):
```css
.toast-action-btn {
  margin-left: 12px; padding: 3px 10px; border-radius: 6px; cursor: pointer;
  background: rgba(255,255,255,0.15); color: inherit;
  border: 1px solid rgba(255,255,255,0.25); font-weight: 700; font-size: 12px;
}
.toast-action-btn:hover { background: rgba(255,255,255,0.28); }
```

### Step 2.2 — A generic optimistic helper
Add one reusable function so every mutation follows the same pattern:

```js
// Optimistically change a job's status, re-render, sync to server, roll back on failure.
async function optimisticStatusChange(jobId, newStatus, { verb = 'Moved', endpoint, method = 'POST', body } = {}) {
  const job = state.jobsList.find(j => String(j.job_id ?? j.id) === String(jobId));
  if (!job) return;
  const prevStatus = job.status;
  if (prevStatus === newStatus) return;

  // 1. optimistic local update
  job.status = newStatus;
  renderKanbanBoard();

  // 2. success toast with Undo
  showToast(`${verb} ${job.company}`, 'success', {
    label: 'Undo',
    onClick: () => { job.status = prevStatus; renderKanbanBoard();
                     syncStatus(jobId, prevStatus, endpoint, method, body); }
  });

  // 3. background sync; roll back if it fails
  try {
    await syncStatus(jobId, newStatus, endpoint, method, body);
  } catch (err) {
    job.status = prevStatus;
    renderKanbanBoard();
    showToast(`Couldn't save — reverted. ${err.message}`, 'error');
  }
}

async function syncStatus(jobId, status, endpoint, method, body) {
  const url = endpoint || `${API_BASE}/jobs/${jobId}/status`;   // adjust to your real route
  const res = await authFetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || { status })
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json().catch(() => ({}));
}
```

> **Before coding:** confirm the real status-update endpoint. Grep the backend:
> `grep -rn "status" backend/app/api/routers/ | grep -i "patch\|put\|post"`
> If none exists, that's a small backend add (a `PATCH /jobs/{id}` that sets status). Note it in the PR.

### Step 2.3 — Convert `applyToJob` to optimistic (app.js:1168)
Right now it toasts "Initializing…", awaits, then `fetchJobsList()`. Make the card jump to **SUBMITTED** instantly:

```js
window.applyToJob = async function(jobId) {
  const job = state.jobsList.find(j => String(j.job_id ?? j.id) === String(jobId));
  const prev = job ? job.status : null;
  if (job) { job.status = 'SUBMITTED'; renderKanbanBoard(); }
  appendTerminalLog('BOT', `Launching apply for Job ID: ${jobId}`);
  try {
    const res = await authFetch(`${API_BASE}/bot/apply/${jobId}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`Applied to ${data.company || job?.company || 'job'} (${data.mode})`, 'success');
      fetchFunnelMetrics();
    } else { throw new Error(data.detail || 'Apply failed'); }
  } catch (err) {
    if (job) { job.status = prev; renderKanbanBoard(); }   // roll back
    showToast(`Apply failed — reverted. ${err.message}`, 'error');
  }
};
```
(Note: drop the immediate `fetchJobsList()` — the optimistic update already reflects the change; refetch only funnel metrics.)

### Step 2.4 — (Optional, higher effort) drag-to-move between columns
If you want Linear-style drag between kanban columns, add HTML5 drag events to cards in `renderJobCardHTML` (`draggable="true"`, `data-job-id`) and `dragover`/`drop` on each `.kanban-cards-list`. On drop, call `optimisticStatusChange(jobId, columnStatus, {verb:'Moved'})`. The column→status map: `discovered→DISCOVERED, queued→QUEUED, submitted→SUBMITTED, interview→INTERVIEW, offer→OFFER`. Do this only after 2.1–2.3 are solid; it's the one piece with real complexity (touch drag on mobile is fiddly — consider a long-press "move to…" menu on mobile instead).

### Step 2.5 — Verify
- Click **Apply Now** on a Discovered card → it jumps to Submitted instantly (no spinner wait).
- Kill the network (DevTools offline) and Apply → card reverts, red "reverted" toast.
- Success toast shows **Undo** for 6s; clicking it puts the card back and re-syncs.
- `renderKanbanBoard()` counts (column badges + mobile segment counts) update on every optimistic change — they already read from `state.jobsList`, so this is automatic.
- Desktop + 375px mobile both re-render correctly.

---

## Suggested order & PRs
1. **PR A:** Feature 1 (palette) — self-contained, no backend dependency, low risk. Ship first.
2. **PR B:** Feature 2 — do 2.1→2.3 first (real value, low risk). Confirm the status endpoint before starting. Leave 2.4 (drag) for a follow-up PR.

Each PR: branch → commit → push → open PR → watch CI → verify live at desktop + 375px → merge.
