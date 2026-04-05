import { test as base } from "@playwright/test";

export interface AuthFixtures {
  apiToken: string;
  baseUrl: string;
}

export const test = base.extend<AuthFixtures>({
  apiToken: async ({}, use) => {
    const token = process.env.DOKPLOY_TOKEN;
    if (!token) throw new Error("DOKPLOY_TOKEN env var required");
    await use(token);
  },
  baseUrl: async ({}, use) => {
    const url = process.env.DOKPLOY_URL || "https://dokploy.kodeme.io";
    await use(url);
  },
});

export { expect } from "@playwright/test";
