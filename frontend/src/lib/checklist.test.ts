import { describe, expect, it } from "vitest";
import { buildChecklist } from "./checklist";

describe("getting-started checklist", () => {
  it("ticks steps from data and recorded actions", () => {
    const steps = buildChecklist({ hasResume: true, hasTracked: false, mfaEnabled: false, flags: { details: true } });
    const done = Object.fromEntries(steps.map((s) => [s.key, s.done]));
    expect(done).toEqual({ resume: true, details: true, preferences: false, reviewed: false, tracked: false, mfa: false });
  });

  it("is complete when everything is done", () => {
    const steps = buildChecklist({ hasResume: true, hasTracked: true, mfaEnabled: true, flags: { details: true, preferences: true, reviewed: true } });
    expect(steps.every((s) => s.done)).toBe(true);
  });
});
