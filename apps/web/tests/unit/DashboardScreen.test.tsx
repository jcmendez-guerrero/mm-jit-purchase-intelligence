// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { api, DashOverview, type Indicator, type IndicatorKey } from "../../src/api/client";
import { DashboardScreen } from "../../src/features/dashboard/DashboardScreen";
import "../../src/i18n";

beforeAll(() => {
  class RO {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  (globalThis as unknown as { ResizeObserver: typeof RO }).ResizeObserver = RO;
});

const today = new Date().toISOString().slice(0, 10);
const fresh = (state: Indicator["freshness"]["state"] = "ok"): Indicator["freshness"] => ({ source: "inventory_snapshot", refreshed_at: `${today}T08:00:00Z`, origin: "erp_sync", state, stale_after_hours: 48 });
const UNITS: Record<IndicatorKey, Indicator["unit"]> = { stock_value: "EUR", coverage_days: "days", demand: "units", forecast: "units", stockout_risk: "count", expiry_exposure: "EUR", capital_tied_up: "EUR", purchasing_budget: "EUR", wape: "percent", bias: "percent" };
const VALUES: Record<IndicatorKey, string> = { stock_value: "1234.50", coverage_days: "5.75", demand: "239", forecast: "98.00", stockout_risk: "3", expiry_exposure: "20.00", capital_tied_up: "1264.50", purchasing_budget: "250.00", wape: "25.00", bias: "-5.00" };
const indicator = (key: IndicatorKey, over: Partial<Indicator> = {}): Indicator => ({ key, value: VALUES[key], unit: UNITS[key], state: "ok", basis: "dashboard.basis.lot_cost", definition_key: `dashboard.def.${key}`, freshness: fresh(), ...over });
const KEYS = Object.keys(UNITS) as IndicatorKey[];
const indicators = (over: Partial<Record<IndicatorKey, Partial<Indicator>>> = {}): Indicator[] => KEYS.map((k) => indicator(k, { ...(k === "stock_value" ? { incomplete_count: 1 } : {}), ...over[k] }));
const overview = (over: Partial<DashOverview> = {}): DashOverview => ({
  indicators: indicators(),
  summary: {
    ok: true,
    data: {
      day: today, inventory_value: "1234.50", valued_with_estimate: 2, unvalued_lots: 1, value_basis: "lot_acquisition_cost", expiring_value: "20.00", stockout_risk: 3, expiry_risk: 1,
      coverage_days_avg: "5.75", variants_without_demand: 4, coverage_basis: { forecast: 6, actual_90d: 9 }, variant_count: 15, forecast_available: true,
    },
  },
  trend: { ok: true, data: { from: "2026-09-10", to: today, estimated: [], series: [{ day: "2026-11-01", actual: 3, censored_rows: 0, kind: "actual_erp" }, { day: "2026-11-02", actual: 9, censored_rows: 0, kind: "actual_erp" }] } },
  abc_xyz: { ok: true, data: { cells: [{ abc: "A", xyz: "X", variant_count: 4, value: "100.00" }, { abc: "B", xyz: "Y", variant_count: 6, value: "50.00" }] } },
  risks: { ok: true, data: [{ variant_id: 7, risk_type: "stockout", explanation_key: "risk.stockout.out_of_stock", params: {} }] },
  options: { ok: true, data: { warehouses: [{ id: 1, name: "Almacén sintético A" }, { id: 2, name: "Almacén sintético B" }], categories: [{ id: "A", kind: "demand_group" }, { id: "critical", kind: "clinical_critical" }], family_available: false } },
  accuracy: { ok: true, data: { run_id: "r1", window_days: 7, metrics: { all: { wape: "0.2500", bias: "-0.0500", stockout_rate: "0.1000" }, A: { stockout_rate: "1.0000" } } } },
  spend: { ok: true, data: { proposal_id: "p1", week: "2026-W46", status: "draft", total: "300.00", by_supplier: [], budget: "250.00", over_budget: true } },
  suppliers: { ok: true, data: [{ id: "s1", name: "Proveedor Sintético A" }] },
  ...over,
});

beforeEach(() => {
  vi.spyOn(api, "getDashboardOverview").mockResolvedValue(overview());
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("DashboardScreen", () => {
  it("offers the product family filter only when families exist, and sends the choice with the other filters", async () => {
    const spy = vi.spyOn(api, "getDashboardOverview").mockResolvedValue(overview());
    const first = render(<DashboardScreen />);
    await screen.findByRole("heading", { name: "Valor del stock" });
    expect(screen.queryByLabelText("Familia de producto")).toBeNull();                       // none synchronised: no empty filter
    first.unmount();
    const withFamilies = overview({
      options: { ok: true, data: { warehouses: [{ id: 1, name: "Almacén sintético A" }], categories: [{ id: "A", kind: "demand_group" }], family_available: true, families: [{ id: "Familia sintética A" }, { id: "Familia sintética B" }] } },
    });
    spy.mockResolvedValue(withFamilies);
    render(<DashboardScreen />);
    fireEvent.change(await screen.findByLabelText("Familia de producto"), { target: { value: "Familia sintética B" } });
    await waitFor(() => expect(spy).toHaveBeenLastCalledWith(expect.objectContaining({ family: "Familia sintética B" })));
  });

  it("shows the ten indicators in Spanish with their period, and the estimated-cost count", async () => {
    const { container } = render(<DashboardScreen />);
    await screen.findByRole("heading", { name: "Valor del stock" });
    for (const name of ["Valor del stock", "Cobertura", "Demanda", "Previsión", "Riesgo de rotura", "Exposición a caducidad", "Capital inmovilizado", "Presupuesto de compras", "Error de previsión (WAPE)", "Sesgo de la previsión"]) {
      expect(screen.getByRole("heading", { name })).toBeTruthy();
    }
    const card = (name: string) => screen.getByRole("heading", { name }).closest("article")!;
    expect(card("Valor del stock").textContent).toContain("1.234,50");
    expect(card("Valor del stock").textContent).toContain("1 registros no incluidos");
    expect(card("Cobertura").textContent).toContain("5,8 días");
    expect(card("Exposición a caducidad").textContent).toContain("20,00");
    expect(container.textContent).toContain("2 lotes valorados con un coste estimado");
    expect(container.textContent).toMatch(/Periodo: \d{2}\/\d{2}\/\d{4} – \d{2}\/\d{2}\/\d{4}/);
  });

  it("fills the filter options from the data and says the product family is pending", async () => {
    render(<DashboardScreen />);
    const wh = await screen.findByLabelText("Almacén");
    expect(within(wh).getAllByRole("option").map((o) => o.textContent)).toEqual(["Todos los almacenes (visión global)", "Almacén sintético A", "Almacén sintético B"]);
    expect(within(screen.getByLabelText("Categoría")).getAllByRole("option").map((o) => o.textContent)).toEqual(["Todas las categorías", "Grupo A (mayor valor)", "Clínicamente crítico"]);
    expect(screen.getByText(/La familia de producto del ERP aparecerá aquí/)).toBeTruthy();
  });

  it("reloads every card with the chosen filters", async () => {
    const spy = vi.spyOn(api, "getDashboardOverview");
    render(<DashboardScreen />);
    await screen.findByLabelText("Almacén");
    fireEvent.change(screen.getByLabelText("Almacén"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Categoría"), { target: { value: "critical" } });
    fireEvent.change(screen.getByLabelText("Periodo"), { target: { value: "90" } });
    await waitFor(() => expect(spy).toHaveBeenLastCalledWith({ warehouse_id: 2, category: "critical", days: 90 }));
  });

  it("gives every chart a text summary and a table alternative", async () => {
    render(<DashboardScreen />);
    expect(await screen.findByText(/12 unidades en 2 días; máximo 9/)).toBeTruthy();
    const toggles = screen.getAllByRole("button", { name: "Ver como tabla" });
    expect(toggles).toHaveLength(2);
    fireEvent.click(toggles[0]!);
    const table = screen.getByRole("table", { name: "Demanda diaria real y previsión" });
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: "Ver como gráfico" }));
    expect(screen.queryByRole("table", { name: "Demanda diaria real y previsión" })).toBeNull();
  });

  it("labels the warehouse view as informational and says the proposal and forecast stay company-wide", async () => {
    render(<DashboardScreen />);
    await screen.findByRole("heading", { name: "Valor del stock" });
    expect(screen.queryByText(/Vista informativa por almacén/)).toBeNull();                  // company-wide: nothing to qualify
    fireEvent.change(screen.getByLabelText("Almacén"), { target: { value: "2" } });
    const note = await screen.findByText(/Vista informativa por almacén/);
    expect(note.textContent).toContain("única para toda la empresa");
    expect(note.textContent).toContain("no cambian con el filtro de almacén");
    fireEvent.change(screen.getByLabelText("Almacén"), { target: { value: "all" } });
    await waitFor(() => expect(screen.queryByText(/Vista informativa por almacén/)).toBeNull());
  });

  const withForecast = (estimated: Array<{ day: string; mean: string; upper: string; kind: string }>, basis: object) => {
    const base = overview();
    if (!base.trend.ok || !base.trend.data) throw new Error("fixture");
    return overview({ trend: { ok: true, data: { ...base.trend.data, estimated, estimated_basis: basis as never } } });
  };
  const days = ["2026-11-10", "2026-11-11"].map((day) => ({ day, mean: "3.50", upper: "5.00", kind: "forecast" }));

  it("shows the forecast and its uncertainty apart from actual demand, with a table alternative and the seed note", async () => {
    vi.spyOn(api, "getDashboardOverview").mockResolvedValue(withForecast(days, { variants: 12, seed_assisted: 3, reason: null, upper_level: "0.95" }));
    render(<DashboardScreen />);
    expect(await screen.findByText(/Previsión para los próximos 2 días: 3,5 unidades al día de media y hasta 5,0 con un 95 % de probabilidad/)).toBeTruthy();
    expect(screen.getByText(/Previsión de 12 productos previsibles/)).toBeTruthy();
    expect(screen.getByText(/3 de ellos apoyan su previsión en datos importados/)).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: "Ver como tabla" })[0]!);
    const table = screen.getByRole("table", { name: "Demanda diaria real y previsión" });
    const heads = within(table).getAllByRole("columnheader").map((h) => h.textContent);
    expect(heads).toEqual(expect.arrayContaining(["Unidades reales", "Previsión (media)", "Previsión (límite superior)"]));
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(5);                                                             // header, 2 actual days, 2 forecast days
    expect(within(rows[3]!).getAllByRole("cell")[1]!.textContent).toBe("—");                  // a forecast day has no actual units
    expect(within(rows[1]!).getAllByRole("cell")[2]!.textContent).toBe("—");                  // an actual day has no forecast
    expect(within(rows[3]!).queryByRole("button")).toBeNull();                                // nothing to drill into on a future day
  });

  it("says so when there is no forecast, or when the warehouse filter hides it", async () => {
    vi.spyOn(api, "getDashboardOverview").mockResolvedValue(withForecast([], { variants: 0, seed_assisted: 0, reason: "no_forecast", upper_level: "0.95" }));
    const first = render(<DashboardScreen />);
    expect(await screen.findByText(/No hay previsión disponible: se muestran solo las ventas reales del ERP/)).toBeTruthy();
    first.unmount();
    vi.spyOn(api, "getDashboardOverview").mockResolvedValue(withForecast([], { variants: 0, seed_assisted: 0, reason: "company_wide_only", upper_level: "0.95" }));
    render(<DashboardScreen />);
    expect(await screen.findByText(/La previsión es global de la empresa/)).toBeTruthy();
  });

  it("shows the proposed spend against the budget and the forecast accuracy by group", async () => {
    render(<DashboardScreen />);
    const spend = await screen.findByLabelText("Gasto propuesto");
    expect(spend.textContent).toContain("300,00");
    expect(spend.textContent).toContain("Propuesta de la semana 2026-W46 (Borrador)");
    expect(spend.textContent).toContain("Presupuesto semanal: 250,00");
    expect(spend.textContent).toContain("Supera el presupuesto semanal");
    const acc = screen.getByRole("table", { name: "Precisión de la previsión" });
    expect(acc.textContent).toContain("25,0");
    expect(within(acc).getByText("Grupo A")).toBeTruthy();
    expect(within(acc).getAllByText("—").length).toBeGreaterThan(0);                           // a metric that was not computed is not invented
  });

  it("explains empty accuracy and sends the supplier filter on, noting it only affects spend", async () => {
    const spy = vi.spyOn(api, "getDashboardOverview").mockResolvedValue(overview({ accuracy: { ok: true, data: { run_id: null, window_days: 7, metrics: {} } } }));
    render(<DashboardScreen />);
    expect(await screen.findByText(/Todavía no hay una previsión con siete días/)).toBeTruthy();
    expect(screen.getByText(/El proveedor filtra el gasto propuesto/)).toBeTruthy();
    await waitFor(() => expect(within(screen.getByLabelText("Proveedor")).getAllByRole("option")).toHaveLength(2));
    fireEvent.change(screen.getByLabelText("Proveedor"), { target: { value: "s1" } });
    await waitFor(() => expect(spy).toHaveBeenLastCalledWith(expect.objectContaining({ supplier_id: "s1" })));
  });

  it("degrades one card without hiding the others", async () => {
    const failed = Object.fromEntries(KEYS.slice(0, 7).map((k) => [k, { value: null, state: "error" as const, freshness: fresh("error") }]));
    vi.spyOn(api, "getDashboardOverview").mockResolvedValue(overview({ indicators: indicators(failed), summary: { ok: false, error: "downstream_unavailable" }, trend: { ok: false, error: "downstream_unavailable" } }));
    render(<DashboardScreen />);
    await screen.findByRole("heading", { name: "Valor del stock" });
    expect(screen.getAllByText(/No se pudo calcular/).length).toBe(7);
    expect(screen.getAllByText(/No se pudo cargar este indicador/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("table", { name: "Tabla de riesgos detectados" })).toBeTruthy();
    expect(screen.getByText(/Variantes por grupo ABC\/XYZ/)).toBeTruthy();
  });

  it("shows an empty state when nothing is at risk and a stale warning for old data", async () => {
    const old = overview({ risks: { ok: true, data: [] }, indicators: indicators({ stock_value: { state: "stale", freshness: fresh("stale") } }) });
    old.summary.data!.day = "2020-01-01";
    vi.spyOn(api, "getDashboardOverview").mockResolvedValue(old);
    render(<DashboardScreen />);
    expect(await screen.findByText(/No se detectaron riesgos de inventario hoy/)).toBeTruthy();
    expect(screen.getByText(/la sincronización con el ERP puede estar retrasada/)).toBeTruthy();
  });

  it("shows the whole-screen error when the BFF itself fails", async () => {
    vi.spyOn(api, "getDashboardOverview").mockRejectedValue(new Error("x"));
    render(<DashboardScreen />);
    expect((await screen.findByRole("alert")).textContent).toContain("Ha ocurrido un error");
  });

  it("opens the product detail from an alert and closes it", async () => {
    vi.spyOn(api, "getVariant").mockResolvedValue({
      variant: { id: 7, sku: "SYN-7", name: "Variante sintética", pack_size: 1, uom: "u", product: { id: 1 } }, stock: { on_hand: 0, available: 0, reserved: 0, as_of: today },
      demand: [{ day: "2026-11-01", warehouse_id: 1, qty: 3, censored: true }], flows: [], history: [], history_reconciled: false,
      segment: { abc: "A", xyz: "X", pattern: "smooth", forecast_eligible: false, reasons: ["new"], metrics: {} },
    });
    render(<DashboardScreen />);
    fireEvent.click(await screen.findByRole("button", { name: "Ver detalle" }));
    const panel = await screen.findByLabelText("Detalle de la variante 7");
    expect(panel.textContent).toContain("SYN-7");
    expect(panel.textContent).toContain("Sin previsión estadística");
    expect(panel.textContent).toContain("día con stock agotado");
    expect(panel.textContent).toContain("historial de stock sin reconciliar");
    fireEvent.click(screen.getByRole("button", { name: "Cerrar detalle" }));
    await waitFor(() => expect(screen.queryByLabelText("Detalle de la variante 7")).toBeNull());
  });

  const detail = (risks: Array<{ risk_type: string; explanation_key: string; params: Record<string, unknown> }>) => ({
    variant: { id: 7, sku: "SYN-7", name: "Variante sintética", pack_size: 1, uom: "u", product: { id: 1 } }, stock: { on_hand: 2, available: 2, reserved: 0, as_of: today },
    demand: [{ day: "2026-11-01", warehouse_id: 1, qty: 3, censored: false }], flows: [], history: [], history_reconciled: true, risks,
    segment: { abc: "A", xyz: "X", pattern: "smooth", forecast_eligible: true, reasons: [], metrics: {} },
  });

  it("shows a product's forecast with its uncertainty apart from actual demand, and its own risk reasons", async () => {
    vi.spyOn(api, "getVariant").mockResolvedValue(detail([{ risk_type: "stockout", explanation_key: "risk.stockout.imminent", params: { sku: "SYN-7", available: 2 } }]));
    vi.spyOn(api, "getForecastBasis").mockResolvedValue({ run_id: "r1", variant_id: 7, eligible: true, policy: "minmax_poisson", seed_used: true, upper_level: "0.95",
      horizons: [{ days: 7, mean: 10.5, upper: 14 }, { days: 14, mean: 21, upper: 27.5 }] });
    render(<DashboardScreen />);
    fireEvent.click(await screen.findByRole("button", { name: "Ver detalle" }));
    const panel = await screen.findByLabelText("Detalle de la variante 7");
    const table = await within(panel).findByRole("table", { name: "Previsión estadística (no son ventas reales)" });
    const rows = within(table).getAllByRole("row").map((r) => within(r).queryAllByRole("cell").map((c) => c.textContent));
    expect(rows).toEqual([[], ["7", "10,5", "14,0"], ["14", "21,0", "27,5"]]);
    expect(panel.textContent).toContain("Se muestra aparte de la demanda real");
    expect(panel.textContent).toContain("Previsión con datos importados");                 // the imported-estimates note stays
    expect(within(panel).getByText("Riesgos de este producto")).toBeTruthy();
    expect(within(panel).getByText("Riesgo de rotura de stock")).toBeTruthy();
    expect(within(panel).getByRole("table", { name: "Demanda reciente (datos reales del ERP)" })).toBeTruthy();
  });

  it("shows a product's category history with the reason for each change, or says there is none", async () => {
    vi.spyOn(api, "getVariant").mockResolvedValue(detail([]));
    vi.spyOn(api, "getForecastBasis").mockRejectedValue(new Error("404"));
    const hist = vi.spyOn(api, "getSegmentHistory").mockResolvedValue({ variant_id: 7, history: [
      { changed_at: "2026-11-05T00:00:00Z", abc: "A", xyz: "X", pattern: "smooth", critical: true, reason_key: "criticality_changed" },
      { changed_at: "2026-10-01T00:00:00Z", abc: "B", xyz: "X", pattern: "smooth", critical: false, reason_key: "first_classification" }] });
    const first = render(<DashboardScreen />);
    fireEvent.click(await screen.findByRole("button", { name: "Ver detalle" }));
    const panel = await screen.findByLabelText("Detalle de la variante 7");
    expect(await within(panel).findByText(/ABC A · XYZ X · smooth · clínicamente crítico · cambió la criticidad \(manual\)/)).toBeTruthy();
    expect(within(panel).getByText(/ABC B · XYZ X · smooth · primera clasificación/)).toBeTruthy();
    expect(within(panel).getByText("Historial de categoría")).toBeTruthy();
    first.unmount();
    hist.mockResolvedValue({ variant_id: 7, history: [] });
    render(<DashboardScreen />);
    fireEvent.click(await screen.findByRole("button", { name: "Ver detalle" }));
    expect(await screen.findByText("Todavía no hay historial de categoría.")).toBeTruthy();
  });

  it("says why there is no forecast table for a min/max product or when no forecast exists, and when no risk was found", async () => {
    vi.spyOn(api, "getVariant").mockResolvedValue(detail([]));
    const basis = vi.spyOn(api, "getForecastBasis").mockResolvedValue({ run_id: "r1", variant_id: 7, eligible: false, policy: "minmax_conservative", seed_used: false, horizons: [] });
    const first = render(<DashboardScreen />);
    fireEvent.click(await screen.findByRole("button", { name: "Ver detalle" }));
    const panel = await screen.findByLabelText("Detalle de la variante 7");
    await waitFor(() => expect(panel.textContent).toContain("mínimos y máximos conservadores"));
    expect(panel.textContent).toContain("No se ha detectado ningún riesgo en este producto");
    first.unmount();
    basis.mockRejectedValue(new Error("404"));
    render(<DashboardScreen />);
    fireEvent.click(await screen.findByRole("button", { name: "Ver detalle" }));
    expect((await screen.findByLabelText("Detalle de la variante 7")).textContent).toContain("Todavía no hay previsión para este producto");
  });
});


describe("DashboardScreen when the role may not see money", () => {
  it("says so instead of showing a broken figure, and keeps the counts", async () => {
    const base = overview();
    const summary = { ...base.summary.data! };
    delete summary.inventory_value;
    delete summary.expiring_value;
    summary.hidden_by_role = ["inventory_value", "expiring_value"];
    const hide = { value: null, state: "hidden_by_role" as const };
    vi.spyOn(api, "getDashboardOverview").mockResolvedValue(overview({
      indicators: indicators({ stock_value: hide, expiry_exposure: hide, capital_tied_up: hide, purchasing_budget: hide }),
      summary: { ok: true, data: summary },
      abc_xyz: { ok: true, data: { cells: [{ abc: "A", xyz: "X", variant_count: 4 }] } },
      spend: { ok: false, error: "hidden_by_role" },
    }));
    const { container } = render(<DashboardScreen />);
    const card = async (name: string) => (await screen.findByRole("heading", { name })).closest("article")!;
    expect((await card("Valor del stock")).textContent).toContain("No disponible para tu rol");
    expect((await card("Exposición a caducidad")).textContent).toContain("No disponible para tu rol");
    expect((await card("Capital inmovilizado")).textContent).toContain("No disponible para tu rol");
    expect((await card("Riesgo de rotura")).textContent).toContain("3");
    expect(screen.getByLabelText("Gasto propuesto").textContent).toContain("No disponible para tu rol");
    expect(container.textContent).not.toMatch(/undefined|NaN/);
  });
});
