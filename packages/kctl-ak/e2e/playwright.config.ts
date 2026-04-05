import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  retries: 1,
  reporter: "list",
  use: {
    baseURL: process.env.AUTHENTIK_URL || "https://auth.kodeme.io",
  },
  projects: [
    { name: "smoke", testMatch: /smoke\/.*\.spec\.ts/ },
    { name: "scenarios", testMatch: /scenarios\/.*\.spec\.ts/ },
  ],
});
