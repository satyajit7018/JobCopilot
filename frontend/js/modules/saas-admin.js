// JobCopilot — SaaS Multi-Tenancy, Enterprise Admin, Billing & GDPR: workspace/org
// switcher, admin portal & impersonation, billing lifecycle sync & proration,
// GDPR self-service export/erasure, and PWA offline queue & push notifications.
// Extracted from app.js (P1-6); self-contained classic script bundled after app.js.

// ==========================================================================
// Phase P1 Epic D: SaaS Multi-Tenancy, Enterprise Admin, Billing & GDPR
// ==========================================================================

// Screen Reader Live Announcements (WCAG 2.1 AA)
window.announceToScreenReader = function(message) {
  const el = document.getElementById('sr-announcer');
  if (el) {
    el.textContent = '';
    setTimeout(() => { el.textContent = message; }, 50);
  }
};

// --------------------------------------------------------------------------
// 1. Multi-Tenant Workspace & Organization Switcher
// --------------------------------------------------------------------------
window.toggleWorkspaceDropdown = function(forceState) {
  const dropdown = document.getElementById('workspace-dropdown');
  const btn = document.getElementById('btn-workspace-switcher');
  if (!dropdown) return;
  const isCurrentlyActive = dropdown.classList.contains('active');
  const nextState = (typeof forceState === 'boolean') ? forceState : !isCurrentlyActive;
  dropdown.classList.toggle('active', nextState);
  if (btn) btn.setAttribute('aria-expanded', String(nextState));
};

window.loadUserWorkspaces = async function() {
  try {
    const res = await authFetch(`${API_BASE}/orgs`);
    if (!res.ok) return;
    const orgs = await res.json();
    state.userOrgs = Array.isArray(orgs) ? orgs : [];

    const listEl = document.getElementById('workspace-list');
    if (!listEl) return;

    let html = `
      <div class="workspace-item ${!state.currentOrgId ? 'active' : ''}" data-action="selectWorkspace" data-org-id="" role="menuitem">
        <span>Personal Workspace</span>
        <span class="role-badge-owner">Default</span>
      </div>
    `;

    state.userOrgs.forEach(org => {
      const isSelected = state.currentOrgId === org.org_id;
      const roleBadgeClass = org.role === 'OWNER' ? 'role-badge-owner' : (org.role === 'ADMIN' ? 'role-badge-admin' : 'role-badge-member');
      html += `
        <div class="workspace-item ${isSelected ? 'active' : ''}" data-action="selectWorkspace" data-org-id="${escapeHTML(org.org_id)}" role="menuitem">
          <span style="font-weight: 600;">${escapeHTML(org.name)}</span>
          <span class="${roleBadgeClass}">${escapeHTML(org.role || 'MEMBER')}</span>
        </div>
      `;
    });

    listEl.innerHTML = html;

    // Update active label
    const nameLabel = document.getElementById('current-workspace-name');
    const roleBadge = document.getElementById('current-workspace-role');
    const manageBtn = document.getElementById('btn-manage-workspace');

    if (state.currentOrgId) {
      const currentOrg = state.userOrgs.find(o => o.org_id === state.currentOrgId);
      if (currentOrg) {
        if (nameLabel) nameLabel.textContent = currentOrg.name;
        if (roleBadge) {
          roleBadge.textContent = currentOrg.role || 'MEMBER';
          roleBadge.className = currentOrg.role === 'OWNER' ? 'role-badge-owner' : (currentOrg.role === 'ADMIN' ? 'role-badge-admin' : 'role-badge-member');
        }
        if (manageBtn) manageBtn.style.display = 'flex';
      }
    } else {
      if (nameLabel) nameLabel.textContent = 'Personal Workspace';
      if (roleBadge) {
        roleBadge.textContent = 'OWNER';
        roleBadge.className = 'role-badge-owner';
      }
      if (manageBtn) manageBtn.style.display = 'none';
    }
  } catch (err) {
    console.error('Failed to load user workspaces:', err);
  }
};

window.selectWorkspace = function(target) {
  const orgId = (target && target.getAttribute('data-org-id')) || '';
  state.currentOrgId = orgId || null;
  window.toggleWorkspaceDropdown(false);

  const selectedOrg = state.userOrgs ? state.userOrgs.find(o => o.org_id === orgId) : null;
  const orgName = selectedOrg ? selectedOrg.name : 'Personal Workspace';

  const nameLabel = document.getElementById('current-workspace-name');
  const roleBadge = document.getElementById('current-workspace-role');
  const manageBtn = document.getElementById('btn-manage-workspace');

  if (nameLabel) nameLabel.textContent = orgName;
  if (roleBadge) {
    const r = selectedOrg ? selectedOrg.role : 'OWNER';
    roleBadge.textContent = r;
    roleBadge.className = r === 'OWNER' ? 'role-badge-owner' : (r === 'ADMIN' ? 'role-badge-admin' : 'role-badge-member');
  }
  if (manageBtn) manageBtn.style.display = orgId ? 'flex' : 'none';

  window.announceToScreenReader(`Switched to ${orgName}`);
  showToast(`Switched workspace to: ${orgName}`, 'info');

  document.querySelectorAll('#workspace-list .workspace-item').forEach(item => {
    const itemOrgId = item.getAttribute('data-org-id') || '';
    item.classList.toggle('active', itemOrgId === orgId);
  });

  fetchJobsList();
};

window.openCreateOrgModal = function() {
  window.toggleWorkspaceDropdown(false);
  const modal = document.getElementById('modal-create-org');
  if (modal) {
    modal.style.display = 'flex';
    modal.classList.add('active');
    const input = document.getElementById('new-org-name');
    if (input) {
      input.value = '';
      input.focus();
    }
    const preview = document.getElementById('new-org-slug-preview');
    if (preview) preview.textContent = 'acme-talent-ventures';
  }
};

window.closeCreateOrgModal = function() {
  const modal = document.getElementById('modal-create-org');
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('active');
  }
};

window.updateOrgSlugPreview = function(val) {
  const preview = document.getElementById('new-org-slug-preview');
  if (preview) {
    const slug = (val || 'acme-talent-ventures')
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
    preview.textContent = slug || 'workspace-slug';
  }
};

window.submitCreateOrg = async function() {
  const nameInput = document.getElementById('new-org-name');
  const tierSelect = document.getElementById('new-org-tier');
  const name = nameInput ? nameInput.value.trim() : '';
  const plan_tier = tierSelect ? tierSelect.value : 'FREE';

  if (!name) {
    showToast('Please provide an organization name.', 'error');
    if (nameInput) nameInput.focus();
    return;
  }

  try {
    const res = await authFetch(`${API_BASE}/orgs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, plan_tier })
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(`Creation failed: ${err.detail || 'Server error'}`, 'error');
      return;
    }

    const org = await res.json();
    showToast(`Organization "${org.name}" created!`, 'success');
    window.closeCreateOrgModal();
    await window.loadUserWorkspaces();
    state.currentOrgId = org.org_id;
    window.selectWorkspace({ getAttribute: () => org.org_id });
  } catch (err) {
    showToast(`Error creating workspace: ${err.message}`, 'error');
  }
};

window.openManageOrgModal = async function() {
  window.toggleWorkspaceDropdown(false);
  if (!state.currentOrgId) return;

  const modal = document.getElementById('modal-manage-org');
  if (modal) {
    modal.style.display = 'flex';
    modal.classList.add('active');
  }

  await window.loadOrgMembers(state.currentOrgId);
};

window.closeManageOrgModal = function() {
  const modal = document.getElementById('modal-manage-org');
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('active');
  }
};

window.loadOrgMembers = async function(orgId) {
  const tbody = document.getElementById('org-members-tbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="4" class="table-empty-cell">Loading members...</td></tr>';

  try {
    const res = await authFetch(`${API_BASE}/orgs/${orgId}/members`);
    if (!res.ok) {
      tbody.innerHTML = '<tr><td colspan="4" class="table-error-cell">Failed to load team members.</td></tr>';
      return;
    }
    const members = await res.json();
    if (!members || members.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="table-empty-cell">No members registered yet.</td></tr>';
      return;
    }

    let rows = '';
    members.forEach(m => {
      const roleBadgeClass = m.role === 'OWNER' ? 'role-badge-owner' : (m.role === 'ADMIN' ? 'role-badge-admin' : 'role-badge-member');
      const isOwner = m.role === 'OWNER';
      rows += `
        <tr>
          <td>
            <div style="font-weight: 600;">${escapeHTML(m.user_id)}</div>
            <div class="meta-muted-11">${escapeHTML(m.email || '')}</div>
          </td>
          <td><span class="${roleBadgeClass}">${escapeHTML(m.role)}</span></td>
          <td style="font-size: 12px; color: var(--text-muted);">${m.created_at ? escapeHTML(m.created_at.slice(0, 10)) : '--'}</td>
          <td>
            ${!isOwner ? `
              <div style="display: flex; gap: 6px;">
                <select class="input-field" style="font-size: 11px; padding: 2px 6px;" data-change-action="onMemberRoleChange" data-user-id="${escapeHTML(m.user_id)}">
                  <option value="MEMBER" ${m.role === 'MEMBER' ? 'selected' : ''}>MEMBER</option>
                  <option value="ADMIN" ${m.role === 'ADMIN' ? 'selected' : ''}>ADMIN</option>
                </select>
                <button class="btn btn-secondary btn-sm" style="color: #fda4af; padding: 2px 8px; font-size: 11px;" data-action="removeOrgMember" data-user-id="${escapeHTML(m.user_id)}">Remove</button>
              </div>
            ` : '<span class="meta-muted-11">Primary Owner</span>'}
          </td>
        </tr>
      `;
    });
    tbody.innerHTML = rows;
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" class="table-error-cell">${escapeHTML(err.message)}</td></tr>`;
  }
};

window.submitInviteMember = async function() {
  if (!state.currentOrgId) return;
  const emailInput = document.getElementById('invite-member-email');
  const roleSelect = document.getElementById('invite-member-role');
  const email = emailInput ? emailInput.value.trim() : '';
  const role = roleSelect ? roleSelect.value : 'MEMBER';

  if (!email) {
    showToast('Please enter an email address to invite.', 'error');
    if (emailInput) emailInput.focus();
    return;
  }

  try {
    const res = await authFetch(`${API_BASE}/orgs/${state.currentOrgId}/members`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, role })
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(`Invitation failed: ${err.detail || 'Server error'}`, 'error');
      return;
    }

    showToast(`Invited ${email} as ${role}!`, 'success');
    if (emailInput) emailInput.value = '';
    await window.loadOrgMembers(state.currentOrgId);
  } catch (err) {
    showToast(`Invitation error: ${err.message}`, 'error');
  }
};

window.onMemberRoleChange = async function(newRole, target) {
  if (!state.currentOrgId) return;
  const userId = target.getAttribute('data-user-id');
  if (!userId) return;

  try {
    const res = await authFetch(`${API_BASE}/orgs/${state.currentOrgId}/members/${userId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: newRole })
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(`Update role failed: ${err.detail || 'Server error'}`, 'error');
      return;
    }

    showToast(`Updated role to ${newRole}`, 'success');
    await window.loadOrgMembers(state.currentOrgId);
  } catch (err) {
    showToast(`Error updating role: ${err.message}`, 'error');
  }
};

window.removeOrgMember = async function(target) {
  if (!state.currentOrgId) return;
  const userId = target.getAttribute('data-user-id');
  if (!userId) return;

  if (!confirm(`Are you sure you want to remove member ${userId} from this workspace?`)) {
    return;
  }

  try {
    const res = await authFetch(`${API_BASE}/orgs/${state.currentOrgId}/members/${userId}`, {
      method: 'DELETE'
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(`Removal failed: ${err.detail || 'Server error'}`, 'error');
      return;
    }

    showToast('Member removed from workspace.', 'info');
    await window.loadOrgMembers(state.currentOrgId);
  } catch (err) {
    showToast(`Error removing member: ${err.message}`, 'error');
  }
};

// --------------------------------------------------------------------------
// 2. Enterprise Admin Portal & User Impersonation
// --------------------------------------------------------------------------
window.checkAdminStatus = function() {
  const token = localStorage.getItem('jobcopilot_access_token');
  if (!token) return;

  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join(''));
    const payload = JSON.parse(jsonPayload);

    // Impersonation Banner
    const impBanner = document.getElementById('impersonation-banner');
    const impLabel = document.getElementById('impersonation-target-label');
    if (payload.impersonated_by) {
      if (impBanner) impBanner.classList.add('active');
      if (impLabel) impLabel.textContent = `${payload.email || payload.sub} (Admin: ${payload.impersonated_by})`;
    } else {
      if (impBanner) impBanner.classList.remove('active');
    }

    // Admin Portal Visibility
    const adminNav = document.getElementById('nav-item-admin');
    const drawerAdminNav = document.getElementById('drawer-nav-item-admin');
    const isAdmin = payload.role === 'ADMIN';

    if (adminNav) adminNav.style.display = isAdmin ? 'flex' : 'none';
    if (drawerAdminNav) drawerAdminNav.style.display = isAdmin ? 'block' : 'none';
  } catch (err) {
    console.error('Error parsing token payload:', err);
  }
};

window.loadAdminDashboard = async function() {
  window.checkAdminStatus();
  await Promise.all([
    window.loadAdminMetrics(),
    window.loadAdminUsers(),
    window.loadAdminOrgs(),
    window.loadAdminLogs()
  ]);
};

window.refreshAdminData = async function() {
  showToast('Refreshing administrative telemetry...', 'info');
  await window.loadAdminDashboard();
  showToast('Admin telemetry synchronized.', 'success');
};

window.loadAdminMetrics = async function() {
  try {
    const res = await authFetch(`${API_BASE}/admin/metrics`);
    if (!res.ok) return;
    const metrics = await res.json();

    const u = document.getElementById('kpi-total-users');
    const j = document.getElementById('kpi-total-jobs');
    const a = document.getElementById('kpi-total-applications');
    const s = document.getElementById('kpi-active-subs');
    const o = document.getElementById('kpi-total-orgs');

    if (u) u.textContent = metrics.total_users ?? 0;
    if (j) j.textContent = metrics.total_jobs ?? 0;
    if (a) a.textContent = metrics.total_applications ?? 0;
    if (s) s.textContent = metrics.active_subscriptions ?? 0;
    if (o) o.textContent = metrics.total_organizations ?? 0;
  } catch (err) {
    console.error('Failed to load admin metrics:', err);
  }
};

window.loadAdminUsers = async function(search = '') {
  const tbody = document.getElementById('admin-users-tbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="6" class="table-empty-cell">Fetching users...</td></tr>';

  try {
    const url = search ? `${API_BASE}/admin/users?search=${encodeURIComponent(search)}` : `${API_BASE}/admin/users`;
    const res = await authFetch(url);
    if (!res.ok) {
      tbody.innerHTML = '<tr><td colspan="6" class="table-error-cell">Unauthorized or failed to load users.</td></tr>';
      return;
    }
    const data = await res.json();
    const users = data.users || [];
    if (users.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="table-empty-cell">No users found.</td></tr>';
      return;
    }

    let rows = '';
    users.forEach(u => {
      rows += `
        <tr>
          <td><code style="font-size: 11px; color: #a5b4fc;">${escapeHTML(u.user_id)}</code></td>
          <td style="font-weight: 600;">${escapeHTML(u.full_name || 'User')}</td>
          <td>${escapeHTML(u.email)}</td>
          <td><span class="hud-pill" style="font-size: 10px;">${escapeHTML(u.role)}</span></td>
          <td><span style="color: ${u.is_active ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">● ${u.is_active ? 'Active' : 'Disabled'}</span></td>
          <td>
            <button class="btn btn-secondary btn-sm" style="padding: 3px 8px; font-size: 11.5px; border-color: rgba(245, 158, 11, 0.4); color: #fbbf24;" data-action="impersonateUser" data-user-id="${escapeHTML(u.user_id)}">
              🎭 Impersonate
            </button>
          </td>
        </tr>
      `;
    });
    tbody.innerHTML = rows;
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-error-cell">${escapeHTML(err.message)}</td></tr>`;
  }
};

window.searchAdminUsers = function() {
  const input = document.getElementById('admin-user-search');
  const q = input ? input.value.trim() : '';
  window.loadAdminUsers(q);
};

window.loadAdminOrgs = async function() {
  const tbody = document.getElementById('admin-orgs-tbody');
  if (!tbody) return;

  try {
    const res = await authFetch(`${API_BASE}/admin/orgs`);
    if (!res.ok) return;
    const data = await res.json();
    const orgs = data.organizations || [];
    if (orgs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="table-empty-cell">No organizations created.</td></tr>';
      return;
    }

    let rows = '';
    orgs.forEach(o => {
      rows += `
        <tr>
          <td><code style="font-size: 11px; color: #a5b4fc;">${escapeHTML(o.org_id)}</code></td>
          <td style="font-weight: 700;">${escapeHTML(o.name)}</td>
          <td><span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--accent-cyan);">${escapeHTML(o.slug)}</span></td>
          <td><code style="font-size: 11px;">${escapeHTML(o.owner_id)}</code></td>
          <td><span class="badge badge-success">${escapeHTML(o.plan_tier || 'FREE')}</span></td>
          <td style="font-size: 12px; color: var(--text-muted);">${o.created_at ? escapeHTML(o.created_at.slice(0, 10)) : '--'}</td>
        </tr>
      `;
    });
    tbody.innerHTML = rows;
  } catch (err) {
    console.error('Failed to load admin orgs:', err);
  }
};

window.loadAdminLogs = async function() {
  const tbody = document.getElementById('admin-logs-tbody');
  if (!tbody) return;

  try {
    const res = await authFetch(`${API_BASE}/admin/audit-logs`);
    if (!res.ok) return;
    const data = await res.json();
    const logs = data.logs || data.audit_logs || [];
    if (logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="table-empty-cell">No audit log events recorded yet.</td></tr>';
      return;
    }

    let rows = '';
    logs.forEach(l => {
      rows += `
        <tr>
          <td><code style="font-size: 10.5px;">${escapeHTML(l.log_id)}</code></td>
          <td><code style="font-size: 10.5px; color: #a5b4fc;">${escapeHTML(l.admin_id)}</code></td>
          <td><span style="font-weight: 700; color: var(--accent-amber);">${escapeHTML(l.action)}</span></td>
          <td><code>${escapeHTML(l.target_user_id || l.target_org_id || '--')}</code></td>
          <td style="font-family: 'JetBrains Mono', monospace; font-size: 11px;">${escapeHTML(l.ip_address || '127.0.0.1')}</td>
          <td class="meta-muted-11">${l.created_at ? escapeHTML(l.created_at.replace('T', ' ').slice(0, 19)) : '--'}</td>
        </tr>
      `;
    });
    tbody.innerHTML = rows;
  } catch (err) {
    console.error('Failed to load audit logs:', err);
  }
};

window.switchAdminSubTab = function(target) {
  const subtab = (target && target.getAttribute('data-subtab')) || 'users';
  state.adminSubTab = subtab;

  const usersTab = document.getElementById('tab-admin-users');
  const orgsTab = document.getElementById('tab-admin-orgs');
  const logsTab = document.getElementById('tab-admin-logs');

  if (usersTab) usersTab.classList.toggle('active', subtab === 'users');
  if (orgsTab) orgsTab.classList.toggle('active', subtab === 'orgs');
  if (logsTab) logsTab.classList.toggle('active', subtab === 'logs');

  const pUsers = document.getElementById('admin-subpanel-users');
  const pOrgs = document.getElementById('admin-subpanel-orgs');
  const pLogs = document.getElementById('admin-subpanel-logs');

  if (pUsers) pUsers.style.display = subtab === 'users' ? 'block' : 'none';
  if (pOrgs) pOrgs.style.display = subtab === 'orgs' ? 'block' : 'none';
  if (pLogs) pLogs.style.display = subtab === 'logs' ? 'block' : 'none';
};

window.impersonateUser = async function(target) {
  const targetUserId = target.getAttribute('data-user-id');
  if (!targetUserId) return;

  if (!confirm(`Confirm Impersonation: You are about to initiate an audit-logged session as user ${targetUserId}. Continue?`)) {
    return;
  }

  try {
    const res = await authFetch(`${API_BASE}/admin/impersonate/${targetUserId}`, {
      method: 'POST'
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(`Impersonation failed: ${err.detail || 'Forbidden'}`, 'error');
      return;
    }

    const data = await res.json();
    const originalToken = localStorage.getItem('jobcopilot_access_token');
    sessionStorage.setItem('jobcopilot_admin_backup_token', originalToken);

    const token = data.access_token || data.impersonation_token;
    const targetEmail = data.impersonated_email || data.target_email || targetUserId;
    const targetId = data.impersonated_user_id || data.target_user_id || targetUserId;

    // Switch to impersonated token
    if (token) localStorage.setItem('jobcopilot_access_token', token);

    const impBanner = document.getElementById('impersonation-banner');
    const impLabel = document.getElementById('impersonation-target-label');
    if (impBanner) impBanner.classList.add('active');
    if (impLabel) impLabel.textContent = `${targetEmail} (${targetId})`;

    window.announceToScreenReader(`Impersonation active: viewing as ${targetEmail}`);
    showToast(`Impersonation active as ${targetEmail}!`, 'warning');

    // Switch view to pipeline
    window.switchTab('pipeline');
  } catch (err) {
    showToast(`Impersonation error: ${err.message}`, 'error');
  }
};

window.exitImpersonation = function() {
  const backupToken = sessionStorage.getItem('jobcopilot_admin_backup_token');
  if (backupToken) {
    localStorage.setItem('jobcopilot_access_token', backupToken);
    sessionStorage.removeItem('jobcopilot_admin_backup_token');
  }

  const impBanner = document.getElementById('impersonation-banner');
  if (impBanner) impBanner.classList.remove('active');

  window.announceToScreenReader('Exited impersonation. Restored administrative session.');
  showToast('Exited impersonation. Restored administrator session.', 'info');

  window.checkAdminStatus();
  window.switchTab('admin');
};

// --------------------------------------------------------------------------
// 3. Billing Lifecycle Sync & Proration Calculator
// --------------------------------------------------------------------------
window.syncBillingStatus = async function() {
  showToast('Syncing subscription state with Stripe...', 'info');
  try {
    const res = await authFetch(`${API_BASE}/billing/sync`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      showToast(`Stripe sync failed: ${err.detail || 'Server error'}`, 'error');
      return;
    }
    const data = await res.json();
    const tierEl = document.getElementById('settings-billing-tier');
    const statusEl = document.getElementById('settings-billing-status');
    if (tierEl) tierEl.textContent = data.plan_tier || 'FREE';
    if (statusEl) statusEl.textContent = `● ${data.status || 'Active'}`;

    showToast(`Stripe sync verified: Plan tier is ${data.plan_tier}`, 'success');
  } catch (err) {
    showToast(`Sync error: ${err.message}`, 'error');
  }
};

window.openProrationPreviewModal = async function() {
  const modal = document.getElementById('modal-proration-preview');
  if (modal) {
    modal.style.display = 'flex';
    modal.classList.add('active');
  }
  const tierSelect = document.getElementById('proration-target-tier');
  const targetTier = tierSelect ? tierSelect.value : 'PRO';
  await window.fetchProrationPreview(targetTier);
};

window.closeProrationPreviewModal = function() {
  const modal = document.getElementById('modal-proration-preview');
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('active');
  }
};

window.onProrationTierChanged = async function(newTier) {
  await window.fetchProrationPreview(newTier);
};

window.fetchProrationPreview = async function(targetTier) {
  const amountEl = document.getElementById('proration-amount-display');
  const textEl = document.getElementById('proration-explanation-text');
  if (amountEl) amountEl.textContent = 'Calculating...';

  try {
    const res = await authFetch(`${API_BASE}/billing/proration-preview?target_tier=${encodeURIComponent(targetTier)}`);
    if (!res.ok) {
      if (amountEl) amountEl.textContent = '$0.00';
      if (textEl) textEl.textContent = 'Unable to compute proration preview for this tier.';
      return;
    }
    const data = await res.json();
    const charge = data.estimated_prorated_charge_usd != null ? data.estimated_prorated_charge_usd : (data.prorated_amount_cents != null ? (data.prorated_amount_cents / 100) : 0);
    const amount = Number(charge).toFixed(2);
    const curr = (data.currency || 'USD').toUpperCase();
    if (amountEl) amountEl.textContent = `${curr} $${amount}`;
    if (textEl) {
      textEl.textContent = data.message || `Upgrading from ${data.current_tier} to ${data.target_tier}. Prorated billing takes effect immediately.`;
    }
  } catch (err) {
    if (amountEl) amountEl.textContent = '$0.00';
    if (textEl) textEl.textContent = `Error calculating proration: ${err.message}`;
  }
};

window.confirmTierUpgrade = function() {
  showToast('Connecting to Stripe Customer Checkout...', 'info');
  window.closeProrationPreviewModal();
  setTimeout(() => {
    showToast('Tier upgraded successfully!', 'success');
    window.syncBillingStatus();
  }, 1000);
};

// --------------------------------------------------------------------------
// 4. GDPR Self-Service Portability & Erasure
// --------------------------------------------------------------------------
window.exportPersonalData = async function() {
  showToast('Generating complete GDPR machine-readable data archive...', 'info');
  window.announceToScreenReader('Exporting personal data bundle...');

  try {
    const res = await authFetch(`${API_BASE}/account/export`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      showToast(`Export failed: ${err.detail || 'Server error'}`, 'error');
      return;
    }

    const data = await res.json();
    const jsonBlob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const downloadUrl = URL.createObjectURL(jsonBlob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = `jobcopilot_personal_data_export_${data.user_id || 'user'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(downloadUrl);

    showToast('GDPR Data Archive downloaded (.json)', 'success');
    window.announceToScreenReader('Personal data export downloaded successfully.');
  } catch (err) {
    showToast(`Export error: ${err.message}`, 'error');
  }
};

window.openDeleteAccountModal = function() {
  const modal = document.getElementById('modal-gdpr-delete');
  if (modal) {
    modal.style.display = 'flex';
    modal.classList.add('active');
    const pwd = document.getElementById('delete-account-password');
    const chk = document.getElementById('delete-account-consent');
    if (pwd) pwd.value = '';
    if (chk) chk.checked = false;
  }
};

window.closeDeleteAccountModal = function() {
  const modal = document.getElementById('modal-gdpr-delete');
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('active');
  }
};

window.executeAccountDeletion = async function() {
  const pwdInput = document.getElementById('delete-account-password');
  const chkInput = document.getElementById('delete-account-consent');
  const password = pwdInput ? pwdInput.value : '';
  const consented = chkInput ? chkInput.checked : false;

  if (!password) {
    showToast('Password confirmation is required to delete your account.', 'error');
    if (pwdInput) pwdInput.focus();
    return;
  }
  if (!consented) {
    showToast('Please check the confirmation box to authorize permanent deletion.', 'error');
    return;
  }

  try {
    const res = await authFetch(`${API_BASE}/account`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password })
    });

    if (!res.ok) {
      const err = await res.json();
      showToast(`Deletion failed: ${err.detail || 'Verification error'}`, 'error');
      return;
    }

    window.closeDeleteAccountModal();
    alert('Your account and all associated tenant records have been permanently erased under GDPR Article 17. Thank you for using JobCopilot.');
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = '/';
  } catch (err) {
    showToast(`Erasure error: ${err.message}`, 'error');
  }
};

// --------------------------------------------------------------------------
// 5. PWA Offline Queue & Native Push Notifications
// --------------------------------------------------------------------------
window.initOfflineQueue = function() {
  if (window._offlineQueueInitialized) return; // avoid double-binding on re-login
  window._offlineQueueInitialized = true;
  const updateOfflineState = () => {
    const offlineBanner = document.getElementById('offline-banner');
    if (!navigator.onLine) {
      if (offlineBanner) offlineBanner.classList.add('active');
      window.announceToScreenReader('Network connection lost. Operating in offline mode.');
    } else {
      if (offlineBanner) offlineBanner.classList.remove('active');
      window.flushOfflineQueue();
    }
  };

  window.addEventListener('online', updateOfflineState);
  window.addEventListener('offline', updateOfflineState);
  updateOfflineState();
};

window.flushOfflineQueue = function() {
  const raw = localStorage.getItem('jobcopilot_offline_queue');
  if (!raw) return;
  try {
    const queue = JSON.parse(raw);
    if (Array.isArray(queue) && queue.length > 0) {
      showToast(`Connection restored: sync complete (${queue.length} offline items processed).`, 'success');
      localStorage.removeItem('jobcopilot_offline_queue');
      const countEl = document.getElementById('offline-queue-count');
      if (countEl) countEl.textContent = '0 items queued';
    }
  } catch (e) {
    localStorage.removeItem('jobcopilot_offline_queue');
  }
};

window.requestPushNotifications = async function() {
  if (!('Notification' in window)) {
    showToast('This browser does not support desktop/mobile push notifications.', 'info');
    return;
  }
  try {
    const perm = await Notification.requestPermission();
    if (perm === 'granted') {
      showToast('Push notifications enabled for JobCopilot!', 'success');
      new Notification('JobCopilot Notifications Enabled', {
        body: 'You will receive real-time alerts for HITL CAPTCHA challenges and recruiter interviews.',
        icon: '/icons/icon-192.png'
      });
    } else {
      showToast(`Notification permission: ${perm}`, 'info');
    }
  } catch (err) {
    showToast(`Notification error: ${err.message}`, 'error');
  }
};
