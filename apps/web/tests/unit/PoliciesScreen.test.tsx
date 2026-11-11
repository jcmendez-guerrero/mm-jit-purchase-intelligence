// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, OverrideRequest, PolicyConsole, PolicyDetail } from "../../src/api/client";
import { PoliciesScreen } from "../../src/features/policies/PoliciesScreen";
import "../../src/i18n";

const consoleData = (over: Partial<PolicyConsole> = {}): PolicyConsole => ({
  purchasing: { ok: true, data: { as_of: "2026-11-09", weekly_budget: "400.00", policies: [{ scope: "global", key: "*", revision: 2, in_force: null }] } },
  demand: {
    ok: true,
    data: {
      exclusions: [{ id: 7, sku: null, from_day: "2026-10-03", to_day: "2026-10-05", reason_code: "closure", active: true, revision: 1 }],
      rules: [{ rule: "min_zero_stock_days", scope: "global", key: "*", value: 1, min: 1, max: 30, default: 1, revision: 0 }],
    },
  },
  forecast: { ok: true, data: { as_of: "2026-11-09", parameters: [{ key: "lead_time", value: "7", default: "7", min: "1", max: "60", kind: "int", revision: 0, in_force_revision: null }] } },
  ...over,
});

const detail: PolicyDetail = {
  scope: "global", key: "*", revision: 2,
  current: { service_level: "0.9500", safety_stock_units: null, min_units: "1", max_units: null, replenishment_cadence_days: null, valid_from: "2026-11-01", revision: 2, changed_by: "buyer-1" },
  history: [
    { revision: 1, valid_from: "2026-10-01", changed_by: "buyer-1", service_level: "0.9000", safety_stock_units: null, min_units: null, max_units: null, replenishment_cadence_days: null },
    { revision: 2, valid_from: "2026-11-01", changed_by: "buyer-1", service_level: "0.9500", safety_stock_units: null, min_units: "1", max_units: null, replenishment_cadence_days: null },
  ],
};

const pending: OverrideRequest = { id: "r1", sku: "SYN-0005", field: "safety_stock", recommended_value: 2, requested_value: 6, reason: "proveedor poco fiable", status: "pending", requested_by: "buyer-1", decided_by: null, recommendation_changed: false };

beforeEach(() => {
  vi.spyOn(api, "getPolicyConsole").mockResolvedValue(consoleData());
  vi.spyOn(api, "getPolicy").mockResolvedValue(detail);
  vi.spyOn(api, "getOverrides").mockResolvedValue([pending]);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const tab = (name: RegExp) => fireEvent.click(screen.getByRole("tab", { name }));

describe("purchasing section", () => {
  it("loads a policy, shows its history and the weekly budget", async () => {
    render(<PoliciesScreen userRoles={["viewer", "buyer"]} />);
    expect(await screen.findByText(/Presupuesto semanal vigente: 400,00/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cargar política" }));
    expect(await screen.findByLabelText("Nivel de servicio (%)")).toHaveProperty("value", "95");
    expect(within(screen.getByRole("table", { name: "Historial de versiones" })).getAllByRole("row")).toHaveLength(3);
  });

  it("previews the effect without saving and then saves with the revision it read", async () => {
    const preview = vi.spyOn(api, "previewPolicy").mockResolvedValue({ as_of: "2026-11-09", affected_count: 1, affected: [{ sku: "SYN-0005", qty_before: 4, qty_after: 9 }], spend_before: "100.00", spend_after: "190.00", spend_delta: "90.00", saved: false, forecast_run_id: "run-1234-abcd" });
    const put = vi.spyOn(api, "putPolicy").mockResolvedValue({ revision: 3 });
    render(<PoliciesScreen userRoles={["buyer"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Cargar política" }));
    fireEvent.change(await screen.findByLabelText("Nivel de servicio (%)"), { target: { value: "99" } });
    fireEvent.click(screen.getByRole("button", { name: "Previsualizar efecto" }));
    expect(await screen.findByText(/Productos afectados: 1/)).toBeTruthy();
    expect(screen.getByText(/SKU SYN-0005: 4 → 9 unidades/)).toBeTruthy();
    expect(screen.queryByText(/Variante 5/)).toBeNull();                      // the ERP id is never shown
    expect(screen.getByText(/Calculado con la última previsión terminada \(ejecución run-1234\) para el 09\/11\/2026/)).toBeTruthy();      // T071: the basis of the preview
    expect(preview).toHaveBeenCalledWith("global", "*", { service_level_pct: "99", min_units: 1 });
    expect(put).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Guardar nueva versión" }));
    await waitFor(() => expect(put).toHaveBeenCalledWith("global", "*", { service_level_pct: "99", min_units: 1 }, 2));
    expect((await screen.findByRole("status")).textContent).toContain("Política guardada (versión 3)");
  });

  it("shows the conflict message when someone saved a newer version", async () => {
    vi.spyOn(api, "putPolicy").mockRejectedValue(new ApiError(412, "revision_conflict", 5));
    render(<PoliciesScreen userRoles={["buyer"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Cargar política" }));
    await screen.findByLabelText("Nivel de servicio (%)");
    fireEvent.click(screen.getByRole("button", { name: "Guardar nueva versión" }));
    expect((await screen.findAllByRole("alert")).map((a) => a.textContent).join(" ")).toContain("versión 5");
  });

  it("is read-only for a viewer: no save or preview, a Spanish explanation instead", async () => {
    render(<PoliciesScreen userRoles={["viewer"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Cargar política" }));
    await screen.findByLabelText("Nivel de servicio (%)");
    expect(screen.queryByRole("button", { name: "Guardar nueva versión" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Previsualizar efecto" })).toBeNull();
    expect(screen.getByText(/Solo lectura/)).toBeTruthy();
    expect((screen.getByLabelText("Nivel de servicio (%)") as HTMLInputElement).disabled).toBe(true);
  });

  it("refuses an invalid number locally and names the field", async () => {
    render(<PoliciesScreen userRoles={["buyer"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Cargar política" }));
    fireEvent.change(await screen.findByLabelText("Mínimo (unidades)"), { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar nueva versión" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Mínimo (unidades)");
  });

  it("shows one unavailable section without hiding the others", async () => {
    vi.spyOn(api, "getPolicyConsole").mockResolvedValue(consoleData({ demand: { ok: false, error: "downstream_unavailable" } }));
    render(<PoliciesScreen userRoles={["buyer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Demanda y criticidad/);
    expect((await screen.findByRole("alert")).textContent).toContain("no está disponible");
    tab(/Compras/);
    expect(screen.getByText(/Presupuesto semanal vigente/)).toBeTruthy();
  });
});

describe("feature 011: revisions, sources and audit", () => {
  const budgetConsole = (revision: number) => consoleData({
    purchasing: { ok: true, data: { as_of: "2026-11-09", weekly_budget: "400.00", weekly_budget_revision: revision, policies: [] } },
  });

  it("saves a budget cap with the revision it read and shows a conflict in Spanish", async () => {
    vi.spyOn(api, "getPolicyConsole").mockResolvedValue(budgetConsole(3));
    const put = vi.spyOn(api, "putBudgetCap").mockRejectedValueOnce(new ApiError(412, "revision_conflict", 4)).mockResolvedValue({ weekly_budget: "500.00", revision: 4 });
    render(<PoliciesScreen userRoles={["buyer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    fireEvent.change(screen.getByLabelText("Importe semanal (€)"), { target: { value: "500" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
    await waitFor(() => expect(put).toHaveBeenCalledWith({ period: "week", scope: "global", amount: "500" }, 3));
    expect((await screen.findAllByRole("alert")).map((a) => a.textContent).join(" ")).toContain("versión 4");
  });

  it("explains a stale second factor on the budget save", async () => {
    vi.spyOn(api, "getPolicyConsole").mockResolvedValue(budgetConsole(0));
    vi.spyOn(api, "putBudgetCap").mockRejectedValue(new ApiError(403, "auth_mfa_stale"));
    render(<PoliciesScreen userRoles={["buyer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    fireEvent.change(screen.getByLabelText("Importe semanal (€)"), { target: { value: "500" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
    expect((await screen.findByRole("alert")).textContent).toContain("segundo factor");
  });

  it("shows where each value of a product comes from, with defaults named as such", async () => {
    vi.spyOn(api, "getPolicy").mockResolvedValue({ ...detail, scope: "product", key: "SYN-0005" });
    vi.spyOn(api, "getEffectivePolicy").mockResolvedValue({
      sku: "SYN-0005", as_of: "2026-11-09",
      rules: {
        service_level: { value: "0.9700", source: "segment", key: "A", revision: 2, valid_from: "2026-11-01" },
        safety_stock_units: { value: null, source: "default", key: null, revision: null, valid_from: null },
        min_units: { value: "4", source: "product", key: "5", revision: 1, valid_from: "2026-11-01" },
        max_units: { value: null, source: "default", key: null, revision: null, valid_from: null },
        replenishment_cadence_days: { value: "7", source: "global", key: "*", revision: 1, valid_from: "2026-11-01" },
      },
    });
    render(<PoliciesScreen userRoles={["viewer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    fireEvent.change(screen.getByLabelText("Ámbito"), { target: { value: "product" } });
    fireEvent.change(screen.getByLabelText("Categoría o SKU"), { target: { value: "SYN-0005" } });
    fireEvent.click(screen.getByRole("button", { name: "Cargar política" }));
    const table = await screen.findByRole("table", { name: "Valores en vigor y su origen" });
    expect(within(table).getAllByText("valor por defecto")).toHaveLength(2);
    expect(within(table).getByText("segmento")).toBeTruthy();
    expect(within(table).getByText("producto")).toBeTruthy();
    expect(within(table).getByText("global")).toBeTruthy();
  });

  it("lists policies whose SKU left the catalogue", async () => {
    vi.spyOn(api, "getPolicyConsole").mockResolvedValue(consoleData({
      purchasing: { ok: true, data: { as_of: "2026-11-09", weekly_budget: null, policies: [{ scope: "product", key: null, revision: 1, in_force: null, orphaned: true }], orphaned: 1 } },
    }));
    render(<PoliciesScreen userRoles={["viewer"]} />);
    expect(await screen.findByText(/Hay 1 política\(s\) de producto cuyo SKU ya no está en el catálogo/)).toBeTruthy();
    expect(screen.getByText(/SKU desconocido/)).toBeTruthy();                 // no ERP id stands in for the missing SKU
  });

  it("removes an override with the revision it read and confirms in Spanish", async () => {
    const clear = vi.spyOn(api, "clearPolicy").mockResolvedValue({ revision: 3 });
    render(<PoliciesScreen userRoles={["viewer", "buyer"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Cargar política" }));
    fireEvent.click(await screen.findByRole("button", { name: /Quitar política/ }));
    await waitFor(() => expect(clear).toHaveBeenCalledWith("global", "*", 2));
    expect((await screen.findByRole("status")).textContent).toContain("Política retirada (versión 3)");
  });

  it("offers no way to remove an override to a viewer", async () => {
    render(<PoliciesScreen userRoles={["viewer"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Cargar política" }));
    await screen.findByLabelText("Nivel de servicio (%)");
    expect(screen.queryByRole("button", { name: /Quitar política/ })).toBeNull();
  });

  it("filters the audit by what changed, the outcome and the dates, and pages through it", async () => {
    const audit = vi.spyOn(api, "getPolicyAudit").mockResolvedValue({ items: [], unavailable: [], total: 120, page: 1, page_size: 50 });
    render(<PoliciesScreen userRoles={["viewer", "buyer", "approver", "admin"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Auditoría de reglas/);
    expect(await screen.findByText("Página 1 de 3 · 120 registros")).toBeTruthy();
    expect(audit).toHaveBeenLastCalledWith({ page: 1 });
    fireEvent.change(screen.getByLabelText("Qué cambió"), { target: { value: "budget" } });
    fireEvent.change(screen.getByLabelText("Resultado", { selector: "#audit-outcome" }), { target: { value: "refused" } });
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-11-01" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-11-09" } });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() => expect(audit).toHaveBeenLastCalledWith({ scope: "budget", outcome: "refused", from: "2026-11-01", to: "2026-11-09", page: 1 }));
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() => expect(audit).toHaveBeenLastCalledWith({ scope: "budget", outcome: "refused", from: "2026-11-01", to: "2026-11-09", page: 2 }));
    expect((screen.getByRole("button", { name: "Anterior" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows the audit tab to admins only", async () => {
    vi.spyOn(api, "getPolicyAudit").mockResolvedValue({
      items: [{ at: "2026-11-09T10:00:00+00:00", actor: "buyer-1", action: "policy.saved", entity_id: "abc", outcome: "accepted" },
              { at: "2026-11-09T11:00:00+00:00", actor: "viewer-1", action: "access.refused", entity_id: "PUT /api/policies/global/*", outcome: "refused", reason_code: "forbidden_missing_role" }],
      unavailable: ["inventory"], total: 2, page: 1, page_size: 50,
    });
    render(<PoliciesScreen userRoles={["viewer", "buyer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    expect(screen.queryByRole("tab", { name: /Auditoría de reglas/ })).toBeNull();
    cleanup();
    render(<PoliciesScreen userRoles={["viewer", "buyer", "approver", "admin"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Auditoría de reglas/);
    const table = await screen.findByRole("table", { name: "Auditoría de reglas de negocio" });
    expect(within(table).getByText("Política guardada")).toBeTruthy();
    expect(within(table).getByText(/denegado \(forbidden_missing_role\)/)).toBeTruthy();
    expect(screen.getByText(/No se pudo leer la auditoría de: inventario/)).toBeTruthy();
  });
});

describe("safety stock section", () => {
  beforeEach(() => {
    vi.spyOn(api, "getRecommendation").mockResolvedValue({ sku: "SYN-0005", safety_stock: 2 });
    vi.spyOn(api, "getStocking").mockResolvedValue({ sku: "SYN-0005", stocking_mode: "standard", min_floor_units: 0, revision: 0 });
    vi.spyOn(api, "getSegmentHistoryBySku").mockResolvedValue({ sku: "SYN-0005", history: [{ changed_at: "2026-11-01T00:00:00Z", abc: "B", xyz: "X", pattern: "smooth", critical: false, reason_key: "first_classification" }] });
  });

  const lookup = async () => {
    render(<PoliciesScreen userRoles={["buyer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Stock de seguridad/);
    fireEvent.change(await screen.findByLabelText("SKU"), { target: { value: "SYN-0005" } });
    fireEvent.click(screen.getByRole("button", { name: "Consultar" }));
  };

  it("shows the recommendation, the category history and creates a request that stays pending", async () => {
    const create = vi.spyOn(api, "createOverride").mockResolvedValue(pending);
    await lookup();
    expect(await screen.findByText("Recomendado por el sistema: 2 unidades")).toBeTruthy();
    expect(screen.getByText(/primera clasificación/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Valor solicitado"), { target: { value: "6" } });
    fireEvent.change(screen.getByLabelText("Motivo"), { target: { value: "proveedor poco fiable" } });
    fireEvent.click(screen.getByRole("button", { name: "Solicitar cambio" }));
    await waitFor(() => expect(create).toHaveBeenCalledWith({ sku: "SYN-0005", field: "safety_stock", requested_value: 6, reason: "proveedor poco fiable" }));
    expect((await screen.findByRole("status")).textContent).toContain("no se aplica hasta que otra persona");
  });

  it("saves the always-stocked mode with its floor and shows the stored revision", async () => {
    const put = vi.spyOn(api, "putStocking").mockResolvedValue({ revision: 1 });
    await lookup();
    fireEvent.change(await screen.findByLabelText("Modo de stock"), { target: { value: "always_stocked" } });
    fireEvent.change(screen.getByLabelText("Unidades mínimas siempre disponibles"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar modo de stock" }));
    await waitFor(() => expect(put).toHaveBeenCalledWith("SYN-0005", { stocking_mode: "always_stocked", min_floor_units: 1 }, 0));
  });

  it("an approver sees the queue with approve and reject; a buyer sees the queue without them", async () => {
    const decide = vi.spyOn(api, "decideOverride").mockResolvedValue({ ...pending, status: "approved" });
    render(<PoliciesScreen userRoles={["viewer", "approver"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Stock de seguridad/);
    expect(await screen.findByText(/recomendado 2, solicitado 6/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Aprobar" }));
    await waitFor(() => expect(decide).toHaveBeenCalledWith("r1", "approve"));
    cleanup();
    render(<PoliciesScreen userRoles={["viewer", "buyer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Stock de seguridad/);
    await screen.findByText(/recomendado 2, solicitado 6/);
    expect(screen.queryByRole("button", { name: "Aprobar" })).toBeNull();
  });

  it("explains a self-approval refusal in Spanish", async () => {
    vi.spyOn(api, "decideOverride").mockRejectedValue(new ApiError(403, "policy_override_self_approval"));
    render(<PoliciesScreen userRoles={["approver"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Stock de seguridad/);
    fireEvent.click(await screen.findByRole("button", { name: "Aprobar" }));
    expect((await screen.findByRole("alert")).textContent).toContain("No puede aprobar su propia solicitud");
  });
});

describe("demand and forecast sections", () => {
  it("adds and deactivates an exclusion and edits the censoring rule", async () => {
    const add = vi.spyOn(api, "addExclusion").mockResolvedValue({ id: 8 });
    const toggle = vi.spyOn(api, "toggleExclusion").mockResolvedValue({});
    const rule = vi.spyOn(api, "putCensoringRule").mockResolvedValue({});
    render(<PoliciesScreen userRoles={["buyer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Demanda y criticidad/);
    expect(await screen.findByText(/todos los productos · cierre del negocio/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Desactivar" }));
    await waitFor(() => expect(toggle).toHaveBeenCalledWith(7, false, 1));          // the revision the editor read
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-11-20" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-11-22" } });
    fireEvent.click(screen.getByRole("button", { name: "Añadir exclusión" }));
    expect((await screen.findAllByRole("alert")).map((a) => a.textContent).join(" ")).toContain("Elija un motivo de la lista");     // free text is no longer accepted
    expect(add).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Motivo"), { target: { value: "promotion" } });
    fireEvent.click(screen.getByRole("button", { name: "Añadir exclusión" }));
    await waitFor(() => expect(add).toHaveBeenCalledWith({ sku: null, from_day: "2026-11-20", to_day: "2026-11-22", reason_code: "promotion" }));
    fireEvent.change(screen.getByLabelText(/Días seguidos sin stock/), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar regla" }));
    await waitFor(() => expect(rule).toHaveBeenCalledWith("min_zero_stock_days", 3, 0));
  });

  it("sets the censoring rule for a segment and for a product by SKU, and lists the saved scopes", async () => {
    vi.spyOn(api, "getPolicyConsole").mockResolvedValue(consoleData({
      demand: { ok: true, data: { exclusions: [], rules: [
        { rule: "min_zero_stock_days", scope: "global", key: "*", value: 1, min: 1, max: 30, default: 1, revision: 2 },
        { rule: "min_zero_stock_days", scope: "segment", key: "A", value: 3, min: 1, max: 30, default: 1, revision: 1 },
      ] } },
    }));
    const rule = vi.spyOn(api, "putCensoringRule").mockResolvedValue({});
    render(<PoliciesScreen userRoles={["buyer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Demanda y criticidad/);
    expect(await screen.findByLabelText(/Días seguidos sin stock.*\(clase A\)/)).toHaveProperty("value", "3");
    fireEvent.change(screen.getByLabelText(/Días seguidos sin stock.*\(clase A\)/), { target: { value: "4" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Guardar regla" })[1]!);
    await waitFor(() => expect(rule).toHaveBeenCalledWith("min_zero_stock_days", 4, 1, { scope: "segment", key: "A" }));       // its own revision, not the global one
    fireEvent.change(screen.getByLabelText("Ámbito de la regla"), { target: { value: "product" } });
    fireEvent.change(screen.getByLabelText("SKU del producto"), { target: { value: "SYN-0005" } });
    fireEvent.change(screen.getByLabelText("Valor de la regla (días)"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar regla para este ámbito" }));
    await waitFor(() => expect(rule).toHaveBeenLastCalledWith("min_zero_stock_days", 2, 0, { scope: "product", key: "SYN-0005" }));
  });

  it("asks for the segment or SKU before saving a scoped rule", async () => {
    const rule = vi.spyOn(api, "putCensoringRule").mockResolvedValue({});
    render(<PoliciesScreen userRoles={["buyer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Demanda y criticidad/);
    fireEvent.change(await screen.findByLabelText("Valor de la regla (días)"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar regla para este ámbito" }));
    expect((await screen.findAllByRole("alert")).map((a) => a.textContent).join(" ")).toContain("segmento o el SKU");
    expect(rule).not.toHaveBeenCalled();
  });

  it("changes clinical criticality only through an explicit toggle", async () => {
    vi.spyOn(api, "getCriticality").mockResolvedValue({ products: [{ sku: "SYN-0005", name: "Producto Sintético", clinical_critical: false, variants: 1 }] });
    const set = vi.spyOn(api, "setCriticality").mockResolvedValue({});
    render(<PoliciesScreen userRoles={["buyer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Demanda y criticidad/);
    fireEvent.click(await screen.findByRole("button", { name: "Cargar política" }));
    fireEvent.click(await screen.findByLabelText(/Crítico: Producto Sintético/));
    await waitFor(() => expect(set).toHaveBeenCalledWith("SYN-0005", true));
  });

  it("edits a forecast parameter with its revision and refuses a non-number", async () => {
    const put = vi.spyOn(api, "putParameter").mockResolvedValue({ revision: 1 });
    render(<PoliciesScreen userRoles={["buyer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Parámetros de previsión/);
    const input = await screen.findByLabelText("Plazo de entrega considerado (días)");
    fireEvent.change(input, { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: /Guardar parámetro: Plazo/ }));
    expect((await screen.findByRole("alert")).textContent).toContain("no es un número válido");
    fireEvent.change(input, { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: /Guardar parámetro: Plazo/ }));
    await waitFor(() => expect(put).toHaveBeenCalledWith("lead_time", "10", 0));
  });

  it("hides every edit control from a viewer", async () => {
    render(<PoliciesScreen userRoles={["viewer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Parámetros de previsión/);
    await screen.findByLabelText("Plazo de entrega considerado (días)");
    expect(screen.queryByRole("button", { name: /Guardar parámetro/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Recalcular previsión ahora" })).toBeNull();
  });
});
