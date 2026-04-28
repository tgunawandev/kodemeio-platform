/**
 * Training Guide Screenshot Capture — TPP Odoo ERP (staging)
 *
 * Run: ODOO_E2E_SCREENSHOT_DIR=<assets> kctl-odoo -p idtpp-tpp-odoo-erp-stg e2e test training-screenshots --screenshots
 *
 * Key staging record IDs:
 * - PO confirmed: PO.2026.01.00001 (id=186, CNY, SHANDONG GOODFARMER) — receipt id=947
 * - PO draft CNY:  PO.2026.01.00003 (id=184, CNY, ZHENGZHOU DEREK)
 * - PO confirmed: PO.2026.01.00003 (id=184, confirmed)
 * - SO confirmed: S00002 (id=562) — delivery id=948
 * - SO draft large: SO.2026.04.00009 (id=430)
 * - Bill posted: BILL/2026/04/0073 (id=41640, PT. ADJI BAYU CIPTA)
 * - Bill posted: BILL/2026/04/0072 (id=41641, PT. Seacon Bintang)
 * - Receipt assigned: UTA10/IN/00057 (id=947)
 * - Delivery confirmed: WH/OUT/00002 (id=948)
 * - Transfer assigned: UTA50/IN/00066 (id=912)
 */

import { test, expect } from "../../fixtures/odoo-test";

async function go(page: any, path: string) {
  await page.goto(path, { waitUntil: "domcontentloaded" });
  await page.locator(".o_main_navbar").first().waitFor({ timeout: 15_000 });
  await page.waitForTimeout(2000);
}

async function snap(page: any, odoo: any, file: string) {
  await odoo.takeScreenshot(page, file);
}

async function scrollDown(page: any, px = 400) {
  await page.evaluate((y: number) => window.scrollBy(0, y), px);
  await page.waitForTimeout(500);
}

async function clickTab(page: any, tabName: string) {
  const tab = page.locator(`.nav-link:has-text("${tabName}")`).first();
  if (await tab.isVisible({ timeout: 2000 }).catch(() => false)) {
    await tab.click();
    await page.waitForTimeout(800);
  }
}

// ─── 00: Authentik SSO ──────────────────────────────────────────────────────

test.describe("00-authentik-sso", () => {
  test("step-01", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase");
    await snap(page, odoo, "00-authentik-sso/step-01");
  });
  test("step-02", async ({ page, odoo }) => {
    await page.goto("/web/login", { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    await snap(page, odoo, "00-authentik-sso/step-02");
  });
  test("step-03", async ({ page, odoo }) => {
    await page.goto("/web/login", { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    const btn = page
      .locator('a:has-text("Authentik"), a:has-text("Login with")')
      .first();
    if (await btn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await btn.click();
      await page.waitForTimeout(3000);
    }
    await snap(page, odoo, "00-authentik-sso/step-03");
  });
  test("step-04", async ({ page, odoo }) => {
    await page.goto("https://auth.idtpp.com", {
      waitUntil: "domcontentloaded",
    });
    await page.waitForTimeout(3000);
    await snap(page, odoo, "00-authentik-sso/step-04");
  });
  test("step-05", async ({ page, odoo }) => {
    await page.goto("https://auth.idtpp.com", {
      waitUntil: "domcontentloaded",
    });
    await page.waitForTimeout(3000);
    await snap(page, odoo, "00-authentik-sso/step-05");
  });
  test("step-06", async ({ page, odoo }) => {
    await go(page, "/odoo");
    await snap(page, odoo, "00-authentik-sso/step-06");
  });
  test("step-07", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase");
    await snap(page, odoo, "00-authentik-sso/step-07");
  });
  test("step-08", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase");
    await odoo.openUserMenu(page);
    await snap(page, odoo, "00-authentik-sso/step-08");
  });
});

// ─── 01: Quick Start ────────────────────────────────────────────────────────

test.describe("01-quick-start", () => {
  test("step-01: toolbar", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase");
    await snap(page, odoo, "01-quick-start/step-01");
  });
  test("step-02: App Switcher", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase");
    await odoo.openAppSwitcher(page);
    await snap(page, odoo, "01-quick-start/step-02");
  });
  test("step-03: breadcrumb", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await snap(page, odoo, "01-quick-start/step-03");
  });
  test("step-04: search bar", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase");
    await odoo.clickSearchBar(page);
    await snap(page, odoo, "01-quick-start/step-04");
  });
  test("step-05: user menu", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase");
    await odoo.openUserMenu(page);
    await snap(page, odoo, "01-quick-start/step-05");
  });
  test("step-06: app landing", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting");
    await snap(page, odoo, "01-quick-start/step-06");
  });
  test("step-07: list view", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/customer-invoices");
    await snap(page, odoo, "01-quick-start/step-07");
  });
  test("step-08: form view", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await snap(page, odoo, "01-quick-start/step-08");
  });
  test("step-09: form scroll chatter", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await scrollDown(page, 600);
    await snap(page, odoo, "01-quick-start/step-09");
  });
  test("step-10: kanban view", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory");
    await snap(page, odoo, "01-quick-start/step-10");
  });
  test("step-11: filter panel", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase");
    await odoo.openSearchPanel(page);
    await snap(page, odoo, "01-quick-start/step-11");
  });
  test("step-12: accounting dashboard", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting");
    await scrollDown(page, 300);
    await snap(page, odoo, "01-quick-start/step-12");
  });
});

// ─── 02: Sales Order ────────────────────────────────────────────────────────

test.describe("02-sales-order", () => {
  test("step-01: SO list", async ({ page, odoo }) => {
    await go(page, "/odoo/sales");
    await snap(page, odoo, "02-sales-order/step-01");
  });
  test("step-02: SO form top", async ({ page, odoo }) => {
    await go(page, "/odoo/sales/562");
    await snap(page, odoo, "02-sales-order/step-02");
  });
  test("step-03: SO customer section", async ({ page, odoo }) => {
    await go(page, "/odoo/sales/430");
    await snap(page, odoo, "02-sales-order/step-03");
  });
  test("step-04: SO order lines", async ({ page, odoo }) => {
    await go(page, "/odoo/sales/562");
    await scrollDown(page, 350);
    await snap(page, odoo, "02-sales-order/step-04");
  });
  test("step-05: SO other info tab", async ({ page, odoo }) => {
    await go(page, "/odoo/sales/562");
    await clickTab(page, "Other Info");
    await snap(page, odoo, "02-sales-order/step-05");
  });
  test("step-06: SO confirmed status", async ({ page, odoo }) => {
    await go(page, "/odoo/sales/562");
    await snap(page, odoo, "02-sales-order/step-06");
  });
  test("step-07: delivery list", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory");
    await snap(page, odoo, "02-sales-order/step-07");
  });
  test("step-08: delivery form", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-948");
    await snap(page, odoo, "02-sales-order/step-08");
  });
  test("step-09: accounting dashboard", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting");
    await snap(page, odoo, "02-sales-order/step-09");
  });
  test("step-10: invoice list", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/customer-invoices");
    await snap(page, odoo, "02-sales-order/step-10");
  });
  test("step-11: vendor bill form", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41640");
    await snap(page, odoo, "02-sales-order/step-11");
  });
  test("step-12: bill payment section", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41641");
    await scrollDown(page, 500);
    await snap(page, odoo, "02-sales-order/step-12");
  });
});

// ─── 03: Purchase Order ─────────────────────────────────────────────────────

test.describe("03-purchase-order", () => {
  test("step-01: PO list", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase");
    await snap(page, odoo, "03-purchase-order/step-01");
  });
  test("step-02: PO form vendor", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await snap(page, odoo, "03-purchase-order/step-02");
  });
  test("step-03: PO products tab", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await scrollDown(page, 350);
    await snap(page, odoo, "03-purchase-order/step-03");
  });
  test("step-04: PO other info", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await clickTab(page, "Other Information");
    await snap(page, odoo, "03-purchase-order/step-04");
  });
  test("step-05: PO taxes line", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/184");
    await scrollDown(page, 350);
    await snap(page, odoo, "03-purchase-order/step-05");
  });
  test("step-06: PO confirmed status", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await snap(page, odoo, "03-purchase-order/step-06");
  });
  test("step-07: Receipt from PO", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-947");
    await snap(page, odoo, "03-purchase-order/step-07");
  });
  test("step-08: Receipt operations", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-947");
    await scrollDown(page, 400);
    await snap(page, odoo, "03-purchase-order/step-08");
  });
  test("step-09: Vendor bill list", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills");
    await snap(page, odoo, "03-purchase-order/step-09");
  });
  test("step-10: Bill form top", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41640");
    await snap(page, odoo, "03-purchase-order/step-10");
  });
  test("step-11: Bill journal items", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41640");
    await clickTab(page, "Journal Items");
    await snap(page, odoo, "03-purchase-order/step-11");
  });
  test("step-12: Bill other info", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41640");
    await clickTab(page, "Other Info");
    await snap(page, odoo, "03-purchase-order/step-12");
  });
  test("step-13: Draft PO CNY", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/183");
    await snap(page, odoo, "03-purchase-order/step-13");
  });
  test("step-14: Draft PO products", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/183");
    await scrollDown(page, 400);
    await snap(page, odoo, "03-purchase-order/step-14");
  });
  test("step-15: PO chatter", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await scrollDown(page, 700);
    await snap(page, odoo, "03-purchase-order/step-15");
  });
});

// ─── 04: Import Clearance ───────────────────────────────────────────────────

test.describe("04-import-clearance", () => {
  test("step-01: New PO foreign vendor", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await snap(page, odoo, "04-import-clearance/step-01");
  });
  test("step-02: Incoterms tab", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await clickTab(page, "Other Information");
    await snap(page, odoo, "04-import-clearance/step-02");
  });
  test("step-03: Product lines valas", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await scrollDown(page, 350);
    await snap(page, odoo, "04-import-clearance/step-03");
  });
  test("step-04: Confirmed PO", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/184");
    await snap(page, odoo, "04-import-clearance/step-04");
  });
  test("step-05: Receipt transfer", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-947");
    await snap(page, odoo, "04-import-clearance/step-05");
  });
  test("step-06: Receipt operations tab", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-947");
    await scrollDown(page, 350);
    await snap(page, odoo, "04-import-clearance/step-06");
  });
  test("step-07: Create Bill from PO", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await snap(page, odoo, "04-import-clearance/step-07");
  });
  test("step-08: Bill currency rate", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41640");
    await snap(page, odoo, "04-import-clearance/step-08");
  });
  test("step-09: Bill posted journal", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41640");
    await clickTab(page, "Journal Items");
    await snap(page, odoo, "04-import-clearance/step-09");
  });
  test("step-10: Landed costs page", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/landed-costs");
    await snap(page, odoo, "04-import-clearance/step-10");
  });
  test("step-11: Inventory transfers list", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory");
    await snap(page, odoo, "04-import-clearance/step-11");
  });
  test("step-12: Transfer detail", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-912");
    await snap(page, odoo, "04-import-clearance/step-12");
  });
  test("step-13: Transfer operations", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-912");
    await scrollDown(page, 400);
    await snap(page, odoo, "04-import-clearance/step-13");
  });
  test("step-14: Product list", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/products");
    await snap(page, odoo, "04-import-clearance/step-14");
  });
  test("step-15: Product form cost", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/products");
    const row = page.locator(".o_data_row").first();
    if (await row.isVisible({ timeout: 3000 }).catch(() => false)) {
      await row.click({ force: true });
      await page.waitForTimeout(2000);
    }
    await snap(page, odoo, "04-import-clearance/step-15");
  });
});

// ─── 05: Inventory & Warehouse ──────────────────────────────────────────────

test.describe("05-inventory-warehouse", () => {
  test("step-01: Overview", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory");
    await snap(page, odoo, "05-inventory-warehouse/step-01");
  });
  test("step-02: New transfer button", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory");
    await snap(page, odoo, "05-inventory-warehouse/step-02");
  });
  test("step-03: Transfer form", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-947");
    await snap(page, odoo, "05-inventory-warehouse/step-03");
  });
  test("step-04: Source/Dest locations", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-948");
    await snap(page, odoo, "05-inventory-warehouse/step-04");
  });
  test("step-05: Scheduled date", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-912");
    await snap(page, odoo, "05-inventory-warehouse/step-05");
  });
  test("step-06: Operations tab", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-947");
    await scrollDown(page, 300);
    await snap(page, odoo, "05-inventory-warehouse/step-06");
  });
  test("step-07: Delivery order", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-944");
    await snap(page, odoo, "05-inventory-warehouse/step-07");
  });
  test("step-08: Delivery operations", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-944");
    await scrollDown(page, 350);
    await snap(page, odoo, "05-inventory-warehouse/step-08");
  });
  test("step-09: Receipt detail", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-826");
    await snap(page, odoo, "05-inventory-warehouse/step-09");
  });
  test("step-10: Receipt chatter", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-826");
    await scrollDown(page, 600);
    await snap(page, odoo, "05-inventory-warehouse/step-10");
  });
  test("step-11: Physical inventory", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/inventory-adjustments");
    await snap(page, odoo, "05-inventory-warehouse/step-11");
  });
  test("step-12: Products list", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/products");
    await snap(page, odoo, "05-inventory-warehouse/step-12");
  });
});

// ─── 06: Accounting AR/AP ───────────────────────────────────────────────────

test.describe("06-accounting-ar-ap", () => {
  test("step-01: Customer invoices list", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/customer-invoices");
    await snap(page, odoo, "06-accounting-ar-ap/step-01");
  });
  test("step-02: Invoice form", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/customer-invoices");
    const r = page.locator(".o_data_row").first();
    if (await r.isVisible({ timeout: 3000 }).catch(() => false)) {
      await r.click({ force: true });
      await page.waitForTimeout(2000);
    }
    await snap(page, odoo, "06-accounting-ar-ap/step-02");
  });
  test("step-03: Invoice journal items", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41640");
    await clickTab(page, "Journal Items");
    await snap(page, odoo, "06-accounting-ar-ap/step-03");
  });
  test("step-04: Invoice other info", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41641");
    await clickTab(page, "Other Info");
    await snap(page, odoo, "06-accounting-ar-ap/step-04");
  });
  test("step-05: Invoice amount section", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41641");
    await scrollDown(page, 500);
    await snap(page, odoo, "06-accounting-ar-ap/step-05");
  });
  test("step-06: Invoice chatter", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41640");
    await scrollDown(page, 700);
    await snap(page, odoo, "06-accounting-ar-ap/step-06");
  });
  test("step-07: Vendor bills list", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills");
    await snap(page, odoo, "06-accounting-ar-ap/step-07");
  });
  test("step-08: Bill form", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41640");
    await snap(page, odoo, "06-accounting-ar-ap/step-08");
  });
  test("step-09: Bill lines detail", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41640");
    await scrollDown(page, 400);
    await snap(page, odoo, "06-accounting-ar-ap/step-09");
  });
  test("step-10: Journal entries", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/journal-entries");
    await snap(page, odoo, "06-accounting-ar-ap/step-10");
  });
  test("step-11: Accounting dashboard", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting");
    await snap(page, odoo, "06-accounting-ar-ap/step-11");
  });
  test("step-12: Dashboard bank section", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting");
    await scrollDown(page, 400);
    await snap(page, odoo, "06-accounting-ar-ap/step-12");
  });
});

// ─── 07: Finance Reports ────────────────────────────────────────────────────

test.describe("07-finance-reports", () => {
  test("step-01: Accounting dashboard", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting");
    await snap(page, odoo, "07-finance-reports/step-01");
  });
  test("step-02: Dashboard scrolled", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting");
    await scrollDown(page, 300);
    await snap(page, odoo, "07-finance-reports/step-02");
  });
  test("step-03: Dashboard bank", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting");
    await scrollDown(page, 600);
    await snap(page, odoo, "07-finance-reports/step-03");
  });
  test("step-04: Reporting menu", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting");
    await odoo.hoverMenu(page, "Reporting");
    await snap(page, odoo, "07-finance-reports/step-04");
  });
  test("step-05: Balance Sheet", async ({ page, odoo }) => {
    await go(page, "/odoo/action-1493");
    await snap(page, odoo, "07-finance-reports/step-05");
  });
  test("step-06: Aged Partner Balance", async ({ page, odoo }) => {
    await go(page, "/odoo/action-608");
    await snap(page, odoo, "07-finance-reports/step-06");
  });
  test("step-07: General Ledger", async ({ page, odoo }) => {
    await go(page, "/odoo/action-609");
    await snap(page, odoo, "07-finance-reports/step-07");
  });
  test("step-08: Trial Balance", async ({ page, odoo }) => {
    await go(page, "/odoo/action-614");
    await snap(page, odoo, "07-finance-reports/step-08");
  });
  test("step-09: Open Items", async ({ page, odoo }) => {
    await go(page, "/odoo/action-612");
    await snap(page, odoo, "07-finance-reports/step-09");
  });
  test("step-10: Journal Ledger", async ({ page, odoo }) => {
    await go(page, "/odoo/action-611");
    await snap(page, odoo, "07-finance-reports/step-10");
  });
  test("step-11: MIS Reports", async ({ page, odoo }) => {
    await go(page, "/odoo/action-838");
    await snap(page, odoo, "07-finance-reports/step-11");
  });
  test("step-12: Invoice Analysis", async ({ page, odoo }) => {
    await go(page, "/odoo/action-411");
    await snap(page, odoo, "07-finance-reports/step-12");
  });
});

// ─── 08: Import Purchase Flow ───────────────────────────────────────────────

test.describe("08-import-purchase-flow", () => {
  test("step-01-pr: Purchase list", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase");
    await snap(page, odoo, "08-import-purchase-flow/step-01-pr");
  });
  test("step-02-po: PO confirmed form", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await snap(page, odoo, "08-import-purchase-flow/step-02-po");
  });
  test("step-03-advance-invoice: Vendor bill", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41641");
    await snap(page, odoo, "08-import-purchase-flow/step-03-advance-invoice");
  });
  test("step-04-payment: Bill payment section", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41640");
    await scrollDown(page, 500);
    await snap(page, odoo, "08-import-purchase-flow/step-04-payment");
  });
  test("step-05-cost-lines: PO products tab", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/184");
    await scrollDown(page, 350);
    await snap(page, odoo, "08-import-purchase-flow/step-05-cost-lines");
  });
  test("step-06-sppb-release: Inventory overview", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory");
    await snap(page, odoo, "08-import-purchase-flow/step-06-sppb-release");
  });
  test("step-07-receipt: Receipt form", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory/id-947");
    await snap(page, odoo, "08-import-purchase-flow/step-07-receipt");
  });
  test("step-08-final-payment: Bill journal items", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41640");
    await clickTab(page, "Journal Items");
    await snap(page, odoo, "08-import-purchase-flow/step-08-final-payment");
  });
  test("container-tracking-lifecycle: Transfer list", async ({
    page,
    odoo,
  }) => {
    await go(page, "/odoo/inventory");
    await snap(
      page,
      odoo,
      "08-import-purchase-flow/container-tracking-lifecycle",
    );
  });
});

// ─── 09: Import Sales Flow ──────────────────────────────────────────────────

test.describe("09-import-sales-flow", () => {
  test("step-01: SO with SC", async ({ page, odoo }) => {
    await go(page, "/odoo/sales/562");
    await snap(page, odoo, "09-import-sales-flow/step-01");
  });
  test("step-02a: SO order lines", async ({ page, odoo }) => {
    await go(page, "/odoo/sales/562");
    await scrollDown(page, 350);
    await snap(page, odoo, "09-import-sales-flow/step-02a");
  });
  test("step-02b: SO large amount", async ({ page, odoo }) => {
    await go(page, "/odoo/sales/430");
    await snap(page, odoo, "09-import-sales-flow/step-02b");
  });
  test("step-03: Customer invoice", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/customer-invoices");
    await snap(page, odoo, "09-import-sales-flow/step-03");
  });
});

// ─── 10: Import Operational Reports ─────────────────────────────────────────

test.describe("10-import-operational-reports", () => {
  test("step-01: Purchase list", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase");
    await snap(page, odoo, "10-import-operational-reports/step-01");
  });
  test("step-02: PO form confirmed", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await snap(page, odoo, "10-import-operational-reports/step-02");
  });
  test("step-03: PO draft list", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/184");
    await snap(page, odoo, "10-import-operational-reports/step-03");
  });
  test("step-04: Inventory transfers", async ({ page, odoo }) => {
    await go(page, "/odoo/inventory");
    await snap(page, odoo, "10-import-operational-reports/step-04");
  });
  test("step-05: Vendor bills list", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills");
    await snap(page, odoo, "10-import-operational-reports/step-05");
  });
  test("step-06: Bill posted form", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting/vendor-bills/41640");
    await snap(page, odoo, "10-import-operational-reports/step-06");
  });
  test("step-07: General Ledger", async ({ page, odoo }) => {
    await go(page, "/odoo/action-609");
    await snap(page, odoo, "10-import-operational-reports/step-07");
  });
  test("step-08: Open Items", async ({ page, odoo }) => {
    await go(page, "/odoo/action-612");
    await snap(page, odoo, "10-import-operational-reports/step-08");
  });
  test("step-09: PO other info", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await clickTab(page, "Other Information");
    await snap(page, odoo, "10-import-operational-reports/step-09");
  });
  test("step-10: PO products", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase/186");
    await scrollDown(page, 400);
    await snap(page, odoo, "10-import-operational-reports/step-10");
  });
});

// ─── 11: Import Management Reports ──────────────────────────────────────────

test.describe("11-import-management-reports", () => {
  test("step-01: Accounting dashboard", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting");
    await snap(page, odoo, "11-import-management-reports/step-01");
  });
  test("step-02: Balance Sheet", async ({ page, odoo }) => {
    await go(page, "/odoo/action-1493");
    await snap(page, odoo, "11-import-management-reports/step-02");
  });
  test("step-03: Trial Balance", async ({ page, odoo }) => {
    await go(page, "/odoo/action-614");
    await snap(page, odoo, "11-import-management-reports/step-03");
  });
  test("step-04: Aged Partner Balance", async ({ page, odoo }) => {
    await go(page, "/odoo/action-608");
    await snap(page, odoo, "11-import-management-reports/step-04");
  });
  test("step-05: Dashboard invoices", async ({ page, odoo }) => {
    await go(page, "/odoo/accounting");
    await scrollDown(page, 300);
    await snap(page, odoo, "11-import-management-reports/step-05");
  });
  test("step-06: Aged receivable", async ({ page, odoo }) => {
    await go(page, "/odoo/action-608");
    await snap(page, odoo, "11-import-management-reports/step-06");
  });
  test("step-07: General Ledger", async ({ page, odoo }) => {
    await go(page, "/odoo/action-609");
    await snap(page, odoo, "11-import-management-reports/step-07");
  });
  test("step-08: Journal Ledger", async ({ page, odoo }) => {
    await go(page, "/odoo/action-611");
    await snap(page, odoo, "11-import-management-reports/step-08");
  });
  test("step-09: MIS Reports", async ({ page, odoo }) => {
    await go(page, "/odoo/action-838");
    await snap(page, odoo, "11-import-management-reports/step-09");
  });
  test("step-10: Open Items", async ({ page, odoo }) => {
    await go(page, "/odoo/action-612");
    await snap(page, odoo, "11-import-management-reports/step-10");
  });
});

// ─── 12: Mattermost Integration ─────────────────────────────────────────────

test.describe("12-mattermost-integration", () => {
  test("step-01", async ({ page, odoo }) => {
    await go(page, "/odoo/discuss");
    await snap(page, odoo, "12-mattermost-integration/step-01");
  });
});

// ─── 13: Approval Workflow ──────────────────────────────────────────────────

test.describe("13-approval-workflow", () => {
  test("step-01", async ({ page, odoo }) => {
    await go(page, "/odoo/purchase");
    await snap(page, odoo, "13-approval-workflow/step-01");
  });
});
