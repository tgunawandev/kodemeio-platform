import { defineConfig, devices } from "@playwright/test";

/**
 * Odoo E2E test configuration.
 *
 * Environment variables (set by kctl-odoo e2e commands):
 *   ODOO_URL       - Base URL of the Odoo instance (default: http://localhost:8069)
 *   ODOO_DATABASE  - Database name
 *   ODOO_USERNAME  - Login username (default: admin)
 *   ODOO_API_KEY   - API key or password
 *   ODOO_E2E_SCREENSHOTS - "on" to capture screenshots on every step
 *   ODOO_E2E_VIDEO       - "on" to record video
 *   ODOO_E2E_MODULE      - Filter tests to a specific Odoo module
 */

const baseURL = process.env.ODOO_URL || "http://localhost:8069";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false, // Odoo tests are stateful — run sequentially
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["html", { open: "never" }], ["list"]],
  timeout: 60_000, // Odoo pages can be slow to load
  expect: {
    timeout: 15_000,
  },

  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot:
      process.env.ODOO_E2E_SCREENSHOTS === "on" ? "on" : "only-on-failure",
    video: process.env.ODOO_E2E_VIDEO === "on" ? "on" : "off",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },

  projects: [
    {
      name: "setup",
      testMatch: /global-setup\.ts/,
      teardown: "teardown",
    },
    {
      name: "teardown",
      testMatch: /global-teardown\.ts/,
    },
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        storageState: "fixtures/.auth/session.json",
      },
      dependencies: ["setup"],
    },
    {
      name: "mobile",
      use: {
        ...devices["iPhone 14"],
        storageState: "fixtures/.auth/session.json",
      },
      dependencies: ["setup"],
    },
  ],

  outputDir: "test-results",
});
