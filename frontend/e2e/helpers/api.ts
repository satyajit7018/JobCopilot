// Puts the app into a known state through the real API (plus one database poke: there's
// no API for granting Premium without a payment).
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import type { Page } from "@playwright/test";
import { API_URL, BACKEND_DIR, PID_FILE, python } from "./env";

const API = `${API_URL}/api`;

export interface Session {
  access_token: string;
  refresh_token: string;
  email: string;
  user_id: string;
}

let counter = 0;
export const uniqueEmail = (tag: string) => `e2e-${tag}-${Date.now()}-${++counter}@example.test`;

/** Signs in through the backend's development sign-in path (bare email, non-production only). */
export async function signIn(email = uniqueEmail("user"), fullName = "E2E Tester"): Promise<Session> {
  const res = await fetch(`${API}/auth/google-sso`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, full_name: fullName }),
  });
  if (!res.ok) throw new Error(`signIn failed: ${res.status} ${await res.text()}`);
  return { ...(await res.json()), email };
}

const auth = (s: Session) => ({ Authorization: `Bearer ${s.access_token}` });

export const SAMPLE_RESUME = `Asha Rao
asha.rao@example.test | +91 90000 12345 | Pune, India

SUMMARY
Backend engineer with 5 years of experience in Python and Go.

SKILLS
Python, Go, FastAPI, PostgreSQL, Redis, Kafka, Docker, Kubernetes, AWS

EXPERIENCE
Senior Software Engineer, Example Payments - Pune
Jan 2022 - Present
- Built a reconciliation service handling 2M events a day

EDUCATION
B.Tech Computer Science, Example Institute, 2019`;

/** Gives the account a profile, so the app skips first-run setup. */
export async function seedProfile(s: Session, text = SAMPLE_RESUME) {
  const form = new FormData();
  form.append("raw_text", text);
  const res = await fetch(`${API}/upload-resume`, { method: "POST", headers: auth(s), body: form });
  if (!res.ok) throw new Error(`seedProfile failed: ${res.status} ${await res.text()}`);
}

/** Creates a job through /jobs/log-call, then moves it to `status`. */
export async function seedJob(s: Session, { company, title, status = "DISCOVERED" }: { company: string; title: string; status?: string }) {
  const headers = { ...auth(s), "Content-Type": "application/json" };
  const created = await fetch(`${API}/jobs/log-call`, {
    method: "POST",
    headers,
    body: JSON.stringify({ company, role_title: title, recruiter_name: "E2E", status: "RESPONDED", call_notes: "Seeded by the E2E suite" }),
  });
  if (!created.ok) throw new Error(`seedJob failed: ${created.status} ${await created.text()}`);
  const { job_id } = (await created.json()) as { job_id: string };
  const patched = await fetch(`${API}/jobs/${job_id}/status`, { method: "PATCH", headers, body: JSON.stringify({ status }) });
  if (!patched.ok) throw new Error(`seedJob status failed: ${patched.status} ${await patched.text()}`);
  return job_id;
}

/** Stores the session the way the app does, before any page script runs. */
export async function useSession(page: Page, s: Pick<Session, "access_token" | "refresh_token">) {
  await page.addInitScript(([access, refresh]) => {
    localStorage.setItem("jobcopilot_access_token", access);
    localStorage.setItem("jobcopilot_refresh_token", refresh);
  }, [s.access_token, s.refresh_token]);
}

/** Puts the account on Premium, as a paid Razorpay subscription would. */
export function makePremium(s: Session) {
  const { dataDir } = JSON.parse(readFileSync(PID_FILE, "utf8")) as { dataDir: string };
  execFileSync(python(), ["-c", "import sys; from app.core.database import db; db.update_user_role(sys.argv[1], 'PRO')", s.user_id], {
    cwd: BACKEND_DIR,
    env: { ...process.env, JOBCOPILOT_DATA_DIR: dataDir, ENV: "development" },
  });
}
