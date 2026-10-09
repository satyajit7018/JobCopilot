import { describe, expect, it } from "vitest";
import { detectRegion, formatPrice, subscriptionIsLive } from "./billing";

describe("plans", () => {
  it("prices India in rupees and everyone else in dollars", () => {
    expect(detectRegion("Asia/Kolkata")).toBe("IN");
    expect(detectRegion("Asia/Calcutta")).toBe("IN");
    expect(detectRegion("America/New_York")).toBe("INTL");
    expect(detectRegion("Asia/Dubai")).toBe("INTL");
  });

  it("formats prices", () => {
    expect(formatPrice({ currency: "INR", amount: 199 })).toBe("₹199");
    expect(formatPrice({ currency: "USD", amount: 5 })).toBe("$5");
  });

  it("knows which subscription states keep Premium on", () => {
    const sub = (status: string) => ({ subscription_id: "sub_1", status, current_end: null });
    for (const s of ["authenticated", "active", "pending", "cancelling"]) expect(subscriptionIsLive(sub(s))).toBe(true);
    for (const s of ["created", "halted", "cancelled", "completed", "expired"]) expect(subscriptionIsLive(sub(s))).toBe(false);
    expect(subscriptionIsLive(null)).toBe(false);
  });
});
