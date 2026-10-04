import { describe, expect, it } from "vitest";
import { auditSummary, type AuditEntry } from "./admin";
import { plainText } from "./prep";
import { eventLabel } from "./settings";

describe("plainText", () => {
  it("strips the decorative emoji the backend adds", () => {
    expect(plainText("🏛️ Distributed Systems Scaling")).toBe("Distributed Systems Scaling");
    expect(plainText("Hire 👍")).toBe("Hire");
    expect(plainText("Proficient")).toBe("Proficient");
    expect(plainText("Ask about 90-day goals?")).toBe("Ask about 90-day goals?");
  });
});

describe("eventLabel", () => {
  it("uses plain-language labels and falls back to a readable version", () => {
    expect(eventLabel("auth.mfa.enabled")).toBe("Turned on two-step sign-in");
    expect(eventLabel("auth.login.failed")).toBe("Failed sign-in attempt");
    expect(eventLabel("auth.password_changed")).toBe("Password changed");
  });
});

describe("auditSummary", () => {
  const entry = (over: Partial<AuditEntry>): AuditEntry => ({
    log_id: "l1",
    admin_id: "a1",
    action: "UPDATE_USER_ROLE",
    target_user_id: "u1",
    details: {},
    created_at: "2026-10-04T10:00:00",
    ...over,
  });

  it("describes role changes with the before and after", () => {
    expect(auditSummary(entry({ details: { old_role: "FREE", new_role: "PRO" } }))).toBe("Changed a role: FREE → PRO");
    expect(auditSummary(entry({ action: "EXPORT_DATA" }))).toBe("export data");
  });
});
