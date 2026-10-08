import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

process.env.PLAYWRIGHT_BROWSERS_PATH ??= fileURLToPath(new URL("../node_modules/.cache/ms-playwright", import.meta.url));

export default defineConfig({
  testDir: ".", testMatch: "live-workflow.spec.ts", workers: 1, retries: 0,
  timeout: 120_000, expect: { timeout: 30_000 },
  outputDir: "../test-results/live",
  reporter: [["list"], ["html", { open: "never",
    outputFolder: fileURLToPath(new URL("../playwright-report/live", import.meta.url)) }]],
  use: { baseURL: process.env.E2E_WEB_URL ?? "http://localhost:3000",
    trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium-live", use: { ...devices["Desktop Chrome"] } }],
});
