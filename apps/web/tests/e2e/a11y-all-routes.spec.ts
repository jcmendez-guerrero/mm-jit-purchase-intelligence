import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { json, overview } from "./dashboard-mock";
import { ROUTES, signInAs } from "./ui-helpers";

/**
 * T082 — WCAG 2.2 A/AA on every route (light appearance; the dark run is added with the dark theme, T070), and a
 * keyboard-only run of the three reference tasks (SC-003, FR-026). Synthetic data, mocked backends.
 */

const TAGS = ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"];

/** Runs axe in the light and then the dark appearance (the app follows the emulated device preference; T070). */
async function expectNoSeriousViolations(page: Page, label: string) {
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await expect.poll(() => page.evaluate(() => document.documentElement.getAttribute("data-theme"))).toBe(scheme);
    await page.waitForTimeout(300); // let colour transitions finish before measuring contrast
    const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
    const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.map((v) => `${scheme} ${label}: ${v.id} (${v.nodes.length}) ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
  }
}

/** Presses Tab until the focused element matches, using only the keyboard. */
async function tabTo(page: Page, matches: (el: { name: string; tag: string }) => boolean, limit = 120) {
  for (let i = 0; i < limit; i++) {
    await page.keyboard.press("Tab");
    const active = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      const labelled = (el as HTMLInputElement | null)?.labels?.[0]?.textContent;
      return { name: (el?.getAttribute("aria-label") ?? labelled ?? el?.textContent ?? "").trim(), tag: el?.tagName ?? "" };
    });
    if (matches(active)) return;
  }
  throw new Error("element not reachable with the keyboard");
}

for (const path of ROUTES) {
  test(`${path} has no serious or critical WCAG 2.2 AA violations (light and dark)`, async ({ page }) => {
    await signInAs(page, "admin");
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await expectNoSeriousViolations(page, path);
  });
}

test("reference task 1 by keyboard: find a product at risk and open its detail", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.route("**/api/dashboard/overview**", (r) => r.fulfill(json(overview(3))));
  await page.route("**/api/inventory/variants/100", (r) => r.fulfill(json({
    variant: { id: 100, sku: "SYN-100", name: "Variante sintética", pack_size: 1, uom: "u", product: { id: 1 } }, stock: { on_hand: 0, available: 0, reserved: 0, as_of: "2026-11-09" },
    demand: [], flows: [], history: [], history_reconciled: true, segment: { abc: "A", xyz: "X", pattern: "smooth", forecast_eligible: true, reasons: [], metrics: {} } })));
  await page.route("**/api/dashboard/variants/100/forecast-basis", (r) => r.fulfill(json({ detail: "no_forecast_run" }, 404)));
  await page.goto("/panel");
  await expect(page.getByRole("table", { name: "Tabla de riesgos detectados" })).toBeVisible();
  await tabTo(page, (e) => e.tag === "BUTTON" && /Ver detalle/.test(e.name));
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Detalle de la variante 100")).toBeVisible();
});

test("reference task 2 by keyboard: review a draft proposal and submit it for approval", async ({ page }) => {
  await signInAs(page, "buyer");
  const summary = { id: "prop-1", week: "2026-W45", status: "draft", version: 3, created_by: "buyer-1", updated_at: "2026-11-04T10:00:00Z" };
  let submitted = 0;
  await page.route("**/api/proposals", (r) => r.fulfill(json([summary])));
  await page.route("**/api/proposals/prop-1", (r) => r.fulfill(json({ ...summary, status: submitted ? "submitted" : "draft", last_edited_by: null, terms_version_ids: null, approval: null, supplier_groups: [], lines: [] })));
  await page.route("**/api/proposals/prop-1/submit", (r) => {
    submitted += 1;
    return r.fulfill(json({ version: 4 }));
  });
  await page.goto("/propuestas");
  await expect(page.getByRole("heading", { level: 3, name: /2026-W45/ })).toBeVisible();
  await tabTo(page, (e) => e.tag === "BUTTON" && /Enviar a aprobación/.test(e.name));
  await page.keyboard.press("Enter");
  // the confirmation dialog takes focus on its confirm button: Enter confirms, still by keyboard
  await expect(page.getByRole("dialog", { name: "Enviar la propuesta a aprobación" })).toBeVisible();
  await page.keyboard.press("Enter");
  await expect.poll(() => submitted).toBe(1);
});

test("reference task 3 by keyboard: edit one supplier term and save it", async ({ page }) => {
  await signInAs(page, "buyer");
  const terms = { min_order_value: "150.0000", min_qty_for_delivery: null, free_delivery_threshold: null, delivery_charge: "9.5000", order_days: [1], delivery_schedule: null, lead_time_days: 3, order_cutoff_time: null, delivery_weekdays: [], discounts: [], payment_terms_days: null, preferred: false, reliability: null, disabled: false, valid_to: null };
  let saved: Record<string, unknown> | null = null;
  await page.route("**/api/suppliers", (r) => r.fulfill(json([{ id: "s1", name: "Proveedor Sintético A", terms, version: 1 }])));
  await page.route("**/api/suppliers/s1/terms", (r) => {
    if (r.request().method() === "GET") return r.fulfill(json({ supplier_id: "s1", version: 1, current: terms, history: [] }));
    saved = r.request().postDataJSON() as Record<string, unknown>;
    return r.fulfill(json({ version: 2 }));
  });
  await page.goto("/proveedores");
  await tabTo(page, (e) => e.tag === "BUTTON" && e.name === "Proveedor Sintético A");
  await page.keyboard.press("Enter");
  await tabTo(page, (e) => e.tag === "INPUT" && e.name === "Plazo de entrega (días)");
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type("7");
  await tabTo(page, (e) => e.tag === "INPUT" && e.name === "Motivo del cambio");
  await page.keyboard.type("nuevo transportista");
  await tabTo(page, (e) => e.tag === "BUTTON" && /Guardar nueva versión/.test(e.name));
  await page.keyboard.press("Enter");
  await expect.poll(() => saved?.lead_time_days).toBe(7);
});
