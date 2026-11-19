// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, DashboardSku } from "../../src/api/client";
import { SkuDetailPage } from "../../src/features/dashboard/SkuDetailPage";
import "../../src/i18n";

const sku = (over: Partial<DashboardSku> = {}): DashboardSku => ({
  sku: "SYN-001",
  name: "Producto sintético",
  stock: { on_hand: 15 },
  coverage: { days: "5.00", basis: "actual_90d" },
  demand: { units: 84, days: 28 },
  forecast: { daily_mean: "2.00", days: 28 },
  supplier: { id: "sup-a" },
  expiry_lots: [
    { batch: "L1", quantity: 10, expiry_date: "2027-12-20", band: "later" },
    { batch: "L2", quantity: 5, expiry_date: "2026-11-19", band: "d0_30" },
  ],
  states: [],
  ...over,
});

const show = (path = "/panel/skus/SYN-001") =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/panel/skus/:sku" element={<SkuDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("SKU detail page", () => {
  it("is titled by the SKU and shows stock, coverage, demand, forecast, supplier and the lots by band", async () => {
    const spy = vi.spyOn(api, "getDashboardSku").mockResolvedValue(sku({ cost: { value: "40.00", estimated: false, unit_cost: "2.00" } }));
    const { container } = show();
    await screen.findByText(/Existencias totales: 15/);
    expect(spy).toHaveBeenCalledWith("SYN-001");
    expect(screen.getByRole("heading", { level: 2 }).textContent).toContain("SYN-001");
    expect(container.textContent).toMatch(/Proveedor: sup-a/);
    expect(container.textContent).toMatch(/Cobertura: 5,0 días \(base: ventas de los últimos 90 días\)/);
    expect(screen.getByText("0 a 30 días")).toBeTruthy();
    expect(container.textContent).toMatch(/40,00/);
  });

  it("shows no cost line when the response carries none, and explains the states", async () => {
    vi.spyOn(api, "getDashboardSku").mockResolvedValue(sku({ states: ["no_demand_history"], coverage: null, forecast: null }));
    const { container } = show();
    await screen.findByText(/Este producto no tiene historial de demanda/);
    expect(container.textContent).not.toMatch(/Valor en stock/);
    expect(container.textContent).toMatch(/Sin demanda para calcular la cobertura/);
  });

  it("says the product does not exist on a 404 and shows nothing else", async () => {
    vi.spyOn(api, "getDashboardSku").mockRejectedValue(new ApiError(404, "sku_not_found"));
    const { container } = show("/panel/skus/NOPE-1");
    await screen.findByText(/No existe ningún producto con la referencia NOPE-1/);
    expect(container.textContent).not.toMatch(/Existencias/);
  });
});
