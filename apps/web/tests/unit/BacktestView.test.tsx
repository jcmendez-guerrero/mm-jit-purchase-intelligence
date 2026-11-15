// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, type ProductBacktest } from "../../src/api/client";
import { BacktestView } from "../../src/features/quality/BacktestView";
import "../../src/i18n";

/** T057: the backtest view - a stored result in Spanish, the baseline flag, and who may start a run. */

const result = (over: Partial<ProductBacktest> = {}): ProductBacktest => ({
  backtest_run_id: "b1", sku: "EJ-1", periods: 12, wape: "0.500000", bias: "0.250000", baseline_wape: "0.400000", baseline_bias: "0.100000", beats_baseline: false,
  model_version: "minmax_poisson@v1", dataset_version_id: null, config_version_id: null, created_at: "2026-11-15T10:00:00Z", ...over,
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function lookUp(sku = "EJ-1") {
  fireEvent.change(screen.getByLabelText("SKU"), { target: { value: sku } });
  fireEvent.click(screen.getByRole("button", { name: "Ver resultado" }));
}

describe("BacktestView", () => {
  it("shows the periods, the method's and the baseline's error and bias, and flags a method that does worse", async () => {
    vi.spyOn(api, "getProductBacktest").mockResolvedValue(result());
    render(<BacktestView userRoles={["viewer"]} />);
    lookUp();
    expect(await screen.findByText("Periodos evaluados")).toBeTruthy();
    expect(screen.getByText("50,0 %")).toBeTruthy();
    expect(screen.getByText("40,0 %")).toBeTruthy();
    expect(screen.getByText("El método no supera a la referencia en los periodos evaluados.")).toBeTruthy();
    expect(screen.getByText(/Modelo: minmax_poisson@v1/)).toBeTruthy();
  });

  it("does not flag a method that matches or beats the baseline", async () => {
    vi.spyOn(api, "getProductBacktest").mockResolvedValue(result({ wape: "0.300000", beats_baseline: true }));
    render(<BacktestView userRoles={["viewer"]} />);
    lookUp();
    expect(await screen.findByText("El método iguala o supera a la referencia.")).toBeTruthy();
    expect(screen.queryByText(/no supera a la referencia/)).toBeNull();
  });

  it("says when there is nothing to assess yet", async () => {
    vi.spyOn(api, "getProductBacktest").mockResolvedValue(result({ periods: 0, wape: null, bias: null, baseline_wape: null, baseline_bias: null, beats_baseline: true }));
    render(<BacktestView userRoles={["viewer"]} />);
    lookUp();
    expect(await screen.findByText(/Todavía no hay periodos evaluables/)).toBeTruthy();
    expect(screen.queryByText("Periodos evaluados")).toBeNull();
  });

  it("offers no start buttons to a viewer", () => {
    render(<BacktestView userRoles={["viewer"]} />);
    expect(screen.queryByRole("button", { name: "Ejecutar la prueba de este producto" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Ejecutar la prueba de todo el catálogo" })).toBeNull();
  });

  it("a buyer starts a product run and then sees its result", async () => {
    const start = vi.spyOn(api, "startBacktest").mockResolvedValue({ job_id: "j1", status: "completed", reused: false, products: 1 });
    vi.spyOn(api, "getProductBacktest").mockResolvedValue(result());
    render(<BacktestView userRoles={["viewer", "buyer"]} />);
    fireEvent.change(screen.getByLabelText("SKU"), { target: { value: "EJ-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Ejecutar la prueba de este producto" }));
    await waitFor(() => expect(start).toHaveBeenCalledWith("product", "EJ-1"));
    expect(await screen.findByText("Prueba terminada (1 productos).")).toBeTruthy();
    expect(await screen.findByText("Periodos evaluados")).toBeTruthy();
  });

  it("starting the whole catalogue needs no SKU and says when the result was reused", async () => {
    const start = vi.spyOn(api, "startBacktest").mockResolvedValue({ job_id: "j2", status: "completed", reused: true, products: 5 });
    render(<BacktestView userRoles={["viewer", "admin"]} />);
    fireEvent.click(screen.getByRole("button", { name: "Ejecutar la prueba de todo el catálogo" }));
    await waitFor(() => expect(start).toHaveBeenCalledWith("catalogue", undefined));
    expect(await screen.findByText(/Ya existía un resultado con los mismos datos; no se ha repetido la prueba \(5 productos\)/)).toBeTruthy();
  });

  it("shows the Spanish message when a full-catalogue run is already going", async () => {
    vi.spyOn(api, "startBacktest").mockRejectedValue(new ApiError(409, "forecast_backtest_conflict"));
    render(<BacktestView userRoles={["viewer", "buyer"]} />);
    fireEvent.click(screen.getByRole("button", { name: "Ejecutar la prueba de todo el catálogo" }));
    expect(await screen.findByText(/Ya hay una prueba retrospectiva del catálogo completo en curso/)).toBeTruthy();
  });

  it("shows a Spanish error for an unknown SKU", async () => {
    vi.spyOn(api, "getProductBacktest").mockRejectedValue(new ApiError(404, "quality_product_not_found"));
    render(<BacktestView userRoles={["viewer"]} />);
    lookUp("NOPE");
    expect(await screen.findByText(/No se encuentra el producto/)).toBeTruthy();
  });
});
