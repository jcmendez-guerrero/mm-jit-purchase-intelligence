import { expect, test, type Page } from "@playwright/test";
import { json } from "./dashboard-mock";
import { signInAs } from "./ui-helpers";

/**
 * T028 (feature 012, quickstart scenarios 1 and 2): the per-product quality summary and the anomaly decision, in Spanish.
 * The BFF is mocked in the browser; synthetic data only.
 */

const summary = {
  sku: "EJ-9104",
  period_start: "2026-01-01",
  period_end: "2026-04-30",
  days_in_period: 120,
  days_with_data: 115,
  coverage_ratio: "0.958333",
  gap_days: [{ from: "2026-01-11", to: "2026-01-15" }],
  rejected_count: 1,
  quarantined_count: 2,
  ambiguous_count: 1,
  reason_counts: [{ key: "ambiguous_sku", count: 1 }],
  excluded_by_type: [{ key: "transfer_out", count: 3 }],
  anomaly_count: 1,
  censored_days: 16,
  origin: "erp",
  config_version_id: "defaults-abc",
  built_at: "2026-11-15T10:00:00Z",
};

type Decision = "pending" | "accepted" | "excluded";

/** Mocks the quality routes; the decision is kept so the table reflects it after a reload, like the real service. */
async function mockQuality(page: Page, opts: { staleMfa?: boolean } = {}) {
  let decision: Decision = "pending";
  const decisions: unknown[] = [];
  await page.route("**/api/data-quality/import-errors**", (r) => r.fulfill(json({ items: [] })));
  await page.route(/\/api\/quality\/products\/EJ-9104$/, (r) => r.fulfill(json(summary)));
  await page.route(/\/api\/quality\/products\/NOPE$/, (r) => r.fulfill(json({ detail: "quality_product_not_found" }, 404)));
  await page.route(/\/api\/quality\/products\/EJ-9104\/anomalies$/, (r) =>
    r.fulfill(json({ sku: "EJ-9104", anomalies: ["mad_outlier", "p95_cap"].map((rule_id) => ({ sku: "EJ-9104", day: "2026-03-12", rule_id, original_value: "90", decision, decided_by: null, decided_at: null, reason_code: null })) })),
  );
  await page.route(/\/api\/quality\/products\/EJ-9104\/anomalies\/2026-03-12$/, async (r) => {
    if (opts.staleMfa) return r.fulfill(json({ detail: "auth_mfa_stale" }, 403));
    const body = r.request().postDataJSON();
    decisions.push(body);
    decision = body.decision;
    return r.fulfill(json({ sku: "EJ-9104", day: "2026-03-12", decision, changed: true }));
  });
  return decisions;
}

async function lookUp(page: Page, sku: string) {
  await page.goto("/calidad");
  await page.getByLabel("SKU").fill(sku);
  await page.getByRole("button", { name: "Ver calidad" }).click();
}

test.describe("quality summary by product", () => {
  test("shows coverage, the gap and the anomalous day in Spanish", async ({ page }) => {
    await signInAs(page, "buyer");
    await mockQuality(page);
    await lookUp(page, "EJ-9104");
    await expect(page.getByText(/95,8\s?%/)).toBeVisible();
    await expect(page.getByText(/115 de 120 días con datos/)).toBeVisible();
    await expect(page.getByText(/Del 11\/01\/2026 al 15\/01\/2026/)).toBeVisible();
    await expect(page.getByText("Movimientos en revisión")).toBeVisible();
    const table = page.getByRole("table", { name: "Días con valores anómalos" });
    await expect(table.getByText("Muy por encima de lo habitual, Supera el límite del percentil 95")).toBeVisible();
    await expect(table.getByText("Pendiente")).toBeVisible();
  });

  test("a buyer excludes the day after confirming, and the table shows the decision", async ({ page }) => {
    await signInAs(page, "buyer");
    const decisions = await mockQuality(page);
    await lookUp(page, "EJ-9104");
    await page.getByRole("button", { name: "Excluir del cálculo" }).click();
    const dialog = page.getByRole("dialog", { name: "Excluir este día del cálculo" });
    await expect(dialog).toContainText("segundo factor");
    await dialog.getByRole("button", { name: "Excluir del cálculo" }).click();
    const table = page.getByRole("table", { name: "Días con valores anómalos" });
    await expect(table.getByText("Excluido del cálculo").first()).toBeVisible();
    expect(decisions).toEqual([{ decision: "excluded", reason_code: "data_error" }]);
    await expect(page.getByRole("button", { name: "Excluir del cálculo" })).toBeDisabled();
  });

  test("a stale second factor shows the Spanish message and changes nothing", async ({ page }) => {
    await signInAs(page, "buyer");
    await mockQuality(page, { staleMfa: true });
    await lookUp(page, "EJ-9104");
    await page.getByRole("button", { name: "Excluir del cálculo" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Excluir del cálculo" }).click();
    await expect(page.getByRole("alert")).toContainText("segundo factor");
    await expect(page.getByRole("table", { name: "Días con valores anómalos" }).getByText("Pendiente")).toBeVisible();
  });

  test("a viewer can read but is offered no decision", async ({ page }) => {
    await signInAs(page, "viewer");
    await mockQuality(page);
    await lookUp(page, "EJ-9104");
    await expect(page.getByText(/115 de 120 días con datos/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Excluir del cálculo" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Aceptar como normal" })).toHaveCount(0);
  });

  test("an unknown SKU shows a Spanish error", async ({ page }) => {
    await signInAs(page, "buyer");
    await mockQuality(page);
    await lookUp(page, "NOPE");
    await expect(page.getByText("No se encuentra el producto o todavía no tiene datos de calidad.")).toBeVisible();
  });
});
