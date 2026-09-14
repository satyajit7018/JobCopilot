// JobCopilot — Knowledge Vault Studio & Search (Step 4 & 7): vault entry
// rendering, category filtering, semantic match simulation, and the add-slot
// modal. Extracted from app.js (P1-6); classic script bundled after app.js so
// it shares the global scope. renderVaultEntries() is read by a debounced
// search handler that stays in app.js (resolved at runtime via shared scope).
// ==========================================================================
// Knowledge Vault Studio & Search (Step 4 & 7)
// ==========================================================================
async function fetchVaultEntries() {
  try {
    const res = await authFetch(`${API_BASE}/vault`);
    const data = await res.json();
    state.vaultEntries = data.entries || [];
    const vaultLabel = `${state.vaultEntries.length}+`;
    if (els.badgeVaultCount) els.badgeVaultCount.textContent = vaultLabel;
    const mobVault = document.getElementById('mob-badge-vault');
    if (mobVault) mobVault.textContent = vaultLabel;
    if (els.vaultTotalBadge) els.vaultTotalBadge.textContent = `${state.vaultEntries.length} Slots Active`;
    renderVaultEntries(state.vaultEntries);
  } catch (err) {
    console.error('Failed to load Knowledge Vault:', err);
  }
}

function renderVaultEntries(entries) {
  if (entries) state.vaultEntries = entries;
  if (!els.vaultEntriesList) return;
  const list = state.vaultEntries || [];
  const searchInput = document.getElementById('vault-search-input');
  const search = (searchInput?.value || '').toLowerCase().trim();
  const category = (state.vaultFilterCategory || 'ALL').toUpperCase();

  const filtered = list.filter(e => {
    const q = (e.question_pattern || '').toLowerCase();
    const a = (e.answer_template || '').toLowerCase();
    const t = (e.slot_type || '').toLowerCase();
    if (search && !q.includes(search) && !a.includes(search) && !t.includes(search)) return false;
    if (category !== 'ALL' && (e.slot_type || '').toUpperCase() !== category) return false;
    return true;
  });

  const badge = document.getElementById('vault-total-badge');
  if (badge) badge.textContent = `${filtered.length} of ${list.length} Slots Active`;

  if (filtered.length === 0) {
    els.vaultEntriesList.innerHTML = `
      <div class="empty-state-card" style="padding: 1.5rem 1rem;">
        <div class="empty-state-icon">🧠</div>
        <div class="empty-state-title">No matching Q&amp;A slots</div>
        <div class="empty-state-desc">Index a custom screening answer to train the autonomous form filler.</div>
        <button class="empty-state-cta" data-action="openNewSlotModal">
          <span>+ Add Custom Q&amp;A Slot</span>
        </button>
      </div>
    `;
    return;
  }

  els.vaultEntriesList.innerHTML = filtered.map(e => `
    <div style="background: rgba(10, 14, 24, 0.6); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 12px 14px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
        <span class="badge badge-info" style="font-size: 10px;">${escapeHTML(e.slot_type || 'CUSTOM')}</span>
        <span class="meta-muted-11">Used ${escapeHTML(String(e.usage_count || 0))}x</span>
      </div>
      <div style="font-weight: 600; font-size: 13px; color: #f1f5f9; margin-bottom: 4px;">${escapeHTML(e.question_pattern || '')}</div>
      <div style="font-size: 12px; color: var(--text-secondary); background: rgba(0,0,0,0.2); padding: 6px 8px; border-radius: 4px;">
        ${escapeHTML(e.answer_template || '')}
      </div>
    </div>
  `).join('');
}

window.filterVaultCategory = function(target) {
  const cat = target.getAttribute('data-vcat') || 'ALL';
  state.vaultFilterCategory = cat;
  document.querySelectorAll('#vault-filter-pills .filter-pill').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-vcat') === cat);
  });
  renderVaultEntries();
};

window.openNewSlotModal = function() {
  const modal = document.getElementById('modal-add-slot');
  if (!modal) return;
  const qInput = document.getElementById('slot-modal-question');
  const aInput = document.getElementById('slot-modal-answer');
  const tSelect = document.getElementById('slot-modal-type');
  if (qInput) qInput.value = '';
  if (aInput) aInput.value = '';
  if (tSelect) tSelect.value = 'CUSTOM';
  modal.classList.add('active');
  if (qInput) setTimeout(() => qInput.focus(), 50);
};

window.submitNewVaultSlot = async function(e) {
  if (e && typeof e.preventDefault === 'function') e.preventDefault();
  const qInput = document.getElementById('slot-modal-question');
  const aInput = document.getElementById('slot-modal-answer');
  const tSelect = document.getElementById('slot-modal-type');
  const question = (qInput?.value || '').trim();
  const answer = (aInput?.value || '').trim();
  const slotType = tSelect?.value || 'CUSTOM';

  if (!question || !answer) {
    showToast('Both question pattern and standard answer are required.', 'error');
    return;
  }

  const saveBtn = document.getElementById('btn-save-slot');
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.textContent = 'Indexing...';
  }

  try {
    const res = await authFetch(`${API_BASE}/vault/learn`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, answer, slot_type: slotType })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast('Custom Q&A slot indexed in Knowledge Vault!', 'success');
      if (typeof window.playProceduralChime === 'function') {
        window.playProceduralChime('success');
      }
      const modal = document.getElementById('modal-add-slot');
      if (modal) modal.classList.remove('active');
      fetchVaultEntries();
    } else {
      showToast(data.detail || data.message || 'Failed to index slot.', 'error');
    }
  } catch (err) {
    showToast(`Error adding vault slot: ${err.message}`, 'error');
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save & Index into Vault';
    }
  }
};

window.simulateVaultMatch = async function() {
  const prompt = els.vaultTestPrompt ? els.vaultTestPrompt.value.trim() : '';
  if (!prompt) {
    showToast('Please type a screening question to test.', 'error');
    return;
  }
  showToast('Querying vector vault...', 'info');

  try {
    const res = await authFetch(`${API_BASE}/vault/match`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: prompt, company: 'Stripe', role: 'Senior Software Engineer' })
    });
    const data = await res.json();
    if (els.vaultTestResult) {
      els.vaultTestResult.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-sm); padding: 12px;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span style="font-weight: 700; color: #34d399; font-size: 13px;">Match Found (${Math.round((data.confidence || 0.95) * 100)}% Confidence)</span>
            <span class="badge badge-low">${escapeHTML(data.slot_key || 'CUSTOM')}</span>
          </div>
          <div style="font-size: 13px; color: #f1f5f9;">${escapeHTML(data.answer || '')}</div>
        </div>
      `;
    }
  } catch (err) {
    showToast(`Vector query failed: ${err.message}`, 'error');
  }
};
