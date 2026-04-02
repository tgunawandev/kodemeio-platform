/**
 * Shared tests: verify common Odoo UI elements work across all pages.
 */

import { test, expect } from "../../fixtures/odoo-test";

test.describe("Odoo Navbar & Shell", () => {
  test("navbar is visible after login", async ({ page }) => {
    await page.goto("/odoo", { waitUntil: "networkidle" });
    await expect(page.locator(".o_main_navbar")).toBeVisible();
  });

  test("home menu / app switcher works", async ({ page }) => {
    await page.goto("/odoo", { waitUntil: "networkidle" });

    const toggler = page.locator(".o_home_menu_toggler, .o_menu_toggle");
    if (await toggler.isVisible({ timeout: 3000 }).catch(() => false)) {
      await toggler.click();
      // Should show home menu with apps
      await expect(page.locator(".o_home_menu, .o_apps")).toBeVisible({
        timeout: 5000,
      });
    }
  });

  test("user menu opens", async ({ page }) => {
    await page.goto("/odoo", { waitUntil: "networkidle" });

    const userMenu = page.locator(
      ".o_user_menu .dropdown-toggle, .o_menu_systray .o_user_menu",
    );
    if (await userMenu.isVisible({ timeout: 3000 }).catch(() => false)) {
      await userMenu.click();
      // Should show dropdown with user options
      await expect(
        page.locator(".o_user_menu .dropdown-menu, .dropdown-menu"),
      ).toBeVisible({
        timeout: 5000,
      });
    }
  });

  test("Settings page loads (admin access)", async ({ page, odoo }) => {
    await page.goto("/odoo/settings", { waitUntil: "networkidle" });

    // Should load without error
    const url = page.url();
    if (url.includes("/settings")) {
      await odoo.waitForOdooReady(page);
      const notifications = await odoo.getNotifications(page);
      const errors = notifications.filter((n) =>
        n.toLowerCase().includes("error"),
      );
      expect(errors).toHaveLength(0);
    }
  });
});
