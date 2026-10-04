import { describe, expect, it } from "vitest";
import { newKey, outcome, taskPhase, type TaskInfo } from "./apply";

const task = (status: string, result: TaskInfo["result"] = null): TaskInfo => ({
  task_id: "t1",
  job_id: "j1",
  status,
  progress_percent: 100,
  result,
});

describe("taskPhase", () => {
  it("keeps polling until the task reaches a final state", () => {
    expect(taskPhase(undefined)).toBe("running");
    expect(taskPhase(task("QUEUED"))).toBe("running");
    expect(taskPhase(task("STARTED"))).toBe("running");
    expect(taskPhase(task("SUCCESS"))).toBe("succeeded");
    expect(taskPhase(task("FAILED"))).toBe("failed");
    expect(taskPhase(task("DLQ"))).toBe("failed");
  });
});

describe("outcome", () => {
  it("only says submitted when the runner confirms a submission", () => {
    expect(outcome(task("SUCCESS", { status: "success", submitted: true })).title).toBe("Application submitted");
    expect(outcome(task("SUCCESS", { status: "success", submitted: false, simulated: true })).title).toBe("Practice run finished");
  });

  it("explains paused and unconfirmed runs instead of calling them failures", () => {
    // The server reports these as FAILED tasks; the runner's status says why.
    expect(outcome(task("FAILED", { status: "hitl_required" })).title).toBe("Paused for your answer");
    const review = outcome(task("FAILED", { status: "needs_review", message: "Submission could not be confirmed" }));
    expect(review.tone).toBe("warn");
    expect(review.detail).toMatch(/could not be confirmed/);
  });

  it("passes the runner's error message through on failure", () => {
    const o = outcome(task("FAILED", { status: "error", message: "Submit button not found; nothing was submitted." }));
    expect(o.tone).toBe("danger");
    expect(o.detail).toMatch(/nothing was submitted/);
  });
});

describe("newKey", () => {
  it("returns a different key each time", () => {
    expect(newKey()).not.toBe(newKey());
  });
});
