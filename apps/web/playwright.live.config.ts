import { defineConfig, devices } from "@playwright/test";

/**
 * Real-services Spanish UI journey (feature 005, FR-011): no mocked backends. Needs the local compose stack up
 * (infra/compose.yaml, synthetic data) and its web address exported, for example:
 *   PLAYWRIGHT_BASE_URL=http://localhost:8080 npx playwright test --config playwright.live.config.ts
 * The fast mocked suite (playwright.config.ts, tests/e2e) stays a separate check.
 */
export default defineConfig({
  testDir: "./tests/live",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  outputDir: "./test-results/live",   // inside the already git-ignored test-results folder
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL, trace: "off" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
