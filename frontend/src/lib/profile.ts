// Candidate profile: resume upload, recruiter answers, and the job sources to search.
import { useMemo, useSyncExternalStore } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "./api";
import { markDone } from "./checklist";

export interface Experience {
  company: string;
  title: string;
  start_date: string;
  end_date: string;
  location?: string | null;
  highlights: string[];
}

export interface Education {
  degree: string;
  institution: string;
  graduation_year?: string | null;
}

export interface Preferences {
  current_ctc: string;
  expected_ctc: string;
  notice_period_days: number;
  work_authorization: string;
  willing_to_relocate: boolean;
  remote_preference: string;
  years_of_experience: number;
  why_looking_for_role: string;
  current_employer?: string | null;
}

export interface Profile {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  location: string;
  linkedin_url?: string | null;
  github_url?: string | null;
  summary: string;
  skills: string[];
  experience: Experience[];
  education: Education[];
  preferences: Preferences;
  updated_at: string;
}

/** The fields POST /questionnaire accepts. */
export interface Answers {
  full_name: string;
  email: string;
  phone: string;
  location: string;
  linkedin_url: string;
  github_url: string;
  expected_ctc: string;
  current_ctc: string;
  notice_period_days: number;
  work_authorization: string;
  willing_to_relocate: boolean;
  remote_preference: string;
  years_of_experience: number;
  why_looking_for_role: string;
  current_employer: string;
}

export interface Question {
  id: string;
  question: string;
  description: string;
  type: string;
  options: string[];
}

interface Questionnaire {
  questions_schema: Question[];
  prefilled: Partial<Answers>;
}

/** The profile, or null when the user hasn't uploaded a resume yet (404). */
export function useProfile() {
  return useQuery({
    queryKey: ["profile"],
    queryFn: async () => {
      try {
        return (await api<{ profile: Profile }>("/profile")).profile;
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
  });
}

export function useQuestionnaire() {
  return useQuery({
    queryKey: ["questionnaire"],
    queryFn: () => api<Questionnaire>("/questionnaire"),
  });
}

export function useUploadResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: File | string) => {
      const form = new FormData();
      if (typeof input === "string") form.append("raw_text", input);
      else form.append("file", input);
      return api<{ profile: Profile }>("/upload-resume", { method: "POST", body: form });
    },
    onSuccess: ({ profile }) => {
      qc.setQueryData(["profile"], profile);
      void qc.invalidateQueries({ queryKey: ["questionnaire"] });
    },
  });
}

export function useSaveAnswers() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (answers: Partial<Answers>) => api<{ profile: Profile }>("/questionnaire", { method: "POST", body: { answers } }),
    onSuccess: ({ profile }) => {
      qc.setQueryData(["profile"], profile);
      markDone("preferences");
      void qc.invalidateQueries({ queryKey: ["questionnaire"] });
    },
  });
}

export interface Background {
  skills: string[];
  experience: Experience[];
  education: Education[];
}

/** Saves corrections to what was read from the resume. */
export function useSaveBackground() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (background: Background) => api<{ profile: Profile }>("/profile/background", { method: "PUT", body: background }),
    onSuccess: ({ profile }) => {
      qc.setQueryData(["profile"], profile);
      markDone("details");
    },
  });
}

/** Splits "Python, Go; FastAPI" into separate skills. */
export function splitSkills(text: string): string[] {
  return text
    .split(/[,;\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export const RESUME_TYPES = ".pdf,.docx,.doc,.txt";
export const MAX_RESUME_BYTES = 10 * 1024 * 1024;

/** Client-side check that mirrors the backend's limits, so users get the error before uploading. */
export function resumeFileError(file: File): string | null {
  const ext = file.name.toLowerCase().match(/\.[a-z]+$/)?.[0] ?? "";
  if (!RESUME_TYPES.split(",").includes(ext)) return "Use a PDF, Word or plain-text file.";
  if (file.size > MAX_RESUME_BYTES) return "That file is over 10 MB. Try a smaller export.";
  if (file.size === 0) return "That file is empty.";
  return null;
}

/**
 * True until a resume has been read. Google sign-in creates an empty placeholder
 * profile, so "has a profile" alone doesn't mean setup is done.
 */
export function needsSetup(p: Profile | null | undefined): boolean {
  if (!p) return true;
  return !p.skills?.length && !p.experience?.length && !p.education?.length && !p.summary?.trim();
}

/** Answers from a profile, used to seed the preferences and contact forms. */
export function answersFromProfile(p: Profile): Answers {
  const prefs = p.preferences;
  return {
    full_name: p.full_name ?? "",
    email: p.email ?? "",
    phone: p.phone ?? "",
    location: p.location ?? "",
    linkedin_url: p.linkedin_url ?? "",
    github_url: p.github_url ?? "",
    expected_ctc: prefs.expected_ctc ?? "",
    // "0 LPA" was an old placeholder default, never something the user typed.
    current_ctc: prefs.current_ctc === "0 LPA" ? "" : (prefs.current_ctc ?? ""),
    notice_period_days: prefs.notice_period_days ?? 0,
    work_authorization: prefs.work_authorization ?? "",
    willing_to_relocate: prefs.willing_to_relocate ?? true,
    remote_preference: prefs.remote_preference ?? "",
    years_of_experience: prefs.years_of_experience ?? 0,
    why_looking_for_role: prefs.why_looking_for_role ?? "",
    current_employer: prefs.current_employer ?? "",
  };
}

/** Plain-language labels for the backend's work-mode values. */
export const WORK_MODES: { value: string; label: string }[] = [
  { value: "Remote Only", label: "Remote only" },
  { value: "Remote / Hybrid", label: "Remote or hybrid" },
  { value: "Remote / Hybrid / On-site", label: "Any" },
  { value: "On-site Only", label: "On-site only" },
];

export const NOTICE_PERIODS = [0, 15, 30, 60, 90];

export function noticeLabel(days: number) {
  return days === 0 ? "Immediately" : `In ${days} days`;
}

/** Keeps a stored value selectable even when it isn't one of the standard options. */
export function withCurrent(options: string[], current: string): string[] {
  return current && !options.includes(current) ? [current, ...options] : options;
}

// ---------------------------------------------------------------------------
// Job sources. The backend has no per-user source setting yet, so this is a
// local preference stored under the legacy UI's key (both UIs stay in sync).

// Only places JobCopilot actually reads postings from belong here.
export const SOURCES = [
  { id: "ats", name: "Company career pages", detail: "Greenhouse, Lever and Ashby" },
  { id: "startups", name: "Startup job boards", detail: "Y Combinator companies and Hacker News \"Who is hiring\"" },
] as const;

export type SourceId = (typeof SOURCES)[number]["id"];
export type SourceState = Record<SourceId, boolean>;

const PLATFORM_HINTS: [SourceId, string[]][] = [
  ["ats", ["greenhouse", "lever", "ashby", "workday"]],
  ["startups", ["y combinator", "yc", "hackernews", "hacker news"]],
];

/** Which source a job's platform belongs to, or null when it isn't one of ours. */
export function sourceForPlatform(platform: string | null | undefined): SourceId | null {
  const p = (platform ?? "").toLowerCase();
  for (const [id, hints] of PLATFORM_HINTS) if (hints.some((h) => p.includes(h))) return id;
  return null;
}

/** Jobs from unchecked sources are hidden; unknown platforms are always shown. */
export function fromChosenSource(platform: string | null | undefined, chosen: SourceState) {
  const id = sourceForPlatform(platform);
  return id === null || chosen[id];
}

const SOURCES_KEY = "jobcopilot_connected_portals";

const SOURCES_EVENT = "jobcopilot:sources";

function readRaw(): string | null {
  try {
    return localStorage.getItem(SOURCES_KEY);
  } catch {
    return null;
  }
}

export function loadSources(): SourceState {
  return parseSources(readRaw());
}

function parseSources(raw: string | null): SourceState {
  const all = Object.fromEntries(SOURCES.map((s) => [s.id, true])) as SourceState;
  try {
    if (!raw) return all;
    const saved = JSON.parse(raw) as Partial<Record<string, unknown>>;
    // A legacy record of all-false means "never chosen"; default to everything on.
    if (!SOURCES.some((s) => saved[s.id] === true)) return all;
    for (const s of SOURCES) all[s.id] = saved[s.id] === true;
    return all;
  } catch {
    return all;
  }
}

export function saveSources(state: SourceState) {
  try {
    localStorage.setItem(SOURCES_KEY, JSON.stringify(state));
  } catch {
    // Storage blocked (private mode): the choice just isn't remembered.
  }
  window.dispatchEvent(new Event(SOURCES_EVENT));
}

function subscribeSources(onChange: () => void) {
  window.addEventListener(SOURCES_EVENT, onChange);
  window.addEventListener("storage", onChange); // other tabs, including the legacy UI
  return () => {
    window.removeEventListener(SOURCES_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** The chosen sources, kept in sync across components and tabs. */
export function useSources(): SourceState {
  const raw = useSyncExternalStore(subscribeSources, readRaw, () => null);
  return useMemo(() => parseSources(raw), [raw]);
}

// Setup can be postponed; Home then shows a reminder instead of redirecting.
const SETUP_LATER_KEY = "jobcopilot_setup_later";

export const setupLater = {
  get() {
    try {
      return sessionStorage.getItem(SETUP_LATER_KEY) === "1";
    } catch {
      return false;
    }
  },
  set() {
    try {
      sessionStorage.setItem(SETUP_LATER_KEY, "1");
    } catch {
      // ignore
    }
  },
};
