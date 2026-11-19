import { expect, test } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

/** T044 (US5): the export buttons and their messages. The services are simulated; the file is a small CSV and the requests are checked. */

const CSV = "﻿Informe;Prueba\r\n\r\nSKU;Producto;Valor (EUR)\r\nSYN-001;Producto sintético;40,00\r\n";
const csv = () => ({ status: 200, contentType: "text/csv; charset=utf-8", headers: { "content-disposition": 'attachment; filename="panel-cards-20261109.csv"', "x-export-rows": "6" }, body: CSV });

test.describe("Dashboard export", () => {
  let exports: URL[];

  test.beforeEach(async ({ page }) => {
    exports = [];
    await signIn(page);                                         // buyer and viewer
    await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
    await page.route("**/api/dashboard/drilldown*", (r) => r.fulfill(json({ kind: "inventory_value", truncated: false, total: 1, offset: 0, sum: "40.00", rows: [{ sku: "SYN-001", name: "Producto sintético", figure: "40.00" }] })));
    await page.route("**/api/dashboard/export*", (r) => {
      exports.push(new URL(r.request().url()));
      return r.fulfill(csv());
    });
  });

  test("a buyer downloads the indicators with the dashboard filters and is told how many rows it has", async ({ page }) => {
    await page.goto("/panel?proveedor=s1&desde=2026-10-01");
    const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Exportar indicadores" }).click()]);
    expect(download.suggestedFilename()).toBe("panel-cards-20261109.csv");
    await expect(page.getByText("Archivo descargado: 6 filas.")).toBeVisible();
    const q = exports[0]!.searchParams;
    expect([q.get("kind"), q.get("supplier_id"), q.get("date_from")]).toEqual(["cards", "s1", "2026-10-01"]);
  });

  test("a chart has its own export that names the chart for a screen reader", async ({ page }) => {
    await page.goto("/panel");
    const button = page.getByRole("button", { name: "Exportar Valor que caduca por tramo" });
    await expect(button).toBeVisible();
    await button.press("Enter");
    await expect.poll(() => exports.length).toBe(1);
    expect([exports[0]!.searchParams.get("kind"), exports[0]!.searchParams.get("chart")]).toEqual(["chart", "expiry_bands"]);
  });

  test("the products behind a figure can be exported with the sort the user chose", async ({ page }) => {
    await page.goto("/panel");
    await page.getByRole("button", { name: "Ver productos" }).first().click();
    const button = page.getByRole("button", { name: "Exportar productos", exact: true });
    await expect(button).toBeVisible();
    await page.locator("#drill-sort").selectOption("sku");
    await button.click();
    await expect.poll(() => exports.length).toBe(1);
    const q = exports[0]!.searchParams;
    expect([q.get("kind"), q.get("sort")]).toEqual(["drilldown", "sku"]);
    expect(q.get("drill_kind")).not.toBeNull();
  });

  test("a result that is too large is explained and nothing is downloaded", async ({ page }) => {
    await page.unroute("**/api/dashboard/export*");
    await page.route("**/api/dashboard/export*", (r) => r.fulfill(json({ detail: "export_too_large" }, 413)));
    let downloaded = false;
    page.on("download", () => (downloaded = true));
    await page.goto("/panel");
    await page.getByRole("button", { name: "Exportar indicadores" }).click();
    await expect(page.getByText("El resultado es demasiado grande para exportarlo: acota los filtros o el periodo.")).toBeVisible();
    expect(downloaded).toBe(false);
  });

  test("a viewer is not offered any export action", async ({ page }) => {
    await page.unroute("**/api/me");
    await signIn(page, ["viewer"]);
    await page.goto("/panel");
    await expect(page.getByRole("heading", { name: "Valor que caduca por tramo" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Exportar/ })).toHaveCount(0);
  });

  test("when the role loses cost access the server refuses, the export buttons and every cost figure go, and nothing stale stays (T076)", async ({ page }) => {
    const { indicators } = await import("./dashboard-mock");
    let revoked = false;
    await page.unroute("**/api/dashboard/overview*");
    await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview(1, { indicators: indicators(revoked) }))));
    await page.unroute("**/api/dashboard/export*");
    await page.route("**/api/dashboard/export*", (r) => {
      revoked = true;                                                    // from now on the services see a viewer
      return r.fulfill(json({ detail: "auth_forbidden_role" }, 403));
    });
    await page.goto("/panel");
    await expect(page.getByLabel("Valor del stock")).toContainText("1.234,50");
    await page.getByRole("button", { name: "Exportar indicadores" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Tu rol ya no puede ver los importes ni exportar datos" })).toBeVisible();     // the user is told why the buttons went
    await expect(page.getByRole("button", { name: /Exportar/ })).toHaveCount(0);
    await expect(page.getByLabel("Valor del stock")).not.toContainText("1.234,50");              // the figures were asked for again: no stale copy of a cost figure
  });
});
