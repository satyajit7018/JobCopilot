// Where the throwaway backend and the built app run during the suite.
import { existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

export const API_PORT = process.env.JOBCOPILOT_E2E_PORT ?? "8811";
export const API_URL = `http://127.0.0.1:${API_PORT}`;
export const APP_PORT = process.env.JOBCOPILOT_E2E_APP_PORT ?? "4173";
export const APP_URL = `http://127.0.0.1:${APP_PORT}`;

export const REPO_ROOT = resolve(__dirname, "..", "..", "..");
export const BACKEND_DIR = join(REPO_ROOT, "backend");
export const PID_FILE = join(tmpdir(), "jobcopilot-e2e-backend.pid");
export const LOG_FILE = join(tmpdir(), "jobcopilot-e2e-backend.log");

/** Explicit override, then the local dev venv, then python3 on PATH (CI). */
export function python(): string {
  if (process.env.JOBCOPILOT_E2E_PYTHON) return process.env.JOBCOPILOT_E2E_PYTHON;
  const venv = join(BACKEND_DIR, "venv", "bin", "python");
  if (existsSync(venv)) return venv;
  return process.platform === "win32" ? "python" : "python3";
}
