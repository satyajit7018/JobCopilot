// Shared constants describing where the E2E-managed backend lives.
// Kept as plain values (no config import) so global-setup/teardown and tests
// can all require this cheaply.
const path = require('path');
const os = require('os');

const PORT = process.env.JOBCOPILOT_E2E_PORT || '8811';
const BASE_URL = `http://127.0.0.1:${PORT}`;
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');
const BACKEND_DIR = path.join(REPO_ROOT, 'backend');
const VENV_PYTHON = path.join(BACKEND_DIR, 'venv', 'bin', 'python');
const PID_FILE = path.join(os.tmpdir(), 'jobcopilot-e2e-backend.pid');
const LOG_FILE = path.join(os.tmpdir(), 'jobcopilot-e2e-backend.log');

module.exports = { PORT, BASE_URL, REPO_ROOT, BACKEND_DIR, VENV_PYTHON, PID_FILE, LOG_FILE };
