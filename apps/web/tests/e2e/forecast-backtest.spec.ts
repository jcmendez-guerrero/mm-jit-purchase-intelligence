import { expect, test, type Page } from "@playwright/test";
import { json } from "./dashboard-mock";
import { signInAs } from "./ui-helpers";

/**
 * T058 (feature 018, quickstart scenario 6): start a backtest, see its status and the per-product result against the baseline, with a method that
 * does worse flagged; a second full-catalogue run while one is going is refused in Spanish. The BFF is mocked; synthetic data only.
 */

const result = (over: Record<string, unknown> = {}) => ({
  backtest_run_id: "b1", sku: "EJ-1", periods: 12, wape: "0.500000", bias: "0.250000", baseline_wape: "0.400000", baseline_bias: "0.100000", beats_baseline: false,
  model_version: "minmax_poisson@v1", dataset_version_id: null, config_version_id: null, created_at: "2026-11-15T10:00:00Z", ...over,
});

async function mockBacktest(page: Page, opts: { running?: boolean } = {}) {
  const started: unknown[] = [];
  await page.route("**/api/data-quality/import-errors**", (r) => r.fulfill(json({ items: [] })));
  await page.route(/\/api\/forecast\/products\/EJ-1\/backtest$/, (r) => r.fulfill(json(result())));
  await page.route(/\/api\/forecast\/products\/NOPE\/backtest$/, (r) => r.fulfill(json({ detail: "quality_product_not_found" }, 404)));
  await page.route(/\/api\/forecast\/backtests$/, (r) => {
    const body = r.request().postDataJSON();
    started.push(body);
    if (opts.running && body.scope === "catalogue") return r.fulfill(json({ detail: "forecast_backtest_conflict", running_job_id: "11111111-1111-1111-1111-111111111111" }, 409));
    return r.fulfill(json({ job_id: "j1", status: "completed", reused: false, products: body.scope === "product" ? 1 : 5 }));
  });
  return started;
}

test.describe("backtest", () => {
  test("a buyer starts a product backtest and sees the result with the flag", async ({ page }) => {
    await signInAs(page, "buyer");
    const started = await mockBacktest(page);
    await page.goto("/calidad");
    const section = page.getByRole("region", { name: "Prueba retrospectiva del método" });
    await section.getByLabel("SKU").fill("EJ-1");
    await section.getByRole("button", { name: "Ejecutar la prueba de este producto" }).click();
    await expect(section.getByText("Prueba terminada (1 productos).")).toBeVisible();
    await expect(section.getByText("Periodos evaluados", { exact: true })).toBeVisible();
    await expect(section.getByText("50,0 %")).toBeVisible();
    await expect(section.getByText("40,0 %")).toBeVisible();
    await expect(section.getByText("El método no supera a la referencia en los periodos evaluados.")).toBeVisible();
    expect(started).toEqual([{ scope: "product", sku: "EJ-1" }]);
  });

  test("a second full-catalogue run while one is going is refused in Spanish", async ({ page }) => {
    await signInAs(page, "buyer");
    await mockBacktest(page, { running: true });
    await page.goto("/calidad");
    const section = page.getByRole("region", { name: "Prueba retrospectiva del método" });
    await section.getByRole("button", { name: "Ejecutar la prueba de todo el catálogo" }).click();
    await expect(section.getByText(/Ya hay una prueba retrospectiva del catálogo completo en curso/)).toBeVisible();
  });

  test("a viewer can read a result but cannot start a run", async ({ page }) => {
    await signInAs(page, "viewer");
    await mockBacktest(page);
    await page.goto("/calidad");
    const section = page.getByRole("region", { name: "Prueba retrospectiva del método" });
    await section.getByLabel("SKU").fill("EJ-1");
    await section.getByRole("button", { name: "Ver resultado" }).click();
    await expect(section.getByText("Periodos evaluados", { exact: true })).toBeVisible();
    await expect(section.getByRole("button", { name: /Ejecutar la prueba/ })).toHaveCount(0);
  });

  test("an unknown SKU shows a Spanish error", async ({ page }) => {
    await signInAs(page, "buyer");
    await mockBacktest(page);
    await page.goto("/calidad");
    const section = page.getByRole("region", { name: "Prueba retrospectiva del método" });
    await section.getByLabel("SKU").fill("NOPE");
    await section.getByRole("button", { name: "Ver resultado" }).click();
    await expect(section.getByText("No se encuentra el producto o todavía no tiene datos de calidad.")).toBeVisible();
  });
});
