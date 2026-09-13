// Stops the backend process started in global-setup.js and cleans up its
// scratch SQLite data directory.
const fs = require('fs');
const { PID_FILE } = require('./backend-env');

module.exports = async function globalTeardown() {
  if (!fs.existsSync(PID_FILE)) return;

  let info;
  try {
    info = JSON.parse(fs.readFileSync(PID_FILE, 'utf-8'));
  } catch (_) {
    return;
  }

  const { pid, dataDir } = info;

  if (pid) {
    try {
      // Negative pid targets the whole detached process group on POSIX so
      // uvicorn's reloader/worker children (if any) die with it too.
      process.kill(process.platform === 'win32' ? pid : -pid, 'SIGTERM');
    } catch (_) {
      try { process.kill(pid, 'SIGTERM'); } catch (_) {}
    }
  }

  if (dataDir) {
    try {
      fs.rmSync(dataDir, { recursive: true, force: true });
    } catch (_) {}
  }

  try { fs.unlinkSync(PID_FILE); } catch (_) {}
};
