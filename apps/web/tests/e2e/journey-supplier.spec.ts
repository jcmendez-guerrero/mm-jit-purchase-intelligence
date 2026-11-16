import { expect, test, type Page } from "@playwright/test";
import { json, overview } from "./dashboard-mock";
import { signInAs } from "./ui-helpers";

/**
 * Feature 012, user story 3: find a supplier, edit its terms with a Spanish validation message and focus on the first error,
 * and keep unsaved edits safe when leaving. Buyer role. Synthetic data; the terms store is a stub.
 */

const terms = {
  min_order_value: "100.0000", min_qty_for_delivery: null, free_delivery_threshold: null, delivery_charge: null, order_days: [], delivery_schedule: null,
  lead_time_days: 3, order_cutoff_time: null, delivery_weekdays: [], discounts: [], payment_terms_days: null, preferred: false, reliability: null, disabled: false, valid_to: null,
};
const supplier = (id: string, name: string) => ({
  id, name, terms: null, version: 0, supplier_version: 1, status: "active", classification: "purchasing", origin: "platform", erp_link_state: "none",
  fiscal_type: "national", country: "ES", currency: "EUR", payment_terms_days: null, order_channel: null, external_contact_id: null,
});

async function backend(page: Page, saved: { body: Record<string, unknown> | null }, role: "viewer" | "buyer" | "approver" | "admin" = "buyer") {
  await signInAs(page, role);
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
  await page.route("**/api/local-load/**", (r) => r.fulfill(json({ detail: "not_found" }, 404)));
  await page.route("**/api/suppliers/review-items", (r) => r.fulfill(json([])));
  await page.route(/\/api\/suppliers(\?.*)?$/, (r) => {
    const q = (new URL(r.request().url()).searchParams.get("q") ?? "").toLowerCase();
    return r.fulfill(json([supplier("s1", "Proveedor Sintético A"), supplier("s2", "Proveedor Sintético B")].filter((s) => s.name.toLowerCase().includes(q))));
  });
  await page.route("**/api/suppliers/*/links", (r) => r.fulfill(json([])));
  await page.route("**/api/suppliers/*/terms", (r) => {
    if (r.request().method() === "GET") return r.fulfill(json({ supplier_id: "s1", version: 1, current: terms, history: [] }));
    saved.body = r.request().postDataJSON() as Record<string, unknown>;
    return r.fulfill(json({ version: 2 }));
  });
}

test("search, open, invalid value with a Spanish message and focus on the first error, then a valid save", async ({ page }) => {
  const saved = { body: null as Record<string, unknown> | null };
  await backend(page, saved);
  await page.goto("/proveedores");

  await page.getByRole("searchbox").or(page.getByRole("textbox", { name: /Buscar/ })).first().fill("Sintético B");
  await expect(page.getByRole("button", { name: "Proveedor Sintético A" })).toHaveCount(0);
  await page.getByRole("searchbox").or(page.getByRole("textbox", { name: /Buscar/ })).first().fill("");
  await page.getByRole("button", { name: "Proveedor Sintético A" }).click();

  const lead = page.getByLabel("Plazo de entrega (días)");
  await expect(lead).toHaveValue("3");
  await lead.fill("abc");
  await page.getByLabel("Motivo del cambio").fill("prueba");
  await page.getByRole("button", { name: "Guardar nueva versión" }).click();

  await expect(page.getByText("Introduce un número entero igual o mayor que cero.")).toBeVisible();
  await expect(lead).toBeFocused();
  await expect(lead).toHaveAttribute("aria-invalid", "true");
  expect(saved.body).toBeNull();

  await lead.fill("7");
  await expect(page.getByText("Introduce un número entero igual o mayor que cero.")).toHaveCount(0);
  await page.getByRole("button", { name: "Guardar nueva versión" }).click();
  await expect.poll(() => saved.body?.lead_time_days).toBe(7);
});

test("leaving with unsaved edits asks first; staying keeps the edit, leaving discards it", async ({ page }) => {
  const saved = { body: null as Record<string, unknown> | null };
  await backend(page, saved);
  await page.goto("/proveedores");
  await page.getByRole("button", { name: "Proveedor Sintético A" }).click();
  const lead = page.getByLabel("Plazo de entrega (días)");
  await lead.fill("9");

  const nav = page.getByRole("navigation", { name: "Menú principal de navegación" });
  await nav.getByRole("link", { name: "Propuestas de compra", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Tienes cambios sin guardar" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Seguir editando" }).click();
  await expect(page).toHaveURL(/\/proveedores$/);
  await expect(lead).toHaveValue("9");

  await nav.getByRole("link", { name: "Propuestas de compra", exact: true }).click();
  await page.getByRole("dialog", { name: "Tienes cambios sin guardar" }).getByRole("button", { name: "Descartar cambios" }).click();
  await expect(page).toHaveURL(/\/propuestas$/);
  expect(saved.body).toBeNull();
});

/** User story 3 and FR-017: only the buyer edits the terms; viewer, approver and admin see them read-only. */
for (const [role, canEdit, manages] of [["viewer", false, false], ["approver", false, false], ["admin", false, true], ["buyer", true, true]] as const) {
  test(`${role}: terms are ${canEdit ? "editable" : "read-only"} and the management controls are ${manages ? "offered" : "hidden"}`, async ({ page }) => {
    await backend(page, { body: null }, role);
    await page.goto("/proveedores");
    await page.getByRole("button", { name: "Proveedor Sintético A" }).click();
    const lead = page.getByLabel("Plazo de entrega (días)");
    await expect(lead).toHaveValue("3");
    if (canEdit) await expect(lead).toBeEnabled();
    else await expect(lead).toBeDisabled();
    await expect(page.getByRole("button", { name: "Guardar nueva versión" })).toHaveCount(canEdit ? 1 : 0);
    await expect(page.getByRole("button", { name: /Nuevo proveedor|Crear proveedor/ })).toHaveCount(manages ? 1 : 0);
  });
}

/** US5/AC3: when a save fails, the person keeps what they typed, sees a Spanish message and can save again. */
test("a failed save keeps the typed values, explains it in Spanish and the next save goes through", async ({ page }) => {
  const saved = { body: null as Record<string, unknown> | null };
  await backend(page, saved);
  let calls = 0;
  await page.route("**/api/suppliers/*/terms", (r) => {
    if (r.request().method() === "GET") return r.fulfill(json({ supplier_id: "s1", version: 1, current: terms, history: [] }));
    calls += 1;
    if (calls === 1) return r.fulfill(json({ detail: "unavailable" }, 500));
    saved.body = r.request().postDataJSON() as Record<string, unknown>;
    return r.fulfill(json({ version: 2 }));
  });
  await page.goto("/proveedores");
  await page.getByRole("button", { name: "Proveedor Sintético A" }).click();
  const lead = page.getByLabel("Plazo de entrega (días)");
  await expect(lead).toHaveValue("3");
  await lead.fill("7");
  await page.getByLabel("Motivo del cambio").fill("nuevo transportista");
  await page.getByRole("button", { name: "Guardar nueva versión" }).click();

  await expect(page.getByRole("alert").filter({ hasText: "Ha ocurrido un error" })).toBeVisible();
  await expect(lead).toHaveValue("7");
  await expect(page.getByLabel("Motivo del cambio")).toHaveValue("nuevo transportista");
  expect(saved.body).toBeNull();

  await page.getByRole("button", { name: "Guardar nueva versión" }).click();
  await expect.poll(() => saved.body?.lead_time_days).toBe(7);
  expect(calls).toBe(2);
});
