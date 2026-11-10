import { expect, test, type Page } from "@playwright/test";

/** Feature 010 (US2 to US5, SC-005, SC-010): audit viewer, queue, alerts, backup and cost cards, in Spanish, with the API mocked. */

const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });
const now = new Date().toISOString();
const old = new Date(Date.now() - 100 * 3_600_000).toISOString();

async function backend(page: Page) {
  const calls = { ack: [] as string[], retry: [] as string[], auditUrls: [] as string[], roleBodies: [] as unknown[] };
  await page.route("**/api/me", (r) => r.fulfill(json({ user_id: "admin-1", roles: ["viewer", "admin"], mfa_auth_time: now, csrf_token: "csrf" })));
  await page.route("**/api/dashboard/risk*", (r) => r.fulfill(json([])));
  await page.route("**/api/admin/roles**", async (r) => {
    if (r.request().method() === "PUT") {
      calls.roleBodies.push(r.request().postDataJSON());
      return r.fulfill(json({ detail: "roles_conflict" }, 409));
    }
    return r.fulfill(json({ users: [{ user_id: "buyer-1", roles: ["buyer", "viewer"], active: true, revision: 4 }], eligible_approvers_count: 2, valid_roles: ["viewer", "buyer", "approver", "admin"], pending: 0, failed: 0, sent: 0, oldest_pending_seconds: 0, items: [] }));
  });
  await page.route("**/api/admin/status", (r) => r.fulfill(json({
    freshness: { ok: true, data: { stock_snapshots: { latest_day: "2026-11-09", rows: 40 }, movements: { rows: 900, quarantined: 3, latest_at: old }, aggregates: { refreshed_at: now } } },
    import_jobs: { ok: true, data: { jobs: [] } }, model_runs: { ok: true, data: { runs: [] } }, policy_history: { ok: true, data: [] },
    role_mirror: { ok: true, data: { pending: 0, failed: 0, sent: 1, oldest_pending_seconds: 0 } },
    cost: { budget_eur: 120, guardrails: { min_replicas: 0, max_replicas: 1, job_parallelism: 1 } },
  })));
  await page.route("**/api/admin/ops/summary", (r) => r.fulfill(json({
    backup: { ok: true, data: { last_success_at: old, last_restore_drill_at: null, captured_at: now, stale_snapshot: false, old: true } },
    cost: { ok: true, data: { currency: "EUR", budget: "120.00", month_to_date: "40.00", projected: "105.00", partial_month: true, captured_at: now, stale_snapshot: false, projected_pct: "87.5", level: "warning", projection_is_estimate: true } },
  })));
  await page.route("**/api/admin/ops/queue", (r) => r.fulfill(json({ items: [
    { kind: "import", id: "job-1", state: "failed", attempts: 0, reason_code: "import_failed" },
    { kind: "message", id: "inventory.projections", state: "dead_lettered", attempts: 2, reason_code: "poison", stale: false },
  ] })));
  await page.route("**/api/admin/ops/queue/*/*/retry", (r) => { calls.retry.push(r.request().url()); return r.fulfill(json({ reused: false }, 202)); });
  let acknowledged = false;
  await page.route("**/api/admin/alerts", (r) => r.fulfill(json({ delivery_configured: false, items: [
    { id: 7, condition_key: "backup_old", subject: "backup", severity: "warning", state: acknowledged ? "acknowledged" : "open", opened_at: now, last_seen_at: now, acknowledged_by: acknowledged ? "admin-1" : null, acknowledged_at: null, reason_code: "backup_old" },
  ] })));
  await page.route("**/api/admin/alerts/*/acknowledge", (r) => { acknowledged = true; calls.ack.push(r.request().url()); return r.fulfill(json({})); });
  await page.route("**/api/admin/ops/settings", (r) => r.fulfill(json({ source_stale_hours: 36, backup_max_age_hours: 26, budget_warn_pct: 80, budget_critical_pct: 100, mirror_lag_minutes: 15, alert_repeat_hours: 24 })));
  await page.route("**/api/admin/audit/verify", (r) => r.fulfill(json({ ok: true, checked: 12, first_broken_id: null })));
  await page.route("**/api/admin/audit?*", (r) => {
    calls.auditUrls.push(r.request().url());
    return r.fulfill(json({ items: [{ id: 9, ts: now, actor: "buyer-1", action: "access.refused", entity: "access", entity_id: "PUT /api/x", outcome: "refused", reason_code: "forbidden_missing_role" }], next_cursor: null }));
  });
  return calls;
}

const open = async (page: Page) => {
  await page.goto("/");
  await page.getByRole("navigation").getByRole("link", { name: "Administración", exact: true }).click();
};

test.describe("Admin operations (feature 010)", () => {
  test("shows stale sources, failed jobs and backup state within 30 seconds (SC-005)", async ({ page }) => {
    await backend(page);
    const t0 = Date.now();
    await open(page);
    await expect(page.getByRole("region", { name: "Frescura de las fuentes" }).getByRole("row", { name: /Movimientos de stock.*Desactualizado/ })).toBeVisible();
    await expect(page.getByRole("region", { name: "Trabajos y colas" }).getByText("Fallido")).toBeVisible();
    await expect(page.getByText("La copia es más antigua que el límite acordado.")).toBeVisible();
    expect(Date.now() - t0).toBeLessThan(30_000);
  });

  test("backup and spend cards are in Spanish with EUR and the estimate label", async ({ page }) => {
    await backend(page);
    await open(page);
    await expect(page.getByText(/Proyección: 105,00/)).toBeVisible();
    await expect(page.getByText("Aviso: la proyección se acerca al presupuesto")).toBeVisible();
    await expect(page.getByText("Es una estimación: el mes aún no ha terminado.")).toBeVisible();
  });

  test("retries a failed job, but offers no retry for a platform message", async ({ page }) => {
    const calls = await backend(page);
    await open(page);
    const queue = page.getByRole("region", { name: "Trabajos y colas" });
    await expect(queue.getByRole("button", { name: /Reintentar/ })).toHaveCount(1);
    await queue.getByRole("button", { name: "Reintentar job-1" }).click();
    await expect.poll(() => calls.retry.length).toBe(1);
    expect(calls.retry[0]).toContain("/api/admin/ops/queue/import/job-1/retry");
  });

  test("acknowledges an alert and says no e-mail channel exists", async ({ page }) => {
    const calls = await backend(page);
    await open(page);
    const alerts = page.getByRole("region", { name: "Alertas" });
    await expect(alerts.getByText(/No hay canal de correo configurado/)).toBeVisible();
    await alerts.getByRole("button", { name: /Reconocer/ }).click();
    await expect.poll(() => calls.ack.length).toBe(1);
    await expect(alerts.getByText(/Reconocida por admin-1/)).toBeVisible();
  });

  test("filters and verifies the audit trail", async ({ page }) => {
    const calls = await backend(page);
    await open(page);
    const audit = page.getByRole("region", { name: "Registro de auditoría" });
    await expect(audit.getByText("access.refused")).toBeVisible();
    await audit.getByLabel("Resultado").selectOption("refused");
    await audit.getByRole("button", { name: "Aplicar filtros" }).click();
    await expect.poll(() => calls.auditUrls.some((u) => u.includes("outcome=refused"))).toBe(true);
    await audit.getByRole("button", { name: "Verificar integridad" }).click();
    await expect(audit.getByText("La cadena es íntegra (12 entradas comprobadas).")).toBeVisible();
  });

  test("a role edit sends the loaded revision and a conflict is explained in Spanish", async ({ page }) => {
    const calls = await backend(page);
    await open(page);
    await page.getByLabel("buyer-1 Aprobador").click();
    await page.getByRole("button", { name: "Aplicar cambio" }).click();
    await expect.poll(() => calls.roleBodies.length).toBe(1);
    expect(calls.roleBodies[0]).toMatchObject({ expected_revision: 4 });
    await expect(page.getByText(/han cambiado mientras los editaba/)).toBeVisible();
    await expect(page.locator("body")).not.toContainText("roles_conflict");
  });

  // Evidence for the PR: SCREENSHOT_DIR=<folder> npx playwright test tests/e2e/admin-ops.spec.ts -g evidence
  test("evidence screenshots in Spanish", async ({ page }) => {
    const dir = process.env.SCREENSHOT_DIR;
    test.skip(!dir, "set SCREENSHOT_DIR to capture the PR screenshots");
    await page.setViewportSize({ width: 1280, height: 900 });
    await backend(page);
    await open(page);
    for (const [name, label] of [["operaciones-cuentas", "Gasto en Azure"], ["trabajos-y-colas", "Trabajos y colas"], ["alertas", "Alertas"], ["auditoria", "Registro de auditoría"]] as const) {
      const region = page.getByRole("region", { name: label }).first();
      await expect(region).toBeVisible();
      await expect(region.locator("table, p").first()).toBeVisible();
      await region.scrollIntoViewIfNeeded();
      await region.screenshot({ path: `${dir}/${name}.png` });
    }
  });
});
