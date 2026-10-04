import { describe, expect, it, vi } from "vitest";
import { ApiError } from "./api";
import { confirmSession } from "./auth";

describe("confirmSession", () => {
  it("is ok when /auth/me succeeds", async () => {
    expect(await confirmSession(async () => undefined)).toBe("ok");
  });

  it("ends the session only when the server rejects it", async () => {
    const fetchMe = vi.fn().mockRejectedValue(new ApiError(401, "expired", null));
    expect(await confirmSession(fetchMe, { delayMs: 0 })).toBe("rejected");
    expect(fetchMe).toHaveBeenCalledTimes(1);
  });

  it("retries network and server errors, then reports unreachable instead of signing out", async () => {
    const fetchMe = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch")).mockRejectedValue(new ApiError(502, "Bad gateway", null));
    expect(await confirmSession(fetchMe, { attempts: 3, delayMs: 0 })).toBe("unreachable");
    expect(fetchMe).toHaveBeenCalledTimes(3);
  });

  it("recovers when a retry succeeds", async () => {
    const fetchMe = vi.fn().mockRejectedValueOnce(new ApiError(503, "busy", null)).mockResolvedValue(undefined);
    expect(await confirmSession(fetchMe, { delayMs: 0 })).toBe("ok");
  });
});
