import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

/** T171: WCAG 2 A and AA (colour contrast included) on the screens added by MMI 002. Synthetic data, mocked backends. */

const recent = new Date(Date.now() - 2 * 3_600_000).toISOString();
const SUMMARY = {
  baseline: { total: "1000.0000", over_budget: "0.0000", lines: 4 },
  scenario: { total: "1100.0000", over_budget: "50.0000", lines: 4, budget: "1200.0000", utilisation: "0.9167" },
  delta_total: "100.0000",
  changes: [{ variant_id: 9001, supplier_before: "s1", supplier_after: "s2", qty_before: 12, qty_after: 12, reasons: ["supplier_disabled"] }],
  binding: [{ key: "min_order:s2", params: { status: "topped_up" } }],
  infeasible: { over_by: "50.0000", clinical_critical_variants: [9001] },
  notes: [],
};
const DETAIL = {
  id: "sc1", name: "Sin proveedor A", status: "ready", parameters: {}, result_hash: "h", created_by: "buyer-1", created_at: recent, summary: SUMMARY,
  results: [{ supplier_id: "s2", supplier_name: "Proveedor B", order_total: "102.5000", subtotal: "108.00", delivery_charge: "4.50", discount: "10.00", free_delivery: false, expected_delivery: "2026-11-16", budget_utilisation: "0.9167", lines: [{ variant_id: 9001, qty: 12, unit_cost: "5.0000", line_total: "60.0000", clinical_critical: true }, { variant_id: 9002, qty: 6, unit_cost: "8.0000", line_total: "48.0000", clinical_critical: false }] }],
  sensitivity: [{ constraint_key: "budget", delta: "100.0000", cost_impact: "-20.0000" }],
};

async function check(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad.flatMap((v) => v.nodes.map((n) => `${v.id}: ${n.target.join(" ")}`))).toEqual([]);
}

test("scenarios", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
  await page.route("**/api/suppliers", (r) => r.fulfill(json([{ id: "s1", name: "Proveedor A" }, { id: "s2", name: "Proveedor B" }])));
  await page.route("**/api/scenarios", (r) => r.fulfill(json({ scenarios: [{ id: "sc1", name: "Sin proveedor A", status: "ready", created_by: "buyer-1", created_at: recent, delta_total: "100.0000" }] })));
  await page.route("**/api/scenarios/sc1", (r) => r.fulfill(json(DETAIL)));
  await page.goto("/");
  await page.click("button:has-text('Escenarios')");
  await page.getByRole("button", { name: "Abrir Sin proveedor A" }).click();
  await page.getByText("Qué cambia y por qué").waitFor();
  await check(page);
});

test("predictive data import", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
  await page.route("**/api/imports", (r) => r.fulfill(json({ datasets: [] })));
  await page.route("**/api/imports/jobs", (r) => r.fulfill(json({ jobs: [], background_over_rows: 10000 })));
  await page.goto("/");
  await page.click("button:has-text('Datos predictivos')");
  await page.getByRole("link", { name: "Plantilla CSV" }).waitFor();
  await check(page);
});

test("administration", async ({ page }) => {
  await signIn(page, ["viewer", "admin"]);
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
  await page.route("**/api/admin/roles**", (r) => r.fulfill(json({ users: [], eligible_approvers_count: 2, valid_roles: ["viewer", "buyer", "approver", "admin"], pending: 0, failed: 0, sent: 0, oldest_pending_seconds: 0, items: [] })));
  await page.route("**/api/admin/status", (r) => r.fulfill(json({
    freshness: { ok: true, data: { stock_snapshots: { latest_day: "2026-11-09", rows: 40 }, movements: { rows: 900, quarantined: 3, latest_at: recent }, aggregates: { refreshed_at: recent } } },
    import_jobs: { ok: true, data: { jobs: [] } }, model_runs: { ok: true, data: { runs: [] } }, policy_history: { ok: true, data: [] },
    role_mirror: { ok: true, data: { pending: 0, failed: 0, sent: 4, oldest_pending_seconds: 0 } },
    cost: { budget_eur: 120, estimate_eur: 0, guardrails: { min_replicas: 0, max_replicas: 1, job_parallelism: 1 } },
  })));
  await page.goto("/");
  await page.click("button:has-text('Administración')");
  await page.getByText("Estado del sistema").waitFor();
  await check(page);
});

test("dashboard drill-down and supplier panels", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview(1, { spend: { ok: true, data: { proposal_id: "p1", week: "2026-W46", status: "draft", total: "300.00", by_supplier: [{ supplier_id: "s1", supplier_name: "Proveedor Sintético A", total: "300.00" }], budget: null, over_budget: false } } }))));
  await page.route("**/api/dashboard/drilldown*", (r) => r.fulfill(json({ kind: "inventory_value", truncated: true, total: 80, rows: [{ variant_id: 100, sku: "SYN-100", name: "Variante sintética", figure: "40.00" }] })));
  await page.route("**/api/suppliers/s1/terms", (r) => r.fulfill(json({ supplier_id: "s1", version: 1, history: [], current: null })));
  await page.goto("/");
  await page.getByLabel("Valor del inventario").getByRole("button", { name: "Ver productos" }).click();
  await page.getByRole("complementary", { name: "Productos que forman el valor del inventario" }).waitFor();
  await page.getByRole("button", { name: "Ver proveedor Proveedor Sintético A" }).click();
  await page.getByRole("complementary", { name: "Proveedor: Proveedor Sintético A" }).waitFor();
  await check(page);
});
