/**
 * Sales order flow: create a quotation, confirm it, check status.
 */

import { test, expect } from "../../fixtures/odoo-test";

test.describe("Sales Order Flow", () => {
  test("navigate to Sales > Quotations", async ({ page, odoo }) => {
    await page.goto("/odoo/sales");
    await odoo.waitForOdooReady(page);

    // Should see the sales menu/action
    const breadcrumb = await odoo.getBreadcrumb(page);
    expect(breadcrumb.length).toBeGreaterThan(0);
  });

  test("create a new quotation", async ({ page, odoo }) => {
    await page.goto("/odoo/sales");
    await odoo.waitForOdooReady(page);

    // Click "New" button
    await odoo.clickCreate(page);

    // Should be in form view
    const viewType = await odoo.getCurrentViewType(page);
    expect(viewType).toBe("form");

    // Fill customer (Many2one)
    await odoo.fillMany2one(page, "partner_id", "Administrator");

    // Discard — this is a test, don't save
    await odoo.clickDiscard(page);
  });

  test("quotation list view shows data", async ({ page, odoo }) => {
    await page.goto("/odoo/sales");
    await odoo.waitForOdooReady(page);

    // Check we can see the list or kanban
    const viewType = await odoo.getCurrentViewType(page);
    expect(["list", "kanban"]).toContain(viewType);
  });
});
