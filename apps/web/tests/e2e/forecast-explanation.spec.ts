import { expect, test, type Page } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

/**
 * T040 (feature 012, quickstart scenarios 3 and 4, SC-003): from a proposal line the buyer reaches the explanation of its forecast in two clicks,
 * in Spanish. A product with no forecast shows the fallback, no figure and the "not a forecast" label. The BFF is mocked; synthetic data only.
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
  run_id: "r1", sku, model_version: "minmax_poisson@v1", dataset_version_id: null, config_version_id: "defaults-abc", history_start: "2026-01-01", history_end: "2026-03-01", abc: "A", xyz: "X",
  pattern: "smooth", intermittent: false, method: "minmax_poisson", method_reason_code: "backtest_adopted", censored_days: 16, anomaly_days_excluded: 2,
  provenance_mix: { observed: 70, estimated: 30, manual: 0 }, low: null, expected: "12.5000", high: null, confidence: null, confidence_reason_codes: [], eligibility: "eligible",
  eligibility_reason_codes: [], ...over,
});

async function openProposals(page: Page) {
  await signIn(page, ["viewer", "buyer"]);
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
  await page.route("**/api/proposals", (r) => r.fulfill(json([summary])));
  await page.route("**/api/proposals/prop-1", (r) => r.fulfill(json({
    ...summary, last_edited_by: null, terms_version_ids: null, approval: null,
    supplier_groups: [{ supplier_id: "s1", supplier_name: "Proveedor Sintético A", subtotal: "200.0000", discount: "0.0000", delivery_charge: "0.0000", total_cost: "200.0000", expected_delivery_date: "2026-11-12", minimum_status: "met", free_delivery: false }],
    lines: [line("l1", "EJ-9101", true), line("l2", "EJ-100", false)],
  })));
  await page.route(/\/api\/forecast\/products\/EJ-9101\/explanation$/, (r) => r.fulfill(json(explanation("EJ-9101"))));
  await page.route(/\/api\/forecast\/products\/EJ-100\/explanation$/, (r) => r.fulfill(json(explanation("EJ-100", {
    eligibility: "not_eligible", eligibility_reason_codes: ["new"], expected: null, method: "minmax_conservative", method_reason_code: "min_max_fallback", pattern: "new", abc: "C", xyz: "Z",
  }))));
  await page.goto("/");
  await page.getByRole("navigation").getByRole("link", { name: "Propuestas de compra", exact: true }).click();
}

test.describe("forecast explanation from a proposal line", () => {
  test("shows versions, class, method and why, and the data origin, in two clicks", async ({ page }) => {
    await openProposals(page);
    const started = Date.now();
    await page.getByRole("button", { name: "Ver justificación" }).first().click();
    await page.getByRole("button", { name: "Ver explicación detallada" }).first().click();
    const panel = page.getByRole("region", { name: "Explicación de la previsión" });
    await expect(panel).toContainText("minmax_poisson@v1");
    await expect(panel).toContainText("Configuración de clases: defaults-abc");
    await expect(panel).toContainText("Del 01/01/2026 al 01/03/2026");
    await expect(panel).toContainText("AX · Demanda regular");
    await expect(panel).toContainText("menor coste en la prueba retrospectiva");
    await expect(panel).toContainText("Observado (ERP): 70; Estimado: 30");
    await expect(panel).toContainText("Días sin existencias que no se usan para aprender: 16");
    expect(Date.now() - started).toBeLessThan(60_000);
  });

  test("a product with no forecast shows the fallback and the not-a-forecast label, and no figure", async ({ page }) => {
    await openProposals(page);
    await page.getByRole("button", { name: "Ver justificación" }).nth(1).click();
    await expect(page.getByText("No es una previsión").first()).toBeVisible();
    await page.getByRole("button", { name: "Ver explicación detallada" }).click();
    const panel = page.getByRole("region", { name: "Explicación de la previsión" });
    await expect(panel).toContainText("Producto nuevo con poco historial");
    await expect(panel).toContainText("mínimo y un máximo prudentes");
    await expect(panel).not.toContainText("Demanda esperada");
  });

  test("closing the detail hides it again", async ({ page }) => {
    await openProposals(page);
    await page.getByRole("button", { name: "Ver justificación" }).first().click();
    await page.getByRole("button", { name: "Ver explicación detallada" }).click();
    await expect(page.getByRole("region", { name: "Explicación de la previsión" })).toBeVisible();
    await page.getByRole("button", { name: "Ocultar explicación detallada" }).click();
    await expect(page.getByRole("region", { name: "Explicación de la previsión" })).toHaveCount(0);
  });
});
