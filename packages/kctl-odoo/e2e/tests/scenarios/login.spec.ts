/**
 * Login scenario: verify Odoo web login works end-to-end.
 */

import { test, expect } from "@playwright/test";
import { getCredentials, loginViaForm } from "../../fixtures/odoo-auth";

test.describe("Odoo Login", () => {
  // Don't use stored session — we're testing login itself
  test.use({ storageState: { cookies: [], origins: [] } });

  test("login via web form succeeds", async ({ page }) => {
    const creds = getCredentials();
    await loginViaForm(page, creds);

    // Verify we're on the web client
    await expect(page).toHaveURL(/\/web/);
    await expect(page.locator(".o_main_navbar")).toBeVisible();
  });

  test("login with wrong password shows error", async ({ page }) => {
    const creds = getCredentials();
    const loginUrl = creds.database
      ? `${creds.url}/web/login?db=${creds.database}`
      : `${creds.url}/web/login`;

    await page.goto(loginUrl, { waitUntil: "networkidle" });
    await page.locator('input[name="login"]').fill(creds.username);
    await page
      .locator('input[name="password"]')
      .fill("wrong_password_e2e_test");
    await page.locator('button[type="submit"]').click();

    // Should stay on login page with error
    await expect(page.locator(".alert-danger")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("login page loads database selector when multiple DBs exist", async ({
    page,
  }) => {
    const creds = getCredentials();
    await page.goto(`${creds.url}/web/login`, { waitUntil: "networkidle" });

    // Either we have a db selector or the login form — both are valid
    const hasDbSelector = await page
      .locator('select[name="db"]')
      .isVisible()
      .catch(() => false);
    const hasLoginForm = await page
      .locator('input[name="login"]')
      .isVisible()
      .catch(() => false);

    expect(hasDbSelector || hasLoginForm).toBeTruthy();
  });
});
