import { expect, test, type Page } from "@playwright/test";
import { json } from "./dashboard-mock";
import { signInAs } from "./ui-helpers";

/**
 * T065 (feature 012, quickstart scenario 7): the catalogue overview shows counts by class, eligibility and confidence; every count opens its list;
 * a filter narrows both. Read-only, so a viewer sees it. The BFF is mocked; synthetic data only.
 */

const bucket = (key: string, count: number, kind: string) => ({ key, count, drilldown: `bucket=${kind}&key=${key}` });
const overview = (active: number, pending: number) => ({
  filters: { category: null, supplier: null }, active_products: active,
  by_class: [bucket("AX", active - 1, "class"), bucket("sin_clasificar", 1, "class")],
  by_eligibility: [bucket("eligible", active - pending, "eligibility"), bucket("manual_review_only", 0, "eligibility"), bucket("not_eligible", 0, "eligibility"), bucket("pending", pending, "eligibility")],
  by_confidence: [bucket("alta", active - pending, "confidence"), bucket("media", 0, "confidence"), bucket("baja", 0, "confidence"), bucket("none", pending, "confidence")],
  worst_quality: [{ sku: "EJ-9103", coverage_ratio: "0.866667", rejected_share: "0.050000", anomaly_share: null }],
});

async function mockPortfolio(page: Page) {
  const seen: string[] = [];
  await page.route("**/api/data-quality/import-errors**", (r) => r.fulfill(json({ items: [] })));
  await page.route(/\/api\/quality\/portfolio(\?.*)?$/, (r) => {
    const url = new URL(r.request().url());
    seen.push(url.search);
    return r.fulfill(json(url.searchParams.get("category") === "A" ? overview(3, 1) : overview(7, 3)));
  });
  await page.route(/\/api\/quality\/portfolio\/products\?/, (r) => {
    const url = new URL(r.request().url());
    seen.push(url.search);
    const narrowed = url.searchParams.get("category") === "A";
    return r.fulfill(json({ bucket: url.searchParams.get("bucket"), key: url.searchParams.get("key"), total: narrowed ? 1 : 3, skus: narrowed ? ["EJ-9105"] : ["EJ-9105", "EJ-9106", "EJ-9107"] }));
  });
  return seen;
}

test.describe("catalogue quality overview", () => {
  test("a viewer sees the counts and opens the list behind one", async ({ page }) => {
    await signInAs(page, "viewer");
    await mockPortfolio(page);
    await page.goto("/calidad");
    const section = page.getByRole("region", { name: "Resumen de calidad del catálogo" });
    await section.getByRole("button", { name: "Ver resumen" }).click();
    await expect(section.getByText("Productos activos: 7")).toBeVisible();
    await expect(section.getByRole("button", { name: "3 productos: ver la lista de Pendiente de previsión" })).toBeVisible();
    await expect(section.getByRole("button", { name: "4 productos: ver la lista de Apto para previsión estadística" })).toBeVisible();
    await section.getByRole("button", { name: "3 productos: ver la lista de Pendiente de previsión" }).click();
    const list = section.getByRole("region", { name: "Productos de «Pendiente de previsión»" });
    await expect(list.getByText("EJ-9106")).toBeVisible();
    await expect(list.getByText("Mostrando 1–3 de 3")).toBeVisible();
    await expect(section.getByText("EJ-9103")).toBeVisible();
  });

  test("a filter narrows the counts and is applied to the list too", async ({ page }) => {
    await signInAs(page, "buyer");
    const seen = await mockPortfolio(page);
    await page.goto("/calidad");
    const section = page.getByRole("region", { name: "Resumen de calidad del catálogo" });
    await section.getByLabel("Categoría").selectOption("A");
    await section.getByRole("button", { name: "Ver resumen" }).click();
    await expect(section.getByText("Productos activos: 3")).toBeVisible();
    await section.getByRole("button", { name: "1 productos: ver la lista de Pendiente de previsión" }).click();
    await expect(section.getByText("Mostrando 1–1 de 1")).toBeVisible();
    expect(seen.some((q) => q.includes("category=A") && q.includes("bucket=eligibility") && q.includes("key=pending"))).toBe(true);
  });

  test("a group with no products offers no list", async ({ page }) => {
    await signInAs(page, "viewer");
    await mockPortfolio(page);
    await page.goto("/calidad");
    const section = page.getByRole("region", { name: "Resumen de calidad del catálogo" });
    await section.getByRole("button", { name: "Ver resumen" }).click();
    await expect(section.getByRole("button", { name: "0 productos: ver la lista de Solo revisión manual" })).toBeDisabled();
  });

  test("the origin selector shows the locally loaded products apart from the ERP ones", async ({ page }) => {
    await signInAs(page, "buyer");
    const seen = await mockPortfolio(page);
    await page.route(/\/api\/quality\/portfolio(\?.*)?$/, (r) => {
      const url = new URL(r.request().url());
      seen.push(url.search);
      return r.fulfill(json(url.searchParams.get("origin") === "local_export" ? overview(2, 2) : overview(7, 3)));
    });
    await page.goto("/calidad");
    const section = page.getByRole("region", { name: "Resumen de calidad del catálogo" });
    await section.getByRole("button", { name: "Ver resumen" }).click();
    await expect(section.getByText("Productos activos: 7")).toBeVisible();
    await section.getByLabel("Origen").selectOption("local_export");
    await section.getByRole("button", { name: "Ver resumen" }).click();
    await expect(section.getByText("Productos activos: 2")).toBeVisible();
    expect(seen.some((q) => q.includes("origin=local_export"))).toBe(true);
  });
});
