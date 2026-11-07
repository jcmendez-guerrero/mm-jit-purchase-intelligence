// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { api, DashOverview } from "../../src/api/client";
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
const overview = (over: Partial<DashOverview> = {}): DashOverview => ({
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
  it("shows the four KPIs in Spanish with their basis and the estimated and unvalued counts", async () => {
    render(<DashboardScreen />);
    const value = await screen.findByLabelText("Valor del inventario");
    expect(value.textContent).toContain("1.234,50");
    expect(value.textContent).toContain("A coste de adquisición por lote");
    expect(value.textContent).toContain("2 lotes valorados con un coste estimado");
    expect(value.textContent).toContain("1 lotes sin coste");
    const cov = screen.getByLabelText("Cobertura media");
    expect(cov.textContent).toContain("5,8 días");
    expect(cov.textContent).toContain("previsión en 6 variantes, demanda real de 90 días en 9");
    expect(screen.getByLabelText("Variantes con riesgo de rotura").textContent).toContain("3");
    expect(screen.getByLabelText("Valor que caduca en 60 días").textContent).toContain("20,00");
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
    const table = screen.getByRole("table", { name: "Demanda diaria real" });
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: "Ver como gráfico" }));
    expect(screen.queryByRole("table", { name: "Demanda diaria real" })).toBeNull();
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
    vi.spyOn(api, "getDashboardOverview").mockResolvedValue(overview({ summary: { ok: false, error: "downstream_unavailable" }, trend: { ok: false, error: "downstream_unavailable" } }));
    render(<DashboardScreen />);
    await screen.findByLabelText("Valor del inventario");
    expect(screen.getAllByText(/No se pudo cargar este indicador/).length).toBeGreaterThanOrEqual(4);
    expect(screen.getByRole("table", { name: "Tabla de riesgos detectados" })).toBeTruthy();
    expect(screen.getByText(/Variantes por grupo ABC\/XYZ/)).toBeTruthy();
  });

  it("shows an empty state when nothing is at risk and a stale warning for old data", async () => {
    const old = overview({ risks: { ok: true, data: [] } });
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
});
