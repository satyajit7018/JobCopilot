// After a deploy, an open tab still runs the old build, whose lazily loaded page files
// (e.g. PrepPage-<hash>.js) no longer exist on the server. Reload once to pick up the
// new build instead of showing an error.

const RELOAD_KEY = "jobcopilot_chunk_reload_at";
/** Don't reload again within this window: the file is really missing, so show the error. */
const RETRY_WINDOW_MS = 10_000;

interface Env {
  now: () => number;
  storage: Pick<Storage, "getItem" | "setItem">;
  reload: () => void;
}

let pendingTarget: () => string | null = () => null;

/** Lets the router say where a navigation is heading, so the reload lands there. */
export function setReloadTarget(getTarget: () => string | null) {
  pendingTarget = getTarget;
}

const browserEnv = (): Env => ({
  now: () => Date.now(),
  storage: window.sessionStorage,
  reload: () => {
    // The address bar still shows the page being left until the new one loads.
    const target = pendingTarget();
    if (target) window.location.assign(target);
    else window.location.reload();
  },
});

/** Wraps a dynamic import; on a missing-file failure, reloads the page once. */
export async function loadPage<T>(importer: () => Promise<T>, env: Env = browserEnv()): Promise<T> {
  try {
    return await importer();
  } catch (error) {
    let last = 0;
    try {
      last = Number(env.storage.getItem(RELOAD_KEY) ?? 0);
    } catch {
      // Storage blocked: fall through and reload once anyway.
    }
    if (env.now() - last < RETRY_WINDOW_MS) throw error;
    try {
      env.storage.setItem(RELOAD_KEY, String(env.now()));
    } catch {
      // ignore
    }
    env.reload();
    // Keep the route pending while the page reloads.
    return new Promise<T>(() => {});
  }
}
