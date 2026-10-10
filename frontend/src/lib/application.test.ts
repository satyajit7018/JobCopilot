import { describe, expect, it } from "vitest";
import { buildTimeline, daysSince, fromLocalInput, parseLpa, plainFollowUp, toLocalInput, type Email, type LedgerEntry } from "./application";
import type { Job } from "./jobs";

const job = (over: Partial<Job> = {}): Job => ({
  job_id: "j1",
  platform: "Greenhouse",
  company: "Acme",
  title: "Backend Engineer",
  location: "Remote",
  url: "https://example.test/job",
  description: "",
  salary_range: null,
  seniority_level: null,
  posted_date: null,
  match_score: 0.9,
  match_reasons: [],
  missing_skills: [],
  status: "SUBMITTED",
  applied_at: null,
  created_at: "2026-09-01T10:00:00",
  interview_date: null,
  notes: null,
  ...over,
});

const ledger = (over: Partial<LedgerEntry>): LedgerEntry => ({
  status: "SUBMITTED",
  attempt_count: 1,
  last_error_message: null,
  confirmation_id: null,
  created_at: "2026-09-02T09:00:00",
  updated_at: "2026-09-02T09:05:00",
  ...over,
});

const email = (over: Partial<Email>): Email => ({
  message_id: "m1",
  sender: "recruiter@acme.test",
  subject: "Next steps",
  body_text: "",
  received_at: "2026-09-05T12:00:00",
  associated_job_id: "j1",
  intent: "INTERVIEW_INVITE",
  scheduling_links: [],
  ...over,
});

describe("buildTimeline", () => {
  it("merges the job, its apply record and its emails, newest first", () => {
    const events = buildTimeline(job(), ledger({ confirmation_id: "GH-123" }), [email({}), email({ message_id: "m2", associated_job_id: "other" })]);
    expect(events.map((e) => e.title)).toEqual(["Interview invite", "Application submitted", "Found this job"]);
    expect(events[0].detail).toBe("Next steps · recruiter@acme.test");
    expect(events[1].detail).toBe("Confirmation GH-123");
  });

  it("reports failures with the reason and the number of tries", () => {
    const [e] = buildTimeline(job({ created_at: null }), ledger({ status: "FAILED", attempt_count: 3, last_error_message: "Submit button not found" }), []);
    expect(e).toMatchObject({ title: "Application failed after 3 tries", detail: "Submit button not found", tone: "danger" });
  });

  it("uses the job's applied date when the bot didn't submit it, without duplicating a bot submission", () => {
    const manual = buildTimeline(job({ applied_at: "2026-09-03T08:00:00" }), null, []);
    expect(manual.map((e) => e.title)).toContain("Applied");
    const both = buildTimeline(job({ applied_at: "2026-09-03T08:00:00" }), ledger({}), []);
    expect(both.map((e) => e.title)).not.toContain("Applied");
  });

  it("skips events with missing or invalid dates", () => {
    expect(buildTimeline(job({ created_at: "not a date", interview_date: "" }), null, [])).toEqual([]);
  });
});

describe("daysSince", () => {
  it("counts whole days, or null without a date", () => {
    expect(daysSince("2026-09-01T00:00:00", new Date("2026-09-08T12:00:00"))).toBe(7);
    expect(daysSince(null)).toBeNull();
  });
});

describe("parseLpa", () => {
  it("reads the number out of typical inputs", () => {
    expect(parseLpa("32")).toBe(32);
    expect(parseLpa("28.5 LPA")).toBe(28.5);
    expect(parseLpa("1,20")).toBe(120);
    expect(parseLpa("lots")).toBeNull();
  });
});

describe("interview date input", () => {
  it("round-trips through the datetime-local format", () => {
    const iso = fromLocalInput("2026-11-03T10:30");
    expect(iso).not.toBeNull();
    expect(toLocalInput(iso)).toBe("2026-11-03T10:30");
  });

  it("treats empty or invalid values as unset", () => {
    expect(toLocalInput(null)).toBe("");
    expect(toLocalInput("garbage")).toBe("");
    expect(fromLocalInput("")).toBeNull();
    expect(fromLocalInput("garbage")).toBeNull();
  });
});

describe("plainFollowUp", () => {
  it("fills in the role, company and name, and never leaves a blank signature", () => {
    const mail = plainFollowUp({ title: "Backend Engineer", company: "Acme", applied_at: "2026-03-02T10:00:00" }, "Asha Rao");
    expect(mail.subject).toBe("Following up on my application: Backend Engineer");
    expect(mail.body).toContain("the Backend Engineer role at Acme on ");
    expect(mail.body.endsWith("Asha Rao")).toBe(true);
    expect(plainFollowUp({ title: "T", company: "C", applied_at: null }, " ").body).toContain("[Your name]");
  });
});
