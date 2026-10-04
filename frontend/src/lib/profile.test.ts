import { beforeEach, describe, expect, it } from "vitest";
import {
  answersFromProfile,
  fromChosenSource,
  loadSources,
  needsSetup,
  resumeFileError,
  saveSources,
  sourceForPlatform,
  withCurrent,
  type Profile,
  type SourceState,
} from "./profile";

const file = (name: string, size: number) => new File([new Uint8Array(size)], name);

describe("resumeFileError", () => {
  it("accepts PDF, Word and text files", () => {
    expect(resumeFileError(file("cv.PDF", 10))).toBeNull();
    expect(resumeFileError(file("cv.docx", 10))).toBeNull();
    expect(resumeFileError(file("cv.txt", 10))).toBeNull();
  });

  it("rejects other types, empty files and files over 10 MB", () => {
    expect(resumeFileError(file("cv.png", 10))).toMatch(/PDF, Word/);
    expect(resumeFileError(file("cv.pdf", 0))).toMatch(/empty/);
    expect(resumeFileError(file("cv.pdf", 10 * 1024 * 1024 + 1))).toMatch(/10 MB/);
  });
});

describe("answersFromProfile", () => {
  it("flattens contact details and preferences, filling nulls with empty strings", () => {
    const profile = {
      full_name: "Asha Rao",
      email: "asha@example.test",
      phone: "+91 90000 00000",
      location: "Pune",
      linkedin_url: null,
      github_url: "https://github.com/asha",
      preferences: {
        current_ctc: "18 LPA",
        expected_ctc: "28 LPA",
        notice_period_days: 30,
        work_authorization: "Citizen",
        willing_to_relocate: false,
        remote_preference: "Remote Only",
        years_of_experience: 5,
        why_looking_for_role: "",
        current_employer: null,
      },
    } as unknown as Profile;

    expect(answersFromProfile(profile)).toMatchObject({
      full_name: "Asha Rao",
      linkedin_url: "",
      github_url: "https://github.com/asha",
      expected_ctc: "28 LPA",
      notice_period_days: 30,
      willing_to_relocate: false,
      current_employer: "",
    });
  });
});

describe("needsSetup", () => {
  const base = { skills: [], experience: [], education: [], summary: "" } as unknown as Profile;
  it("is true with no profile or the empty placeholder Google sign-in creates", () => {
    expect(needsSetup(null)).toBe(true);
    expect(needsSetup(base)).toBe(true);
  });
  it("is false once anything was read from a resume", () => {
    expect(needsSetup({ ...base, skills: ["Go"] })).toBe(false);
    expect(needsSetup({ ...base, summary: "Backend engineer" })).toBe(false);
  });
});

describe("withCurrent", () => {
  it("keeps a non-standard stored value selectable", () => {
    expect(withCurrent(["A", "B"], "Citizen")).toEqual(["Citizen", "A", "B"]);
    expect(withCurrent(["A", "B"], "B")).toEqual(["A", "B"]);
    expect(withCurrent(["A"], "")).toEqual(["A"]);
  });
});

describe("job sources", () => {
  beforeEach(() => localStorage.clear());

  it("maps platforms to sources", () => {
    expect(sourceForPlatform("LinkedIn Easy Apply")).toBe("linkedin");
    expect(sourceForPlatform("Greenhouse")).toBe("ats");
    expect(sourceForPlatform("Cutshort")).toBe("instahyre");
    expect(sourceForPlatform("Wellfound")).toBe("indeed");
    expect(sourceForPlatform("Some Board")).toBeNull();
    expect(sourceForPlatform(undefined)).toBeNull();
  });

  it("defaults to every source when nothing (or the legacy all-off record) is saved", () => {
    expect(Object.values(loadSources()).every(Boolean)).toBe(true);
    localStorage.setItem("jobcopilot_connected_portals", JSON.stringify({ linkedin: false, naukri: false }));
    expect(Object.values(loadSources()).every(Boolean)).toBe(true);
  });

  it("round-trips a saved choice under the legacy key", () => {
    const choice = { ...loadSources(), naukri: false, indeed: false };
    saveSources(choice);
    expect(JSON.parse(localStorage.getItem("jobcopilot_connected_portals")!)).toMatchObject({ naukri: false, linkedin: true });
    expect(loadSources()).toEqual(choice);
  });

  it("hides jobs from unchecked sources but always shows unknown platforms", () => {
    const chosen = { ...loadSources(), naukri: false } as SourceState;
    expect(fromChosenSource("Naukri", chosen)).toBe(false);
    expect(fromChosenSource("Lever", chosen)).toBe(true);
    expect(fromChosenSource("Unknown Board", chosen)).toBe(true);
  });
});
