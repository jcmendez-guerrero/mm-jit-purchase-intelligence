// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, SupplierSummary } from "../../src/api/client";
import { LocalLoadScreen } from "../../src/features/localload/LocalLoadScreen";
import { SupplierImport } from "../../src/features/suppliers/SupplierImport";
import { SupplierReview } from "../../src/features/suppliers/SupplierReview";
import { SuppliersScreen } from "../../src/features/suppliers/SuppliersScreen";
import "../../src/i18n";

const sup = (id: string, over: Partial<SupplierSummary> = {}): SupplierSummary => ({
  id, name: `Proveedor ${id}`, terms: null, version: 0, supplier_version: 2, status: "active", classification: "unclassified", origin: "imported",
  erp_link_state: "unverified", fiscal_type: "national", country: "ES", currency: "EUR", payment_terms_days: 30, order_channel: null, ...over,
});

beforeEach(() => {
  vi.spyOn(api, "getSupplierReviewItems").mockResolvedValue([]);
  vi.spyOn(api, "getLocalLoadReview").mockResolvedValue([]);
  vi.spyOn(api, "getLocalLoadDifferences").mockResolvedValue([]);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("SupplierImport", () => {
  it("shows only imported suppliers that still need a decision", () => {
    const list = [sup("a"), sup("b", { classification: "non_purchasing" }), sup("c", { classification: "purchasing" }), sup("d", { origin: "platform" }), sup("e", { status: "deactivated" })];
    render(<SupplierImport suppliers={list} onChanged={() => undefined} />);
    expect(screen.getByText("Proveedor a")).toBeTruthy();
    expect(screen.getByText("Proveedor b")).toBeTruthy();
    for (const hidden of ["Proveedor c", "Proveedor d", "Proveedor e"]) expect(screen.queryByText(hidden)).toBeNull();
    expect(screen.getByText("Sin compras")).toBeTruthy();
  });

  it("renders nothing when there is nothing to classify", () => {
    const { container } = render(<SupplierImport suppliers={[sup("c", { classification: "purchasing" })]} onChanged={() => undefined} />);
    expect(container.textContent).toBe("");
  });

  it("marks the selected suppliers with their own versions and reports the count", async () => {
    const update = vi.spyOn(api, "updateSupplier").mockResolvedValue(sup("a"));
    const changed = vi.fn();
    render(<SupplierImport suppliers={[sup("a", { supplier_version: 3 }), sup("b", { supplier_version: 5 })]} onChanged={changed} />);
    expect((screen.getByRole("button", { name: "Marcar como de compra" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("Seleccionar Proveedor a"));
    fireEvent.click(screen.getByLabelText("Seleccionar Proveedor b"));
    fireEvent.click(screen.getByRole("button", { name: "Marcar como de compra" }));
    await waitFor(() => expect(update).toHaveBeenCalledTimes(2));
    expect(update).toHaveBeenCalledWith("a", { classification: "purchasing" }, 3);
    expect(update).toHaveBeenCalledWith("b", { classification: "purchasing" }, 5);
    expect(await screen.findByText("Se actualizaron 2 proveedores.")).toBeTruthy();
    expect(changed).toHaveBeenCalled();
  });

  it("selects all, marks them as no-purchase, and reports the ones that failed", async () => {
    const update = vi.spyOn(api, "updateSupplier").mockResolvedValueOnce(sup("a")).mockRejectedValueOnce(new ApiError(412, "supplier_version_conflict", 9));
    render(<SupplierImport suppliers={[sup("a"), sup("b")]} onChanged={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "Seleccionar todos" }));
    fireEvent.click(screen.getByRole("button", { name: "Marcar como sin compras" }));
    await waitFor(() => expect(update).toHaveBeenCalledTimes(2));
    expect(update.mock.calls.every((c) => (c[1] as { classification: string }).classification === "non_purchasing")).toBe(true);
    expect(await screen.findByText("Se actualizaron 1 proveedores.")).toBeTruthy();
    expect(await screen.findByText(/1 no se pudieron actualizar/)).toBeTruthy();
  });

  it("is offered to managers only on the suppliers screen", async () => {
    vi.spyOn(api, "getSuppliers").mockResolvedValue([sup("a")]);
    const { unmount } = render(<SuppliersScreen userRoles={["viewer"]} />);
    await screen.findByRole("button", { name: "Proveedor a" });
    expect(screen.queryByText("Proveedores importados por clasificar")).toBeNull();
    unmount();
    render(<SuppliersScreen userRoles={["viewer", "buyer"]} />);
    expect(await screen.findByText("Proveedores importados por clasificar")).toBeTruthy();
  });
});

describe("review of unparsed payment terms", () => {
  it("tells the buyer to edit the supplier", async () => {
    vi.spyOn(api, "getSupplierReviewItems").mockResolvedValue([{ id: "i1", kind: "payment_terms_unparsed", supplier_id: "a", detail: "", status: "open", created_at: "x" }]);
    render(<SupplierReview suppliers={[sup("a")]} onChanged={() => undefined} />);
    const item = (await screen.findByText("Plazo de pago no interpretado")).closest("li") as HTMLElement;
    expect(within(item).getByText(/indique el plazo de pago en días/)).toBeTruthy();
  });
});

describe("local load of suppliers", () => {
  it("offers the supplier file first and loads it without the tax acknowledgement", async () => {
    const result = { run_id: "r", kind: "suppliers" as const, rows: 4, loaded: 3, updated: 0, unchanged: 0, quarantined: 0, excluded: 1, services: 0, review: [] };
    const check = vi.spyOn(api, "checkLocalLoad").mockResolvedValue(result);
    const run = vi.spyOn(api, "runLocalLoad").mockResolvedValue(result);
    render(<LocalLoadScreen userRoles={["buyer"]} />);
    const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(headings.slice(0, 3)).toEqual(["Proveedores", "Inventario y stock", "Movimientos de stock"]);
    fireEvent.change(screen.getByLabelText("Archivo de proveedores (CSV)"), { target: { files: [new File([new Uint8Array(5)], "proveedores.csv", { type: "text/csv" })] } });
    fireEvent.click(screen.getAllByRole("button", { name: "Comprobar archivo" })[0] as HTMLElement);
    await waitFor(() => expect(check).toHaveBeenCalledWith("suppliers", expect.any(File)));
    const load = (await screen.findByRole("button", { name: "Cargar datos" })) as HTMLButtonElement;
    expect(load.disabled).toBe(false);
    expect(screen.queryByLabelText("Confirmo la interpretación de impuestos y precios")).toBeNull();
    fireEvent.click(load);
    await waitFor(() => expect(run).toHaveBeenCalledWith("suppliers", expect.any(File), false, expect.any(String)));
  });
});
