import { expect, test } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

/**
 * T125 / T083: the screen shows its first meaningful content within 2 seconds (SC-005) for a payload of about
 * 1,000 variants, and the layout does not visibly shift when the data arrives. This measures the browser side; the
 * services are timed in their own suites.
 */

const BUDGET_MS = 2000;
const MAX_LAYOUT_SHIFT = 0.1; // the usual "good" threshold for cumulative layout shift

test("first meaningful content is visible within 2 seconds with 1,000 alerts, without layout shift", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview(1000))));
  await page.addInitScript(() => {
    (window as unknown as { __cls: number }).__cls = 0;
    new PerformanceObserver((list) => {
      for (const e of list.getEntries() as unknown as Array<{ value: number; hadRecentInput: boolean }>) {
        if (!e.hadRecentInput) (window as unknown as { __cls: number }).__cls += e.value;
      }
    }).observe({ type: "layout-shift", buffered: true });
  });
  const t0 = Date.now();
  await page.goto("/");
  await expect(page.getByLabel("Valor del stock")).toContainText("1.234,50");
  await expect(page.getByRole("table", { name: "Tabla de riesgos detectados" })).toBeVisible();
  const elapsed = Date.now() - t0;
  await page.waitForTimeout(500); // let late shifts happen
  const cls = await page.evaluate(() => (window as unknown as { __cls: number }).__cls);
  console.log(`dashboard first meaningful content: ${elapsed} ms, cumulative layout shift ${cls.toFixed(3)}`);
  expect(elapsed).toBeLessThan(BUDGET_MS);
  expect(cls).toBeLessThan(MAX_LAYOUT_SHIFT);
});

test("when the data arrives after a delay the page does not jump (the skeleton has the final shape)", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/dashboard/overview*", async (r) => {
    await new Promise((res) => setTimeout(res, 800));
    return r.fulfill(json(overview(3)));
  });
  await page.addInitScript(() => {
    (window as unknown as { __cls: number }).__cls = 0;
    new PerformanceObserver((list) => {
      for (const e of list.getEntries() as unknown as Array<{ value: number; hadRecentInput: boolean }>) {
        if (!e.hadRecentInput) (window as unknown as { __cls: number }).__cls += e.value;
      }
    }).observe({ type: "layout-shift", buffered: true });
  });
  await page.goto("/");
  await expect(page.getByRole("status", { name: "Cargando datos" })).toBeVisible();
  await expect(page.getByLabel("Valor del stock")).toBeVisible({ timeout: 5000 });
  await page.waitForTimeout(500);
  const cls = await page.evaluate(() => (window as unknown as { __cls: number }).__cls);
  console.log(`layout shift when data arrives after a delay: ${cls.toFixed(3)}`);
  expect(cls).toBeLessThan(MAX_LAYOUT_SHIFT);
});
