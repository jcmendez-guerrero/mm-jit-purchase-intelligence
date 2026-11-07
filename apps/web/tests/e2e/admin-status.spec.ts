import { expect, test, type Page } from "@playwright/test";

/** T152: the admin status page in Spanish: freshness, a failed import re-run, model runs, degraded section, non-admin has no tab. */

const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });
const old = new Date(Date.now() - 100 * 3_600_000).toISOString();
const recent = new Date(Date.now() - 2 * 3_600_000).toISOString();

async function backend(page: Page, roles: string[], runsDown = false) {
  const state = { reruns: [] as string[], forecastReruns: 0 };
  await page.route("**/api/me", (r) => r.fulfill(json({ user_id: "admin-1", roles, mfa_auth_time: new Date().toISOString(), csrf_token: "csrf" })));
  await page.route("**/api/dashboard/risk*", (r) => r.fulfill(json([])));
  await page.route("**/api/admin/roles**", (r) => r.fulfill(json({ users: [], eligible_approvers_count: 2, valid_roles: ["viewer", "buyer", "approver", "admin"], pending: 0, failed: 0, sent: 0, oldest_pending_seconds: 0, items: [] })));
  await page.route("**/api/admin/status", (r) => r.fulfill(json({
    freshness: { ok: true, data: { stock_snapshots: { latest_day: "2026-11-09", rows: 40 }, movements: { rows: 900, quarantined: 3, latest_at: old }, aggregates: { refreshed_at: recent } } },
    import_jobs: { ok: true, data: { jobs: [{ id: "5ba24d0e-5860-4dc0-baf2-caf0cb702742", dataset_id: "d1", version: 2, name: "Hoja sintética", rows: 12000, stage: "validate", state: "failed", queued_at: recent, started_at: recent, finished_at: recent, error_key: "import_failed", requested_by: "buyer-1" }] } },
    model_runs: runsDown ? { ok: false, error: "downstream_unavailable" } : { ok: true, data: { runs: [{ id: "r1", started_at: recent, status: "completed", through_day: "2026-11-09", total: 5, eligible: 3, dataset_version_id: "abcdef1234" }] } },
    policy_history: { ok: true, data: [{ id: "o1", status: "approved", variant_id: 9001 }] },
    role_mirror: { ok: true, data: { pending: 1, failed: 0, sent: 4, oldest_pending_seconds: 120 } },
    cost: { budget_eur: 120, estimate_eur: 0, guardrails: { min_replicas: 0, max_replicas: 1, job_parallelism: 1 } },
  })));
  await page.route("**/api/admin/rerun/import/*", (r) => { state.reruns.push(r.request().url()); return r.fulfill(json({ job_id: "j2", state: "queued", reused: false }, 202)); });
  await page.route("**/api/admin/rerun/forecast", (r) => { state.forecastReruns += 1; return r.fulfill(json({ run_id: "r1", reused: true, eligible: 3 }, 202)); });
  return state;
}

const open = async (page: Page) => {
  await page.goto("/");
  await page.click("button:has-text('Administración')");
};

test.describe("Admin status (T152)", () => {
  test("shows stale sources, re-runs a failed import and the forecast", async ({ page }) => {
    const state = await backend(page, ["viewer", "admin"]);
    await open(page);
    const fresh = page.getByRole("region", { name: "Frescura de las fuentes" });
    await expect(fresh.getByRole("row", { name: /Movimientos de stock.*Desactualizado/ })).toBeVisible();
    await expect(fresh.getByRole("row", { name: /Indicadores del panel.*Al día/ })).toBeVisible();
    await expect(page.getByText("Pendientes: 1 · Fallidos: 0 · Más antiguo: 2 min")).toBeVisible();
    await page.getByRole("button", { name: "Repetir Hoja sintética" }).click();
    await expect(page.getByText(/Repetición solicitada/)).toBeVisible();
    expect(state.reruns).toHaveLength(1);
    await page.getByRole("button", { name: "Repetir previsión" }).click();
    expect(state.forecastReruns).toBe(1);
    await expect(page.getByText(/Réplicas mínimas: 0 · Réplicas máximas: 1 · Tareas en paralelo: 1/)).toBeVisible();
  });

  test("a failing source degrades alone", async ({ page }) => {
    await backend(page, ["viewer", "admin"], true);
    await open(page);
    await expect(page.getByRole("region", { name: "Ejecuciones del modelo de previsión" }).getByText("Esta sección no está disponible ahora mismo.")).toBeVisible();
    await expect(page.getByRole("region", { name: "Frescura de las fuentes" }).getByRole("table")).toBeVisible();
  });

  test("a buyer does not get the administration tab", async ({ page }) => {
    await backend(page, ["viewer", "buyer"]);
    await page.goto("/");
    await expect(page.getByRole("button", { name: "Administración" })).toHaveCount(0);
  });
});
