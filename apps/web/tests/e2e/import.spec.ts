import { expect, test, type Page } from "@playwright/test";

/** T105: the import wizard in Spanish, with a valid synthetic file and hostile ones. The backend is a small in-test store. */

const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });
const CSV = "ID de variante Siweb;Fecha;Cantidad;Tipo de dato;Origen;Sintético/Real;Notas\n9001;2026-01-05;2;estimado;Hoja sintética A;sintético;nota\n9999;2026-01-06;2;estimado;Hoja sintética A;sintético;\n";

async function backend(page: Page, roles: string[]) {
  const state = { datasets: [] as Array<Record<string, unknown>>, uploads: 0, activated: [] as unknown[], validated: [] as unknown[], rolledBack: 0 };
  await page.route("**/api/me", (r) => r.fulfill(json({ user_id: "buyer-1", roles, mfa_auth_time: new Date().toISOString(), csrf_token: "csrf" })));
  await page.route("**/api/dashboard/risk*", (r) => r.fulfill(json([])));
  await page.route("**/api/imports", (r) => {
    if (r.request().method() === "GET") return r.fulfill(json({ datasets: state.datasets }));
    state.uploads += 1;
    return r.fulfill(json({
      id: "d1", version: 1, format: "csv", row_count: 2, duplicate_of: null, missing: [], headers: ["ID de variante Siweb", "Fecha", "Cantidad", "Tipo de dato", "Origen", "Sintético/Real", "Notas"],
      suggested_mapping: { "ID de variante Siweb": "variant_id", Fecha: "day", Cantidad: "quantity", "Tipo de dato": "kind", Origen: "provenance", "Sintético/Real": "origin" },
      preview: [{ variant_id: "9001", day: "2026-01-05", quantity: "2", kind: "estimado", provenance: "Hoja sintética A", origin: "sintético" }],
    }, 201));
  });
  await page.route("**/api/imports/d1/validate", (r) => {
    state.validated.push(r.request().postDataJSON());
    return r.fulfill(json({ id: "d1", origin: "synthetic", accepted: 1, quarantined: 1, kinds: { estimated: 1 } }));
  });
  await page.route("**/api/imports/d1/quarantine", (r) => r.fulfill(json({ rows: [{ row_no: 3, reason_key: "import_unknown_variant", params: {} }] })));
  await page.route("**/api/imports/d1/dry-run", (r) => r.fulfill(json({ dataset_id: "d1", compared_with: null, rows: { added: 1, removed: 0, changed: 0, unchanged: 0 }, variants_gaining_history: [9001], variants_losing_history: [], skipped_sparse: [], overlap: { variants: 0, days: 0 }, backtest: { status: "ok", basis: "actual_demand_only", before: { variants: 3, windows: 90, cost: "120.00" }, after: { variants: 4, windows: 120, cost: "110.50" }, delta_cost: "-9.50" } })));
  await page.route("**/api/imports/d1/activate", (r) => {
    state.activated.push(r.request().postDataJSON());
    state.datasets = [{ id: "d1", version: 1, name: "Hoja", status: "active", origin: "synthetic", uploader: "buyer-1", uploaded_at: "2026-11-09T00:00:00Z", activated_by: "buyer-1", activated_at: null, accepted: 1, quarantined: 1, kinds: {} }];
    return r.fulfill(json({ id: "d1", status: "active" }));
  });
  await page.route("**/api/imports/rollback", (r) => {
    state.rolledBack += 1;
    state.datasets = [];
    return r.fulfill(json({ status: "rolled_back" }));
  });
  return state;
}

async function open(page: Page) {
  await page.goto("/");
  await page.click("button:has-text('Datos predictivos')");
}

test.describe("Predictive data import (T105)", () => {
  test("a buyer completes the wizard with a valid synthetic file and rolls it back", async ({ page }) => {
    const state = await backend(page, ["viewer", "buyer"]);
    await open(page);
    await expect(page.getByRole("link", { name: "Plantilla CSV" })).toBeVisible();
    await page.getByLabel("Archivo (CSV o XLSX)").setInputFiles({ name: "datos.csv", mimeType: "text/csv", buffer: Buffer.from(CSV) });
    await page.click("button:has-text('Subir archivo')");
    await expect(page.getByText("Archivo recibido: 2 filas.")).toBeVisible();
    await expect(page.getByLabel("Campo: Notas")).toHaveValue("");                              // the notes column is not mapped, so it is never sent on
    await page.click("button:has-text('Validar')");
    await expect(page.getByText(/Aceptadas: 1 · En cuarentena: 1 · Datos sintéticos/)).toBeVisible();
    await expect(page.getByText("Fila 3: La variante no existe en el catálogo.")).toBeVisible();
    expect(JSON.stringify(state.validated[0])).not.toContain("Notas");
    await page.click("button:has-text('Comparar con el conjunto activo')");
    await expect(page.getByText(/Filas nuevas 1/)).toBeVisible();
    await expect(page.getByText(/Diferencia de coste simulado/)).toBeVisible();
    await expect(page.getByText(/no coinciden con días que ya tengan ventas reales del ERP/)).toBeVisible();
    await page.click("button:has-text('Activar conjunto')");
    await expect(page.getByText(/Conjunto activado/)).toBeVisible();
    await expect(page.getByRole("cell", { name: "Activo" })).toBeVisible();
    await page.click("button:has-text('Volver a la versión anterior')");
    await expect(page.getByText(/Versión anterior restaurada/)).toBeVisible();
    expect(state.rolledBack).toBe(1);
  });

  test("hostile and oversized files are refused in Spanish before anything is uploaded", async ({ page }) => {
    const state = await backend(page, ["viewer", "buyer"]);
    await open(page);
    await page.getByLabel("Archivo (CSV o XLSX)").setInputFiles({ name: "macro.xlsm", mimeType: "application/vnd.ms-excel.sheet.macroEnabled.12", buffer: Buffer.from("PK\u0003\u0004synthetic") });
    await page.click("button:has-text('Subir archivo')");
    await expect(page.getByText("Solo se admiten archivos .csv y .xlsx.")).toBeVisible();
    await page.getByLabel("Archivo (CSV o XLSX)").setInputFiles({ name: "grande.csv", mimeType: "text/csv", buffer: Buffer.alloc(6 * 1024 * 1024, "a") });
    await page.click("button:has-text('Subir archivo')");
    await expect(page.getByText("El archivo supera el tamaño máximo permitido.")).toBeVisible();
    expect(state.uploads).toBe(0);
  });

  test("a viewer sees the list but no upload", async ({ page }) => {
    await backend(page, ["viewer"]);
    await open(page);
    await expect(page.getByText(/Solo lectura/)).toBeVisible();
    await expect(page.getByLabel("Archivo (CSV o XLSX)")).toHaveCount(0);
  });
});
