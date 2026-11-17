import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

/**
 * Feature 014 (T060, US7): the dashboard against the real stack: the BFF, the services and PostgreSQL seeded with the synthetic reference dataset
 * (packages/testing/fixtures/dashboard_reference, expected totals in TOTALS.md). Nothing is simulated here.
 *
 * Run with the live config, after starting and seeding the stack as scripts/live-stack/README.md says:
 *   PLAYWRIGHT_BASE_URL=http://localhost:8080 npx playwright test --config playwright.live.config.ts tests/live/dashboard.spec.ts
 * When the reference dataset is not loaded (for example in the e2e gate's own stack, which has no seed step) every test here is skipped, with that reason: never a silent pass.
 * The reference data is dated 2026-11-09, so on any later day it is older than the 48-hour limit: the stale banner is expected, and is part of what is checked.
 */

async function signInAs(page: Page, userId: "buyer-1" | "viewer-1") {
  const res = await page.request.post("/api/auth/dev-login", { data: { user_id: userId, roles: [] } });       // the registry decides the roles
  expect(res.ok(), `dev login as ${userId}: ${res.status()} ${await res.text()}`).toBeTruthy();
}

/** True when the stack holds the reference dataset: a buyer's stock value is the documented 100.00. */
async function referenceDataLoaded(page: Page): Promise<boolean> {
  const res = await page.request.get("/api/dashboard/overview");
  if (!res.ok()) return false;
  const body = (await res.json()) as { indicators?: Array<{ key: string; value: string | null }> };
  return Number(body.indicators?.find((i) => i.key === "stock_value")?.value) === 100;
}

const card = (page: Page, name: string) => page.getByRole("heading", { name, exact: true }).locator("xpath=ancestor::article");

test.describe("Dashboard on the live stack", () => {
  test.describe.configure({ mode: "serial" });                // one real stack, one sign-in at a time (the gateway limits logins per second)

  test.beforeEach(async ({ page }) => {
    await signInAs(page, "buyer-1");
    test.skip(!(await referenceDataLoaded(page)), "the synthetic reference dataset is not loaded: run scripts/live-stack/seed.py (scripts/live-stack/README.md)");
  });

  test("a buyer sees the documented totals, the origin, and that the data is stale", async ({ page }) => {
    await signInAs(page, "buyer-1");
    await page.goto("/panel");
    await expect(card(page, "Valor del stock")).toContainText("100,00");                      // TOTALS.md: stock value, all warehouses
    await expect(card(page, "Exposición a caducidad")).toContainText("60,00");                // TOTALS.md: expiring within 60 days
    await expect(card(page, "Valor del stock")).toContainText("Origen: ERP");
    await expect(page.getByRole("alert").filter({ hasText: "Los datos están desactualizados" })).toBeVisible();
  });

  test("the charts show the reference figures and their tables carry the same numbers", async ({ page }) => {
    await signInAs(page, "buyer-1");
    await page.goto("/panel");
    const bands = page.getByRole("figure", { name: "Valor que caduca por tramo" });
    await bands.getByRole("button", { name: "Ver como tabla" }).click();
    const table = bands.getByRole("table");
    await expect(table).toContainText("20,00");
    await expect(table).toContainText("40,00");
    const groups = page.getByRole("figure", { name: "Capital en stock por grupo ABC" });
    await groups.getByRole("button", { name: "Ver como tabla" }).click();
    await expect(groups.getByRole("table")).toContainText("40,00");                            // groups A and C
    await expect(groups.getByRole("table")).toContainText("20,00");                            // group B
  });

  test("a figure drills down to its products and each product opens its own page by SKU", async ({ page }) => {
    await signInAs(page, "buyer-1");
    await page.goto("/panel");
    await card(page, "Valor del stock").getByRole("button", { name: "Ver productos" }).click();
    const panel = page.getByRole("complementary", { name: "Productos que forman el valor del inventario" });
    await expect(panel).toContainText("SYN-001");
    await expect(panel).toContainText("Total: 100,00");                                         // the rows add up to the card
    await panel.getByRole("link", { name: "Ver ficha" }).first().click();
    await expect(page).toHaveURL(/\/panel\/skus\/SYN-00\d/);
    await expect(page.getByRole("heading", { name: /^Ficha del producto SYN-00\d$/ })).toBeVisible();
    await expect(page.getByText(/Existencias totales: \d+/)).toBeVisible();
    await expect(page.getByText(/Valor en stock al coste/)).toBeVisible();                      // a buyer sees the cost
  });

  test("the indicators export is the screen in a file: the same figure, Spanish format, no internal ids", async ({ page }) => {
    await signInAs(page, "buyer-1");
    await page.goto("/panel");
    const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Exportar indicadores" }).click()]);
    expect(download.suggestedFilename()).toMatch(/^panel-cards-\d{8}\.csv$/);
    const text = await readFile((await download.path())!, "utf8");
    expect(text.startsWith("﻿")).toBe(true);
    expect(text).toMatch(/Valor del stock;100,00;EUR;/);
    expect(text).toMatch(/Exposición a caducidad;60,00;EUR;/);
    expect(text).toContain("Generado (Madrid)");
    expect(text.toLowerCase()).not.toMatch(/variant_id|external_id/);
    await expect(page.getByText(/Archivo descargado: \d+ filas\./)).toBeVisible();
  });

  test("a viewer gets no amounts and no export, and the charts carry no money column", async ({ page }) => {
    await signInAs(page, "viewer-1");
    await page.goto("/panel");
    await expect(card(page, "Valor del stock")).not.toContainText("100,00");
    await expect(page.getByRole("button", { name: /Exportar/ })).toHaveCount(0);
    const bands = page.getByRole("figure", { name: "Valor que caduca por tramo" });
    await bands.getByRole("button", { name: "Ver como tabla" }).click();
    await expect(bands.getByRole("table")).not.toContainText("€");
    await expect(page.getByText("Tu rol no puede ver los importes de este gráfico.")).toBeVisible();   // the value history
    const direct = await page.request.get("/api/dashboard/export?kind=cards");
    expect(direct.status()).toBe(403);                                                         // and the server refuses it too
  });

  test("a SKU that does not exist is said so and shows nothing of other products", async ({ page }) => {
    await signInAs(page, "buyer-1");
    await page.goto("/panel/skus/NOPE-1");
    await expect(page.getByText("No existe ningún producto con la referencia NOPE-1.")).toBeVisible();
    await expect(page.getByText(/SYN-00/)).toHaveCount(0);
  });
});
