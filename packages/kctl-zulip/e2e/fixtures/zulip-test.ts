import { test as base, expect } from "@playwright/test";

const ZULIP_URL = process.env.ZULIP_URL || "https://zulip.kodeme.io";
const ZULIP_EMAIL = process.env.ZULIP_EMAIL || "";
const ZULIP_API_KEY = process.env.ZULIP_API_KEY || "";

export interface ZulipFixtures {
  zulipURL: string;
  zulipEmail: string;
  zulipAPIKey: string;
}

export const test = base.extend<ZulipFixtures>({
  zulipURL: ZULIP_URL,
  zulipEmail: ZULIP_EMAIL,
  zulipAPIKey: ZULIP_API_KEY,
});

export { expect };
