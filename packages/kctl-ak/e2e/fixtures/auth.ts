import { test as base } from "@playwright/test";

export interface AuthFixtures {
  apiToken: string;
  baseUrl: string;
}

export const test = base.extend<AuthFixtures>({
  apiToken: async ({}, use) => {
    const token = process.env.AUTHENTIK_TOKEN;
    if (!token) throw new Error("AUTHENTIK_TOKEN env var required");
    await use(token);
  },
  baseUrl: async ({}, use) => {
    const url = process.env.AUTHENTIK_URL || "https://auth.kodeme.io";
    await use(url);
  },
});

export { expect } from "@playwright/test";
