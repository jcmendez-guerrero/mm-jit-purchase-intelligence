import { expect, test } from "@playwright/test";
import { freshness, indicators, json, overview, signIn, today } from "./dashboard-mock";

/** T055 (US6): the user can tell how far to trust the figures: stale data, a failed figure with a retry, what was left out and where to review it, local loads kept apart, newer data on offer. The services are simulated. */

const staleSources = () => freshness({}, "2026-10-01T08:00:00Z").sources.map((s) => ({ ...s, state: "stale" }));

test.describe("Dashboard trust", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page);
  });

  test("a stale source shows a prominent alert with the last refresh, and each card says when it was updated", async ({ page }) => {
    await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview(1, { indicators: indicators().map((i) => (i.key === "stock_value" ? { ...i, state: "stale" } : i)) }))));
    await page.route("**/api/dashboard/freshness*", (r) => r.fulfill(json({ ...freshness(), sources: staleSources() })));
    await page.goto("/panel");
    await expect(page.getByRole("alert").filter({ hasText: "Los datos están desactualizados" })).toBeVisible();
    const card = page.getByRole("heading", { name: "Valor del stock" }).locator("xpath=ancestor::article");
    await expect(card).toContainText("Datos desactualizados");
    await expect(card).toContainText("Actualizado:");
    await expect(card).toContainText("Origen: ERP");
  });

  test("a figure that could not be calculated says so, offers a retry, and the other cards stay correct", async ({ page }) => {
    let calls = 0;
    await page.route("**/api/dashboard/overview*", (r) => {
      calls += 1;
      const failed = calls === 1;
      return r.fulfill(json(overview(1, { indicators: indicators().map((i) => (failed && i.key === "stock_value" ? { ...i, state: "error", value: null } : i)) })));
    });
    await page.goto("/panel");
    const card = page.getByRole("heading", { name: "Valor del stock" }).locator("xpath=ancestor::article");
    await expect(card.getByRole("alert")).toHaveText("No se pudo calcular");
    await expect(page.getByRole("heading", { name: "Cobertura" }).locator("xpath=ancestor::article")).toContainText("5,8");   // another card is untouched
    await card.getByRole("button", { name: "Reintentar" }).click();
    await expect(card.getByRole("alert")).toHaveCount(0);
    expect(calls).toBe(2);
  });

  test("records left out of the figures are counted and linked to the review list; local loads are kept apart and counted", async ({ page }) => {
    await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
    await page.route("**/api/dashboard/freshness*", (r) => r.fulfill(json(freshness({ excluded_records: 3, local_load_excluded: 2 }))));
    await page.goto("/panel");
    await expect(page.getByText(/3 registros se han dejado fuera de las cifras/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Revisarlos" })).toHaveAttribute("href", "/calidad");
    await expect(page.getByText("2 productos de carga local no se suman a las cifras del ERP.")).toBeVisible();
  });

  test("a failing source shows the card as unavailable with a retry, never as a zero", async ({ page }) => {
    await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview(1, { abc_xyz: { ok: false, error: "downstream_unavailable" } }))));
    await page.goto("/panel");
    await expect(page.getByRole("alert").filter({ hasText: "No se pudo cargar este indicador" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Reintentar" }).first()).toBeVisible();
  });

  test("newer data is offered without changing the figures, and loads only when the user accepts", async ({ page }) => {
    await page.clock.install();
    let overviewCalls = 0;
    let newData = false;                                         // the test decides when newer data exists, not the number of polls (dev and production builds poll a different number of times)
    await page.route("**/api/dashboard/overview*", (r) => {
      overviewCalls += 1;
      return r.fulfill(json(overview(1, { indicators: indicators().map((i) => (i.key === "demand" ? { ...i, value: overviewCalls === 1 ? "239" : "301" } : i)) })));
    });
    await page.route("**/api/dashboard/freshness*", (r) => {
      return r.fulfill(json(freshness({}, newData ? `${today}T09:00:00Z` : `${today}T08:00:00Z`)));
    });
    await page.goto("/panel");
    const demand = page.getByRole("heading", { name: "Demanda" }).locator("xpath=ancestor::article");
    await expect(demand).toContainText("239");
    await page.clock.fastForward(60_000);
    await expect(page.getByRole("status").filter({ hasText: "Hay datos más recientes" })).toHaveCount(0);       // a poll that finds the same data offers nothing
    newData = true;
    await page.clock.fastForward(60_000);
    await expect(page.getByRole("status").filter({ hasText: "Hay datos más recientes" })).toBeVisible();
    await expect(demand).toContainText("239");                                                                  // the figure did not change by itself
    expect(overviewCalls).toBe(1);
    await page.getByRole("button", { name: "Actualizar datos" }).click();
    await expect(demand).toContainText("301");
    await expect(page.getByRole("status").filter({ hasText: "Hay datos más recientes" })).toHaveCount(0);
  });
});
