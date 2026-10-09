import { describe, expect, it, vi } from "vitest";
import { loadPage } from "./chunks";

function env(start = 100_000) {
  const store = new Map<string, string>();
  let t = start;
  return {
    now: () => t,
    tick: (ms: number) => (t += ms),
    storage: { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) },
    reload: vi.fn(),
  };
}

const missing = () => Promise.reject(new TypeError("Failed to fetch dynamically imported module"));

describe("loadPage", () => {
  it("returns the module when it loads", async () => {
    const e = env();
    await expect(loadPage(() => Promise.resolve("ok"), e)).resolves.toBe("ok");
    expect(e.reload).not.toHaveBeenCalled();
  });

  it("reloads once when the file is missing, then gives up within the window", async () => {
    const e = env();
    void loadPage(missing, e);
    await Promise.resolve();
    await Promise.resolve();
    expect(e.reload).toHaveBeenCalledTimes(1);

    e.tick(2_000);
    await expect(loadPage(missing, e)).rejects.toThrow("Failed to fetch");
    expect(e.reload).toHaveBeenCalledTimes(1);

    e.tick(20_000);
    void loadPage(missing, e);
    await Promise.resolve();
    await Promise.resolve();
    expect(e.reload).toHaveBeenCalledTimes(2);
  });
});
