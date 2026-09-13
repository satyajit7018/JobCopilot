// Thin helpers around the real backend REST API used to get the app into a
// known state before a Playwright UI test starts (login + seed jobs), instead
// of poking the database directly. Every call here exercises real endpoints.
const { BASE_URL } = require('./backend-env');

const API = `${BASE_URL}/api`;

/**
 * Logs in through the real /auth/google-sso endpoint (the same one the demo
 * button and "Sign in with Google" flow call) and returns the issued tokens.
 */
async function apiLogin(email = `e2e_${Date.now()}@jobcopilot.test`, fullName = 'E2E Test User') {
  const res = await fetch(`${API}/auth/google-sso`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      full_name: fullName,
      avatar_url: 'https://example.test/avatar.png',
      auto_login_permissions: true,
    }),
  });
  if (!res.ok) {
    throw new Error(`apiLogin failed: HTTP ${res.status} ${await res.text()}`);
  }
  const data = await res.json();
  if (!data.access_token) {
    throw new Error(`apiLogin: no access_token in response: ${JSON.stringify(data)}`);
  }
  return data; // { access_token, refresh_token, user_id, email, role }
}

/**
 * Creates a job via the real /jobs/log-call endpoint (INTERVIEW by default),
 * then moves it to the requested pipeline status via the real status-update
 * endpoint. This seeds deterministic pipeline data without touching the DB
 * directly or depending on flaky live-network job discovery.
 */
async function seedJob(accessToken, { company, title, status = 'DISCOVERED' } = {}) {
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${accessToken}`,
  };

  const createRes = await fetch(`${API}/jobs/log-call`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      company,
      role_title: title,
      recruiter_name: 'E2E Seed Script',
      status: 'RESPONDED',
      call_notes: 'Seeded by Playwright E2E suite',
    }),
  });
  if (!createRes.ok) {
    throw new Error(`seedJob(log-call) failed: HTTP ${createRes.status} ${await createRes.text()}`);
  }
  const created = await createRes.json();
  const jobId = created.job_id;

  // Always PATCH to the requested final status explicitly (idempotent, and
  // avoids depending on log-call's default status mapping).
  const patchRes = await fetch(`${API}/jobs/${jobId}/status`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({ status }),
  });
  if (!patchRes.ok) {
    throw new Error(`seedJob(status patch) failed: HTTP ${patchRes.status} ${await patchRes.text()}`);
  }

  return jobId;
}

/**
 * Sets the JobCopilot auth token(s) in localStorage before the app's own
 * DOMContentLoaded bootstrap runs, then navigates — this is the same
 * mechanism the real app uses (jobcopilot_access_token in localStorage).
 */
async function primeAuthenticatedSession(page, { accessToken, refreshToken } = {}) {
  await page.addInitScript(
    ([token, refresh]) => {
      localStorage.setItem('jobcopilot_access_token', token);
      if (refresh) localStorage.setItem('jobcopilot_refresh_token', refresh);
      // Skip the portal-connect onboarding screen by default so pipeline tests
      // land directly on the pipeline view; onboarding tests override this.
      localStorage.setItem('jobcopilot_portals_configured', 'true');
    },
    [accessToken, refreshToken]
  );
}

module.exports = { API_BASE: API, apiLogin, seedJob, primeAuthenticatedSession };
