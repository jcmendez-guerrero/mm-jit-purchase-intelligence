import { expect, test } from "@playwright/test";
import { json } from "./dashboard-mock";
import { expectNoHorizontalScroll, signInAs } from "./ui-helpers";

/**
 * Feature 012 edge case and FR-014: 500 or more rows and amounts of nine digits keep the layout (no horizontal page scroll)
 * and the Spanish euro format, with the whole value still readable. Synthetic data.
 */

const BIG = "123456789.1200";
const BIG_ES = /123\.456\.789,12\s*€/;

const line = (n: number) => ({
  id: `l-${n}`, sku: `SYN-${String(n).padStart(4, "0")}`, product_name: `Producto sintético con un nombre bastante largo número ${n}`, supplier_id: "supp-1", supplier_name: "Proveedor Sintético A", qty: 10,
  unit_cost_with_recargo: BIG, line_total: BIG, risk: "low", confidence: "high", manual_override: false, topup: false, constraints_applied: [],
  explanation: {
    policy: "forecast", forecast_eligible: true, service_level: "95", horizon_days: 14, expected_demand: 8, safety_stock: 2, order_up_to: 12, reorder_point: 5, need: 10, top_up: false,
    clinical_critical: false, position: { on_hand: 0, expiring: 0, usable: 0, inbound: 0, total: 0 }, supplier: { chosen: "supp-1", reason: "lowest_cost", alternatives: [], rejected: [] },
    cost: { unit: BIG, source: "manual", status: "ok" }, constraints: [],
  },
});

test("a proposal with 520 lines and nine-digit amounts pages, formats in euros and does not scroll sideways", async ({ page }) => {
  await signInAs(page, "buyer");
  const summary = { id: "prop-1", week: "2026-W45", status: "draft", version: 3, created_by: "buyer-1", updated_at: "2026-11-04T10:00:00Z" };
  const group = { supplier_id: "supp-1", supplier_name: "Proveedor Sintético A", subtotal: BIG, discount: "0.0000", delivery_charge: "0.0000", total_cost: BIG, expected_delivery_date: null, minimum_status: "ok", free_delivery: false };
  await page.route("**/api/proposals", (r) => r.fulfill(json([summary])));
  await page.route("**/api/proposals/prop-1", (r) => r.fulfill(json({ ...summary, last_edited_by: null, terms_version_ids: null, approval: null, supplier_groups: [group], lines: Array.from({ length: 520 }, (_, i) => line(i + 1)) })));
  for (const width of [1280, 375]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/propuestas");
    await expect(page.getByRole("heading", { level: 3, name: /2026-W45/ })).toBeVisible();
    await expect(page.getByText(BIG_ES).first()).toBeVisible();
    await expect(page.getByText("520", { exact: false }).first()).toBeVisible();   // the row count of the paged list
    await expectNoHorizontalScroll(page);
  }
  // the first page shows 50 lines; the page control reaches the rest
  expect(await page.locator("tbody tr:has(strong)").count()).toBeLessThanOrEqual(60);
});

test("a cost list of 500 rows with nine-digit costs formats in euros and does not scroll sideways", async ({ page }) => {
  await signInAs(page, "buyer");
  const cost = (n: number) => ({ id: `c-${n}`, product_id: n, supplier_id: "supp-1", sku: `SYN-${1000 + n}`, version: 1, cost_net: BIG, cost_with_recargo: BIG, recargo_rate: "0.0520", source: "manual", verified_at: "2026-11-08T10:00:00Z", status: "pending_review" });
  await page.route("**/api/costs", (r) => r.fulfill(json(Array.from({ length: 500 }, (_, i) => cost(i + 1)))));
  await page.route("**/api/cost-writes", (r) => r.fulfill(json([])));
  for (const width of [1280, 375]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/costes");
    await expect(page.getByRole("heading", { level: 1, name: "Costes y proveedores" })).toBeVisible();
    await expect(page.getByText(BIG_ES).first()).toBeVisible();
    await expectNoHorizontalScroll(page);
  }
});
