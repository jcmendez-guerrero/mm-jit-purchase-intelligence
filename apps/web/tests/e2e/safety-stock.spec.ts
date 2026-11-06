import { expect, test, type Page } from "@playwright/test";

/** T080: override request, approval queue and the always-stocked setting. */

const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });

async function backend(page: Page, user: string, roles: string[]) {
  const state = {
    queue: [{ id: "r1", variant_id: 5, field: "safety_stock", recommended_value: 2, requested_value: 6, reason: "proveedor poco fiable", status: "pending", requested_by: "buyer-1", decided_by: null, recommendation_changed: false }] as Array<Record<string, unknown>>,
    stocking: { variant_id: 5, stocking_mode: "standard", min_floor_units: 0, revision: 0 },
    created: [] as unknown[], stockingSaved: [] as unknown[],
  };
  await page.route("**/api/me", (r) => r.fulfill(json({ user_id: user, roles, mfa_auth_time: new Date().toISOString(), csrf_token: "csrf" })));
  await page.route("**/api/dashboard/risk*", (r) => r.fulfill(json([])));
  await page.route("**/api/policy-console", (r) => r.fulfill(json({
    purchasing: { ok: true, data: { as_of: "2026-11-09", weekly_budget: null, policies: [] } },
    demand: { ok: true, data: { exclusions: [], rules: [] } }, forecast: { ok: true, data: { as_of: "2026-11-09", parameters: [] } },
  })));
  await page.route("**/api/policy-overrides?status=pending", (r) => r.fulfill(json(state.queue)));
  await page.route("**/api/policy-overrides/recommendation/5", (r) => r.fulfill(json({ variant_id: 5, safety_stock: 2 })));
  await page.route("**/api/segments/5/history", (r) => r.fulfill(json({ variant_id: 5, history: [{ changed_at: "2026-11-01T00:00:00Z", abc: "B", xyz: "X", pattern: "smooth", critical: false, reason_key: "first_classification" }] })));
  await page.route("**/api/stocking/5", (r) => {
    const req = r.request();
    if (req.method() === "GET") return r.fulfill(json(state.stocking));
    const body = req.postDataJSON() as { stocking_mode: string; min_floor_units: number };
    state.stockingSaved.push(body);
    state.stocking = { variant_id: 5, stocking_mode: body.stocking_mode, min_floor_units: body.min_floor_units, revision: state.stocking.revision + 1 };
    return r.fulfill(json({ revision: state.stocking.revision }));
  });
  await page.route("**/api/policy-overrides", (r) => {
    state.created.push(r.request().postDataJSON());
    return r.fulfill(json({ id: "r2" }, 201));
  });
  await page.route("**/api/policy-overrides/r1/approve", (r) => {
    state.queue = [];
    return r.fulfill(json({ id: "r1", status: "approved" }));
  });
  return state;
}

async function open(page: Page) {
  await page.goto("/");
  await page.click("button:has-text('Configuración')");
  await page.getByRole("tab", { name: /Stock de seguridad/ }).click();
}

test.describe("Safety stock and always-stocked (T080)", () => {
  test("a buyer requests a different value and sets a product as always stocked", async ({ page }) => {
    const state = await backend(page, "buyer-1", ["viewer", "buyer"]);
    await open(page);
    await page.getByLabel("Variante").fill("5");
    await page.click("button:has-text('Consultar')");
    await expect(page.getByText("Recomendado por el sistema: 2 unidades")).toBeVisible();
    await expect(page.getByText(/primera clasificación/)).toBeVisible();
    await page.getByLabel("Valor solicitado").fill("6");
    await page.getByLabel("Motivo").fill("proveedor poco fiable");
    await page.click("button:has-text('Solicitar cambio')");
    await expect(page.getByText(/no se aplica hasta que otra persona/)).toBeVisible();
    expect(state.created).toEqual([{ variant_id: 5, field: "safety_stock", requested_value: 6, reason: "proveedor poco fiable" }]);
    await page.getByLabel("Modo de stock").selectOption("always_stocked");
    await page.getByLabel("Unidades mínimas siempre disponibles").fill("1");
    await page.click("button:has-text('Guardar modo de stock')");
    await expect(page.getByText("Modo de stock guardado (versión 1)")).toBeVisible();
    expect(state.stockingSaved).toEqual([{ stocking_mode: "always_stocked", min_floor_units: 1 }]);
  });

  test("an approver sees the queue and approves; the request leaves the queue", async ({ page }) => {
    await backend(page, "approver-1", ["viewer", "approver"]);
    await open(page);
    await expect(page.getByText(/recomendado 2, solicitado 6/)).toBeVisible();
    await page.click("button:has-text('Aprobar')");
    await expect(page.getByText("Solicitud resuelta.")).toBeVisible();
    await expect(page.getByText("No hay solicitudes pendientes.")).toBeVisible();
  });

  test("a buyer sees the queue but cannot approve", async ({ page }) => {
    await backend(page, "buyer-1", ["viewer", "buyer"]);
    await open(page);
    await expect(page.getByText(/recomendado 2, solicitado 6/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Aprobar" })).toHaveCount(0);
  });
});
