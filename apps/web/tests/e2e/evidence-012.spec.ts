import { test, type Page } from "@playwright/test";
import { json, overview } from "./dashboard-mock";
import { signInAs } from "./ui-helpers";

/** Feature 012 (FR-018): screenshots of the Spanish UI as review evidence. Synthetic data only. Run with CAPTURE_EVIDENCE=1. */

const OUT = "../../specs/012-ux-navigation-localization/evidence/screenshots";
test.skip(!process.env.CAPTURE_EVIDENCE, "set CAPTURE_EVIDENCE=1 to refresh the screenshots");

async function shot(page: Page, name: string) {
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
}

for (const [name, width, height] of [["desktop-1280", 1280, 800], ["tablet-768", 768, 1024], ["narrow-375", 375, 812]] as const) {
  test(`dashboard at ${name}`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await signInAs(page, "buyer");
    await page.route("**/api/dashboard/overview**", (r) => r.fulfill(json(overview(3))));
    await page.goto("/panel");
    await page.getByRole("heading", { level: 1, name: "Panel de control" }).waitFor();
    await shot(page, `panel-${name}`);
  });
}

test("product detail shows the SKU, not the ERP id", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await signInAs(page, "buyer");
  await page.route("**/api/dashboard/overview**", (r) => r.fulfill(json(overview(3))));
  await page.route("**/api/inventory/skus/SYN-100", (r) => r.fulfill(json({
    variant: { sku: "SYN-100", name: "Variante sintética", pack_size: 1, uom: "u", product: { status: "active" } }, stock: { on_hand: 0, available: 0, reserved: 0, as_of: "2026-11-09" },
    demand: [], flows: [], history: [], history_reconciled: true, segment: { abc: "A", xyz: "X", pattern: "smooth", forecast_eligible: true, reasons: [], metrics: {} } })));
  await page.route("**/api/dashboard/skus/SYN-100/forecast-basis", (r) => r.fulfill(json({ detail: "no_forecast_run" }, 404)));
  await page.goto("/panel");
  await page.getByRole("button", { name: /Ver detalle/ }).first().click();
  await page.getByLabel("Detalle del producto").waitFor();
  await shot(page, "product-detail-sku");
});

test("quick-jump palette", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await signInAs(page, "buyer");
  await page.goto("/panel");
  await page.getByRole("heading", { level: 1 }).waitFor();
  await page.keyboard.press("Control+k");
  await page.getByPlaceholder("Escribe el nombre de una pantalla").fill("prov");
  await shot(page, "quick-jump");
});

test("error state with retry on a screen the server cannot answer", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await signInAs(page, "buyer");
  await page.goto("/calidad");
  await page.getByRole("heading", { level: 1, name: "Calidad y datos" }).waitFor();
  await shot(page, "error-state-calidad");
});

test("narrow window with the menu open", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await signInAs(page, "admin");
  await page.goto("/panel");
  await page.getByRole("heading", { level: 1 }).waitFor();
  await page.getByRole("button", { name: /menú/i }).first().click();
  await shot(page, "menu-narrow-375");
});
