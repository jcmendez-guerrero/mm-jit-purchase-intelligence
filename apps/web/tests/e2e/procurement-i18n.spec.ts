import { expect, test } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

/** T036 (FR-015, SC-007): the proposal screen is Spanish, amounts are EUR in Spanish format, dates are dd/mm/aaaa, and a viewer gets no export. */

const summary = { id: "prop-12345678", week: "2026-W45", status: "approved", version: 3, created_by: "buyer-1", updated_at: "2026-11-04T10:00:00Z" };
const group = { supplier_id: "s1", supplier_name: "Proveedor Sintético A", subtotal: "1234.5000", discount: "0.0000", delivery_charge: "9.0000", total_cost: "1243.5000", expected_delivery_date: "2026-11-12", minimum_status: "met", free_delivery: false };

test("the proposal screen is Spanish with EUR and Spanish dates, and a viewer sees no export", async ({ page }) => {
  await signIn(page, ["viewer"]);
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
  await page.route("**/api/proposals", (r) => r.fulfill(json([summary])));
  await page.route("**/api/proposals/prop-12345678", (r) =>
    r.fulfill(json({ ...summary, last_edited_by: null, terms_version_ids: null, approval: null, supplier_groups: [group], lines: [], review_notes: [] })),
  );
  await page.goto("/");
  await page.getByRole("navigation").getByRole("link", { name: "Propuestas de compra", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Propuestas de compra" })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", /^es/);
  const body = page.getByRole("region").first();
  await expect(page.getByText("1.234,50", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("12/11/2026", { exact: false }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: /Exportar/ })).toHaveCount(0);
  await expect(body).not.toContainText(/\b(Submit|Approve|Export|Supplier|Total cost)\b/);
});
