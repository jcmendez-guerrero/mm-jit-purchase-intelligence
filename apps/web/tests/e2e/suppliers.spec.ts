import { expect, test, type Page } from "@playwright/test";

/** T050: edit supplier terms, reload and see them persisted with history; a stale save shows the conflict message. The backend is a small in-test store. */

const baseTerms = {
  min_order_value: "150.0000", min_qty_for_delivery: null, free_delivery_threshold: null, delivery_charge: "9.5000", order_days: [1], delivery_schedule: null,
  lead_time_days: 3, order_cutoff_time: null, delivery_weekdays: [], discounts: [], payment_terms_days: null, preferred: false, reliability: null, disabled: false, valid_to: null,
};

async function backend(page: Page, roles: string[]) {
  const store = { version: 1, current: { ...baseTerms }, history: [{ version: 1, valid_from: "2026-01-01T00:00:00Z", valid_to: null, source: "erp", reason: "alta inicial", changed_by: "buyer-1", terms: { ...baseTerms } }] };
  let staleOnce = false;
  const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });
  await page.route("**/api/me", (r) => r.fulfill(json({ user_id: "buyer-1", roles, mfa_auth_time: new Date().toISOString(), csrf_token: "csrf" })));
  await page.route("**/api/dashboard/risk*", (r) => r.fulfill(json([])));
  await page.route("**/api/suppliers", (r) => r.fulfill(json([{ id: "s1", name: "Proveedor Sintético A", terms: store.current, version: store.version }])));
  await page.route("**/api/suppliers/s1/terms", async (r) => {
    if (r.request().method() === "GET") return r.fulfill(json({ supplier_id: "s1", version: store.version, current: store.current, history: store.history }));
    if (staleOnce) {
      staleOnce = false;
      return r.fulfill(json({ detail: "revision_conflict", current_version: store.version + 1 }, 412));
    }
    const body = r.request().postDataJSON() as Record<string, unknown>;
    store.version += 1;
    store.current = { ...store.current, lead_time_days: Number(body.lead_time_days) } as typeof baseTerms;
    store.history.push({ version: store.version, valid_from: "2026-11-05T00:00:00Z", valid_to: null, source: "manual", reason: String(body.reason ?? ""), changed_by: "buyer-1", terms: store.current });
    return r.fulfill(json({ version: store.version }));
  });
  return { makeNextSaveStale: () => (staleOnce = true), store };
}

test.describe("Supplier terms (T050)", () => {
  test("a buyer edits the lead time, reloads and sees it and the history", async ({ page }) => {
    await backend(page, ["viewer", "buyer"]);
    await page.goto("/");
    await page.getByRole("navigation").getByRole("link", { name: "Proveedores", exact: true }).click();
    await page.click("button:has-text('Proveedor Sintético A')");
    await page.getByLabel("Plazo de entrega (días)").fill("5");
    await page.getByLabel("Motivo del cambio").fill("nuevo transportista");
    await page.click("button:has-text('Guardar nueva versión')");
    await expect(page.getByText("Condiciones guardadas (versión 2)")).toBeVisible();
    await page.reload();
    await page.getByRole("navigation").getByRole("link", { name: "Proveedores", exact: true }).click();
    await page.click("button:has-text('Proveedor Sintético A')");
    await expect(page.getByLabel("Plazo de entrega (días)")).toHaveValue("5");
    await expect(page.getByRole("cell", { name: "nuevo transportista" })).toBeVisible();
  });

  test("a stale save shows the conflict message in Spanish", async ({ page }) => {
    const b = await backend(page, ["viewer", "buyer"]);
    await page.goto("/");
    await page.getByRole("navigation").getByRole("link", { name: "Proveedores", exact: true }).click();
    await page.click("button:has-text('Proveedor Sintético A')");
    b.makeNextSaveStale();
    await page.getByLabel("Plazo de entrega (días)").fill("7");
    await page.click("button:has-text('Guardar nueva versión')");
    await expect(page.getByText(/Otra persona ha guardado una versión más reciente/)).toBeVisible();
  });

  test("a viewer sees the terms read-only", async ({ page }) => {
    await backend(page, ["viewer"]);
    await page.goto("/");
    await page.getByRole("navigation").getByRole("link", { name: "Proveedores", exact: true }).click();
    await page.click("button:has-text('Proveedor Sintético A')");
    await expect(page.getByText(/Solo lectura/)).toBeVisible();
    await expect(page.getByLabel("Plazo de entrega (días)")).toBeDisabled();
  });
});
