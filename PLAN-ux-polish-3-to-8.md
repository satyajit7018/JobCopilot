# Implementation Plan — UX Polish (Features 3–8)

Companion to `PLAN-palette-and-optimistic-ui.md` (features 1–2). Same conventions: paths relative to `frontend/`, each feature is its own branch/PR, verify at desktop + 375px mobile.

Ordering by effort-vs-payoff: **3 → 4 → 8 → 5 → 6 → 7**.

---

## FEATURE 3 — Consolidated toast / loading / error system

**Why:** There are **42 `catch (err)` blocks** and **~40 hand-written `showToast(..., 'error')`** calls across `app.js`, each formatting errors differently (`Save error:`, `Bot apply error:`, `Vector query failed:`…). Loading states are ad-hoc `innerHTML = 'Loading...'`. Loved apps (Linear) use ONE toast system, ONE skeleton loader, ONE error path. This is cleanup + consistency, low risk.

### Files touched
- `js/app.js`, `css/style.css`

### Step 3.1 — One error handler
Add near `showToast` (app.js:288):
```js
// Central error reporter — every catch block funnels through here.
function reportError(context, err) {
  const msg = (err && err.message) ? err.message : String(err || 'Unknown error');
  console.error(`[${context}]`, err);
  showToast(`${context}: ${msg}`, 'error');
}
```
Then sweep the 42 catch blocks. Pattern to replace:
```js
} catch (err) { showToast(`Save error: ${err.message}`, 'error'); }
// becomes:
} catch (err) { reportError('Save', err); }
```
Do it view-by-view (search `catch (err)`), not all at once, so each is easy to eyeball.

### Step 3.2 — One skeleton loader
Add a helper + CSS so every list/card region shows the same shimmer while loading:
```js
function renderSkeleton(el, rows = 3) {
  if (!el) return;
  el.innerHTML = Array.from({ length: rows })
    .map(() => '<div class="skeleton-row"></div>').join('');
}
```
```css
.skeleton-row {
  height: 44px; margin: 8px 0; border-radius: 8px;
  background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.09) 37%, rgba(255,255,255,0.04) 63%);
  background-size: 400% 100%; animation: skeletonShimmer 1.4s ease infinite;
}
@keyframes skeletonShimmer { 0% { background-position: 100% 0; } 100% { background-position: -100% 0; } }
```
Use it in fetchers: call `renderSkeleton(els.cardsDiscovered)` before `await fetchJobsList()`, cleared by the normal render.

### Step 3.3 — Verify
- Trigger a failing action (offline) in 3–4 different views → identical error toast format.
- Slow network (DevTools throttle) → skeleton shimmer shows, then real content replaces it. No layout jump.

---

## FEATURE 4 — Empty states that teach + act

**Why:** Current empty states are passive text: `<p class="empty-state-text">No leads discovered.</p>` (app.js:1019–1023), plus admin/email ones (3101, 3311, 3354, 3387, 1444). Loved apps turn an empty box into an onboarding nudge: icon + one line + a primary CTA.

### Files touched
- `js/app.js`, `css/style.css`

### Step 4.1 — One empty-state helper
```js
function emptyState(icon, title, { action, actionAttr } = {}) {
  const btn = action
    ? `<button class="btn btn-primary btn-sm empty-cta" ${actionAttr || ''}>${action}</button>`
    : '';
  return `<div class="empty-state">
    <div class="empty-state-icon">${icon}</div>
    <div class="empty-state-title">${title}</div>${btn}</div>`;
}
```
```css
.empty-state { text-align: center; padding: 28px 16px; color: var(--text-muted); }
.empty-state-icon { font-size: 30px; opacity: 0.7; margin-bottom: 8px; }
.empty-state-title { font-size: 13px; margin-bottom: 12px; }
.empty-cta { margin: 0 auto; }
```

### Step 4.2 — Swap the pipeline empties (app.js:1019–1023)
```js
if (els.cardsDiscovered) els.cardsDiscovered.innerHTML =
  columns.discovered.map(j => renderJobCardHTML(j)).join('') ||
  emptyState('🛰️', 'No leads yet — run a discovery cycle to pull 0-day roles.',
             { action: '⚡ Run Discovery', actionAttr: 'data-action="triggerDiscoveryCycle"' });
```
Apply the same to `queued` / `submitted` / `interview` / `offer` (each with a fitting icon + line; the queued/submitted ones can point at the pipeline, no CTA needed). The CTA works automatically — it goes through the existing `data-action` click dispatcher (app.js:2718).

### Step 4.3 — Verify
- Fresh account / filtered-to-empty column → icon + line + working CTA button.
- Clicking the Discovered empty-state CTA runs discovery.

---

## FEATURE 5 — Progressive disclosure (Interview Studio + Negotiation)

**Why:** These are your densest screens (Interview Studio at `#view-interview` index.html:778; you already fixed an overflow bug there). Everything renders flat. Loved apps (Linear issue view, Notion) collapse secondary detail behind expandable sections. There are **no `<details>`/accordions** in the app today — this adds the pattern.

### Files touched
- `index.html`, `css/style.css`, `js/app.js` (tiny)

### Step 5.1 — A reusable collapsible (use native `<details>` — zero JS, a11y-free)
Wrap secondary panels — the interviewer dossier (`#interview-dossier-container` index.html:1007), the AI eval view (`#eval-content-view` index.html:909), and on Negotiation (`#view-negotiation` index.html:1055) the breakdown tables — in:
```html
<details class="disclosure" open>
  <summary class="disclosure-head">Interviewer Dossier</summary>
  <div class="disclosure-body"> … existing content … </div>
</details>
```
Default the primary panel `open`; leave secondary ones closed so the screen opens calm.
```css
.disclosure { border: var(--border-card); border-radius: 10px; margin-bottom: 12px; }
.disclosure-head { cursor: pointer; padding: 10px 14px; font-weight: 700; font-size: 13px;
  list-style: none; display: flex; justify-content: space-between; align-items: center; }
.disclosure-head::after { content: '⌄'; transition: transform .2s; }
.disclosure[open] .disclosure-head::after { transform: rotate(180deg); }
.disclosure-body { padding: 0 14px 14px; }
summary::-webkit-details-marker { display: none; }
```

### Step 5.2 — Persist open/closed (optional nicety)
On `toggle`, save to `localStorage` so a user's preferred layout sticks:
```js
document.querySelectorAll('details.disclosure[id]').forEach(d => {
  const k = 'disc_' + d.id;
  try { const v = localStorage.getItem(k); if (v !== null) d.open = v === '1'; } catch {}
  d.addEventListener('toggle', () => { try { localStorage.setItem(k, d.open ? '1' : '0'); } catch {} });
});
```
(Wrap in try/catch — localStorage can throw in some contexts.)

### Step 5.3 — Verify
- Interview Studio opens with the answer/question primary and dossier/eval collapsed.
- Expanding/collapsing is smooth; state persists across reload.
- 375px: collapsed sections keep the screen short and scroll-free where possible.

---

## FEATURE 6 — Onboarding as a guided narrative

**Why:** Onboarding is a 4-step wizard (`stepContent1–4` / `wstep-1..4`, functions `proceedToStep2/3/4` app.js:585–630). It collects fields into a void — the user doesn't see a payoff until the end. Notion/Linear show the workspace *forming live* as you answer, which is the emotional hook.

### Files touched
- `index.html`, `js/app.js`

### Step 6.1 — Live preview panel
Add a persistent right-hand (desktop) / top (mobile) card in the onboarding view that mirrors what the user is entering — name, target roles, parsed skills — updating on input. It's read-only and reuses data already captured. Bind to the existing resume-parse result + target-role toggles (`toggleTargetRole` app.js:633).
```js
function updateOnboardingPreview() {
  const p = document.getElementById('onboarding-live-preview');
  if (!p) return;
  const name = (document.getElementById('resume-name-field')?.value) || 'Your name';
  const roles = [...document.querySelectorAll('.target-role-btn.active')].map(b => b.textContent.trim());
  p.innerHTML = `<div class="preview-card">
    <div class="preview-name">${escapeHTML(name)}</div>
    <div class="preview-roles">${roles.map(r => `<span class="chip">${escapeHTML(r)}</span>`).join('') || '<span class="text-muted">Pick target roles…</span>'}</div>
  </div>`;
}
```
Call it from the resume-parse success handler and inside `toggleTargetRole`.

### Step 6.2 — Progress payoff copy
Change each step badge (`currentStepBadge`) from "Step 2: Recruiter Screening Form" to outcome-framed lines ("2 of 4 · Building your screening profile"). Small wording change, big feel difference.

### Step 6.3 — Verify
- Typing name / picking roles updates the live preview instantly.
- Preview stacks above the form at 375px (reuse the `.studio-grid` single-column pattern you already added).

> This is the highest-effort of the six because it touches live-binding across steps. Consider scoping the PR to Step 6.1 only first.

---

## FEATURE 7 — Dark-theme contrast polish (+ optional light theme)

**Why:** The app is dark-only with a well-structured token set on `:root` (`--bg-*`, `--text-*`, `--accent-*` at style.css:8–58). There's **no `prefers-color-scheme`, no theme toggle, no light palette**. Two independent tracks:

### Track A (cheap, high polish) — contrast audit of the existing dark theme
- Check `--text-muted: #64748b` and `--text-dim: #475569` against your card backgrounds for WCAG AA (4.5:1 body / 3:1 large). `#475569` on a dark card is likely **below AA** — bump dim/muted a notch.
- Verify accent-on-dark for the amber/rose used in badges.
- Tool: paste values into any contrast checker, or use the `design:accessibility-review` skill for a full pass.
- This is a handful of token tweaks in `:root` — no structural change.

### Track B (optional, larger) — add a light theme + toggle
- Define a `[data-theme="light"]` block that overrides the same tokens (don't redefine colors only inside a media query — set light on `:root`, override for dark, per theming best practice). Since the app is dark-first, the pragmatic move is: keep `:root` dark, add `:root[data-theme="light"] { … }` overrides.
- Add a toggle button (topbar) that sets `document.documentElement.dataset.theme` and persists to `localStorage`.
- Budget real time: every hardcoded inline color in `index.html` (there are many — e.g. the `style="color:#34d399"` badges) will look wrong in light mode. This is why Track A alone is the recommended first PR.

### Verify
- Track A: run a contrast checker on the 3–4 smallest/greyest text tokens; all body text ≥ 4.5:1.
- Track B (if done): toggle flips cleanly, persists across reload, no unreadable inline-colored text.

---

## FEATURE 8 — Micro-interactions on state changes

**Why:** You already have a keyframe library (`pulseGlow`, `fadeInView`, `slideInToast`, `micPulseGlow`, `pulse-danger` in style.css) and a `playProceduralChime('celebrate')` audio cue (app.js:1820). The emotional peaks — **application submitted**, **stage → Offer**, **interview scored** — currently just re-render. A small celebratory animation there is disproportionately memorable.

### Files touched
- `css/style.css`, `js/app.js`

### Step 8.1 — A pop/glow on the card that changed
```css
@keyframes cardPop { 0% { transform: scale(1); } 40% { transform: scale(1.04); box-shadow: 0 0 22px rgba(16,185,129,0.55); } 100% { transform: scale(1); } }
.card-celebrate { animation: cardPop 0.6s ease; }
```
```js
function celebrateCard(jobId) {
  const el = document.querySelector(`[data-job-id="${jobId}"]`);
  if (!el) return;
  el.classList.add('card-celebrate');
  el.addEventListener('animationend', () => el.classList.remove('card-celebrate'), { once: true });
}
```

### Step 8.2 — Fire it on the peak moments
Hook into the optimistic update from Feature 2 (or the current handlers): when a job reaches `OFFER`, or `applyToJob` succeeds — call `celebrateCard(jobId)` and `window.playProceduralChime('celebrate')` (audio already exists; keep it opt-in/subtle).

### Step 8.3 — Confetti for Offer only (optional, ~30 lines, no library)
A tiny canvas/DOM confetti burst on reaching Offer — the single biggest win in a job hunt. Keep it to one screen event, respect `prefers-reduced-motion`:
```css
@media (prefers-reduced-motion: reduce) { .card-celebrate { animation: none; } }
```

### Step 8.4 — Verify
- Applying / moving a card to Offer triggers a one-shot pop (no lingering/looping).
- `prefers-reduced-motion: reduce` (emulate in DevTools) disables the animation.
- No layout shift; other cards don't jump.

---

## Suggested PR sequence
1. **PR:** Feature 3 (error/skeleton consolidation) — cleanup, unblocks consistency everywhere.
2. **PR:** Feature 4 (empty states) — cheap, visible polish.
3. **PR:** Feature 8 (micro-interactions) — cheap, high delight; pairs naturally with Feature 2's optimistic updates.
4. **PR:** Feature 5 (progressive disclosure) — directly reduces the Interview Studio clutter.
5. **PR:** Feature 7 Track A (contrast polish) — small token tweaks.
6. **PR:** Feature 6 (onboarding narrative) — largest; scope to the live-preview panel first.
7. **PR (optional/later):** Feature 7 Track B (light theme).

Each PR: branch → commit → push → open PR → watch CI → verify live (desktop + 375px) → merge.
