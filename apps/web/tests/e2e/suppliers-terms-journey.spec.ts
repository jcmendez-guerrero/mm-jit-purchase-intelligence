import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { overview } from "./dashboard-mock";

/**
 * T017 / T024 (MMI-6): the supplier-terms journey on the supplier screen: values persist across a reload, a future-dated version leaves today's
 * terms in force, a stale save shows the newer version and recovers, viewers only read, search narrows a long list, and no ERP id reaches the
 * screen. A small in-test store stands in for the backend. Synthetic data only.
 */

const ERP_CONTACT_ID = "987654";
const ERP_VARIANT_ID = "424242";
const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });
const day = (offset: number) => new Date(Date.now() + offset * 86_400_000).toISOString();

interface Terms { lead_time_days: number | null; min_order_value: string | null; [k: string]: unknown }
interface Ver { version: number; valid_from: string; valid_to: string | null; source: "manual"; reason: string | null; changed_by: string; terms: Terms }

const baseTerms = (lead: number, minimum: string): Terms => ({
  min_order_value: minimum, min_qty_for_delivery: null, free_delivery_threshold: null, delivery_charge: null, order_days: [], delivery_schedule: null,
  lead_time_days: lead, order_cutoff_time: null, delivery_weekdays: [], discounts: [], payment_terms_days: null, preferred: false, reliability: null,
  disabled: false, valid_to: null,
});

const supplier = (id: string, name: string) => ({
  id, name, terms: null, version: 0, supplier_version: 1, status: "active", classification: "purchasing", origin: "platform", erp_link_state: "none",
  fiscal_type: "national", country: "ES", currency: "EUR", payment_terms_days: null, order_channel: null, external_contact_id: Number(ERP_CONTACT_ID),
});

async function backend(page: Page, roles: string[], extra = 0, endsInDays: number | null = null) {
  const suppliers = [supplier("s1", "Proveedor Sintético Alfa"), ...Array.from({ length: extra }, (_, i) => supplier(`g${i}`, `Proveedor Sintético ${String(i + 1).padStart(3, "0")}`))];
  const versions: Ver[] = [{ version: 1, valid_from: day(-30), valid_to: endsInDays === null ? null : day(endsInDays), source: "manual", reason: "alta inicial", changed_by: "buyer-1", terms: baseTerms(3, "100") }];
  const keys: string[] = [];
  const failures = { next: false };
  const view = () => {
    const now = Date.now();
    const started = versions.filter((v) => Date.parse(v.valid_from) <= now);
    const last = started.at(-1) ?? null;
    const expired = last?.valid_to != null && Date.parse(last.valid_to) <= now;
    const status = (v: Ver) => (!started.includes(v) ? "planned" : v !== last ? "superseded" : expired ? "expired" : "in_force");
    return { supplier_id: "s1", version: versions.at(-1)?.version ?? 0, current: last && !expired ? { ...last.terms, valid_to: last.valid_to } : null,
      history: versions.map((v) => ({ ...v, status: status(v) })) };
  };
  await page.route("**/api/me", (r) => r.fulfill(json({ user_id: "buyer-1", roles, mfa_auth_time: new Date().toISOString(), csrf_token: "csrf" })));
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
  await page.route("**/api/dashboard/risk*", (r) => r.fulfill(json([])));
  await page.route("**/api/local-load/**", (r) => r.fulfill(json({ detail: "not_found" }, 404)));
  await page.route("**/api/suppliers/review-items", (r) => r.fulfill(json([])));
  await page.route(/\/api\/suppliers(\?.*)?$/, (r) => {
    const q = (new URL(r.request().url()).searchParams.get("q") ?? "").toLowerCase();
    return r.fulfill(json(suppliers.filter((s) => s.name.toLowerCase().includes(q))));
  });
  await page.route("**/api/suppliers/*/links", (r) => r.fulfill(json([{ sku: "SYN-000001", name: "Pienso sintético", cost: "2.1040", currency: "EUR", cost_source: "inventory_export",
    includes_recargo: false, pack_size: 6, min_qty: null, verified_at: "2026-11-08T10:00:00Z", erp_link: "no_link", variant_id: Number(ERP_VARIANT_ID) }])));
  await page.route("**/api/product-suppliers/**", (r) => r.fulfill(json({ variant_id: 1, supplier_id: "s1", version: 0, override: null, history: [], effective: {} })));
  await page.route("**/api/suppliers/*/terms", async (r) => {
    if (r.request().method() === "GET") return r.fulfill(json(view()));
    keys.push(r.request().headers()["idempotency-key"] ?? "");
    if (failures.next) { failures.next = false; return r.abort("connectionreset"); }       // the response is lost: the user retries
    const match = /"(\d+)"/.exec(r.request().headers()["if-match"] ?? "");
    const current = versions.at(-1)?.version ?? 0;
    if (!match) return r.fulfill(json({ detail: "revision_required" }, 428));
    if (Number(match[1]) !== current) return r.fulfill(json({ detail: "revision_conflict", current_version: current }, 412));
    const body = r.request().postDataJSON() as { lead_time_days: number; min_order_value: string; valid_from?: string; reason?: string };
    versions.push({ version: current + 1, valid_from: body.valid_from ?? new Date().toISOString(), valid_to: null, source: "manual", reason: body.reason ?? null,
      changed_by: "buyer-1", terms: baseTerms(body.lead_time_days, body.min_order_value) });
    return r.fulfill(json({ version: current + 1 }));
  });
  return {
    /** Another person saves a newer version while this page is open. */
    otherPersonSaves: () => versions.push({ version: versions.length + 1, valid_from: day(0), valid_to: null, source: "manual", reason: "cambio de otra persona",
      changed_by: "buyer-2", terms: baseTerms(9, "200") }),
    versions,
    keys,
    failures,
  };
}

const open = async (page: Page, name = "Proveedor Sintético Alfa") => {
  await page.goto("/");
  await page.getByRole("navigation").getByRole("link", { name: "Proveedores", exact: true }).click();
  await page.click(`button:has-text('${name}')`);
};

test.describe("Supplier terms journey (MMI-6)", () => {
  test("saved terms appear in the history and are still there after a reload", async ({ page }) => {
    await backend(page, ["viewer", "buyer"]);
    await open(page);
    await expect(page.getByLabel("Plazo de entrega (días)")).toHaveValue("3");
    await page.getByLabel("Plazo de entrega (días)").fill("4");
    await page.getByLabel("Motivo del cambio").fill("nuevo transportista");
    await page.getByRole("button", { name: "Guardar nueva versión" }).click();
    await expect(page.getByText("Condiciones guardadas (versión 2).")).toBeVisible();
    await expect(page.getByRole("cell", { name: "nuevo transportista" })).toBeVisible();
    await page.reload();
    await open(page);
    await expect(page.getByLabel("Plazo de entrega (días)")).toHaveValue("4");
  });

  test("a version that starts in the future is stored without changing the terms in force today", async ({ page }) => {
    const b = await backend(page, ["viewer", "buyer"]);
    await open(page);
    await page.getByLabel("Plazo de entrega (días)").fill("7");
    await page.getByLabel("Válido desde").fill(day(30).slice(0, 10));
    await page.getByLabel("Motivo del cambio").fill("tarifa del mes que viene");
    await page.getByRole("button", { name: "Guardar nueva versión" }).click();
    await expect(page.getByText("Condiciones guardadas (versión 2).")).toBeVisible();
    await expect(page.getByRole("cell", { name: "tarifa del mes que viene" })).toBeVisible();
    await expect(page.getByLabel("Plazo de entrega (días)")).toHaveValue("3");            // today's terms are untouched
    expect(b.versions).toHaveLength(2);
  });

  test("a stale save names the newer version, stores nothing, and reloading shows the other person's values", async ({ page }) => {
    const b = await backend(page, ["viewer", "buyer"]);
    await open(page);
    b.otherPersonSaves();                                                                  // someone else saves while this page is open
    await page.getByLabel("Plazo de entrega (días)").fill("6");
    await page.getByRole("button", { name: "Guardar nueva versión" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "versión 2" })).toBeVisible();
    expect(b.versions).toHaveLength(2);                                                    // the stale save did not create a version
    await page.getByRole("button", { name: "Cargar versión actual" }).click();
    await expect(page.getByLabel("Plazo de entrega (días)")).toHaveValue("9");
    await expect(page.getByRole("alert").filter({ hasText: "versión 2" })).toHaveCount(0);
  });

  test("a retry of the same save sends the same key, and a different save sends a new one", async ({ page }) => {
    const b = await backend(page, ["viewer", "buyer"]);
    await open(page);
    b.failures.next = true;                                                                // the first attempt loses its response
    await page.getByLabel("Plazo de entrega (días)").fill("5");
    await page.getByRole("button", { name: "Guardar nueva versión" }).click();
    await expect(page.getByRole("alert")).toBeVisible();
    await page.getByRole("button", { name: "Guardar nueva versión" }).click();            // the user presses save again
    await expect(page.getByText("Condiciones guardadas (versión 2).")).toBeVisible();
    expect(b.keys).toHaveLength(2);
    expect(b.keys[0]).not.toBe("");
    expect(b.keys[1]).toBe(b.keys[0]);                                                     // same save, same key
    await page.getByLabel("Plazo de entrega (días)").fill("6");
    await page.getByRole("button", { name: "Guardar nueva versión" }).click();
    await expect(page.getByText("Condiciones guardadas (versión 3).")).toBeVisible();
    expect(b.keys[2]).not.toBe(b.keys[0]);                                                 // a different save, a new key
  });

  test("the history says which version is in force, planned or superseded", async ({ page }) => {
    await backend(page, ["viewer", "buyer"]);
    await open(page);
    await page.getByLabel("Plazo de entrega (días)").fill("7");
    await page.getByLabel("Válido desde").fill(day(30).slice(0, 10));
    await page.getByLabel("Motivo del cambio").fill("tarifa del mes que viene");
    await page.getByRole("button", { name: "Guardar nueva versión" }).click();
    await expect(page.getByRole("row", { name: /tarifa del mes que viene/ })).toContainText("Programada");
    await expect(page.getByRole("row", { name: /alta inicial/ })).toContainText("En vigor");
  });

  test("terms that end on a date warn the buyer when nothing is scheduled after them", async ({ page }) => {
    await backend(page, ["viewer", "buyer"], 0, 20);
    await open(page);
    await expect(page.getByText(/Estas condiciones dejan de aplicarse el .* y no hay ninguna versión posterior programada\./)).toBeVisible();
    await page.getByLabel("Válido desde").fill(day(21).slice(0, 10));
    await page.getByLabel("Motivo del cambio").fill("sucesora");
    await page.getByRole("button", { name: "Guardar nueva versión" }).click();
    await expect(page.getByText("Condiciones guardadas (versión 2).")).toBeVisible();
    await expect(page.getByText(/Estas condiciones dejan de aplicarse/)).toHaveCount(0);   // a later version is now planned
  });

  test("a viewer reads the terms but cannot change them", async ({ page }) => {
    await backend(page, ["viewer"]);
    await open(page);
    await expect(page.getByText(/Solo lectura/)).toBeVisible();
    await expect(page.getByLabel("Plazo de entrega (días)")).toBeDisabled();
    await expect(page.getByRole("button", { name: "Guardar nueva versión" })).toHaveCount(0);
  });

  test("search narrows a list of one hundred suppliers", async ({ page }) => {
    await backend(page, ["viewer", "buyer"], 100);
    await page.goto("/");
    await page.getByRole("navigation").getByRole("link", { name: "Proveedores", exact: true }).click();
    await expect(page.locator("button:has-text('Proveedor Sintético 007')")).toBeVisible();
    await page.getByLabel("Buscar proveedor").fill("Sintético 042");
    await expect(page.locator("button:has-text('Proveedor Sintético 042')")).toBeVisible();
    await expect(page.locator("button:has-text('Proveedor Sintético 007')")).toHaveCount(0);
  });

  test("no ERP identifier appears on the supplier, terms or product screens", async ({ page }) => {
    await backend(page, ["viewer", "buyer"]);
    await open(page);
    await expect(page.getByText("SYN-000001")).toBeVisible();                              // products are shown by SKU
    const text = await page.locator("body").innerText();
    expect(text).not.toContain(ERP_CONTACT_ID);
    expect(text).not.toContain(ERP_VARIANT_ID);
  });

  test("the supplier screen is Spanish only, with euro and Spanish number and date formats (SC-008)", async ({ page }) => {
    await backend(page, ["viewer", "buyer"]);
    await open(page);
    await expect(page.getByLabel("Plazo de entrega (días)")).toBeVisible();
    const text = await page.locator("body").innerText();
    expect(text).not.toMatch(/\b[a-z]+(\.[a-z_]+){1,}\b(?!\s*\()/);                      // no raw translation key such as suppliers.terms.save
    expect(text).not.toMatch(/\b(Save|Cancel|Loading|Error|Supplier|Lead time|Delete|Submit)\b/); // no English left over
    expect(text).not.toMatch(/undefined|NaN|\[object/);
    expect(text).toMatch(/2,10\s?€/);                                                    // decimal comma and the euro sign after the amount
    expect(text).not.toMatch(/2\.10\b|\$\s?\d|€\s?\d/);                                    // no decimal point, dollar sign or prefix euro sign
    expect(text).not.toMatch(/\b\d{4}-\d{2}-\d{2}\b/);                                   // no ISO dates
    expect(text).toMatch(/\b\d{1,2}\/\d{1,2}\/\d{4}\b/);                                 // dates as dd/mm/yyyy
    if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/proveedor-condiciones.png`, fullPage: true }); // T050, on request only
  });

  test("no serious accessibility problem on the terms editor", async ({ page }) => {
    await backend(page, ["viewer", "buyer"]);
    await open(page);
    await expect(page.getByLabel("Plazo de entrega (días)")).toBeVisible();
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
    const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.flatMap((v) => v.nodes.map((n) => `${v.id}: ${n.target.join(" ")}`))).toEqual([]);
  });
});
