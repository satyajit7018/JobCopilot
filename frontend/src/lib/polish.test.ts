import { describe, expect, it } from "vitest";
import { isNewSince, isRemote, jobRegions, type Job } from "./jobs";
import { splitSkills } from "./profile";
import { searchStage } from "../components/SearchProgress";

const job = (over: Partial<Job> = {}): Job =>
  ({ job_id: "j", company: "Acme", title: "Engineer", location: "", created_at: null, status: "DISCOVERED", ...over }) as Job;

describe("job filters", () => {
  it("finds regions by whole words", () => {
    expect(jobRegions("Bangalore / Mumbai, India")).toEqual(["india"]);
    expect(jobRegions("Remote - United States")).toEqual(["usa"]);
    expect(jobRegions("Sydney, Australia")).toEqual([]);
    expect(jobRegions("London or Toronto")).toEqual(["europe", "canada"]);
    expect(isRemote("Remote (India)")).toBe(true);
    expect(isRemote("Hybrid - Remoteville")).toBe(false);
  });

  it("marks jobs found since the last visit as new", () => {
    const since = new Date("2026-10-01T00:00:00Z").getTime();
    expect(isNewSince(job({ created_at: "2026-10-02T00:00:00Z" }), since)).toBe(true);
    expect(isNewSince(job({ created_at: "2026-09-30T00:00:00Z" }), since)).toBe(false);
    expect(isNewSince(job({ created_at: "2026-10-02T00:00:00Z" }), null)).toBe(false);
  });
});

describe("profile editing", () => {
  it("splits pasted skill lists", () => {
    expect(splitSkills("Python, Go;FastAPI\n  Redis ,")).toEqual(["Python", "Go", "FastAPI", "Redis"]);
  });
});

describe("first search progress", () => {
  it("moves through the stages", () => {
    expect(searchStage(0)).toMatch(/career pages/);
    expect(searchStage(13_000)).toMatch(/Scoring/);
    expect(searchStage(60_000)).toMatch(/slow/);
  });
});
