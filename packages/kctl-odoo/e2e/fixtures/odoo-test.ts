/**
 * Extended Playwright test fixture with Odoo helpers pre-loaded.
 *
 * Usage in test files:
 *   import { test, expect } from '../fixtures/odoo-test';
 */

import { test as base, expect } from "@playwright/test";
import * as helpers from "./odoo-helpers";

/** Custom test fixture that provides Odoo helpers on the page. */
export const test = base.extend<{ odoo: typeof helpers }>({
  odoo: async ({}, use) => {
    await use(helpers);
  },
});

export { expect };
