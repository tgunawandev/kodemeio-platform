/**
 * Global setup: authenticate once and save session state for all tests.
 *
 * This runs as the "setup" project in playwright.config.ts.
 * The saved session is reused by desktop/mobile projects via storageState.
 */

import { test as setup } from "@playwright/test";
import { loginViaForm, getCredentials } from "../fixtures/odoo-auth";

const AUTH_FILE = "fixtures/.auth/session.json";

setup("authenticate", async ({ page }) => {
  const creds = getCredentials();

  if (!creds.url) {
    throw new Error(
      "ODOO_URL not set. Run via kctl-odoo e2e test or set ODOO_URL env var.",
    );
  }

  await loginViaForm(page, creds);

  // Save signed-in state for reuse
  await page.context().storageState({ path: AUTH_FILE });
});
