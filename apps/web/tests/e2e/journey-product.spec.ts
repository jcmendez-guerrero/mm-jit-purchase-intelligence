import { expect, test, type Page } from "@playwright/test";
import { json, overview } from "./dashboard-mock";
import { signInAs } from "./ui-helpers";

/**
 * Feature 012, user story 2: dashboard signal -> product detail by SKU -> proposal lines of that product -> back to the
 * same product, with the SKU shown throughout and never the Siweb variant id. Buyer role, keyboard operable. Synthetic data.
 */

const line = (id: string, sku: string, name: string) => ({
  id, sku, product_name: name, supplier_id: "supp-1", supplier_name: "Proveedor Sintético A", qty: 10,
  unit_cost_with_recargo: "5.2600", line_total: "52.6000", risk: "low", confidence: "high", manual_override: false, topup: false, constraints_applied: [],
  explanation: {
    policy: "forecast", forecast_eligible: true, service_level: "95", horizon_days: 14, expected_demand: 8, safety_stock: 2, order_up_to: 12, reorder_point: 5, need: 10, top_up: false,
    clinical_critical: false, position: { on_hand: 0, expiring: 0, usable: 0, inbound: 0, total: 0 }, supplier: { chosen: "supp-1", reason: "lowest_cost", alternatives: [], rejected: [] },
    cost: { unit: "5.2600", source: "manual", status: "ok" }, constraints: [],
  },
});

async function mock(page: Page, variant: Record<string, unknown>) {
  await page.route("**/api/dashboard/overview**", (r) => r.fulfill(json(overview(3))));
  await page.route("**/api/inventory/skus/SYN-100", (r) => r.fulfill(json(variant)));
  await page.route("**/api/dashboard/skus/SYN-100/forecast-basis", (r) => r.fulfill(json({ detail: "no_forecast_run" }, 404)));
  const summary = { id: "prop-1", week: "2026-W45", status: "draft", version: 3, created_by: "buyer-1", updated_at: "2026-11-04T10:00:00Z" };
  await page.route("**/api/proposals", (r) => r.fulfill(json([summary])));
  await page.route("**/api/proposals/prop-1", (r) => r.fulfill(json({ ...summary, last_edited_by: null, terms_version_ids: null, approval: null, supplier_groups: [], lines: [line("l-1", "SYN-100", "Variante sintética"), line("l-2", "SYN-200", "Otro producto")] })));
}

const variant = (over: Record<string, unknown> = {}) => ({
  variant: { sku: "SYN-100", name: "Variante sintética", pack_size: 1, uom: "u", product: { status: "active" } }, stock: { on_hand: 0, available: 0, reserved: 0, as_of: "2026-11-09" },
  demand: [], flows: [], history: [], history_reconciled: true, segment: { abc: "A", xyz: "X", pattern: "smooth", forecast_eligible: true, reasons: [], metrics: {} }, ...over,
});

test("from a product at risk to its proposal lines and back to the same product, by SKU", async ({ page }) => {
  await signInAs(page, "buyer");
  await mock(page, variant());
  await page.goto("/panel");
  await page.getByRole("button", { name: /Ver detalle/ }).first().focus();
  await page.keyboard.press("Enter");

  const detail = page.getByLabel("Detalle del producto");
  await expect(detail.getByRole("heading", { level: 3 })).toHaveText("Detalle del producto · SYN-100 · Variante sintética");
  await expect(detail).not.toContainText(/variante 100/i);
  await expect(page).toHaveURL(/producto=SYN-100/);

  await detail.getByRole("link", { name: "Ver en propuestas de compra" }).click();
  await expect(page).toHaveURL(/\/propuestas\?sku=SYN-100&volver=SYN-100/);
  await expect(page.getByRole("status").filter({ hasText: "Mostrando solo las líneas del producto SYN-100." })).toBeVisible();
  await expect(page.getByRole("table", { name: /líneas|Líneas/ }).or(page.locator("tbody")).first()).toBeVisible();
  await expect(page.getByText("SYN-100", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("SYN-200")).toHaveCount(0);

  await page.getByRole("link", { name: "Volver al producto" }).click();
  await expect(page).toHaveURL(/\/panel\?producto=SYN-100/);
  await expect(page.getByLabel("Detalle del producto").getByRole("heading", { level: 3 })).toHaveText("Detalle del producto · SYN-100 · Variante sintética");
});

test("the filter can be removed and the browser back button returns to the product", async ({ page }) => {
  await signInAs(page, "buyer");
  await mock(page, variant());
  await page.goto("/panel?producto=SYN-100");
  await page.getByLabel("Detalle del producto").getByRole("link", { name: "Ver en propuestas de compra" }).click();
  await expect(page.getByText("SYN-200")).toHaveCount(0);
  await page.getByRole("button", { name: "Ver todas las líneas" }).click();
  await expect(page.getByText("SYN-200").first()).toBeVisible();
  await page.goBack();
  await expect(page.getByLabel("Detalle del producto")).toBeVisible();
});

test("a product with missing data says what is missing instead of showing a blank", async ({ page }) => {
  await signInAs(page, "buyer");
  await mock(page, variant({ stock: null, segment: null, demand: [] }));
  await page.goto("/panel?producto=SYN-100");
  const detail = page.getByLabel("Detalle del producto");
  await expect(detail).toContainText("Todavía no hay previsión para este producto.");
  await expect(detail).toContainText("Sin ventas en el periodo.");
  await expect(detail).toContainText("Todavía no hay historial de categoría.");
});

test("a SKU with no lines in the proposal explains it", async ({ page }) => {
  await signInAs(page, "buyer");
  await mock(page, variant());
  await page.goto("/propuestas?sku=SYN-999");
  await expect(page.getByText("El producto SYN-999 no tiene líneas en esta propuesta.")).toBeVisible();
});

test("opening and closing the product detail add no history entry: Back leaves the panel", async ({ page }) => {
  await signInAs(page, "buyer");
  await mock(page, variant());
  await page.goto("/calidad");
  await page.goto("/panel");
  await page.getByRole("button", { name: /Ver detalle/ }).first().click();
  await expect(page).toHaveURL(/producto=SYN-100/);
  await page.getByRole("button", { name: "Cerrar detalle" }).click();
  await expect(page).not.toHaveURL(/producto=/);
  await page.goBack();
  await expect(page).toHaveURL(/\/calidad$/);
});
