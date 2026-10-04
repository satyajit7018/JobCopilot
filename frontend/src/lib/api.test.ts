import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, onUnauthorized, tokens } from "./api";

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  localStorage.clear();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  onUnauthorized(null);
  vi.unstubAllGlobals();
});

const authHeader = (call: number) => (fetchMock.mock.calls[call][1]?.headers as Record<string, string>).Authorization;

describe("api()", () => {
  it("sends the stored bearer token", async () => {
    tokens.set({ access_token: "a1", refresh_token: "r1" });
    fetchMock.mockResolvedValueOnce(json(200, { ok: true }));
    await expect(api("/jobs")).resolves.toEqual({ ok: true });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/jobs");
    expect(authHeader(0)).toBe("Bearer a1");
  });

  it("sends extra headers, and sends FormData as multipart without a JSON content type", async () => {
    tokens.set({ access_token: "a1" });
    fetchMock.mockImplementation(async () => json(200, {}));
    await api("/jobs/apply-async/j1", { method: "POST", headers: { "Idempotency-Key": "k1" } });
    const sent = fetchMock.mock.calls[0][1]?.headers as Record<string, string>;
    expect(sent["Idempotency-Key"]).toBe("k1");
    expect(sent.Authorization).toBe("Bearer a1");

    const form = new FormData();
    form.append("raw_text", "resume");
    await api("/upload-resume", { method: "POST", body: form });
    const init = fetchMock.mock.calls[1][1]!;
    expect(init.body).toBe(form);
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });

  it("refreshes once on 401 and retries with the new token", async () => {
    tokens.set({ access_token: "old", refresh_token: "r1" });
    fetchMock
      .mockResolvedValueOnce(json(401, { detail: "expired" }))
      .mockResolvedValueOnce(json(200, { access_token: "new", refresh_token: "r2" }))
      .mockResolvedValueOnce(json(200, { jobs: [] }));

    await expect(api("/jobs")).resolves.toEqual({ jobs: [] });
    expect(fetchMock.mock.calls[1][0]).toBe("/api/auth/refresh");
    expect(authHeader(2)).toBe("Bearer new");
    expect(tokens.access).toBe("new");
    expect(tokens.refresh).toBe("r2");
  });

  it("shares a single refresh between concurrent 401s", async () => {
    tokens.set({ access_token: "old", refresh_token: "r1" });
    fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) return json(200, { access_token: "new" });
      const auth = (init?.headers as Record<string, string>).Authorization;
      return auth === "Bearer new" ? json(200, { url }) : json(401, {});
    });

    await Promise.all([api("/a"), api("/b"), api("/c")]);
    const refreshes = fetchMock.mock.calls.filter(([u]) => String(u).endsWith("/auth/refresh"));
    expect(refreshes).toHaveLength(1);
  });

  it("clears tokens and notifies when the session cannot be refreshed", async () => {
    tokens.set({ access_token: "old", refresh_token: "r1" });
    const handler = vi.fn();
    onUnauthorized(handler);
    fetchMock.mockResolvedValueOnce(json(401, {})).mockResolvedValueOnce(json(401, { detail: "revoked" })).mockResolvedValueOnce(json(401, { detail: "Not authenticated" }));

    await expect(api("/jobs")).rejects.toMatchObject({ status: 401 });
    expect(handler).toHaveBeenCalledOnce();
    expect(tokens.access).toBeNull();
    expect(tokens.refresh).toBeNull();
  });

  it("does not attach tokens or refresh for auth: false calls", async () => {
    tokens.set({ access_token: "a1", refresh_token: "r1" });
    const handler = vi.fn();
    onUnauthorized(handler);
    fetchMock.mockResolvedValueOnce(json(401, { detail: "Invalid email or password." }));

    await expect(api("/auth/login", { method: "POST", body: {}, auth: false })).rejects.toThrow("Invalid email or password.");
    expect(authHeader(0)).toBeUndefined();
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(handler).not.toHaveBeenCalled();
    expect(tokens.access).toBe("a1");
  });

  it("turns FastAPI validation errors into a readable message", async () => {
    fetchMock.mockResolvedValueOnce(json(422, { detail: [{ msg: "field required" }, { msg: "value is not a valid email" }] }));
    const err = (await api("/auth/register", { method: "POST", body: {}, auth: false }).catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toBe("field required. value is not a valid email");
  });
});
