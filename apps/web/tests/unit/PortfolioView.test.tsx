// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, type PortfolioSummary } from "../../src/api/client";
import { PortfolioView } from "../../src/features/quality/PortfolioView";
import "../../src/i18n";

/** T064: the catalogue quality overview - counts that add up, lists behind every count, filters, and the weakest data. */

const bucket = (key: string, count: number, kind: string) => ({ key, count, drilldown: `bucket=${kind}&key=${key}` });
const summary = (over: Partial<PortfolioSummary> = {}): PortfolioSummary => ({
  filters: { category: null, supplier: null }, active_products: 7,
  by_class: [bucket("AX", 2, "class"), bucket("CZ", 4, "class"), bucket("sin_clasificar", 1, "class")],
  by_eligibility: [bucket("eligible", 2, "eligibility"), bucket("manual_review_only", 1, "eligibility"), bucket("not_eligible", 1, "eligibility"), bucket("pending", 3, "eligibility")],
  by_confidence: [bucket("alta", 1, "confidence"), bucket("media", 1, "confidence"), bucket("baja", 1, "confidence"), bucket("none", 4, "confidence")],
  worst_quality: [{ sku: "EJ-9103", coverage_ratio: "0.866667", rejected_share: "0.050000", anomaly_share: null }], ...over,
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const load = () => fireEvent.click(screen.getByRole("button", { name: "Ver resumen" }));

describe("PortfolioView", () => {
  it("shows the active products and every distribution with its labels in Spanish", async () => {
    vi.spyOn(api, "getPortfolio").mockResolvedValue(summary());
    render(<PortfolioView />);
    load();
    expect(await screen.findByText("Productos activos: 7")).toBeTruthy();
    expect(screen.getByRole("button", { name: "2 productos: ver la lista de AX" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "1 productos: ver la lista de Sin clasificar" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "3 productos: ver la lista de Pendiente de previsión" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "1 productos: ver la lista de Solo revisión manual" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "4 productos: ver la lista de Sin confianza asignada" })).toBeTruthy();
    expect(api.getPortfolio).toHaveBeenCalledWith({});
  });

  it("opens the list behind a count with its SKUs and the range shown", async () => {
    vi.spyOn(api, "getPortfolio").mockResolvedValue(summary());
    const products = vi.spyOn(api, "getPortfolioProducts").mockResolvedValue({ bucket: "eligibility", key: "pending", total: 3, skus: ["EJ-9105", "EJ-9106", "EJ-9107"] });
    render(<PortfolioView />);
    load();
    fireEvent.click(await screen.findByRole("button", { name: "3 productos: ver la lista de Pendiente de previsión" }));
    expect(await screen.findByText("EJ-9106")).toBeTruthy();
    expect(screen.getByText("Mostrando 1–3 de 3")).toBeTruthy();
    expect(products).toHaveBeenCalledWith("eligibility", "pending", {}, 0, 50);
  });

  it("pages through a long list", async () => {
    vi.spyOn(api, "getPortfolio").mockResolvedValue(summary({ active_products: 120 }));
    const skus = (from: number, n: number) => Array.from({ length: n }, (_, i) => `EJ-${from + i}`);
    const products = vi.spyOn(api, "getPortfolioProducts").mockResolvedValueOnce({ bucket: "class", key: "CZ", total: 120, skus: skus(1, 50) }).mockResolvedValueOnce({ bucket: "class", key: "CZ", total: 120, skus: skus(51, 50) });
    render(<PortfolioView />);
    load();
    fireEvent.click(await screen.findByRole("button", { name: "4 productos: ver la lista de CZ" }));
    expect(await screen.findByText("Mostrando 1–50 de 120")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(await screen.findByText("Mostrando 51–100 de 120")).toBeTruthy();
    expect(products).toHaveBeenLastCalledWith("class", "CZ", {}, 50, 50);
    expect((screen.getByRole("button", { name: "Anterior" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("a group with no products cannot be opened", async () => {
    vi.spyOn(api, "getPortfolio").mockResolvedValue(summary({ by_class: [bucket("AX", 0, "class")] }));
    render(<PortfolioView />);
    load();
    expect(((await screen.findByRole("button", { name: "0 productos: ver la lista de AX" })) as HTMLButtonElement).disabled).toBe(true);
  });

  it("passes the filters to the overview and to every list", async () => {
    const getPortfolio = vi.spyOn(api, "getPortfolio").mockResolvedValue(summary({ filters: { category: "A", supplier: "s1" } }));
    const products = vi.spyOn(api, "getPortfolioProducts").mockResolvedValue({ bucket: "eligibility", key: "pending", total: 1, skus: ["EJ-9105"] });
    render(<PortfolioView />);
    fireEvent.change(screen.getByLabelText("Categoría"), { target: { value: "A" } });
    fireEvent.change(screen.getByLabelText("Proveedor (identificador)"), { target: { value: " s1 " } });
    load();
    await waitFor(() => expect(getPortfolio).toHaveBeenCalledWith({ category: "A", supplier_id: "s1" }));
    fireEvent.click(await screen.findByRole("button", { name: "3 productos: ver la lista de Pendiente de previsión" }));
    await waitFor(() => expect(products).toHaveBeenCalledWith("eligibility", "pending", { category: "A", supplier_id: "s1" }, 0, 50));
  });

  it("lists the products with the weakest data with Spanish percentages", async () => {
    vi.spyOn(api, "getPortfolio").mockResolvedValue(summary());
    render(<PortfolioView />);
    load();
    expect(await screen.findByText("EJ-9103")).toBeTruthy();
    expect(screen.getByText(/86,7\s?%/)).toBeTruthy();
    expect(screen.getByText(/5,0\s?%/)).toBeTruthy();
  });

  it("shows a Spanish message when the overview cannot be read", async () => {
    vi.spyOn(api, "getPortfolio").mockRejectedValue(new ApiError(422, "request_invalid"));
    render(<PortfolioView />);
    load();
    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});

describe("PortfolioView origin", () => {
  it("offers ERP by default and sends no origin unless the other one is chosen", async () => {
    vi.spyOn(api, "getPortfolio").mockResolvedValue(summary());
    render(<PortfolioView />);
    expect((screen.getByLabelText("Origen") as HTMLSelectElement).value).toBe("");
    expect(screen.getByRole("option", { name: "ERP" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "Carga local" })).toBeTruthy();
    load();
    await screen.findByText("Productos activos: 7");
    expect(api.getPortfolio).toHaveBeenCalledWith({});
  });

  it("sends the chosen origin for the counts and for the list behind a count", async () => {
    vi.spyOn(api, "getPortfolio").mockResolvedValue(summary({ active_products: 2 }));
    const products = vi.spyOn(api, "getPortfolioProducts").mockResolvedValue({ bucket: "eligibility", key: "pending", total: 3, skus: ["EJ-9801"] });
    render(<PortfolioView />);
    fireEvent.change(screen.getByLabelText("Origen"), { target: { value: "local_export" } });
    load();
    await screen.findByText("Productos activos: 2");
    expect(api.getPortfolio).toHaveBeenCalledWith({ origin: "local_export" });
    fireEvent.click(screen.getByRole("button", { name: "3 productos: ver la lista de Pendiente de previsión" }));
    await screen.findByText("EJ-9801");
    expect(products).toHaveBeenCalledWith("eligibility", "pending", { origin: "local_export" }, 0, 50);
  });
});
