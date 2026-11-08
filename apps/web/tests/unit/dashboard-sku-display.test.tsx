// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, DrillResponse } from "../../src/api/client";
import { DrillDownPanel } from "../../src/features/dashboard/DrillDownPanel";
import "../../src/i18n";

const rows = (from: number, n: number): DrillResponse["rows"] =>
  Array.from({ length: n }, (_, i) => ({ variant_id: 900000 + from + i, sku: `SYN-${String(from + i).padStart(3, "0")}`, name: `Variante ${from + i}`, figure: "10.00" }));
const page = (over: Partial<DrillResponse>): DrillResponse => ({ kind: "inventory_value", truncated: false, total: 2, offset: 0, sum: "20.00", rows: rows(1, 2), ...over });

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("drill-down shows products by SKU", () => {
  it("never shows the internal id, in the text or in the button names", async () => {
    vi.spyOn(api, "getDrilldown").mockResolvedValue(page({}));
    const { container } = render(<DrillDownPanel request={{ kind: "inventory_value" }} title="Productos" onOpenProduct={() => {}} onClose={() => {}} />);
    await screen.findByText(/SYN-001/);
    expect(container.textContent).not.toMatch(/#\d|9000\d\d/);
    expect(screen.getByRole("button", { name: /Ver detalle SYN-002/ })).toBeTruthy();
  });

  it("says 'Sin SKU' instead of falling back to the id when a product has none", async () => {
    vi.spyOn(api, "getDrilldown").mockResolvedValue(page({ rows: [{ variant_id: 900001, sku: null, name: "Sin código", figure: "1.00" }], total: 1 }));
    const { container } = render(<DrillDownPanel request={{ kind: "inventory_value" }} title="Productos" onOpenProduct={() => {}} onClose={() => {}} />);
    await screen.findByText(/Sin SKU/);
    expect(container.textContent).not.toMatch(/9000\d\d/);
  });

  it("pages forward and back and shows the range", async () => {
    const spy = vi.spyOn(api, "getDrilldown").mockImplementation(async (r) =>
      (r.offset ?? 0) === 0 ? page({ total: 120, truncated: true, rows: rows(1, 50) }) : page({ total: 120, truncated: false, offset: 50, rows: rows(51, 50) }));
    render(<DrillDownPanel request={{ kind: "inventory_value" }} title="Productos" onOpenProduct={() => {}} onClose={() => {}} />);
    await screen.findByText("Mostrando 1–50 de 120 productos.");
    expect((screen.getByRole("button", { name: "Anterior" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    await screen.findByText("Mostrando 51–100 de 120 productos.");
    expect(spy).toHaveBeenLastCalledWith(expect.objectContaining({ limit: 50, offset: 50 }));
    fireEvent.click(screen.getByRole("button", { name: "Anterior" }));
    await waitFor(() => expect(screen.getByText("Mostrando 1–50 de 120 productos.")).toBeTruthy());
  });
});
