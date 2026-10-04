// Stops the backend from global-setup and removes its scratch data.
import { existsSync, readFileSync, rmSync } from "node:fs";
import { PID_FILE } from "./env";

export default async function globalTeardown() {
  if (!existsSync(PID_FILE)) return;
  const { pid, dataDir } = JSON.parse(readFileSync(PID_FILE, "utf8")) as { pid?: number; dataDir?: string };
  if (pid) {
    try {
      // Negative pid: the whole detached process group, so uvicorn's children go too.
      process.kill(process.platform === "win32" ? pid : -pid, "SIGTERM");
    } catch {
      try {
        process.kill(pid, "SIGTERM");
      } catch {
        // already gone
      }
    }
  }
  if (dataDir) rmSync(dataDir, { recursive: true, force: true });
  rmSync(PID_FILE, { force: true });
}
