import { expect, test, type Page } from "@playwright/test";

/** T083: edit a policy, preview its effect, see a conflict message, and the refusal for viewers. The backend is a small in-test store. */

const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });

async function backend(page: Page, roles: string[]) {
  const state = { revision: 1, level: "0.9500", staleOnce: false, saved: [] as unknown[] };
  const policy = () => ({
    scope: "global", key: "*", revision: state.revision,
    current: { service_level: state.level, safety_stock_units: null, min_units: null, max_units: null, replenishment_cadence_days: null, valid_from: "2026-11-01", revision: state.revision, changed_by: "buyer-1" },
    history: [{ revision: state.revision, valid_from: "2026-11-01", changed_by: "buyer-1", service_level: state.level, safety_stock_units: null, min_units: null, max_units: null, replenishment_cadence_days: null }],
  });
  await page.route("**/api/me", (r) => r.fulfill(json({ user_id: "buyer-1", roles, mfa_auth_time: new Date().toISOString(), csrf_token: "csrf" })));
  await page.route("**/api/dashboard/risk*", (r) => r.fulfill(json([])));
  await page.route("**/api/policy-console", (r) => r.fulfill(json({
    purchasing: { ok: true, data: { as_of: "2026-11-09", weekly_budget: null, policies: [{ scope: "global", key: "*", revision: state.revision, in_force: null }] } },
    demand: { ok: true, data: { exclusions: [], rules: [] } }, forecast: { ok: true, data: { as_of: "2026-11-09", parameters: [] } },
  })));
  await page.route("**/api/policies/global/*", (r) => {
    const req = r.request();
    if (req.method() === "GET") return r.fulfill(json(policy()));
    if (state.staleOnce) {
      state.staleOnce = false;
      return r.fulfill(json({ detail: "revision_conflict", current_version: state.revision + 1 }, 412));
    }
    const body = req.postDataJSON() as { service_level_pct: string };
    state.level = (parseFloat(body.service_level_pct) / 100).toFixed(4);
    state.revision += 1;
    state.saved.push(body);
    return r.fulfill(json({ revision: state.revision }));
  });
  await page.route("**/api/policies/global/*/preview", (r) => r.fulfill(json({
    as_of: "2026-11-09", affected_count: 1, affected: [{ sku: "SYN-0005", qty_before: 4, qty_after: 9 }], spend_before: "100.00", spend_after: "190.00", spend_delta: "90.00", saved: false,
  })));
  return state;
}

async function open(page: Page) {
  await page.goto("/");
  await page.getByRole("navigation").getByRole("link", { name: "Configuración", exact: true }).click();
  await page.click("button:has-text('Cargar política')");
}

test.describe("Policy console (T083)", () => {
  test("a buyer previews the effect without saving, then saves and sees the new version", async ({ page }) => {
    const state = await backend(page, ["viewer", "buyer"]);
    await open(page);
    await page.getByLabel("Nivel de servicio (%)").fill("99");
    await page.click("button:has-text('Previsualizar efecto')");
    await expect(page.getByText("Productos afectados: 1")).toBeVisible();
    await expect(page.getByText("SKU SYN-0005: 4 → 9 unidades")).toBeVisible();
    expect(state.saved).toHaveLength(0);
    await page.click("button:has-text('Guardar nueva versión')");
    await expect(page.getByText("Política guardada (versión 2)")).toBeVisible();
    expect(state.saved).toEqual([{ service_level_pct: "99" }]);
  });

  test("a stale save shows the conflict message in Spanish", async ({ page }) => {
    const state = await backend(page, ["viewer", "buyer"]);
    await open(page);
    state.staleOnce = true;
    await page.getByLabel("Nivel de servicio (%)").fill("97");
    await page.click("button:has-text('Guardar nueva versión')");
    await expect(page.getByText(/Otra persona ha guardado una versión más reciente \(versión 2\)/)).toBeVisible();
  });

  test("a viewer can read but not edit", async ({ page }) => {
    await backend(page, ["viewer"]);
    await open(page);
    await expect(page.getByText(/Solo lectura/)).toBeVisible();
    await expect(page.getByLabel("Nivel de servicio (%)")).toBeDisabled();
    await expect(page.getByRole("button", { name: "Guardar nueva versión" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Previsualizar efecto" })).toHaveCount(0);
  });
});
