import { expect, test, type Page } from "@playwright/test";
import { json } from "./dashboard-mock";
import { signInAs } from "./ui-helpers";

/**
 * T055 — field-level validation, the unsaved-change prompt, non-blocking notices and explicit confirmations; the
 * safeguards behind them (separation of duties, fresh authentication, audit) stay on the server and are unchanged
 * (FR-016 to FR-019, FR-027). Synthetic data.
 */

const terms = { min_order_value: "150.0000", min_qty_for_delivery: null, free_delivery_threshold: null, delivery_charge: "9.5000", order_days: [1], delivery_schedule: null, lead_time_days: 3, order_cutoff_time: null, delivery_weekdays: [], discounts: [], payment_terms_days: null, preferred: false, reliability: null, disabled: false, valid_to: null };

async function suppliers(page: Page) {
  const puts: unknown[] = [];
  await page.route("**/api/suppliers", (r) => r.fulfill(json([{ id: "s1", name: "Proveedor Sintético A", terms, version: 1 }])));
  await page.route("**/api/suppliers/s1/terms", (r) => {
    if (r.request().method() === "GET") return r.fulfill(json({ supplier_id: "s1", version: 1, current: terms, history: [] }));
    puts.push(r.request().postDataJSON());
    return r.fulfill(json({ version: 2 }));
  });
  return puts;
}

async function openSupplier(page: Page) {
  await page.goto("/proveedores");
  await page.getByRole("button", { name: "Proveedor Sintético A" }).click();
  await expect(page.getByLabel("Plazo de entrega (días)")).toHaveValue("3");
}

test("an invalid value shows its message beside the field, moves focus there and sends nothing", async ({ page }) => {
  await signInAs(page, "buyer");
  const puts = await suppliers(page);
  await openSupplier(page);
  const lead = page.getByLabel("Plazo de entrega (días)");
  await lead.fill("tres");
  await page.getByLabel("Motivo del cambio").fill("prueba");
  await page.getByRole("button", { name: "Guardar nueva versión" }).click();
  await expect(page.getByText("Introduce un número entero igual o mayor que cero.")).toBeVisible();
  await expect(lead).toHaveAttribute("aria-invalid", "true");
  await expect(lead).toBeFocused();
  expect(puts).toHaveLength(0);
  await expect(lead).toHaveAccessibleDescription(/Introduce un número entero/);
});

test("leaving a field validates it", async ({ page }) => {
  await signInAs(page, "buyer");
  await suppliers(page);
  await openSupplier(page);
  await page.getByLabel("Gastos de envío (€)").fill("abc");
  await page.getByLabel("Plazo de entrega (días)").focus();
  await expect(page.getByText("Introduce un número válido, por ejemplo 12,50.")).toBeVisible();
});

test("leaving with unsaved changes asks first; keep editing stays and discard leaves", async ({ page }) => {
  await signInAs(page, "buyer");
  await suppliers(page);
  await openSupplier(page);
  await page.getByLabel("Plazo de entrega (días)").fill("9");
  await page.getByRole("navigation").getByRole("link", { name: "Escenarios", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Tienes cambios sin guardar" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Seguir editando" }).click();
  await expect(page).toHaveURL(/\/proveedores$/);
  await expect(page.getByLabel("Plazo de entrega (días)")).toHaveValue("9");
  await page.getByRole("navigation").getByRole("link", { name: "Escenarios", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Descartar cambios" }).click();
  await expect(page).toHaveURL(/\/escenarios$/);
});

test("saving shows a non-blocking notice that can be dismissed from the keyboard", async ({ page }) => {
  await signInAs(page, "buyer");
  const puts = await suppliers(page);
  await openSupplier(page);
  await page.getByLabel("Plazo de entrega (días)").fill("5");
  await page.getByRole("button", { name: "Guardar nueva versión" }).click();
  const notices = page.getByRole("region", { name: "Avisos" });
  await expect(notices.getByText("Condiciones guardadas (versión 2).")).toBeVisible();
  expect(puts).toHaveLength(1);
  // the page stays usable while the notice is shown
  await page.getByLabel("Motivo del cambio").fill("sigue editable");
  await notices.getByRole("button", { name: "Cerrar aviso" }).focus();
  await page.keyboard.press("Enter");
  await expect(notices.getByText("Condiciones guardadas (versión 2).")).toHaveCount(0);
});

test("approving a proposal asks first, sends the same request on confirm and nothing on cancel", async ({ page }) => {
  await signInAs(page, "approver");
  const summary = { id: "prop-1", week: "2026-W45", status: "submitted", version: 5, created_by: "buyer-1", updated_at: "2026-11-04T10:00:00Z" };
  const approvals: Array<{ ifMatch: string | undefined }> = [];
  await page.route("**/api/proposals", (r) => r.fulfill(json([summary])));
  await page.route("**/api/proposals/prop-1", (r) => r.fulfill(json({ ...summary, last_edited_by: null, terms_version_ids: null, approval: null, supplier_groups: [], lines: [] })));
  await page.route("**/api/proposals/prop-1/approve", (r) => {
    approvals.push({ ifMatch: r.request().headers()["if-match"] });
    return r.fulfill(json({ version: 6 }));
  });
  await page.goto("/propuestas");
  const approve = page.getByRole("button", { name: /Aprobar propuesta/ });
  await approve.click();
  const dialog = page.getByRole("dialog", { name: "Aprobar la propuesta" });
  await expect(dialog).toContainText("Semana 2026-W45");
  await expect(dialog).toContainText("no envía ningún pedido a los proveedores");
  await dialog.getByRole("button", { name: "Cancelar" }).click();
  expect(approvals).toHaveLength(0);
  await expect(approve).toBeFocused();
  await approve.click();
  await page.getByRole("dialog").getByRole("button", { name: /Aprobar propuesta/ }).click();
  await expect.poll(() => approvals.length).toBe(1);
  expect(approvals[0]!.ifMatch).toBe('"5"'); // the version that was reviewed, as before
});

test("releasing a cost names the product, supplier and value; confirming calls the same endpoint", async ({ page }) => {
  await signInAs(page, "buyer");
  const write = {
    id: "w1", product_id: 10, supplier_id: "s1", trigger: "receipt_matched", proposed_value: "9.0000", previous_siweb_value: "8.0000", status: "pending_review", attempts: 0, last_error: null, median_cost: "9.00",
    lots: [{ variant_id: 1, lot: "L1", quantity: 3, unit_cost: "9.0000" }], pvp_used: "20.00", pvp_source: "stock_movement_price", margin_before: "0.5000", margin_after: "0.5500", rule_flags: [], tips: { cap: "0.30", cost_at_minimum: "8.50", cost_at_cap: "7.00" }, override: null,
  };
  const approved: string[] = [];
  await page.route("**/api/suppliers", (r) => r.fulfill(json([{ id: "s1", name: "Proveedor Sintético A", terms: null, version: 0 }])));
  await page.route("**/api/costs", (r) => r.fulfill(json([])));
  await page.route("**/api/cost-writes", (r) => r.fulfill(json([write])));
  await page.route("**/api/cost-writes/w1/approve", (r) => {
    approved.push(r.request().method());
    return r.fulfill(json({}));
  });
  await page.goto("/costes");
  await page.getByRole("button", { name: /Liberar coste/ }).click();
  const dialog = page.getByRole("dialog", { name: "Liberar la actualización del coste en el ERP" });
  await expect(dialog).toContainText("Proveedor Sintético A");
  await expect(dialog).toContainText("9,00");
  await expect(dialog).toContainText("auditoría");
  await dialog.getByRole("button", { name: "Cancelar" }).click();
  expect(approved).toHaveLength(0);
  await page.getByRole("button", { name: /Liberar coste/ }).click();
  await page.getByRole("dialog").getByRole("button", { name: /Liberar coste/ }).click();
  await expect.poll(() => approved).toEqual(["POST"]);
});

test("changing a user's roles asks first", async ({ page }) => {
  await signInAs(page, "admin");
  const updates: unknown[] = [];
  const listing = { users: [{ user_id: "buyer-1", roles: ["buyer", "viewer"], active: true, revision: 1 }], eligible_approvers_count: 2, valid_roles: ["viewer", "buyer", "approver", "admin"] };
  await page.route("**/api/admin/roles", (r) => r.fulfill(json(listing)));
  await page.route("**/api/admin/roles/mirror", (r) => r.fulfill(json({ pending: 0, failed: 0, sent: 1, oldest_pending_seconds: 0, items: [] })));
  await page.route("**/api/admin/status", (r) => r.fulfill(json({ detail: "unavailable" }, 500)));
  await page.route("**/api/admin/roles/buyer-1", (r) => {
    updates.push(r.request().postDataJSON());
    return r.fulfill(json({}));
  });
  await page.goto("/administracion");
  await page.getByLabel("buyer-1 Aprobador").click();
  await expect(page.getByRole("dialog", { name: "Cambiar el acceso de un usuario" })).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Cancelar" }).click();
  expect(updates).toHaveLength(0);
});

test("ignoring a quarantined movement asks first, names it and sends the same decision on confirm", async ({ page }) => {
  await signInAs(page, "buyer");
  const decisions: unknown[] = [];
  await page.route("**/api/data-quality/import-errors", (r) => r.fulfill(json({ count: 1, items: [{ id: 7, variant_id: 42, movement_reason_raw: "Ajuste", anomaly_codes: ["negative_quantity"], created_at: "2026-11-01T10:30:00Z" }] })));
  await page.route("**/api/data-quality/import-errors/7/resolve", (r) => {
    decisions.push(r.request().postDataJSON());
    return r.fulfill({ status: 204 });
  });
  await page.goto("/calidad");
  await page.getByRole("button", { name: "Descartar / Ignorar" }).click();
  const dialog = page.getByRole("dialog", { name: "Ignorar el movimiento retenido" });
  await expect(dialog).toContainText("Variante #42");
  await dialog.getByRole("button", { name: "Cancelar" }).click();
  expect(decisions).toHaveLength(0);
  await page.getByRole("button", { name: "Descartar / Ignorar" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Descartar / Ignorar" }).click();
  await expect.poll(() => decisions).toEqual([{ decision: "ignore" }]);
});

test("an admin's cost override asks first and says another buyer must release it", async ({ page }) => {
  await signInAs(page, "admin");
  const write = {
    id: "w1", product_id: 10, supplier_id: "s1", trigger: "receipt_matched", proposed_value: "9.0000", previous_siweb_value: "8.0000", status: "pending_review", attempts: 0, last_error: null, median_cost: "9.00",
    lots: [{ variant_id: 1, lot: "L1", quantity: 3, unit_cost: "9.0000" }], pvp_used: "20.00", pvp_source: "stock_movement_price", margin_before: "0.5000", margin_after: "0.5500", rule_flags: [], tips: { cap: "0.30", cost_at_minimum: "8.50", cost_at_cap: "7.00" }, override: null,
  };
  const overrides: unknown[] = [];
  await page.route("**/api/suppliers", (r) => r.fulfill(json([{ id: "s1", name: "Proveedor Sintético A", terms: null, version: 0 }])));
  await page.route("**/api/costs", (r) => r.fulfill(json([])));
  await page.route("**/api/cost-writes", (r) => r.fulfill(json([write])));
  await page.route("**/api/cost-writes/w1/override", (r) => {
    overrides.push(r.request().postDataJSON());
    return r.fulfill(json({}));
  });
  await page.goto("/costes");
  await page.getByLabel("Coste (€)").fill("8,5");
  await page.getByLabel("Motivo").fill("oferta puntual");
  await page.getByRole("button", { name: "Guardar valor propio" }).click();
  const dialog = page.getByRole("dialog", { name: "Sustituir el valor propuesto del coste" });
  await expect(dialog).toContainText("Otra persona con rol de comprador tendrá que liberarlo");
  await dialog.getByRole("button", { name: "Cancelar" }).click();
  expect(overrides).toHaveLength(0);
  await page.getByRole("button", { name: "Guardar valor propio" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Guardar valor propio" }).click();
  await expect.poll(() => overrides.length).toBe(1);
});

test("scenario parameters show their message beside the field and focus it", async ({ page }) => {
  await signInAs(page, "buyer");
  const created: unknown[] = [];
  await page.route("**/api/scenarios", (r) => {
    if (r.request().method() === "POST") created.push(r.request().postDataJSON());
    return r.fulfill(json({ scenarios: [] }));
  });
  await page.route("**/api/suppliers", (r) => r.fulfill(json([])));
  await page.goto("/escenarios");
  await page.getByLabel("Nombre del escenario").fill("Sin proveedor A");
  const budget = page.getByLabel(/Presupuesto semanal/);
  await budget.fill("abc");
  await page.getByRole("button", { name: "Calcular escenario" }).click();
  await expect(budget).toHaveAttribute("aria-invalid", "true");
  await expect(budget).toBeFocused();
  expect(created).toHaveLength(0);
  await budget.fill("1200");
  await expect(budget).not.toHaveAttribute("aria-invalid", "true"); // the message goes away as soon as the field changes
});

test("the opening-cost form names the field with a problem", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.route("**/api/suppliers", (r) => r.fulfill(json([{ id: "s1", name: "Proveedor Sintético A", terms: null, version: 0 }])));
  await page.route("**/api/costs", (r) => r.fulfill(json([])));
  await page.route("**/api/cost-writes", (r) => r.fulfill(json([])));
  await page.goto("/costes");
  await page.getByLabel("Proveedor", { exact: true }).selectOption("s1");
  await page.getByLabel("Producto (número)").fill("10");
  await page.getByLabel("Variante (número)").fill("uno");
  await page.getByLabel("Coste (€)").fill("9,5");
  await page.getByRole("button", { name: "Guardar coste inicial" }).click();
  const variant = page.getByLabel("Variante (número)");
  await expect(variant).toHaveAttribute("aria-invalid", "true");
  await expect(variant).toBeFocused();
});

test("the cost opening form and the policy parameters ask before edits are lost", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.route("**/api/suppliers", (r) => r.fulfill(json([{ id: "s1", name: "Proveedor Sintético A", terms: null, version: 0 }])));
  await page.route("**/api/costs", (r) => r.fulfill(json([])));
  await page.route("**/api/cost-writes", (r) => r.fulfill(json([])));
  await page.goto("/costes");
  await page.getByLabel("Producto (número)").fill("10");
  await page.getByRole("navigation").getByRole("link", { name: "Escenarios", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Tienes cambios sin guardar" })).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Seguir editando" }).click();
  await expect(page).toHaveURL(/\/costes$/);

  const console_ = {
    purchasing: { ok: true, data: { as_of: "2026-11-09", weekly_budget: null, policies: [] } },
    demand: { ok: true, data: { exclusions: [], rules: [] } },
    forecast: { ok: true, data: { as_of: "2026-11-09", parameters: [{ key: "lead_time", value: "7", min: "1", max: "60", default: "7", revision: 1 }] } },
  };
  await page.route("**/api/policy-console", (r) => r.fulfill(json(console_)));
  await page.getByRole("navigation").getByRole("link", { name: "Configuración", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Descartar cambios" }).click();
  await expect(page).toHaveURL(/\/configuracion$/);
  await page.getByRole("tab", { name: "Parámetros de previsión" }).click();
  const param = page.locator("#par-lead_time");
  await expect(param).toBeVisible();
  await param.fill("9");
  await page.getByRole("navigation").getByRole("link", { name: "Panel de control", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Tienes cambios sin guardar" })).toBeVisible();
});

test("each screen's primary action sits in the page header", async ({ page }) => {
  await signInAs(page, "buyer");
  const header = page.locator(".mmi-page-header");

  const summary = { id: "prop-1", week: "2026-W45", status: "draft", version: 3, created_by: "buyer-1", updated_at: "2026-11-04T10:00:00Z" };
  await page.route("**/api/proposals", (r) => r.fulfill(json([summary])));
  await page.route("**/api/proposals/prop-1", (r) => r.fulfill(json({ ...summary, last_edited_by: null, terms_version_ids: null, approval: null, supplier_groups: [], lines: [] })));
  await page.goto("/propuestas");
  await expect(header.getByRole("button", { name: "Enviar a aprobación" })).toBeVisible();
  await expect(header.getByRole("link", { name: "Exportar CSV (formato es-ES)" })).toBeVisible();

  await page.route("**/api/scenarios", (r) => r.fulfill(json({ scenarios: [] })));
  await page.route("**/api/suppliers", (r) => r.fulfill(json([{ id: "s1", name: "Proveedor Sintético A", terms, version: 1 }])));
  await page.route("**/api/suppliers/s1/terms", (r) => r.fulfill(json({ supplier_id: "s1", version: 1, current: terms, history: [] })));
  await page.getByRole("navigation").getByRole("link", { name: "Escenarios", exact: true }).click();
  await expect(header.getByRole("button", { name: "Calcular escenario" })).toBeVisible();

  await page.getByRole("navigation").getByRole("link", { name: "Proveedores", exact: true }).click();
  await page.getByRole("button", { name: "Proveedor Sintético A" }).click();
  await expect(header.getByRole("button", { name: "Guardar nueva versión" })).toBeVisible();

  await page.route("**/api/imports", (r) => r.fulfill(json({ datasets: [] })));
  await page.route("**/api/imports/jobs", (r) => r.fulfill(json({ jobs: [], background_over_rows: 0 })));
  await page.getByRole("navigation").getByRole("link", { name: "Datos predictivos", exact: true }).click();
  await expect(header.getByRole("button", { name: "Subir archivo" })).toBeVisible();

  await page.route("**/api/costs", (r) => r.fulfill(json([])));
  await page.route("**/api/cost-writes", (r) => r.fulfill(json([])));
  await page.getByRole("navigation").getByRole("link", { name: "Costes y proveedores", exact: true }).click();
  await expect(header.getByRole("button", { name: "Guardar coste inicial" })).toBeVisible();

  const policy = { scope: "global", key: "*", revision: 1, current: { service_level: "0.9500", safety_stock_units: null, min_units: null, max_units: null, replenishment_cadence_days: null, valid_from: "2026-11-01", revision: 1, changed_by: "buyer-1" }, history: [] };
  await page.route("**/api/policy-console", (r) => r.fulfill(json({
    purchasing: { ok: true, data: { as_of: "2026-11-09", weekly_budget: null, policies: [{ scope: "global", key: "*", revision: 1, in_force: null }] } },
    demand: { ok: true, data: { exclusions: [], rules: [] } }, forecast: { ok: true, data: { as_of: "2026-11-09", parameters: [] } },
  })));
  await page.route("**/api/policies/global/*", (r) => r.fulfill(json(policy)));
  await page.getByRole("navigation").getByRole("link", { name: "Configuración", exact: true }).click();
  await page.getByRole("button", { name: "Cargar política" }).click();
  await expect(header.getByRole("button", { name: "Guardar nueva versión" })).toBeVisible();
});

test("leaving the import wizard with a pending upload asks first", async ({ page }) => {
  await signInAs(page, "buyer");
  await page.route("**/api/imports", (r) => {
    if (r.request().method() === "GET") return r.fulfill(json({ datasets: [] }));
    return r.fulfill(json({
      id: "d1", version: 1, format: "csv", row_count: 2, duplicate_of: null, missing: [], headers: ["ID de variante Siweb", "Fecha", "Cantidad", "Tipo de dato", "Origen", "Sintético/Real"],
      suggested_mapping: { "ID de variante Siweb": "variant_id", Fecha: "day", Cantidad: "quantity", "Tipo de dato": "kind", Origen: "provenance", "Sintético/Real": "origin" },
      preview: [{ variant_id: "9001", day: "2026-01-05", quantity: "2", kind: "estimado", provenance: "Hoja sintética A", origin: "sintético" }],
    }, 201));
  });
  await page.route("**/api/imports/jobs", (r) => r.fulfill(json({ jobs: [], background_over_rows: 0 })));
  await page.goto("/importaciones");
  await page.getByLabel("Archivo (CSV o XLSX)").setInputFiles({ name: "datos.csv", mimeType: "text/csv", buffer: Buffer.from("a;b\n1;2\n") });
  await page.getByRole("button", { name: "Subir archivo" }).click();
  await expect(page.getByText("Archivo recibido: 2 filas.")).toBeVisible();
  await page.getByRole("navigation").getByRole("link", { name: "Escenarios", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Tienes cambios sin guardar" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Seguir editando" }).click();
  await expect(page).toHaveURL(/\/importaciones$/);
  await page.getByRole("navigation").getByRole("link", { name: "Escenarios", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Descartar cambios" }).click();
  await expect(page).toHaveURL(/\/escenarios$/);
});
