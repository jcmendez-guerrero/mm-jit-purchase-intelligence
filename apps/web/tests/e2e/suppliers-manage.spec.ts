import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { overview } from "./dashboard-mock";

/**
 * T045 (MMI 004): create and configure a supplier from the screen, see the duplicate warning, the deactivation dialog with the affected lines and
 * the bulk preview; axe finds no serious problem; no text is hard-coded. A small in-test store stands in for the backend. Synthetic data only.
 */

interface Sup { id: string; name: string; terms: null; version: number; supplier_version: number; status: string; classification: string; origin: string; erp_link_state: string; fiscal_type: string; country: string; currency: string; payment_terms_days: number | null; order_channel: string | null }
const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });
const mk = (id: string, name: string, over: Partial<Sup> = {}): Sup => ({ id, name, terms: null, version: 0, supplier_version: 1, status: "active", classification: "purchasing", origin: "platform", erp_link_state: "none", fiscal_type: "national", country: "ES", currency: "EUR", payment_terms_days: null, order_channel: null, ...over });

async function backend(page: Page, roles: string[]) {
  const suppliers: Sup[] = [mk("s1", "Proveedor Sintético Alfa")];
  const calls: string[] = [];
  await page.route("**/api/me", (r) => r.fulfill(json({ user_id: "buyer-1", roles, mfa_auth_time: new Date().toISOString(), csrf_token: "csrf" })));
  await page.route("**/api/dashboard/overview*", (r) => r.fulfill(json(overview())));
  await page.route("**/api/dashboard/risk*", (r) => r.fulfill(json([])));
  await page.route("**/api/local-load/**", (r) => r.fulfill(json({ detail: "not_found" }, 404)));
  await page.route("**/api/suppliers/review-items", (r) => r.fulfill(json([])));
  await page.route(/\/api\/suppliers(\?.*)?$/, async (r) => {
    if (r.request().method() === "POST") {
      const body = r.request().postDataJSON() as { name: string };
      calls.push(`POST ${r.request().url().includes("confirm_duplicate=true") ? "confirmed" : "plain"}`);
      if (!r.request().url().includes("confirm_duplicate=true") && suppliers.some((s) => s.name.toLowerCase() === body.name.toLowerCase())) return r.fulfill(json({ detail: "supplier_possible_duplicate", duplicates: ["s1"] }, 409));
      const created = mk(`s${suppliers.length + 1}`, body.name);
      suppliers.push(created);
      return r.fulfill(json(created, 201));
    }
    return r.fulfill(json(suppliers));
  });
  await page.route("**/api/suppliers/*/terms", (r) => r.fulfill(json({ supplier_id: "s1", version: 0, current: null, history: [] })));
  await page.route("**/api/product-suppliers/**", (r) => r.fulfill(json({ variant_id: 1, supplier_id: "s1", version: 0, override: null, history: [], effective: {} })));
  await page.route("**/api/suppliers/*/links", (r) => r.fulfill(json([{ sku: "SYN-000001", name: "Pienso sintético", cost: "2.1040", currency: "EUR", cost_source: "inventory_export", includes_recargo: false, pack_size: 6, min_qty: null, verified_at: "2026-11-08T10:00:00Z", erp_link: "no_link" }])));
  await page.route("**/api/suppliers/*/deactivate", async (r) => {
    const confirm = (r.request().postDataJSON() as { confirm: boolean }).confirm;
    calls.push(`deactivate ${confirm}`);
    return r.fulfill(json({ deactivated: confirm, open_proposal_lines: 3, lines: [] }));
  });
  await page.route("**/api/suppliers/*/links/bulk/preview", (r) => r.fulfill(json({ batch_id: "b1", matched: 5, new: 4, existing: 1, conflicts: 0, conflict_skus: [], unknown: ["SYN-404"], expires_at: "x" })));
  return { calls, suppliers };
}

const open = async (page: Page) => {
  await page.goto("/");
  await page.getByRole("navigation").getByRole("link", { name: "Proveedores", exact: true }).click();
};

test.describe("Supplier management (MMI 004)", () => {
  test("a buyer creates a supplier and sees the duplicate warning before creating a lookalike", async ({ page }) => {
    const b = await backend(page, ["viewer", "buyer"]);
    await open(page);
    await page.getByRole("button", { name: "Nuevo proveedor" }).click();
    await page.getByLabel("Nombre comercial").fill("Proveedor Sintético Beta");
    await page.getByRole("button", { name: "Guardar proveedor" }).click();
    await expect(page.getByText("Proveedor guardado.")).toBeVisible();
    await page.getByRole("button", { name: "Nuevo proveedor" }).click();
    await page.getByLabel("Nombre comercial").fill("proveedor sintético beta");
    await page.getByRole("button", { name: "Guardar proveedor" }).click();
    await expect(page.getByText(/nombre muy parecido/)).toBeVisible();
    await page.getByRole("button", { name: "Crear de todos modos" }).click();
    await expect(page.getByText("Proveedor guardado.")).toBeVisible();
    expect(b.calls).toEqual(["POST plain", "POST plain", "POST confirmed"]);
  });

  test("deactivation asks first and names the proposal lines that will need another supplier", async ({ page }) => {
    const b = await backend(page, ["viewer", "admin"]);
    await open(page);
    await page.click("button:has-text('Proveedor Sintético Alfa')");
    await page.getByRole("button", { name: "Desactivar proveedor" }).click();
    await expect(page.getByText(/Tiene 3 líneas en propuestas abiertas/)).toBeVisible();
    expect(b.calls).toEqual(["deactivate false"]);
    await page.getByRole("dialog").getByRole("button", { name: "Desactivar", exact: true }).click();
    await expect.poll(() => b.calls).toEqual(["deactivate false", "deactivate true"]);
  });

  test("the bulk assignment shows a preview before anything is applied", async ({ page }) => {
    await backend(page, ["viewer", "buyer"]);
    await open(page);
    await page.click("button:has-text('Proveedor Sintético Alfa')");
    await page.getByLabel("Lista de SKU (uno por línea)").fill("SYN-000001\nSYN-000002");
    await page.getByRole("button", { name: "Vista previa" }).click();
    await expect(page.getByText("Coinciden")).toBeVisible();
    await expect(page.getByText(/SKU desconocidos: SYN-404/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Aplicar asignación" })).toBeEnabled();
  });

  test("a viewer sees the suppliers and their products but no management controls", async ({ page }) => {
    await backend(page, ["viewer"]);
    await open(page);
    await page.click("button:has-text('Proveedor Sintético Alfa')");
    await expect(page.getByText("SYN-000001")).toBeVisible();
    for (const name of ["Nuevo proveedor", "Desactivar proveedor", "Vista previa", "Guardar producto"]) await expect(page.getByRole("button", { name })).toHaveCount(0);
  });

  test("no serious accessibility problem on the management screen", async ({ page }) => {
    await backend(page, ["viewer", "buyer"]);
    await open(page);
    await page.click("button:has-text('Proveedor Sintético Alfa')");
    await page.getByRole("button", { name: "Nuevo proveedor" }).click();
    await expect(page.getByLabel("Nombre comercial")).toBeVisible();
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
    const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.flatMap((v) => v.nodes.map((n) => `${v.id}: ${n.target.join(" ")}`))).toEqual([]);
  });
});
