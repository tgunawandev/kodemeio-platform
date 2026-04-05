import { test as base } from "@playwright/test";

export interface AuthFixtures {
  monorepoPath: string;
}

export const test = base.extend<AuthFixtures>({
  monorepoPath: async ({}, use) => {
    const path = process.env.REACT_MONOREPO_PATH;
    if (!path) throw new Error("REACT_MONOREPO_PATH env var required");
    await use(path);
  },
});

export { expect } from "@playwright/test";
