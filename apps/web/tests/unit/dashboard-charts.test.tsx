// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { api, ChartSeries } from "../../src/api/client";
import { AnalyticChart } from "../../src/features/dashboard/charts/AnalyticChart";
import { ChartsSection } from "../../src/features/dashboard/charts/ChartsSection";
import "../../src/i18n";

beforeAll(() => {
  class RO {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  (globalThis as unknown as { ResizeObserver: typeof RO }).ResizeObserver = RO;
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const expiry: ChartSeries = {
  key: "expiry_bands",
  title_key: "dashboard.chart.title.expiry_bands",
  summary_params: { horizon_days: 60 },
  columns: ["band", "products", "value"],
  rows: [["expired", 0, "0.00"], ["d0_30", 1, "20.00"], ["d31_60", 1, "40.00"]],
  state: "ok",
};
const history = (over: Partial<ChartSeries> = {}): ChartSeries => ({
  key: "stock_value_history",
  title_key: "dashboard.chart.title.stock_value_history",
  summary_params: {},
  columns: ["day", "value"],
  rows: [["2026-11-08", "90.00"], ["2026-11-09", "100.00"]],
  range_available: { from: "2026-10-01", to: "2026-11-09" },
  state: "ok",
  ...over,
});

describe("AnalyticChart", () => {
  it("has a title, a text summary and a table with exactly the rows of the chart", () => {
    render(<AnalyticChart chart={expiry} onRetry={() => {}} />);
    expect(screen.getByRole("heading", { name: "Valor que caduca por tramo" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ver como tabla" }));
    const table = screen.getByRole("table", { name: "Valor que caduca por tramo" });
    const body = within(table).getAllByRole("row").slice(1);
    expect(body.map((r) => within(r).getAllByRole("cell").map((c) => (c.textContent ?? "").replace(/\u00a0/g, " ")))).toEqual([
      ["Caducado", "0", "0,00 €"],
      ["0 a 30 días", "1", "20,00 €"],
      ["31 a 60 días", "1", "40,00 €"],
    ]);
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Tramo", "Productos", "Valor"]);
  });

  it("opens the drill-down of an expiry band from the table, by keyboard-reachable button", () => {
    const onDrill = vi.fn();
    render(<AnalyticChart chart={expiry} onRetry={() => {}} onDrillBand={onDrill} />);
    fireEvent.click(screen.getByRole("button", { name: "Ver como tabla" }));
    fireEvent.click(screen.getByRole("button", { name: "Ver productos: 0 a 30 días" }));
    expect(onDrill).toHaveBeenCalledWith("d0_30");
  });

  it("shows a role without cost access a table with no money column", () => {
    render(<AnalyticChart chart={{ ...expiry, columns: ["band", "products"], rows: [["expired", 0], ["d0_30", 1], ["d31_60", 1]] }} onRetry={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Ver como tabla" }));
    expect(screen.queryByText("Valor")).toBeNull();
    expect(screen.getByRole("table").textContent).not.toMatch(/€/);
  });

  it("says why there is no data instead of drawing an empty chart, and states the available history", () => {
    const { container } = render(<AnalyticChart chart={history({ rows: [], state: "no_data", summary_params: { reason: "range_outside_history" } })} onRetry={() => {}} />);
    expect(container.textContent).toMatch(/queda fuera del histórico disponible/);
    expect(container.textContent).toMatch(/01\/10\/2026/);
    expect(screen.queryByRole("button", { name: "Ver como tabla" })).toBeNull();
    expect(container.querySelector("svg")).toBeNull();
  });

  it("tells a role without cost access that its role cannot see the amounts", () => {
    const { container } = render(<AnalyticChart chart={history({ rows: [], state: "no_data", summary_params: { reason: "hidden_by_role" } })} onRetry={() => {}} />);
    expect(container.textContent).toMatch(/Tu rol no puede ver los importes/);
  });

  it("shows an error with a retry that asks again, and no figures", () => {
    const onRetry = vi.fn();
    const { container } = render(<AnalyticChart chart={{ key: "coverage_buckets", title_key: "dashboard.chart.title.coverage_buckets", columns: [], rows: [], state: "error" }} onRetry={onRetry} />);
    expect(container.textContent).toMatch(/No se ha podido cargar este gráfico/);
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe("ChartsSection", () => {
  const filters = { warehouse_id: 2, supplier_id: "sup-a", date_from: "2026-09-11" };

  it("asks for the charts with the dashboard filters and shows each one", async () => {
    const spy = vi.spyOn(api, "getDashboardCharts").mockResolvedValue({ charts: [expiry, history()] });
    render(<ChartsSection filters={filters} onDrillBand={() => {}} />);
    await screen.findByRole("heading", { name: "Valor que caduca por tramo" });
    expect(screen.getByRole("heading", { name: "Evolución del inventario valorado" })).toBeTruthy();
    expect(spy).toHaveBeenCalledWith(filters, expect.any(Array));
  });

  it("shows a loading state, then an error with a retry that loads again", async () => {
    const spy = vi.spyOn(api, "getDashboardCharts").mockRejectedValueOnce(new Error("down")).mockResolvedValueOnce({ charts: [expiry] });
    render(<ChartsSection filters={{}} onDrillBand={() => {}} />);
    expect(screen.getByRole("status", { name: /Cargando/ })).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Reintentar" }));
    await screen.findByRole("heading", { name: "Valor que caduca por tramo" });
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("reloads when a filter changes", async () => {
    const spy = vi.spyOn(api, "getDashboardCharts").mockResolvedValue({ charts: [expiry] });
    const { rerender } = render(<ChartsSection filters={{}} onDrillBand={() => {}} />);
    await screen.findByRole("heading", { name: "Valor que caduca por tramo" });
    rerender(<ChartsSection filters={{ category: "A" }} onDrillBand={() => {}} />);
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
  });
});
