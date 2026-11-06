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

  test("drills down from an alert to the product detail and closes it", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Ver detalle" }).first().click();
    await expect(page.getByLabel("Detalle de la variante 100")).toContainText("SYN-100");
    await expect(page.getByLabel("Detalle de la variante 100")).toContainText("Previsión estadística disponible");
    await page.getByRole("button", { name: "Cerrar detalle" }).click();
    await expect(page.getByLabel("Detalle de la variante 100")).toHaveCount(0);
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
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).disableRules(["color-contrast"]).analyze();
    const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
  });
});
