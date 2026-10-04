/// <reference types="vitest/config" />
import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The FastAPI backend serves every endpoint under /api (canonical /api/v1 also exists).
const API_TARGET = process.env.JOBCOPILOT_API ?? "http://localhost:8000";

const proxy = {
  "/api": { target: API_TARGET, changeOrigin: true },
  "/ws": { target: API_TARGET, ws: true, changeOrigin: true },
};

/**
 * The production security headers (CSP and friends) from the nginx snippet, so
 * `vite preview` and the end-to-end tests run under exactly what production sends.
 * Not applied to `vite dev`: hot reload needs inline scripts the CSP forbids.
 */
function productionHeaders(): Record<string, string> {
  const conf = readFileSync(new URL("./security-headers.conf", import.meta.url), "utf8");
  const headers: Record<string, string> = {};
  for (const [, name, value] of conf.matchAll(/^add_header\s+(\S+)\s+"([^"]*)"/gm)) headers[name] = value;
  return headers;
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy, headers: productionHeaders() },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
