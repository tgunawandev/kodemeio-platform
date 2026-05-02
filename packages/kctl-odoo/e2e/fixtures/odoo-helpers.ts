/**
 * Odoo page helpers for E2E tests.
 *
 * Provides utilities for navigating Odoo's web client, interacting with
 * views, and waiting for RPC calls to complete.
 */

import { type Page, type Locator, expect } from "@playwright/test";

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

/** Navigate to an Odoo menu by its complete path (e.g. "Sales/Orders/Quotations"). */
export async function navigateToMenu(
  page: Page,
  menuPath: string,
): Promise<void> {
  const parts = menuPath.split("/");

  // Click top-level app menu in the navbar
  const topMenu = parts[0];
  const navItem = page.locator(
    `.o_main_navbar .o_menu_sections, .o_main_navbar`,
  );
  const appLink = navItem.getByRole("menuitem", { name: topMenu }).first();

  // Try clicking the app switcher icon first
  const homeMenu = page.locator(".o_home_menu_toggler, .o_menu_toggle");
  if (await homeMenu.isVisible({ timeout: 2000 }).catch(() => false)) {
    await homeMenu.click();
    // In home menu, click the app
    await page
      .locator(`.o_home_menu .o_app`)
      .filter({ hasText: topMenu })
      .click();
  } else if (await appLink.isVisible({ timeout: 2000 }).catch(() => false)) {
    await appLink.click();
  }

  // Navigate sub-menus
  for (let i = 1; i < parts.length; i++) {
    const subMenu = parts[i];
    const menuItem = page.getByRole("menuitem", { name: subMenu }).first();
    await menuItem.click({ timeout: 10_000 });
  }

  await waitForOdooReady(page);
}

/** Navigate to an Odoo menu by action ID (e.g. "sale.action_quotations_with_onboarding"). */
export async function navigateToAction(
  page: Page,
  actionXmlId: string,
): Promise<void> {
  const baseUrl = process.env.ODOO_URL || "http://localhost:8069";
  await page.goto(`${baseUrl}/odoo/action-${actionXmlId}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForOdooReady(page);
}

// ---------------------------------------------------------------------------
// Odoo state helpers
// ---------------------------------------------------------------------------

/** Wait for Odoo's action manager to finish loading. */
export async function waitForOdooReady(page: Page): Promise<void> {
  // Wait for loading indicator to disappear
  const loading = page.locator(".o_loading");
  if (await loading.isVisible({ timeout: 1000 }).catch(() => false)) {
    await loading.waitFor({ state: "hidden", timeout: 30_000 });
  }

  // Wait for any Odoo content to be ready (action manager, discuss, or navbar)
  await expect(
    page
      .locator(
        ".o_action_manager .o_action, .o_action_manager .o_view_controller, .o_action_manager .o-mail-DiscussCore, .o_main_navbar",
      )
      .first(),
  ).toBeVisible({ timeout: 30_000 });
}

/** Wait for any pending RPC calls to complete. */
export async function waitForRPC(page: Page): Promise<void> {
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(1500);
}

// ---------------------------------------------------------------------------
// View interactions
// ---------------------------------------------------------------------------

/** Get the current view type (list, form, kanban, etc.). */
export async function getCurrentViewType(page: Page): Promise<string> {
  const viewController = page.locator(".o_view_controller");
  const classList = await viewController.getAttribute("class");
  if (!classList) return "unknown";

  const viewTypes = [
    "list",
    "form",
    "kanban",
    "calendar",
    "pivot",
    "graph",
    "map",
    "activity",
  ];
  for (const vt of viewTypes) {
    if (classList.includes(`o_${vt}_view`)) return vt;
  }
  return "unknown";
}

/** Click the "New" / "Create" button in list/kanban views. */
export async function clickCreate(page: Page): Promise<void> {
  const createBtn = page.locator(
    '.o_control_panel button.o_list_button_add, .o_control_panel button:has-text("New")',
  );
  await createBtn.first().click();
  await waitForOdooReady(page);
}

/** Click the "Save" button in form views (Odoo 18 auto-saves, but explicit save exists). */
export async function clickSave(page: Page): Promise<void> {
  const saveBtn = page.locator('.o_form_button_save, button:has-text("Save")');
  if (await saveBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await saveBtn.click();
    await waitForRPC(page);
  }
}

/** Click the "Discard" button in form views. */
export async function clickDiscard(page: Page): Promise<void> {
  const discardBtn = page.locator(
    '.o_form_button_cancel, button:has-text("Discard")',
  );
  if (await discardBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await discardBtn.click();
  }
}

// ---------------------------------------------------------------------------
// Form field helpers
// ---------------------------------------------------------------------------

/** Fill a Many2one field (autocomplete). */
export async function fillMany2one(
  page: Page,
  fieldName: string,
  value: string,
): Promise<void> {
  const field = page.locator(`.o_field_many2one[name="${fieldName}"] input`);
  await field.fill(value);
  // Wait for dropdown
  await page
    .locator(".o_m2o_dropdown_option, .dropdown-item")
    .first()
    .waitFor({ timeout: 10_000 });
  await page
    .locator(".o_m2o_dropdown_option, .dropdown-item")
    .filter({ hasText: value })
    .first()
    .click();
  await waitForRPC(page);
}

/** Fill a text/char field. */
export async function fillField(
  page: Page,
  fieldName: string,
  value: string,
): Promise<void> {
  const field = page
    .locator(`[name="${fieldName}"] input, [name="${fieldName}"] textarea`)
    .first();
  await field.fill(value);
}

/** Select a value in a Selection field. */
export async function selectField(
  page: Page,
  fieldName: string,
  value: string,
): Promise<void> {
  const field = page.locator(`[name="${fieldName}"] select`);
  await field.selectOption({ label: value });
}

// ---------------------------------------------------------------------------
// Breadcrumb & navigation
// ---------------------------------------------------------------------------

/** Get the current breadcrumb text. */
export async function getBreadcrumb(page: Page): Promise<string> {
  const breadcrumb = page.locator(".o_breadcrumb .active");
  return (await breadcrumb.textContent()) ?? "";
}

/** Click a breadcrumb item by text. */
export async function clickBreadcrumb(page: Page, text: string): Promise<void> {
  await page.locator(".o_breadcrumb").getByText(text).click();
  await waitForOdooReady(page);
}

// ---------------------------------------------------------------------------
// List view helpers
// ---------------------------------------------------------------------------

/** Get the row count displayed in a list view. */
export async function getListRowCount(page: Page): Promise<number> {
  const rows = page.locator(".o_list_view .o_data_row");
  return await rows.count();
}

/** Click on a row in the list view by index (0-based). */
export async function clickListRow(page: Page, index: number): Promise<void> {
  const row = page.locator(".o_list_view .o_data_row").nth(index);
  await row.click();
  await waitForOdooReady(page);
}

// ---------------------------------------------------------------------------
// Notification helpers
// ---------------------------------------------------------------------------

/** Get all visible notification messages. */
export async function getNotifications(page: Page): Promise<string[]> {
  const notifications = page.locator(".o_notification_content");
  const count = await notifications.count();
  const messages: string[] = [];
  for (let i = 0; i < count; i++) {
    const text = await notifications.nth(i).textContent();
    if (text) messages.push(text.trim());
  }
  return messages;
}

/** Close all notification toasts. */
export async function closeNotifications(page: Page): Promise<void> {
  const closeBtns = page.locator(".o_notification .o_notification_close");
  const count = await closeBtns.count();
  for (let i = 0; i < count; i++) {
    await closeBtns.nth(i).click();
  }
}

// ---------------------------------------------------------------------------
// UI interaction helpers (hover menus, dropdowns, panels)
// ---------------------------------------------------------------------------

/** Hover a top-level navbar menu to reveal its dropdown, then screenshot. */
export async function hoverMenu(page: Page, menuText: string): Promise<void> {
  const menuBtn = page
    .locator(".o_main_navbar .o_menu_sections")
    .getByRole("button", { name: menuText })
    .first();
  if (await menuBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await menuBtn.hover();
    await page.waitForTimeout(500);
  }
}

/** Open the App Switcher (home menu grid). */
export async function openAppSwitcher(page: Page): Promise<void> {
  const toggle = page
    .locator('.o_main_navbar button:first-child, [aria-label="Home Menu"]')
    .first();
  if (await toggle.isVisible({ timeout: 3000 }).catch(() => false)) {
    await toggle.click();
    await page.waitForTimeout(1000);
  }
}

/** Open the user menu dropdown (top-right avatar). */
export async function openUserMenu(page: Page): Promise<void> {
  const userBtn = page.locator('.o_user_menu button, img[alt="User"]').first();
  if (await userBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await userBtn.click();
    await page.waitForTimeout(600);
  }
}

/** Open the search/filter panel (toggle the dropdown arrow). */
export async function openSearchPanel(page: Page): Promise<void> {
  const toggle = page
    .locator(
      '.o_searchview_dropdown_toggler, button[aria-label="Toggle Search Panel"]',
    )
    .first();
  if (await toggle.isVisible({ timeout: 2000 }).catch(() => false)) {
    await toggle.click();
    await page.waitForTimeout(600);
  }
}

/** Click search bar to show autocomplete suggestions. */
export async function clickSearchBar(page: Page): Promise<void> {
  const input = page
    .locator('.o_searchview_input, input[placeholder="Search..."]')
    .first();
  if (await input.isVisible({ timeout: 2000 }).catch(() => false)) {
    await input.click();
    await page.waitForTimeout(600);
  }
}

/** Dismiss Odoo onboarding banners and sample data overlays. */
export async function dismissBanners(page: Page): Promise<void> {
  // Tolerant of navigation race conditions
  try {
    await page.evaluate(() => {
      document
        .querySelectorAll(
          '.o_onboarding_container, [class*="sample_data_message"], .o_view_sample_data .o_sample_data_message',
        )
        .forEach((el: any) => (el.style.display = "none"));
    });
  } catch {
    // Page navigated mid-evaluate — banner removal is best-effort
  }
}

/** Switch view type (list, kanban, pivot, calendar, graph, map, activity). */
export async function switchView(page: Page, viewType: string): Promise<void> {
  const btn = page.locator(`.o_switch_view.o_${viewType}`).first();
  if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await btn.click();
    await page.waitForTimeout(1500);
  }
}

// ---------------------------------------------------------------------------
// Screenshot helper
// ---------------------------------------------------------------------------

/** Take a named screenshot, saving to the configured screenshot directory. */
export async function takeScreenshot(page: Page, name: string): Promise<void> {
  const dir = process.env.ODOO_E2E_SCREENSHOT_DIR || "screenshots";
  await dismissBanners(page);
  try {
    await page.screenshot({ path: `${dir}/${name}.png`, fullPage: false });
  } catch (e) {
    console.log(`Screenshot ${name} failed, retrying:`, e);
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${dir}/${name}.png`, fullPage: false });
  }
}

/** Take screenshot with a specific viewport crop (not full page). */
export async function takeViewportScreenshot(
  page: Page,
  name: string,
): Promise<void> {
  const dir = process.env.ODOO_E2E_SCREENSHOT_DIR || "screenshots";
  await dismissBanners(page);
  await page.screenshot({ path: `${dir}/${name}.png`, fullPage: false });
}
