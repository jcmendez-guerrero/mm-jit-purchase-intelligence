import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

/** T124: KPIs, charts, filters, drill-down, states, keyboard use and accessibility, in Spanish. */

test.describe("Dashboard (T124)", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page);
    await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
    await page.route("**/api/inventory/variants/100", (r) => r.fulfill(json({
      variant: { id: 100, sku: "SYN-100", name: "Variante sintética", pack_size: 1, uom: "u", product: { id: 1 } }, stock: { on_hand: 0, available: 0, reserved: 0, as_of: "2026-11-09" },
      demand: [{ day: "2026-11-01", warehouse_id: 1, qty: 3, censored: false }], flows: [], history: [], history_reconciled: true,
      segment: { abc: "A", xyz: "X", pattern: "smooth", forecast_eligible: true, reasons: [], metrics: {} } })));
  });

  test("shows the KPIs with their basis and the charts with a text summary", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByLabel("Valor del inventario")).toContainText("1.234,50");
    await expect(page.getByLabel("Valor del inventario")).toContainText("A coste de adquisición por lote");
    await expect(page.getByLabel("Cobertura media")).toContainText("5,8 días");
    await expect(page.getByRole("img", { name: /unidades en 60 días/ })).toBeVisible();
    await expect(page.getByText("Solo ventas reales del ERP")).toBeVisible();
  });

  test("a chart can be read as a table with the keyboard", async ({ page }) => {
    await page.goto("/");
    const toggle = page.getByRole("button", { name: "Ver como tabla" }).first();
    await toggle.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("table", { name: "Demanda diaria real" })).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("table", { name: "Demanda diaria real" })).toHaveCount(0);
  });

  test("the product detail says when the forecast rests on imported estimates", async ({ page }) => {
    await page.route("**/api/dashboard/variants/100/forecast-basis", (r) => r.fulfill(json({ run_id: "r1", variant_id: 100, eligible: true, policy: "minmax_poisson", seed_used: true })));
    await page.goto("/");
    await page.getByRole("button", { name: "Ver detalle" }).first().click();
    await expect(page.getByLabel("Detalle de la variante 100")).toContainText("Previsión con datos importados");
  });

  test("a product with no forecast basis shows no estimate label", async ({ page }) => {
    await page.route("**/api/dashboard/variants/100/forecast-basis", (r) => r.fulfill(json({ detail: "no_forecast_run" }, 404)));
    await page.goto("/");
    await page.getByRole("button", { name: "Ver detalle" }).first().click();
    await expect(page.getByLabel("Detalle de la variante 100")).toContainText("Previsión estadística disponible");
    await expect(page.getByLabel("Detalle de la variante 100")).not.toContainText("Previsión con datos importados");
  });

  test("drills down from an alert to the product detail and closes it", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Ver detalle" }).first().click();
    await expect(page.getByLabel("Detalle de la variante 100")).toContainText("SYN-100");
    await expect(page.getByLabel("Detalle de la variante 100")).toContainText("Previsión estadística disponible");
    await page.getByRole("button", { name: "Cerrar detalle" }).click();
    await expect(page.getByLabel("Detalle de la variante 100")).toHaveCount(0);
  });

  test("every KPI and chart opens the products behind it, and a product opens its detail", async ({ page }) => {
    const asked: string[] = [];
    await page.route("**/api/dashboard/drilldown*", (r) => {
      asked.push(new URL(r.request().url()).search);
      const kind = new URL(r.request().url()).searchParams.get("kind");
      const rows = kind === "abc_xyz" ? [] : [{ variant_id: 100, sku: "SYN-100", name: "Variante sintética", figure: kind === "inventory_value" ? "40.00" : kind === "coverage" ? "4.0" : kind === "trend_day" ? "3" : null }];
      return r.fulfill(json({ kind, truncated: kind === "inventory_value", total: kind === "inventory_value" ? 80 : rows.length, rows }));
    });
    await page.goto("/");
    await page.getByLabel("Valor del inventario").getByRole("button", { name: "Ver productos" }).click();
    const panel = page.getByRole("complementary", { name: "Productos que forman el valor del inventario" });
    await expect(panel).toContainText("#100 · Variante sintética (SYN-100)");
    await expect(panel).toContainText("40,00");
    await expect(panel).toContainText("Se muestran 1 de 80 productos.");
    await panel.getByRole("button", { name: /Ver detalle #100/ }).click();
    await expect(page.getByLabel("Detalle de la variante 100")).toBeVisible();
    await page.getByRole("button", { name: "Cerrar detalle" }).click();
    await page.keyboard.press("Escape");
    for (const kpi of ['Cobertura media', 'Variantes con riesgo de rotura', 'Valor que caduca en 60 días']) await page.getByLabel(kpi, { exact: true }).getByRole("button", { name: "Ver productos" }).click();
    expect(asked.some((q) => q.includes("kind=stockout_risk"))).toBe(true);
    expect(asked.some((q) => q.includes("kind=coverage"))).toBe(true);
    await page.getByRole("button", { name: "Ver como tabla" }).nth(1).click();
    await page.getByRole("button", { name: "Ver productos del grupo AX" }).click();
    await expect(page.getByRole("complementary", { name: "Productos del grupo AX" })).toContainText("No hay productos detrás de esta cifra");
    expect(asked.some((q) => q.includes("kind=abc_xyz") && q.includes("abc=A") && q.includes("xyz=X"))).toBe(true);
  });

  test("a trend day opens the products sold that day, with the current filters", async ({ page }) => {
    const asked: string[] = [];
    await page.route("**/api/dashboard/drilldown*", (r) => { asked.push(new URL(r.request().url()).search); return r.fulfill(json({ kind: "trend_day", truncated: false, total: 0, rows: [] })); });
    await page.goto("/");
    await page.getByLabel("Almacén").selectOption("2");
    await page.getByRole("button", { name: "Ver como tabla" }).first().click();
    await page.getByRole("button", { name: /Ver productos del / }).first().click();
    await expect(page.getByRole("complementary", { name: /Productos vendidos el/ })).toBeVisible();
    expect(asked[0]).toMatch(/kind=trend_day&day=2026-10-\d\d&warehouse_id=2/);
  });

  test("the supplier detail shows the terms in force and the proposed spend, read-only", async ({ page }) => {
    await page.unroute("**/api/dashboard/overview*");
    await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview(1, { spend: { ok: true, data: { proposal_id: "p1", week: "2026-W46", status: "draft", total: "300.00", by_supplier: [{ supplier_id: "s1", supplier_name: "Proveedor Sintético A", total: "300.00" }], budget: null, over_budget: false } } }))));
    await page.route("**/api/suppliers/s1/terms", (r) => r.fulfill(json({ supplier_id: "s1", version: 3, history: [], current: { min_order_value: "100.00", min_qty_for_delivery: null, free_delivery_threshold: "250.00", delivery_charge: "12.50", order_days: [], delivery_schedule: null,
      lead_time_days: 4, order_cutoff_time: null, delivery_weekdays: [], discounts: [], payment_terms_days: 30, preferred: true, reliability: null, disabled: false, valid_to: null } })));
    await page.goto("/");
    await page.getByRole("button", { name: "Ver proveedor Proveedor Sintético A" }).click();
    const panel = page.getByRole("complementary", { name: "Proveedor: Proveedor Sintético A" });
    await expect(panel).toContainText("Plazo de entrega (días): 4");
    await expect(panel).toContainText("Pedido mínimo: 100,00");
    await expect(panel).toContainText("Gasto propuesto con este proveedor: 300,00");
    await expect(panel.getByRole("textbox")).toHaveCount(0);
  });

  test("error, empty and stale states are explicit", async ({ page }) => {
    await page.unroute("**/api/dashboard/overview*");
    await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json({}, 500)));
    await page.goto("/");
    await expect(page.getByRole("alert").first()).toBeVisible();
    await page.unroute("**/api/dashboard/overview*");
    const old = overview(0);
    (old.summary.data as { day: string }).day = "2020-01-01";
    await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(old)));
    await page.reload();
    await expect(page.getByText("No se detectaron riesgos de inventario hoy.")).toBeVisible();
    await expect(page.getByText(/puede estar retrasada/)).toBeVisible();
  });

  test("a failing card does not hide the others", async ({ page }) => {
    await page.unroute("**/api/dashboard/overview*");
    await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview(1, { summary: { ok: false, error: "downstream_unavailable" } }))));
    await page.goto("/");
    await expect(page.getByText(/No se pudo cargar este indicador/).first()).toBeVisible();
    await expect(page.getByRole("table", { name: "Tabla de riesgos detectados" })).toBeVisible();
  });

  test("has no serious or critical accessibility violations", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByLabel("Valor del inventario")).toBeVisible();
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
  });
});
