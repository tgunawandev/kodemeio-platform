import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  retries: 0,
  reporter: [["html", { open: "never" }]],
  use: {
    baseURL: process.env.ZULIP_URL || "https://zulip.kodeme.io",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "setup", testMatch: /global-setup\.ts/ },
    {
      name: "desktop",
      dependencies: ["setup"],
      use: { viewport: { width: 1280, height: 720 } },
      testMatch: /scenarios\/.*\.spec\.ts/,
    },
  ],
});
