import { test as base } from "@playwright/test";

export interface AuthFixtures {
  pgHost: string;
  pgPassword: string;
  pgProfile: string;
}

export const test = base.extend<AuthFixtures>({
  pgHost: async ({}, use) => {
    const host = process.env.PG_HOST;
    if (!host) throw new Error("PG_HOST env var required");
    await use(host);
  },
  pgPassword: async ({}, use) => {
    const password = process.env.PG_PASSWORD;
    if (!password) throw new Error("PG_PASSWORD env var required");
    await use(password);
  },
  pgProfile: async ({}, use) => {
    const profile = process.env.KCTL_PG_PROFILE || "default";
    await use(profile);
  },
});

export { expect } from "@playwright/test";
