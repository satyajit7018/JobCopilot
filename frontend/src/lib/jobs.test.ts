import { describe, expect, it } from "vitest";
import { buildTodos } from "../pages/HomePage";
import { matchSummary, readableReason, relativeTime, scorePercent, type Job } from "./jobs";

function job(overrides: Partial<Job>): Job {
  return {
    job_id: Math.random().toString(36).slice(2),
    platform: "Greenhouse",
    company: "Northwind",
    title: "Backend Engineer",
    location: "Remote",
    url: "https://example.com/job",
    description: "",
    salary_range: null,
    seniority_level: null,
    posted_date: null,
    match_score: 0,
    match_reasons: [],
    missing_skills: [],
    status: "DISCOVERED",
    applied_at: null,
    created_at: null,
    interview_date: null,
    notes: null,
    ...overrides,
  };
}

describe("scorePercent", () => {
  it("converts the backend's 0–1 score", () => {
    expect(scorePercent(0.94)).toBe(94);
    expect(scorePercent(1)).toBe(100);
  });
  it("tolerates legacy 0–100 values and junk", () => {
    expect(scorePercent(76)).toBe(76);
    expect(scorePercent(140)).toBe(100);
    expect(scorePercent(-1)).toBe(0);
    expect(scorePercent(null)).toBe(0);
  });
});

describe("matchSummary", () => {
  it("prefers a reason and mentions what's missing", () => {
    expect(matchSummary(job({ match_reasons: ["Strong FastAPI match"], missing_skills: ["Kafka", "Go", "Rust"] }))).toBe(
      "Strong FastAPI match. Missing: Kafka, Go",
    );
  });
  it("returns null when there is nothing to say", () => {
    expect(matchSummary(job({ match_reasons: ["  "] }))).toBeNull();
  });
});

describe("relativeTime", () => {
  const now = new Date("2026-10-03T12:00:00Z");
  it("formats recent times compactly", () => {
    expect(relativeTime("2026-10-03T11:30:00Z", now)).toBe("30m ago");
    expect(relativeTime("2026-10-03T07:00:00Z", now)).toBe("5h ago");
    expect(relativeTime("2026-10-01T12:00:00Z", now)).toBe("2d ago");
  });
  it("ignores missing or invalid dates", () => {
    expect(relativeTime(null, now)).toBeNull();
    expect(relativeTime("not a date", now)).toBeNull();
  });
});

describe("buildTodos", () => {
  const now = new Date("2026-10-03T12:00:00Z");

  it("is empty when nothing needs attention", () => {
    expect(buildTodos([job({ match_score: 0.5 })], now)).toEqual([]);
  });

  it("surfaces upcoming interviews, blocked applications, stale applications and strong matches", () => {
    const todos = buildTodos(
      [
        job({ status: "INTERVIEW", interview_date: "2026-10-05T11:00:00Z", company: "Lumen" }),
        job({ status: "INTERVIEW", interview_date: "2026-09-01T11:00:00Z" }), // past: ignored
        job({ status: "HITL_REQUIRED", company: "Quill" }),
        job({ status: "SUBMITTED", applied_at: "2026-09-20T00:00:00Z", company: "Acorn" }),
        job({ status: "SUBMITTED", applied_at: "2026-10-02T00:00:00Z" }), // recent: ignored
        job({ match_score: 0.91 }),
        job({ match_score: 0.6 }),
      ],
      now,
    );
    expect(todos.map((t) => t.key)).toEqual([expect.stringMatching(/^iv-/), "blocked", "follow-up", "matches"]);
    expect(todos[1].title).toBe("1 application needs you");
    expect(todos[2].title).toBe("Follow up with Acorn");
    expect(todos[3].title).toBe("1 strong match to look at");
  });
});

describe("readableReason", () => {
  it("rewrites the old experience sentence and leaves others alone", () => {
    expect(readableReason("Experience level (5.0 yrs) fits Mid-Level requirements.")).toBe("Your 5 years of experience fits a mid-level role.");
    expect(readableReason("Experience level (1.0 yrs) fits Intern requirements.")).toBe("Your 1 year of experience fits an internship.");
    expect(readableReason("Role fits your backend background.")).toBe("Role fits your backend background.");
  });
});
