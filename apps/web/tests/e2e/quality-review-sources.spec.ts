import { expect, test } from "@playwright/test";
import { json } from "./dashboard-mock";
import { signInAs } from "./ui-helpers";

/**
 * T107 (FR-006, R15): the data-quality screen shows the platform's quarantine and, in the local environment, the rows the local loader
 * could not express, each labelled with its source. Outside the local environment the loader table never appears. Synthetic data only.
 */

const platformItem = { id: 7, variant_id: 9000001, movement_reason_raw: "sale_shipment", anomaly_codes: ["unreferenced_sale"], created_at: "2026-11-05T10:00:00Z" };
const loaderItems = [
  { kind: "movements", row: 4, code: "unknown_sku", detail: "", source: "loader" },
  { kind: "inventory", row: 12, code: "currency_not_eur", detail: "", source: "loader" },
];

test.describe("data quality: review sources", () => {
  test("shows the loader rows next to the platform quarantine when the loader is available", async ({ page }) => {
    await signInAs(page, "buyer");
    await page.route("**/api/local-load/capability", (r) => r.fulfill(json({ enabled: true })));
    await page.route("**/api/local-load/review", (r) => r.fulfill(json(loaderItems)));
    await page.route("**/api/data-quality/import-errors**", (r) => r.fulfill(json({ items: [platformItem] })));
    await page.goto("/calidad");
    await expect(page.getByRole("heading", { name: "Filas de la carga local pendientes de revisión" })).toBeVisible();
    const table = page.getByRole("table", { name: "Filas de la carga local pendientes de revisión" });
    await expect(table.getByText("SKU no presente en el inventario")).toBeVisible();
    await expect(table.getByText("Moneda distinta de EUR")).toBeVisible();
    await expect(table.getByText("Carga local").first()).toBeVisible();
    await expect(page.getByRole("table", { name: "Calidad de datos y revisión de movimientos" })).toBeVisible();
  });

  test("never shows the loader table when the capability is off", async ({ page }) => {
    await signInAs(page, "buyer");
    await page.route("**/api/local-load/capability", (r) => r.fulfill(json({ enabled: false })));
    await page.route("**/api/local-load/review", (r) => r.fulfill(json(loaderItems)));
    await page.route("**/api/data-quality/import-errors**", (r) => r.fulfill(json({ items: [platformItem] })));
    await page.goto("/calidad");
    await expect(page.getByRole("table", { name: "Calidad de datos y revisión de movimientos" })).toBeVisible();
    await expect(page.getByText("Filas de la carga local pendientes de revisión")).toHaveCount(0);
  });

  test("the navigation offers the local-load screen only when it is available", async ({ page }) => {
    await signInAs(page, "buyer");
    await page.route("**/api/local-load/capability", (r) => r.fulfill(json({ enabled: true })));
    await page.route("**/api/data-quality/import-errors**", (r) => r.fulfill(json({ items: [] })));
    await page.goto("/calidad");
    await expect(page.getByRole("link", { name: "Carga local" })).toBeVisible();
  });

  test("a viewer is never offered the local-load screen", async ({ page }) => {
    await signInAs(page, "viewer");
    await page.route("**/api/data-quality/import-errors**", (r) => r.fulfill(json({ items: [] })));
    await page.goto("/calidad");
    await expect(page.getByRole("link", { name: "Carga local" })).toHaveCount(0);
  });
});
