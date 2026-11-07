import { expect, test, type Page } from "@playwright/test";

/** T141: the scenario builder in Spanish: compute, compare, explain, promote. The backend is a small in-test store. */

const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });

const SUMMARY = {
  baseline: { total: "1000.0000", over_budget: "0.0000", lines: 4 },
  scenario: { total: "1100.0000", over_budget: "0.0000", lines: 4, budget: "1200.0000", utilisation: "0.9167" },
  delta_total: "100.0000",
  changes: [{ variant_id: 9001, supplier_before: "s1", supplier_after: "s2", qty_before: 12, qty_after: 12, reasons: ["supplier_disabled"] }],
  binding: [{ key: "min_order:s2", params: { status: "topped_up" } }],
  infeasible: null,
  notes: [],
};
const DETAIL = {
  id: "sc1", name: "Sin proveedor A", status: "ready", parameters: {}, result_hash: "h", input_versions: { dataset: "12345678-0000-4000-8000-000000000000", forecast_run: "abcdef12-0000-4000-8000-000000000000" }, created_by: "buyer-1", created_at: "2026-11-09T08:00:00Z", summary: SUMMARY,
  results: [{ supplier_id: "s2", supplier_name: "Proveedor B", order_total: "102.5000", subtotal: "108.00", delivery_charge: "4.50", discount: "10.00", free_delivery: false, expected_delivery: "2026-11-16", budget_utilisation: "0.9167", lines: [{ variant_id: 9001, qty: 12, unit_cost: "5.0000", line_total: "60.0000", clinical_critical: true }, { variant_id: 9002, qty: 6, unit_cost: "8.0000", line_total: "48.0000", clinical_critical: false }] }],
  sensitivity: [{ constraint_key: "budget", delta: "100.0000", cost_impact: "-20.0000" }],
};

async function backend(page: Page, roles: string[]) {
  const state = { created: [] as Array<{ body: unknown; key: string | undefined }>, promoted: 0, status: "ready" };
  await page.route("**/api/me", (r) => r.fulfill(json({ user_id: "buyer-1", roles, mfa_auth_time: new Date().toISOString(), csrf_token: "csrf" })));
  await page.route("**/api/dashboard/risk*", (r) => r.fulfill(json([])));
  await page.route("**/api/suppliers", (r) => r.fulfill(json([{ id: "s1", name: "Proveedor A" }, { id: "s2", name: "Proveedor B" }])));
  await page.route("**/api/scenarios", (r) => {
    if (r.request().method() === "GET") return r.fulfill(json({ scenarios: state.created.length ? [{ id: "sc1", name: "Sin proveedor A", status: state.status, created_by: "buyer-1", created_at: "2026-11-09T08:00:00Z", delta_total: "100.0000" }] : [] }));
    state.created.push({ body: r.request().postDataJSON(), key: r.request().headers()["idempotency-key"] });
    return r.fulfill(json(DETAIL, 201));
  });
  await page.route("**/api/scenarios/sc1", (r) => r.fulfill(json({ ...DETAIL, status: state.status })));
  await page.route("**/api/scenarios/sc1/promote", (r) => {
    state.promoted += 1;
    state.status = "promoted";
    return r.fulfill(json({ proposal_id: "p1", week: "2026-11-09", superseded: [] }));
  });
  return state;
}

const open = async (page: Page) => {
  await page.goto("/");
  await page.click("button:has-text('Escenarios')");
};

test.describe("Purchasing scenarios (T141)", () => {
  test("a buyer computes a scenario, reads the comparison and promotes it", async ({ page }) => {
    const state = await backend(page, ["viewer", "buyer"]);
    await open(page);
    await page.getByLabel("Nombre del escenario").fill("Sin proveedor A");
    await page.getByLabel("Presupuesto semanal (€)").fill("1200,00");
    await page.getByRole("group", { name: "Proveedor A" }).getByLabel("No usar este proveedor").check();
    await page.click("button:has-text('Calcular escenario')");
    await expect(page.getByRole("heading", { name: /Sin proveedor A — Listo/ })).toBeVisible();
    expect(state.created[0]?.key).toBeTruthy();
    expect(state.created[0]?.body).toMatchObject({ budget: "1200.00", disabled_suppliers: ["s1"] });
    await expect(page.getByLabel("Datos usados")).toContainText("ejecución de previsión abcdef12 · conjunto de datos importados 12345678");
    await expect(page.getByText("Diferencia de coste: 100,00 €")).toBeVisible();
    await expect(page.getByText(/Variante 9001: Proveedor A \(12\) → Proveedor B \(12\) — proveedor desactivado/)).toBeVisible();
    await expect(page.getByText(/Pedido mínimo de Proveedor B \(completado para llegar\)/)).toBeVisible();
    await expect(page.getByRole("row", { name: /Uso del presupuesto.*91,7\s?%/ }).first()).toBeVisible();      // a fraction from the service, shown as a percentage
    const group = page.getByRole("region", { name: "Pedido a Proveedor B" });
    await expect(group.getByRole("row", { name: /#9001 · clínicamente crítico\s+12\s+5,00 €\s+60,00 €/ })).toBeVisible();
    await expect(group).toContainText("Importe de las líneas: 108,00 €");
    await expect(group).toContainText("Gastos de envío: 4,50 €");
    await expect(group).toContainText("Descuento: 10,00 €");
    await expect(group).toContainText("Total del pedido: 102,50 €");
    await expect(group).toContainText("Entrega prevista: 16/11/2026");
    await page.click("button:has-text('Convertir en propuesta')");
    await expect(page.getByText(/Propuesta creada como borrador para la semana 2026-11-09/)).toBeVisible();
    expect(state.promoted).toBe(1);
    await expect(page.getByRole("link", { name: "Exportar CSV" })).toHaveAttribute("href", /scenarios\/sc1\/export\?format=csv/);
  });

  test("invalid values are named and nothing is sent", async ({ page }) => {
    const state = await backend(page, ["viewer", "buyer"]);
    await open(page);
    await page.getByLabel("Nombre del escenario").fill("x");
    await page.getByLabel("Presupuesto semanal (€)").fill("abc");
    await page.click("button:has-text('Calcular escenario')");
    await expect(page.getByRole("alert")).toContainText("Presupuesto");
    expect(state.created).toHaveLength(0);
  });

  test("a viewer can read but not create", async ({ page }) => {
    await backend(page, ["viewer"]);
    await open(page);
    await expect(page.getByText(/crear escenarios requiere el rol de comprador/)).toBeVisible();
    await expect(page.getByLabel("Nombre del escenario")).toHaveCount(0);
  });
});
