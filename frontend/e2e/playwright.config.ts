import { defineConfig, devices } from "@playwright/test";
import { API_URL, APP_PORT, APP_URL } from "./helpers/env";

export default defineConfig({
  testDir: "./tests",
  timeout: 45_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  globalSetup: "./helpers/global-setup.ts",
  globalTeardown: "./helpers/global-teardown.ts",
  // The production build, served with production security headers, proxying /api to the test backend.
  webServer: {
    command: `npx vite build && npx vite preview --host 127.0.0.1 --port ${APP_PORT} --strictPort`,
    cwd: "..",
    url: APP_URL,
    env: { JOBCOPILOT_API: API_URL },
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  use: {
    baseURL: APP_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
