/**
 * Odoo authentication helpers for Playwright E2E tests.
 *
 * Handles login via /web/session/authenticate (JSON-RPC) and
 * the web login form as fallback.
 */

import { type Page, expect } from "@playwright/test";

export interface OdooCredentials {
  url: string;
  database: string;
  username: string;
  password: string;
}

/** Read Odoo credentials from environment variables. */
export function getCredentials(): OdooCredentials {
  return {
    url: process.env.ODOO_URL || "http://localhost:8069",
    database: process.env.ODOO_DATABASE || "",
    username: process.env.ODOO_USERNAME || "admin",
    password: process.env.ODOO_API_KEY || "admin",
  };
}

/**
 * Login to Odoo via the web login form.
 *
 * This is the most reliable method as it handles all edge cases
 * (database selector, 2FA, redirects).
 */
export async function loginViaForm(
  page: Page,
  creds?: OdooCredentials,
): Promise<void> {
  const { url, database, username, password } = creds ?? getCredentials();

  // Navigate to login page
  const loginUrl = database
    ? `${url}/web/login?db=${database}`
    : `${url}/web/login`;
  await page.goto(loginUrl, { waitUntil: "networkidle" });

  // Handle database selector if present
  const dbSelect = page.locator('select[name="db"]');
  if (await dbSelect.isVisible({ timeout: 2000 }).catch(() => false)) {
    if (database) {
      await dbSelect.selectOption(database);
    }
  }

  // Fill login form
  await page.locator('input[name="login"]').fill(username);
  await page.locator('input[name="password"]').fill(password);
  await page.locator('button[type="submit"]').click();

  // Wait for redirect to /web (Odoo main app)
  await page.waitForURL(/\/web/, { timeout: 30_000 });

  // Wait for the Odoo app shell to be ready
  await expect(page.locator(".o_action_manager, .o_main_navbar")).toBeVisible({
    timeout: 30_000,
  });
}

/**
 * Login via JSON-RPC API (faster, no page navigation).
 * Sets session cookie directly.
 */
export async function loginViaRPC(
  page: Page,
  creds?: OdooCredentials,
): Promise<void> {
  const { url, database, username, password } = creds ?? getCredentials();

  const response = await page.request.post(`${url}/web/session/authenticate`, {
    data: {
      jsonrpc: "2.0",
      method: "call",
      params: {
        db: database,
        login: username,
        password: password,
      },
    },
  });

  const body = await response.json();
  if (body.error) {
    throw new Error(
      `Odoo login failed: ${body.error.message || JSON.stringify(body.error)}`,
    );
  }

  // Navigate to /web to establish the session in the browser context
  await page.goto(`${url}/web`, { waitUntil: "networkidle" });
  await expect(page.locator(".o_action_manager, .o_main_navbar")).toBeVisible({
    timeout: 30_000,
  });
}
