import { expect, test, type Page } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

/**
 * T048 (feature 012, quickstart scenario 5): a forecast shows its range and a confidence label; a low-confidence line is flagged, shows
 * the fallback and no figure, and says why. The BFF is mocked; synthetic data only.
 */

const summary = { id: "prop-1", week: "2026-W45", status: "draft", version: 3, created_by: "buyer-1", updated_at: "2026-11-04T10:00:00Z" };

const line = (id: string, sku: string, eligible: boolean) => ({
  id, variant_id: 1, sku, product_name: `Producto ${sku}`, supplier_id: "s1", supplier_name: "Proveedor Sintético A", qty: 10, unit_cost_with_recargo: "10.0000", line_total: "100.0000",
  risk: "low", confidence: "high", manual_override: false, topup: false, constraints_applied: [],
  explanation: {
    policy: eligible ? "forecast" : "minmax", forecast_eligible: eligible, service_level: "95", horizon_days: 14, expected_demand: 8, safety_stock: 2, order_up_to: 12, reorder_point: 5, need: 10, top_up: false,
    clinical_critical: false, position: { on_hand: 0, expiring: 0, usable: 0, inbound: 0, total: 0 }, supplier: { chosen: "s1", reason: "lower_total_with_supplier_terms", alternatives: [], rejected: [] },
    cost: { unit: "10.0000", source: "manual", status: "ok" }, constraints: [],
  },
});

const explanation = (sku: string, over: Record<string, unknown> = {}) => ({
  run_id: "r1", sku, model_version: "minmax_poisson@v1", dataset_version_id: null, config_version_id: "defaults-abc", history_start: "2026-01-01", history_end: "2026-06-01", abc: "A", xyz: "X",
  pattern: "smooth", intermittent: false, method: "minmax_poisson", method_reason_code: "backtest_adopted", censored_days: 4, anomaly_days_excluded: 0,
  provenance_mix: { observed: 148, estimated: 0, manual: 0 }, low: "8.0000", expected: "12.5000", high: "19.5000", confidence: "alta", confidence_reason_codes: [], eligibility: "eligible",
  eligibility_reason_codes: [], ...over,
});

async function openProposals(page: Page) {
  await signIn(page, ["viewer", "buyer"]);
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
  await page.route("**/api/proposals", (r) => r.fulfill(json([summary])));
  await page.route("**/api/proposals/prop-1", (r) => r.fulfill(json({
    ...summary, last_edited_by: null, terms_version_ids: null, approval: null,
    supplier_groups: [{ supplier_id: "s1", supplier_name: "Proveedor Sintético A", subtotal: "200.0000", discount: "0.0000", delivery_charge: "0.0000", total_cost: "200.0000", expected_delivery_date: "2026-11-12", minimum_status: "met", free_delivery: false }],
    lines: [line("l1", "EJ-9101", true), line("l2", "EJ-200", false)],
  })));
  await page.route(/\/api\/forecast\/products\/EJ-9101\/explanation$/, (r) => r.fulfill(json(explanation("EJ-9101", { confidence: "media", confidence_reason_codes: ["short_history"] }))));
  await page.route(/\/api\/forecast\/products\/EJ-200\/explanation$/, (r) => r.fulfill(json(explanation("EJ-200", {
    eligibility: "manual_review_only", eligibility_reason_codes: ["low_confidence"], low: null, expected: null, high: null, confidence: "baja",
    confidence_reason_codes: ["short_history", "sparse_sales", "high_variability"], method: "minmax_conservative", method_reason_code: "min_max_fallback", pattern: "intermittent", intermittent: true,
  }))));
  await page.goto("/");
  await page.getByRole("navigation").getByRole("link", { name: "Propuestas de compra", exact: true }).click();
}

test.describe("forecast uncertainty", () => {
  test("a forecast shows its range and its confidence with the reasons", async ({ page }) => {
    await openProposals(page);
    await page.getByRole("button", { name: "Ver justificación" }).first().click();
    await page.getByRole("button", { name: "Ver explicación detallada" }).first().click();
    const panel = page.getByRole("region", { name: "Explicación de la previsión" });
    await expect(panel).toContainText("8,0 – 19,5");
    await expect(panel).toContainText("Confianza media");
    await expect(panel).toContainText("historial corto");
    await expect(panel).not.toContainText("Confianza baja: la línea no se sugiere");
  });

  test("a low-confidence line is flagged, shows the fallback and no figure, and says why", async ({ page }) => {
    await openProposals(page);
    await page.getByRole("button", { name: "Ver justificación" }).nth(1).click();
    await expect(page.getByText("No es una previsión").first()).toBeVisible();
    await page.getByRole("button", { name: "Ver explicación detallada" }).click();
    const panel = page.getByRole("region", { name: "Explicación de la previsión" });
    await expect(panel).toContainText("Confianza baja: la línea no se sugiere automáticamente");
    await expect(panel).toContainText("Solo revisión manual");
    await expect(panel).toContainText("historial corto, ventas escasas, demanda muy variable");
    await expect(panel).toContainText("mínimo y un máximo prudentes");
    await expect(panel).not.toContainText("Demanda esperada");
    await expect(panel).not.toContainText("Rango");
  });
});
