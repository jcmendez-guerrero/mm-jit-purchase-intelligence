// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Indicator } from "../../src/api/client";
import { IndicatorCard } from "../../src/features/dashboard/IndicatorCard";
import "../../src/i18n";

// T020 / T025: one card per indicator; every state is told in words, numbers use es-ES, and nothing is shown as zero when there is no figure.

const FRESH = { source: "inventory_snapshot" as const, refreshed_at: "2026-11-09T08:00:00Z", refreshed_at_original: null, origin: "erp_sync" as const, state: "ok" as const, stale_after_hours: 48 };
const ind = (over: Partial<Indicator>): Indicator => ({ key: "stock_value", value: "1234.50", unit: "EUR", state: "ok", basis: "dashboard.basis.lot_cost", definition_key: "dashboard.def.stock_value", freshness: FRESH, ...over });

afterEach(cleanup);

describe("indicator card states", () => {
  it("shows an ok figure in euros with Spanish separators, its basis, origin and refresh time", () => {
    const { container } = render(<IndicatorCard indicator={ind({})} />);
    expect(screen.getByRole("heading", { name: "Valor del stock" })).toBeTruthy();
    expect(container.textContent).toMatch(/1\.234,50\s€/);
    expect(container.textContent).toMatch(/coste de adquisición/i);
    expect(container.textContent).toMatch(/Origen: ERP/);
    expect(container.textContent).toMatch(/Actualizado: /);
  });

  it("says 'Sin datos' for no_data and never a zero", () => {
    const { container } = render(<IndicatorCard indicator={ind({ value: null, state: "no_data" })} />);
    expect(container.textContent).toMatch(/Sin datos/);
    expect(container.textContent).not.toMatch(/0,00|\b0\b/);
  });

  it("keeps the figure but warns when the data is stale", () => {
    const { container } = render(<IndicatorCard indicator={ind({ state: "stale" })} />);
    expect(container.textContent).toMatch(/1\.234,50\s€/);
    expect(screen.getByText("Datos desactualizados")).toBeTruthy();
  });

  it("announces an error without any figure", () => {
    const { container } = render(<IndicatorCard indicator={ind({ value: null, state: "error" })} />);
    expect(screen.getByRole("alert").textContent).toMatch(/No se pudo calcular/);
    expect(container.textContent).not.toMatch(/€/);
  });

  it("tells a role without cost access that the figure is not available, with no number", () => {
    const { container } = render(<IndicatorCard indicator={ind({ value: null, state: "hidden_by_role" })} />);
    expect(container.textContent).toMatch(/No disponible para tu rol/);
    expect(container.textContent).not.toMatch(/\d{2,}/);
  });
});

describe("indicator card content", () => {
  it("formats days, units, counts and percentages the Spanish way", () => {
    const cases: Array<[Partial<Indicator>, RegExp]> = [
      [{ key: "coverage_days", unit: "days", value: "12.5", definition_key: "dashboard.def.coverage_days" }, /12,5 días/],
      [{ key: "demand", unit: "units", value: "12345", definition_key: "dashboard.def.demand" }, /12\.345 uds\./],
      [{ key: "stockout_risk", unit: "count", value: "7", definition_key: "dashboard.def.stockout_risk" }, /^7$/],
      [{ key: "wape", unit: "percent", value: "23.45", definition_key: "dashboard.def.wape" }, /23,5 %|23,45 %/],
      [{ key: "bias", unit: "percent", value: "-5.12", definition_key: "dashboard.def.bias" }, /-5,1 %|-5,12 %/],
    ];
    for (const [over, re] of cases) {
      const { container, unmount } = render(<IndicatorCard indicator={ind(over)} />);
      expect(container.querySelector(".mmi-figure__value")?.textContent).toMatch(re);
      unmount();
    }
  });

  it("lists the parts of a composed figure and the period of each cap", () => {
    const capital = ind({
      key: "capital_tied_up", value: "130.05", definition_key: "dashboard.def.capital_tied_up", basis: "dashboard.basis.stock_plus_open_orders",
      parts: [
        { key: "stock_at_cost", label_key: "dashboard.part.stock_at_cost", value: "100.10" },
        { key: "open_orders", label_key: "dashboard.part.open_orders", value: "29.95" },
      ],
    });
    render(<IndicatorCard indicator={capital} />);
    const list = screen.getByRole("list", { name: "Composición" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    expect(list.textContent).toMatch(/100,10\s€/);
    expect(list.textContent).toMatch(/29,95\s€/);
    cleanup();
    const budget = ind({ key: "purchasing_budget", value: "500.00", definition_key: "dashboard.def.purchasing_budget", basis: "dashboard.basis.purchasing_budget",
      parts: [{ key: "cap_week", label_key: "dashboard.part.cap_week", value: "500.00", period: { from: "2026-10-26", to: "2026-11-01" } }] });
    render(<IndicatorCard indicator={budget} />);
    expect(screen.getByRole("list", { name: "Composición" }).textContent).toMatch(/26\/10\/2026/);
  });

  it("counts what is left out and names the filters the figure does not follow", () => {
    const { container } = render(<IndicatorCard indicator={ind({ incomplete_count: 3, filters_unsupported: ["warehouse", "category"] })} />);
    expect(container.textContent).toMatch(/3 registros no incluidos/);
    expect(container.textContent).toMatch(/No aplica a: Almacén, Categoría/);
  });

  it("explains how the figure is calculated inside a details element, and shows the period when given", () => {
    const { container } = render(<IndicatorCard indicator={ind({})} period={{ from: "2026-09-11", to: "2026-11-09" }} />);
    const details = container.querySelector("details");
    expect(details?.querySelector("summary")?.textContent).toBe("Cómo se calcula");
    expect(details?.textContent).toMatch(/cantidad de cada lote por su coste de adquisición/);
    expect(container.textContent).toMatch(/Periodo: 11\/09\/2026 – 09\/11\/2026/);
  });

  it("offers the drill action when there is a figure or only the amount is hidden, and not for no data or an error", () => {
    const onDrill = vi.fn();
    render(<IndicatorCard indicator={ind({})} onDrill={onDrill} />);
    fireEvent.click(screen.getByRole("button", { name: /Ver productos/ }));
    expect(onDrill).toHaveBeenCalledTimes(1);
    cleanup();
    render(<IndicatorCard indicator={ind({ value: null, state: "hidden_by_role" })} onDrill={onDrill} />);
    expect(screen.getByRole("button", { name: /Ver productos/ })).toBeTruthy();
    for (const state of ["no_data", "error"] as const) {
      cleanup();
      render(<IndicatorCard indicator={ind({ value: null, state })} onDrill={onDrill} />);
      expect(screen.queryByRole("button", { name: /Ver productos/ })).toBeNull();
    }
  });
});
