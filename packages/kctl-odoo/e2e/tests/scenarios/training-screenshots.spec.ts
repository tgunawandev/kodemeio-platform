/**
 * Training Guide Screenshot Capture — TPP Odoo ERP (staging)
 *
 * SINGLE-TEST FAST VERSION: reuses one browser page across all 133 screenshots.
 * Avoids per-test setup overhead (28s per test → 5s per screenshot).
 *
 * Run: ODOO_E2E_SCREENSHOT_DIR=<assets> kctl-odoo -p idtpp-tpp-odoo-erp-stg e2e test training-screenshots --screenshots
 *
 * Staging record IDs:
 * - PO confirmed CNY: 186 (Shandong), 184 (Zhengzhou), 183 (Jiangsu)
 * - PO draft CNY:    59 (Qixian), 60, 61, 62, 63, 64
 * - PO draft IDR:    70 (Aufa Jaya)
 * - SO confirmed:    562 (S00002), 430 (large 5B IDR)
 * - Bill posted:     41640 (Adji Bayu), 41641 (Seacon), 41257 (Global Terminal),
 *                    36946 (Graha Segara), 36947 (Karantina), 35128 (JICT)
 * - Receipt:         947 (UTA10/IN/00057), 912 (UTA50/IN/00066), 826 (PEL10/IN/00088)
 * - Delivery:        948 (WH/OUT/00002), 944 (PEL10/OUT/00130)
 */

import { test, expect } from "../../fixtures/odoo-test";

// One mega-test, sequential screenshots, page reused throughout
test.describe.configure({ mode: "serial" });

test("capture all training screenshots", async ({ page, odoo }) => {
  test.setTimeout(45 * 60 * 1000); // 45 minutes total

  async function go(path: string) {
    try {
      await page.goto(path, {
        waitUntil: "domcontentloaded",
        timeout: 60_000,
      });
    } catch (e) {
      // Continue even if navigation timed out — page may still be partially loaded
    }
    await page
      .locator(".o_main_navbar")
      .first()
      .waitFor({ timeout: 30_000 })
      .catch(() => {});
    // Wait for actual view content to render (NOT just navbar)
    await page
      .locator(
        ".o_action_manager .o_view_controller, .o_action_manager .o_action, .o-mail-DiscussCore, .o_home_menu",
      )
      .first()
      .waitFor({ timeout: 30_000 })
      .catch(() => {});
    // Wait for any "Loading" indicators to disappear
    await page
      .locator(".o_loading, .o_loading_indicator")
      .first()
      .waitFor({ state: "hidden", timeout: 15_000 })
      .catch(() => {});
    await page.waitForTimeout(2000);
  }

  async function snap(file: string) {
    // Validate page is not showing an error dialog before screenshot
    const errorDialog = page.locator(
      '.modal-dialog:has-text("Missing Action"), .modal-dialog:has-text("Oops"), .modal-dialog:has-text("does not exist")',
    );
    if (await errorDialog.isVisible({ timeout: 500 }).catch(() => false)) {
      // Try closing the dialog first
      const closeBtn = page
        .locator('.modal-dialog button:has-text("Close")')
        .first();
      if (await closeBtn.isVisible({ timeout: 500 }).catch(() => false)) {
        await closeBtn.click();
        await page.waitForTimeout(500);
      }
      console.warn(`⚠ Error dialog on ${file}, screenshot will be invalid`);
    }
    await odoo.takeScreenshot(page, file);
  }

  async function scrollDown(px = 400) {
    await page.evaluate((y: number) => window.scrollBy(0, y), px);
    await page.waitForTimeout(400);
  }

  async function clickTab(tabName: string) {
    const selectors = [
      `.o_notebook .nav-link:has-text("${tabName}")`,
      `a.nav-link:has-text("${tabName}")`,
      `[role="tab"]:has-text("${tabName}")`,
    ];
    for (const sel of selectors) {
      const tab = page.locator(sel).first();
      if (await tab.isVisible({ timeout: 1000 }).catch(() => false)) {
        await tab.click();
        await page.waitForTimeout(800);
        return;
      }
    }
  }

  // ─── 00: Authentik SSO ───────────────────────────────────────────
  await go("/odoo/purchase");
  await snap("00-authentik-sso/step-01");
  try {
    await page.goto("/web/login", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await page.waitForTimeout(1500);
    await snap("00-authentik-sso/step-02");
    await page.goto("/web/login", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await page.waitForTimeout(1500);
    const authBtn = page
      .locator('a:has-text("Authentik"), a:has-text("Login with")')
      .first();
    if (await authBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await authBtn.click();
      await page.waitForTimeout(2500);
    }
    await snap("00-authentik-sso/step-03");
    await page.goto("https://auth.idtpp.com", {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    await page.waitForTimeout(2500);
    await snap("00-authentik-sso/step-04");
    await snap("00-authentik-sso/step-05");
  } catch (e) {
    console.log("SSO external nav skipped:", e);
  }
  await go("/odoo");
  await snap("00-authentik-sso/step-06");
  await go("/odoo/purchase");
  await snap("00-authentik-sso/step-07");
  await go("/odoo/purchase");
  await odoo.openUserMenu(page);
  await snap("00-authentik-sso/step-08");

  // ─── 01: Quick Start ─────────────────────────────────────────────
  await go("/odoo/purchase");
  await snap("01-quick-start/step-01");
  await go("/odoo/purchase");
  await odoo.openAppSwitcher(page);
  await snap("01-quick-start/step-02");
  await go("/odoo/purchase/186");
  await snap("01-quick-start/step-03");
  await go("/odoo/purchase");
  await odoo.clickSearchBar(page);
  await snap("01-quick-start/step-04");
  await go("/odoo/purchase");
  await odoo.openUserMenu(page);
  await snap("01-quick-start/step-05");
  await go("/odoo/accounting");
  await snap("01-quick-start/step-06");
  await go("/odoo/action-378");
  await snap("01-quick-start/step-07");
  await go("/odoo/purchase/186");
  await snap("01-quick-start/step-08");
  await go("/odoo/purchase/186");
  await scrollDown(600);
  await snap("01-quick-start/step-09");
  await go("/odoo/inventory");
  await snap("01-quick-start/step-10");
  await go("/odoo/purchase");
  await odoo.openSearchPanel(page);
  await snap("01-quick-start/step-11");
  await go("/odoo/accounting");
  await scrollDown(300);
  await snap("01-quick-start/step-12");

  // ─── 02: Sales Order ─────────────────────────────────────────────
  await go("/odoo/sales");
  await snap("02-sales-order/step-01");
  await go("/odoo/sales/562");
  await snap("02-sales-order/step-02");
  await go("/odoo/sales/430");
  await snap("02-sales-order/step-03");
  await go("/odoo/sales/562");
  await scrollDown(350);
  await snap("02-sales-order/step-04");
  await go("/odoo/sales/562");
  await clickTab("Other Info");
  await snap("02-sales-order/step-05");
  await go("/odoo/sales/562");
  await snap("02-sales-order/step-06");
  await go("/odoo/inventory");
  await snap("02-sales-order/step-07");
  await go("/odoo/action-531/948");
  await snap("02-sales-order/step-08");
  await go("/odoo/accounting");
  await snap("02-sales-order/step-09");
  await go("/odoo/action-378");
  await snap("02-sales-order/step-10");
  await go("/odoo/action-381/41640");
  await snap("02-sales-order/step-11");
  await go("/odoo/action-381/41641");
  await scrollDown(500);
  await snap("02-sales-order/step-12");

  // ─── 03: Purchase Order ──────────────────────────────────────────
  await go("/odoo/purchase");
  await snap("03-purchase-order/step-01");
  await go("/odoo/purchase/186");
  await snap("03-purchase-order/step-02");
  await go("/odoo/purchase/186");
  await scrollDown(500);
  await snap("03-purchase-order/step-03");
  await go("/odoo/purchase/70");
  await snap("03-purchase-order/step-04");
  await go("/odoo/purchase/59");
  await snap("03-purchase-order/step-05");
  await go("/odoo/purchase/186");
  await scrollDown(1200);
  await snap("03-purchase-order/step-06");
  await go("/odoo/action-531/947");
  await snap("03-purchase-order/step-07");
  await go("/odoo/action-531/912");
  await snap("03-purchase-order/step-08");
  await go("/odoo/action-381");
  await snap("03-purchase-order/step-09");
  await go("/odoo/action-381/41640");
  await snap("03-purchase-order/step-10");
  await go("/odoo/action-381/41641");
  await snap("03-purchase-order/step-11");
  await go("/odoo/action-381/41257");
  await snap("03-purchase-order/step-12");
  await go("/odoo/action-381/36946");
  await snap("03-purchase-order/step-13");
  await go("/odoo/action-381/36947");
  await snap("03-purchase-order/step-14");
  await go("/odoo/action-381/35128");
  await scrollDown(600);
  await snap("03-purchase-order/step-15");

  // ─── 04: Import Clearance ────────────────────────────────────────
  await go("/odoo/purchase/186");
  await snap("04-import-clearance/step-01");
  await go("/odoo/purchase/186");
  await scrollDown(600);
  await snap("04-import-clearance/step-02");
  await go("/odoo/purchase/184");
  await snap("04-import-clearance/step-03");
  await go("/odoo/purchase/183");
  await snap("04-import-clearance/step-04");
  await go("/odoo/action-531/947");
  await snap("04-import-clearance/step-05");
  await go("/odoo/action-531/947");
  await scrollDown(700);
  await snap("04-import-clearance/step-06");
  await go("/odoo/action-531/912");
  await snap("04-import-clearance/step-07");
  await go("/odoo/action-381/41640");
  await snap("04-import-clearance/step-08");
  await go("/odoo/action-381/41641");
  await snap("04-import-clearance/step-09");
  await go("/odoo/action-1127");
  await snap("04-import-clearance/step-10");
  await go("/odoo/inventory");
  await snap("04-import-clearance/step-11");
  await go("/odoo/action-531/826");
  await snap("04-import-clearance/step-12");
  await go("/odoo/action-531/944");
  await snap("04-import-clearance/step-13");
  await go("/odoo/action-241");
  await snap("04-import-clearance/step-14");
  await go("/odoo/action-381/36946");
  await snap("04-import-clearance/step-15");

  // ─── 05: Inventory & Warehouse ───────────────────────────────────
  await go("/odoo/inventory");
  await snap("05-inventory-warehouse/step-01");
  await go("/odoo/inventory");
  await snap("05-inventory-warehouse/step-02");
  await go("/odoo/action-531/947");
  await snap("05-inventory-warehouse/step-03");
  await go("/odoo/action-531/948");
  await snap("05-inventory-warehouse/step-04");
  await go("/odoo/action-531/912");
  await snap("05-inventory-warehouse/step-05");
  await go("/odoo/action-531/947");
  await scrollDown(300);
  await snap("05-inventory-warehouse/step-06");
  await go("/odoo/action-531/944");
  await snap("05-inventory-warehouse/step-07");
  await go("/odoo/action-531/944");
  await scrollDown(350);
  await snap("05-inventory-warehouse/step-08");
  await go("/odoo/action-531/826");
  await snap("05-inventory-warehouse/step-09");
  await go("/odoo/action-531/826");
  await scrollDown(600);
  await snap("05-inventory-warehouse/step-10");
  await go("/odoo/action-522");
  await snap("05-inventory-warehouse/step-11");
  await go("/odoo/action-241");
  await snap("05-inventory-warehouse/step-12");

  // ─── 06: Accounting AR/AP ────────────────────────────────────────
  await go("/odoo/action-378");
  await snap("06-accounting-ar-ap/step-01");
  await go("/odoo/action-378");
  const r2 = page.locator(".o_data_row").first();
  if (await r2.isVisible({ timeout: 3000 }).catch(() => false)) {
    await r2.click({ force: true });
    await page.waitForTimeout(1500);
  }
  await snap("06-accounting-ar-ap/step-02");
  await go("/odoo/action-378");
  const r3 = page.locator(".o_data_row").first();
  if (await r3.isVisible({ timeout: 3000 }).catch(() => false)) {
    await r3.click({ force: true });
    await page.waitForTimeout(1500);
  }
  await scrollDown(600);
  await snap("06-accounting-ar-ap/step-03");
  await go("/odoo/action-381/41641");
  await snap("06-accounting-ar-ap/step-04");
  await go("/odoo/action-381/41257");
  await snap("06-accounting-ar-ap/step-05");
  await go("/odoo/action-381/36946");
  await snap("06-accounting-ar-ap/step-06");
  await go("/odoo/action-381");
  await snap("06-accounting-ar-ap/step-07");
  await go("/odoo/action-381/41640");
  await snap("06-accounting-ar-ap/step-08");
  await go("/odoo/action-381/36947");
  await snap("06-accounting-ar-ap/step-09");
  await go("/odoo/action-377");
  await snap("06-accounting-ar-ap/step-10");
  await go("/odoo/accounting");
  await snap("06-accounting-ar-ap/step-11");
  await go("/odoo/accounting");
  await scrollDown(400);
  await snap("06-accounting-ar-ap/step-12");

  // ─── 07: Finance Reports ─────────────────────────────────────────
  await go("/odoo/accounting");
  await snap("07-finance-reports/step-01");
  await go("/odoo/accounting");
  await scrollDown(300);
  await snap("07-finance-reports/step-02");
  await go("/odoo/accounting");
  await scrollDown(600);
  await snap("07-finance-reports/step-03");
  await go("/odoo/accounting");
  await odoo.hoverMenu(page, "Reporting");
  await snap("07-finance-reports/step-04");
  await go("/odoo/action-1493");
  await snap("07-finance-reports/step-05");
  await go("/odoo/action-608");
  await snap("07-finance-reports/step-06");
  await go("/odoo/action-609");
  await snap("07-finance-reports/step-07");
  await go("/odoo/action-614");
  await snap("07-finance-reports/step-08");
  await go("/odoo/action-612");
  await snap("07-finance-reports/step-09");
  await go("/odoo/action-611");
  await snap("07-finance-reports/step-10");
  await go("/odoo/action-838");
  await snap("07-finance-reports/step-11");
  await go("/odoo/action-411");
  await snap("07-finance-reports/step-12");

  // ─── 08: Import Purchase Flow ────────────────────────────────────
  await go("/odoo/purchase");
  await snap("08-import-purchase-flow/step-01-pr");
  await go("/odoo/purchase/186");
  await snap("08-import-purchase-flow/step-02-po");
  await go("/odoo/action-381/41641");
  await snap("08-import-purchase-flow/step-03-advance-invoice");
  await go("/odoo/action-381/41640");
  await scrollDown(500);
  await snap("08-import-purchase-flow/step-04-payment");
  await go("/odoo/purchase/184");
  await scrollDown(350);
  await snap("08-import-purchase-flow/step-05-cost-lines");
  await go("/odoo/inventory");
  await snap("08-import-purchase-flow/step-06-sppb-release");
  await go("/odoo/action-531/947");
  await snap("08-import-purchase-flow/step-07-receipt");
  await go("/odoo/action-381/41640");
  await clickTab("Journal Items");
  await snap("08-import-purchase-flow/step-08-final-payment");
  await go("/odoo/inventory");
  await snap("08-import-purchase-flow/container-tracking-lifecycle");

  // ─── 09: Import Sales Flow ───────────────────────────────────────
  await go("/odoo/sales/562");
  await snap("09-import-sales-flow/step-01");
  await go("/odoo/sales/562");
  await scrollDown(350);
  await snap("09-import-sales-flow/step-02a");
  await go("/odoo/sales/430");
  await snap("09-import-sales-flow/step-02b");
  await go("/odoo/action-378");
  await snap("09-import-sales-flow/step-03");

  // ─── 10: Import Operational Reports ──────────────────────────────
  await go("/odoo/purchase");
  await snap("10-import-operational-reports/step-01");
  await go("/odoo/purchase/186");
  await snap("10-import-operational-reports/step-02");
  await go("/odoo/purchase/184");
  await snap("10-import-operational-reports/step-03");
  await go("/odoo/purchase/70");
  await snap("10-import-operational-reports/step-04");
  await go("/odoo/action-381");
  await snap("10-import-operational-reports/step-05");
  await go("/odoo/action-381/41640");
  await snap("10-import-operational-reports/step-06");
  await go("/odoo/action-609");
  await snap("10-import-operational-reports/step-07");
  await go("/odoo/action-612");
  await snap("10-import-operational-reports/step-08");
  await go("/odoo/purchase/183");
  await snap("10-import-operational-reports/step-09");
  await go("/odoo/purchase/59");
  await snap("10-import-operational-reports/step-10");

  // ─── 11: Import Management Reports ───────────────────────────────
  await go("/odoo/accounting");
  await snap("11-import-management-reports/step-01");
  await go("/odoo/action-1493");
  await snap("11-import-management-reports/step-02");
  await go("/odoo/action-614");
  await snap("11-import-management-reports/step-03");
  await go("/odoo/action-608");
  await snap("11-import-management-reports/step-04");
  await go("/odoo/accounting");
  await scrollDown(300);
  await snap("11-import-management-reports/step-05");
  await go("/odoo/action-608");
  await snap("11-import-management-reports/step-06");
  await go("/odoo/action-609");
  await snap("11-import-management-reports/step-07");
  await go("/odoo/action-611");
  await snap("11-import-management-reports/step-08");
  await go("/odoo/action-838");
  await snap("11-import-management-reports/step-09");
  await go("/odoo/action-612");
  await snap("11-import-management-reports/step-10");

  // ─── 12: Mattermost Integration ──────────────────────────────────
  await go("/odoo/discuss");
  await snap("12-mattermost-integration/step-01");

  // ─── 13: Approval Workflow ───────────────────────────────────────
  await go("/odoo/purchase");
  await snap("13-approval-workflow/step-01");
});
