// Boots the real FastAPI backend (SQLite, scratch data dir) for the suite.
import { spawn } from "node:child_process";
import { createWriteStream, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { API_PORT, API_URL, BACKEND_DIR, LOG_FILE, PID_FILE, python } from "./env";

async function waitForHealthy(url: string, timeoutMs: number) {
  const start = Date.now();
  let last: unknown = null;
  while (Date.now() - start < timeoutMs) {
    try {
      if ((await fetch(url)).ok) return;
    } catch (err) {
      last = err;
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`Backend not healthy within ${timeoutMs}ms at ${url}: ${String(last)}`);
}

export default async function globalSetup() {
  const dataDir = mkdtempSync(join(tmpdir(), "jobcopilot-e2e-data-"));
  const log = createWriteStream(LOG_FILE, { flags: "a" });
  const child = spawn(python(), ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", API_PORT], {
    cwd: BACKEND_DIR,
    env: {
      ...process.env,
      JOBCOPILOT_DATA_DIR: dataDir,
      // Non-production: /auth/google-sso accepts a bare email (the dev sign-in path the helpers use).
      ENV: "development",
      // The suite never depends on the internet: company tiles show their initial.
      COMPANY_LOGOS_ENABLED: "false",
      INSTAHYRE_ENABLED: "false",
      PYTHONUNBUFFERED: "1",
    },
    stdio: ["ignore", "pipe", "pipe"],
    detached: process.platform !== "win32",
  });
  child.stdout?.pipe(log);
  child.stderr?.pipe(log);
  writeFileSync(PID_FILE, JSON.stringify({ pid: child.pid, dataDir }));
  child.unref();

  try {
    await waitForHealthy(`${API_URL}/api/health`, 45_000);
  } catch (err) {
    console.error(readFileSync(LOG_FILE, "utf8").slice(-4000));
    throw err;
  }
}
