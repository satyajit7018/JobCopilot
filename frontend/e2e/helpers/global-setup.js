// Boots the real JobCopilot FastAPI backend (SQLite, no external deps) against
// a scratch data directory so the E2E suite runs headlessly and hermetically.
// The backend is spawned as a child process and torn down in global-teardown.js.
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const { PORT, BASE_URL, BACKEND_DIR, VENV_PYTHON, PID_FILE, LOG_FILE } = require('./backend-env');

async function waitForHealthy(url, timeoutMs) {
  const start = Date.now();
  let lastErr = null;
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url, { method: 'GET' });
      if (res.ok || res.status === 404) {
        // Any non-network-error response means the server is up and routing requests.
        return true;
      }
    } catch (err) {
      lastErr = err;
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`Backend did not become healthy within ${timeoutMs}ms at ${url}: ${lastErr}`);
}

module.exports = async function globalSetup() {
  if (!fs.existsSync(VENV_PYTHON)) {
    throw new Error(
      `Backend venv python not found at ${VENV_PYTHON}. Create it with:\n` +
      `  python3 -m venv backend/venv && source backend/venv/bin/activate && pip install -r backend/requirements.txt`
    );
  }

  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'jobcopilot-e2e-data-'));

  const logStream = fs.createWriteStream(LOG_FILE, { flags: 'a' });

  const child = spawn(
    VENV_PYTHON,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', PORT],
    {
      cwd: BACKEND_DIR,
      env: {
        ...process.env,
        // Fresh, isolated SQLite store per test run — never touches the dev DB.
        JOBCOPILOT_DATA_DIR: dataDir,
        // Non-production so /auth/google-sso accepts a bare email (demo/dev login path).
        ENV: 'development',
        PYTHONUNBUFFERED: '1',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: process.platform !== 'win32',
    }
  );

  child.stdout.pipe(logStream);
  child.stderr.pipe(logStream);

  fs.writeFileSync(
    PID_FILE,
    JSON.stringify({ pid: child.pid, dataDir }),
    'utf-8'
  );

  // Detach our Node process's handle refcount from the child so Playwright's
  // globalSetup can exit cleanly without waiting on the long-lived server.
  child.unref();

  try {
    await waitForHealthy(`${BASE_URL}/api/health`, 30_000);
  } catch (err) {
    console.error(`[global-setup] Backend failed to start. See log: ${LOG_FILE}`);
    try {
      console.error(fs.readFileSync(LOG_FILE, 'utf-8').slice(-4000));
    } catch (_) {}
    throw err;
  }

  console.log(`[global-setup] Backend healthy at ${BASE_URL} (pid ${child.pid}, data dir ${dataDir})`);
};
