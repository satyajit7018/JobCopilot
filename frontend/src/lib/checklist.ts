// Getting-started checklist: which first steps are done. Steps the data can show
// (resume, applications, 2-step sign-in) come from it; the rest are recorded here,
// in this browser, when the person does them.
import { useSyncExternalStore } from "react";

export type ChecklistFlag = "details" | "preferences" | "reviewed" | "dismissed";

const KEY = "jobcopilot_checklist";
const listeners = new Set<() => void>();
let cache: string | null = null;

function read(): Record<string, boolean> {
  try {
    cache = localStorage.getItem(KEY);
    return cache ? (JSON.parse(cache) as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

export function markDone(flag: ChecklistFlag) {
  const flags = read();
  if (flags[flag]) return;
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...flags, [flag]: true }));
  } catch {
    // Storage blocked: the step just stays unticked.
  }
  listeners.forEach((l) => l());
}

export function useChecklistFlags(): Record<string, boolean> {
  const raw = useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => {
      read();
      return cache;
    },
  );
  try {
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

export interface ChecklistStep {
  key: string;
  title: string;
  done: boolean;
  to: string;
  cta: string;
}

export function buildChecklist(input: {
  hasResume: boolean;
  hasTracked: boolean;
  mfaEnabled: boolean;
  flags: Record<string, boolean>;
}): ChecklistStep[] {
  const { hasResume, hasTracked, mfaEnabled, flags } = input;
  return [
    { key: "resume", title: "Add your resume", done: hasResume, to: "/setup", cta: "Add" },
    { key: "details", title: "Check the details we read from it", done: !!flags.details, to: "/profile", cta: "Check" },
    { key: "preferences", title: "Tell us what you're looking for", done: !!flags.preferences, to: "/profile", cta: "Set" },
    { key: "reviewed", title: "Review a job match", done: !!flags.reviewed, to: "/jobs", cta: "See jobs" },
    { key: "tracked", title: "Track your first application", done: hasTracked, to: "/jobs", cta: "Start" },
    { key: "mfa", title: "Turn on 2-step sign-in", done: mfaEnabled, to: "/settings", cta: "Turn on" },
  ];
}
