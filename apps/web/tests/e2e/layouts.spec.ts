import { expect, test } from "@playwright/test";
import { json } from "./dashboard-mock";
import { signInAs } from "./ui-helpers";

/** T094 / T095 — the screen layouts of design.md §8, and how they stack on narrow screens. Synthetic data. */

const line = (id: string, supplier: string, name: string) => ({
  id, variant_id: 100 + id.length, sku: `SYN-${id}`, product_name: `Producto ${id}`, supplier_id: supplier, supplier_name: name, qty: 10, unit_cost_with_recargo: "5.2600", line_total: "52.6000",
  risk: "low", confidence: "high", manual_override: false, topup: false, constraints_applied: [],
  explanation: { policy: "forecast", forecast_eligible: true, service_level: "95", horizon_days: 14, expected_demand: 8, safety_stock: 2, order_up_to: 12, reorder_point: 5, need: 10, top_up: false, clinical_critical: false, position: { on_hand: 0, expiring: 0, usable: 0, inbound: 0, total: 0 }, supplier: { chosen: supplier, reason: "lowest_cost", alternatives: [], rejected: [] }, cost: { unit: "5.2600", source: "manual", status: "ok" }, constraints: [] },
});

test("proposal lines are grouped per supplier with the supplier's subtotal at the foot", async ({ page }) => {
  await signInAs(page, "buyer");
  const summary = { id: "prop-1", week: "2026-W45", status: "draft", version: 3, created_by: "buyer-1", updated_at: "2026-11-04T10:00:00Z" };
  const group = (id: string, name: string, subtotal: string) => ({ supplier_id: id, supplier_name: name, subtotal, discount: "0.00", delivery_charge: "0.00", total_cost: subtotal, free_delivery: false, minimum_status: "ok", expected_delivery_date: null });
  await page.route("**/api/proposals", (r) => r.fulfill(json([summary])));
  await page.route("**/api/proposals/prop-1", (r) => r.fulfill(json({ ...summary, last_edited_by: null, terms_version_ids: null, approval: null, supplier_groups: [group("s1", "Proveedor A", "105.20"), group("s2", "Proveedor B", "52.60")], lines: [line("a", "s1", "Proveedor A"), line("b", "s2", "Proveedor B"), line("cc", "s1", "Proveedor A")] })));
  await page.goto("/propuestas");
  const table = page.getByRole("table", { name: "Tabla de propuestas de compra" });
  await expect(table.getByRole("columnheader", { name: "Proveedor A" })).toBeVisible();
  await expect(table.getByRole("columnheader", { name: "Proveedor B" })).toBeVisible();
  await expect(table.getByRole("row", { name: /Subtotal de Proveedor A.*105,20/ })).toBeVisible();
  await expect(table.getByRole("row", { name: /Subtotal de Proveedor B.*52,60/ })).toBeVisible();
  // the two lines of Proveedor A sit together, before Proveedor B's
  const order = await table.locator("tbody tr").evaluateAll((rows) => rows.map((r) => (r.textContent ?? "").trim().slice(0, 14)));
  expect(order.findIndex((t) => t.includes("Producto cc"))).toBeLessThan(order.findIndex((t) => t.includes("Proveedor B")));
});

test("scenarios: the form sits beside the comparison on wide screens and stacks below 1024 px", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.route("**/api/scenarios", (r) => r.fulfill(json({ scenarios: [{ id: "sc1", name: "Sin proveedor A", status: "ready", created_by: "buyer-1", created_at: "2026-11-09T08:00:00Z", delta_total: "100.0000" }] })));
  await page.route("**/api/suppliers", (r) => r.fulfill(json([])));
  await page.route("**/api/scenarios/sc1", (r) => r.fulfill(json({
    id: "sc1", name: "Sin proveedor A", status: "ready", parameters: {}, result_hash: "h", created_by: "buyer-1", created_at: "2026-11-09T08:00:00Z",
    summary: { baseline: { total: "1000.0000", over_budget: "0.0000", lines: 4 }, scenario: { total: "1100.0000", over_budget: "0.0000", lines: 4, budget: null, utilisation: null }, delta_total: "100.0000", changes: [], binding: [], infeasible: null, notes: [] },
    results: [], sensitivity: [],
  })));
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/escenarios");
  await page.getByRole("button", { name: /Abrir Sin proveedor A/ }).click();
  const form = page.getByRole("form", { name: /Nuevo escenario|Escenario/ }).first();
  const detail = page.getByRole("article", { name: "Sin proveedor A" });
  await expect(detail).toBeVisible();
  const wide = await page.evaluate(() => {
    const f = document.querySelector("#scenario-form")!.getBoundingClientRect();
    const d = document.querySelector("article")!.getBoundingClientRect();
    return { formRight: f.right, detailLeft: d.left, formWidth: f.width };
  });
  expect(wide.detailLeft).toBeGreaterThanOrEqual(wide.formRight - 1);
  expect(wide.formWidth).toBeLessThan(420);
  await page.setViewportSize({ width: 900, height: 900 });
  const narrow = await page.evaluate(() => ({ formBottom: document.querySelector("#scenario-form")!.getBoundingClientRect().bottom, detailTop: document.querySelector("article")!.getBoundingClientRect().top }));
  expect(narrow.detailTop).toBeGreaterThanOrEqual(narrow.formBottom - 1);
  void form;
});

test("suppliers: the list sits beside the term editor on wide screens", async ({ page }) => {
  await signInAs(page, "buyer");
  const terms = { min_order_value: "150.0000", min_qty_for_delivery: null, free_delivery_threshold: null, delivery_charge: "9.5000", order_days: [1], delivery_schedule: null, lead_time_days: 3, order_cutoff_time: null, delivery_weekdays: [], discounts: [], payment_terms_days: null, preferred: false, reliability: null, disabled: false, valid_to: null };
  await page.route("**/api/suppliers", (r) => r.fulfill(json([{ id: "s1", name: "Proveedor Sintético A", terms, version: 1 }])));
  await page.route("**/api/suppliers/s1/terms", (r) => r.fulfill(json({ supplier_id: "s1", version: 1, current: terms, history: [] })));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/proveedores");
  await page.getByRole("button", { name: "Proveedor Sintético A" }).click();
  const geometry = await page.evaluate(() => {
    const list = document.querySelector(".mmi-split__aside")!.getBoundingClientRect();
    const editor = document.querySelector("#terms-title")!.getBoundingClientRect();
    return { listRight: list.right, editorLeft: editor.left };
  });
  expect(geometry.editorLeft).toBeGreaterThanOrEqual(geometry.listRight - 1);
});

test("configuration: the sections are a column of tabs beside the form on wide screens", async ({ page }) => {
  await signInAs(page, "buyer");
  const consoleData = {
    purchasing: { ok: true, data: { as_of: "2026-11-09", weekly_budget: null, policies: [] } },
    demand: { ok: true, data: { exclusions: [], rules: [] } },
    forecast: { ok: true, data: { as_of: "2026-11-09", parameters: [] } },
  };
  await page.route("**/api/policy-console", (r) => r.fulfill(json(consoleData)));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/configuracion");
  const tabs = page.getByRole("tab");
  await expect(tabs).toHaveCount(4);
  const boxes = await tabs.evaluateAll((els) => els.map((e) => e.getBoundingClientRect()));
  expect(boxes[1]!.top).toBeGreaterThan(boxes[0]!.top + boxes[0]!.height - 1); // stacked, not in a row
  const panel = await page.getByRole("tabpanel").evaluate((e) => e.getBoundingClientRect().left);
  expect(panel).toBeGreaterThanOrEqual(boxes[0]!.right - 1);
});

test("imports: the steps are numbered because they really are a sequence", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.route("**/api/imports", (r) => r.fulfill(json({ datasets: [] })));
  await page.route("**/api/imports/jobs", (r) => r.fulfill(json({ jobs: [], background_over_rows: 0 })));
  await page.goto("/importaciones");
  await expect(page.getByRole("heading", { name: /^1\. / })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^2\. / })).toBeVisible();
});

test("a 500-line proposal shows its lines in pages, keeping each supplier's header and subtotal with its lines", async ({ page }) => {
  await signInAs(page, "buyer");
  const summary = { id: "prop-1", week: "2026-W45", status: "draft", version: 3, created_by: "buyer-1", updated_at: "2026-11-04T10:00:00Z" };
  const lines = Array.from({ length: 500 }, (_, i) => line(`l${i}`, i < 300 ? "s1" : "s2", i < 300 ? "Proveedor A" : "Proveedor B"));
  const group = (id: string, name: string, subtotal: string) => ({ supplier_id: id, supplier_name: name, subtotal, discount: "0.00", delivery_charge: "0.00", total_cost: subtotal, free_delivery: false, minimum_status: "ok", expected_delivery_date: null });
  await page.route("**/api/proposals", (r) => r.fulfill(json([summary])));
  await page.route("**/api/proposals/prop-1", (r) => r.fulfill(json({ ...summary, last_edited_by: null, terms_version_ids: null, approval: null, supplier_groups: [group("s1", "Proveedor A", "1578.00"), group("s2", "Proveedor B", "1052.00")], lines })));
  const t0 = Date.now();
  await page.goto("/propuestas");
  const table = page.getByRole("table", { name: "Tabla de propuestas de compra" });
  await expect(table).toBeVisible();
  expect(Date.now() - t0).toBeLessThan(3000);
  // 50 lines plus one supplier header row: only the first page is in the page
  expect(await table.locator("tbody tr").count()).toBe(51);
  await expect(page.getByText("Página 1 de 10")).toBeVisible();
  await expect(table.getByRole("row", { name: /Subtotal de Proveedor A/ })).toHaveCount(0); // Proveedor A continues on later pages
  await page.getByRole("button", { name: "Siguiente" }).click();
  await expect(table.getByRole("columnheader", { name: "Proveedor A (continúa)" })).toBeVisible();
  for (let i = 0; i < 4; i++) await page.getByRole("button", { name: "Siguiente" }).click();
  await expect(page.getByText("Página 6 de 10")).toBeVisible();
  await expect(table.getByRole("row", { name: /Subtotal de Proveedor A.*1\.578,00/ })).toBeVisible(); // page 6 holds the last A line (line 300)
});
