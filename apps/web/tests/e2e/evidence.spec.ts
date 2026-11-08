import { test, type Page } from "@playwright/test";
import { json, overview, signIn } from "./dashboard-mock";

/** T155: screenshots of the new Spanish screens as review evidence. Synthetic data only. Run with CAPTURE_EVIDENCE=1. */

const OUT = "../../docs/architecture/evidence";
test.skip(!process.env.CAPTURE_EVIDENCE, "set CAPTURE_EVIDENCE=1 to refresh the screenshots");
test.use({ viewport: { width: 1366, height: 900 } });

const recent = new Date(Date.now() - 2 * 3_600_000).toISOString();
const old = new Date(Date.now() - 100 * 3_600_000).toISOString();

const SUMMARY = {
  baseline: { total: "1000.0000", over_budget: "0.0000", lines: 4 },
  scenario: { total: "1100.0000", over_budget: "0.0000", lines: 4, budget: "1200.0000", utilisation: "0.9167" },
  delta_total: "100.0000",
  changes: [{ variant_id: 9001, supplier_before: "s1", supplier_after: "s2", qty_before: 12, qty_after: 12, reasons: ["supplier_disabled"] }],
  binding: [{ key: "min_order:s2", params: { status: "topped_up" } }], infeasible: null, notes: [],
};
const DETAIL = {
  id: "sc1", name: "Sin proveedor A", status: "ready", parameters: {}, result_hash: "h", created_by: "buyer-1", created_at: recent, summary: SUMMARY,
  results: [{ supplier_id: "s2", supplier_name: "Proveedor B", order_total: "102.5000", subtotal: "108.00", delivery_charge: "4.50", discount: "10.00", free_delivery: false, expected_delivery: "2026-11-16", budget_utilisation: "0.9167", lines: [{ variant_id: 9001, qty: 12, unit_cost: "5.0000", line_total: "60.0000", clinical_critical: true }, { variant_id: 9002, qty: 6, unit_cost: "8.0000", line_total: "48.0000", clinical_critical: false }] }],
  sensitivity: [{ constraint_key: "budget", delta: "100.0000", cost_impact: "-20.0000" }],
};

async function shot(page: Page, name: string) {
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
}

test("dashboard", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
  await page.goto("/");
  await page.getByLabel("Valor del inventario").waitFor();
  await shot(page, "panel");
});

test("scenarios", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/suppliers", (r) => r.fulfill(json([{ id: "s1", name: "Proveedor A" }, { id: "s2", name: "Proveedor B" }])));
  await page.route("**/api/scenarios", (r) => r.fulfill(json({ scenarios: [{ id: "sc1", name: "Sin proveedor A", status: "ready", created_by: "buyer-1", created_at: recent, delta_total: "100.0000" }] })));
  await page.route("**/api/scenarios/sc1", (r) => r.fulfill(json(DETAIL)));
  await page.goto("/");
  await page.getByRole("navigation").getByRole("link", { name: "Escenarios", exact: true }).click();
  await page.getByRole("button", { name: "Abrir Sin proveedor A" }).click();
  await page.getByText("Qué cambia y por qué").waitFor();
  await shot(page, "escenarios");
});

test("imports", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/imports", (r) => r.fulfill(json({ datasets: [] })));
  await page.route("**/api/imports/jobs", (r) => r.fulfill(json({ jobs: [], background_over_rows: 10000 })));
  await page.goto("/");
  await page.getByRole("navigation").getByRole("link", { name: "Datos predictivos", exact: true }).click();
  await page.getByRole("link", { name: "Plantilla CSV" }).waitFor();
  await shot(page, "datos-predictivos");
});

test("admin", async ({ page }) => {
  await signIn(page, ["viewer", "admin"]);
  await page.route("**/api/admin/roles**", (r) => r.fulfill(json({ users: [], eligible_approvers_count: 2, valid_roles: ["viewer", "buyer", "approver", "admin"], pending: 0, failed: 0, sent: 0, oldest_pending_seconds: 0, items: [] })));
  await page.route("**/api/admin/status", (r) => r.fulfill(json({
    freshness: { ok: true, data: { stock_snapshots: { latest_day: "2026-11-09", rows: 40 }, movements: { rows: 900, quarantined: 3, latest_at: old }, aggregates: { refreshed_at: recent } } },
    import_jobs: { ok: true, data: { jobs: [{ id: "5ba24d0e-5860-4dc0-baf2-caf0cb702742", dataset_id: "d1", version: 2, name: "Hoja sintética", rows: 12000, stage: "validate", state: "failed", queued_at: recent, started_at: recent, finished_at: recent, error_key: "import_failed", requested_by: "buyer-1" }] } },
    model_runs: { ok: true, data: { runs: [{ id: "r1", started_at: recent, status: "completed", through_day: "2026-11-09", total: 5, eligible: 3, dataset_version_id: "abcdef1234" }] } },
    policy_history: { ok: true, data: [{ id: "o1", status: "approved", variant_id: 9001 }] },
    role_mirror: { ok: true, data: { pending: 1, failed: 0, sent: 4, oldest_pending_seconds: 120 } },
    cost: { budget_eur: 120, estimate_eur: 0, guardrails: { min_replicas: 0, max_replicas: 1, job_parallelism: 1 } },
  })));
  await page.goto("/");
  await page.getByRole("navigation").getByRole("link", { name: "Administración", exact: true }).click();
  await page.getByText("Estado del sistema").waitFor();
  await shot(page, "administracion");
});
