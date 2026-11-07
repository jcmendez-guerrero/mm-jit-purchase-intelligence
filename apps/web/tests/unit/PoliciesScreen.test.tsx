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
      exclusions: [{ id: 7, variant_id: null, from_day: "2026-10-03", to_day: "2026-10-05", reason: "cierre por obras", active: true, revision: 1 }],
      rules: [{ rule: "min_zero_stock_days", value: 1, min: 1, max: 30, default: 1 }],
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

const pending: OverrideRequest = { id: "r1", variant_id: 5, field: "safety_stock", recommended_value: 2, requested_value: 6, reason: "proveedor poco fiable", status: "pending", requested_by: "buyer-1", decided_by: null, recommendation_changed: false };

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
    const preview = vi.spyOn(api, "previewPolicy").mockResolvedValue({ as_of: "2026-11-09", affected_count: 1, affected: [{ variant_id: 5, qty_before: 4, qty_after: 9 }], spend_before: "100.00", spend_after: "190.00", spend_delta: "90.00", saved: false });
    const put = vi.spyOn(api, "putPolicy").mockResolvedValue({ revision: 3 });
    render(<PoliciesScreen userRoles={["buyer"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Cargar política" }));
    fireEvent.change(await screen.findByLabelText("Nivel de servicio (%)"), { target: { value: "99" } });
    fireEvent.click(screen.getByRole("button", { name: "Previsualizar efecto" }));
    expect(await screen.findByText(/Productos afectados: 1/)).toBeTruthy();
    expect(screen.getByText(/Variante 5: 4 → 9 unidades/)).toBeTruthy();
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

describe("safety stock section", () => {
  beforeEach(() => {
    vi.spyOn(api, "getRecommendation").mockResolvedValue({ variant_id: 5, safety_stock: 2 });
    vi.spyOn(api, "getStocking").mockResolvedValue({ variant_id: 5, stocking_mode: "standard", min_floor_units: 0, revision: 0 });
    vi.spyOn(api, "getSegmentHistory").mockResolvedValue({ variant_id: 5, history: [{ changed_at: "2026-11-01T00:00:00Z", abc: "B", xyz: "X", pattern: "smooth", critical: false, reason_key: "first_classification" }] });
  });

  const lookup = async () => {
    render(<PoliciesScreen userRoles={["buyer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Stock de seguridad/);
    fireEvent.change(await screen.findByLabelText("Variante"), { target: { value: "5" } });
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
    await waitFor(() => expect(create).toHaveBeenCalledWith({ variant_id: 5, field: "safety_stock", requested_value: 6, reason: "proveedor poco fiable" }));
    expect((await screen.findByRole("status")).textContent).toContain("no se aplica hasta que otra persona");
  });

  it("saves the always-stocked mode with its floor and shows the stored revision", async () => {
    const put = vi.spyOn(api, "putStocking").mockResolvedValue({ revision: 1 });
    await lookup();
    fireEvent.change(await screen.findByLabelText("Modo de stock"), { target: { value: "always_stocked" } });
    fireEvent.change(screen.getByLabelText("Unidades mínimas siempre disponibles"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar modo de stock" }));
    await waitFor(() => expect(put).toHaveBeenCalledWith(5, { stocking_mode: "always_stocked", min_floor_units: 1 }, 0));
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
    expect(await screen.findByText(/cierre por obras/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Desactivar" }));
    await waitFor(() => expect(toggle).toHaveBeenCalledWith(7, false));
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-11-20" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-11-22" } });
    fireEvent.change(screen.getByLabelText("Motivo"), { target: { value: "promoción" } });
    fireEvent.click(screen.getByRole("button", { name: "Añadir exclusión" }));
    await waitFor(() => expect(add).toHaveBeenCalledWith({ variant_id: null, from_day: "2026-11-20", to_day: "2026-11-22", reason: "promoción" }));
    fireEvent.change(screen.getByLabelText(/Días seguidos sin stock/), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar regla" }));
    await waitFor(() => expect(rule).toHaveBeenCalledWith("min_zero_stock_days", 3));
  });

  it("changes clinical criticality only through an explicit toggle", async () => {
    vi.spyOn(api, "getCriticality").mockResolvedValue({ products: [{ product_id: 5, name: "Producto Sintético", clinical_critical: false, variants: 1 }] });
    const set = vi.spyOn(api, "setCriticality").mockResolvedValue({});
    render(<PoliciesScreen userRoles={["buyer"]} />);
    await screen.findByText(/Presupuesto semanal vigente/);
    tab(/Demanda y criticidad/);
    fireEvent.click(await screen.findByRole("button", { name: "Cargar política" }));
    fireEvent.click(await screen.findByLabelText(/Crítico: Producto Sintético/));
    await waitFor(() => expect(set).toHaveBeenCalledWith(5, true));
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
