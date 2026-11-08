// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, BulkPreview, SupplierLinkRow, SupplierSummary } from "../../src/api/client";
import { BulkAssign } from "../../src/features/suppliers/BulkAssign";
import { LinksPanel } from "../../src/features/suppliers/LinksPanel";
import { SupplierForm } from "../../src/features/suppliers/SupplierForm";
import { SupplierReview } from "../../src/features/suppliers/SupplierReview";
import { SuppliersScreen } from "../../src/features/suppliers/SuppliersScreen";
import { canManage, diff, EMPTY_FORM, formFrom, linkPayload, parseCost, parseSkuList, toPayload, validate } from "../../src/features/suppliers/supplierModel";
import "../../src/i18n";
import { confirmAction } from "./confirm";

const sup = (over: Partial<SupplierSummary> = {}): SupplierSummary => ({
  id: "s1", name: "Proveedor Sintético Uno", terms: null, version: 0, supplier_version: 3, status: "active", classification: "purchasing", origin: "platform",
  erp_link_state: "none", fiscal_type: "national", country: "ES", currency: "EUR", payment_terms_days: 30, order_channel: "email", ...over,
});
const link = (over: Partial<SupplierLinkRow> = {}): SupplierLinkRow => ({
  sku: "SYN-000001", name: "Pienso sintético", cost: "2.1040", currency: "EUR", cost_source: "inventory_export", includes_recargo: false, pack_size: 6, min_qty: null,
  verified_at: "2026-11-08T10:00:00Z", erp_link: "no_link", ...over,
});
const preview = (over: Partial<BulkPreview> = {}): BulkPreview => ({ batch_id: "b1", matched: 3, new: 2, existing: 1, conflicts: 0, conflict_skus: [], unknown: [], expires_at: "x", ...over });
const type = (label: string | RegExp, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

beforeEach(() => {
  vi.spyOn(api, "getSupplierLinks").mockResolvedValue([]);
  vi.spyOn(api, "getSupplierReviewItems").mockResolvedValue([]);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("supplier model", () => {
  it("validates the form fields with Spanish message keys", () => {
    expect(validate({ ...EMPTY_FORM, name: "Proveedor" })).toEqual({});
    expect(validate(EMPTY_FORM).name).toBe("suppliers.form.err.name_required");
    expect(validate({ ...EMPTY_FORM, name: "x".repeat(201) }).name).toBe("suppliers.form.err.name_long");
    expect(validate({ ...EMPTY_FORM, name: "a", country: "esp" }).country).toBe("suppliers.form.err.country");
    expect(validate({ ...EMPTY_FORM, name: "a", currency: "euro" }).currency).toBe("suppliers.form.err.currency");
    expect(validate({ ...EMPTY_FORM, name: "a", payment_terms_days: "400" }).payment_terms_days).toBe("suppliers.form.err.days");
    expect(validate({ ...EMPTY_FORM, name: "a", payment_terms_days: "30" })).toEqual({});
  });

  it("builds the payload and sends only what changed", () => {
    const before = formFrom(sup());
    expect(toPayload({ ...before, payment_terms_days: "", order_channel: "" })).toMatchObject({ payment_terms_days: null, order_channel: null });
    expect(diff(before, { ...before, payment_terms_days: "45", name: " Otro " })).toEqual({ payment_terms_days: 45, name: "Otro" });
    expect(diff(before, before)).toEqual({});
  });

  it("parses SKU lists and Spanish decimals", () => {
    expect(parseSkuList("A1\n a1 ,B2;C3\t\n\n")).toEqual(["A1", "B2", "C3"]);
    expect(parseCost("12,50")).toBe("12.50");
    expect(parseCost(" 7.5 ")).toBe("7.5");
    expect(parseCost("abc")).toBeNull();
    expect(parseCost("-1")).toBeNull();
    expect(linkPayload({ cost: "", includesRecargo: true, pack: "", minQty: "" })).toEqual({ includes_recargo: true });
    expect(linkPayload({ cost: "1,2", includesRecargo: false, pack: "6", minQty: "12" })).toEqual({ includes_recargo: false, cost: "1.2", pack_size: 6, min_qty: 12 });
    expect(linkPayload({ cost: "x", includesRecargo: true, pack: "", minQty: "" })).toBeNull();
    expect(linkPayload({ cost: "", includesRecargo: true, pack: "0", minQty: "" })).toBeNull();
  });

  it("lets only buyers and admins manage", () => {
    expect(canManage(["viewer"])).toBe(false);
    expect(canManage(["viewer", "approver"])).toBe(false);
    expect(canManage(["buyer"])).toBe(true);
    expect(canManage(["viewer", "admin"])).toBe(true);
  });
});

describe("SupplierForm", () => {
  it("refuses an empty name locally without calling the server", async () => {
    const create = vi.spyOn(api, "createSupplier");
    render(<SupplierForm onSaved={() => undefined} onCancel={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "Guardar proveedor" }));
    expect(await screen.findByText("Indique el nombre del proveedor.")).toBeTruthy();
    expect(create).not.toHaveBeenCalled();
  });

  it("creates a supplier and says nothing about tax ids or bank data being kept", async () => {
    const created = sup();
    const create = vi.spyOn(api, "createSupplier").mockResolvedValue(created);
    const saved = vi.fn();
    render(<SupplierForm onSaved={saved} onCancel={() => undefined} />);
    expect(screen.getByText(/No se guardan identificadores fiscales/)).toBeTruthy();
    expect(screen.queryByLabelText(/CIF|IBAN|banco/i)).toBeNull();
    type("Nombre comercial", "Proveedor Sintético Uno");
    fireEvent.click(screen.getByRole("button", { name: "Guardar proveedor" }));
    await waitFor(() => expect(saved).toHaveBeenCalledWith(created));
    expect(create).toHaveBeenCalledWith(expect.objectContaining({ name: "Proveedor Sintético Uno", country: "ES", currency: "EUR" }), false);
  });

  it("warns about a duplicate and creates it only after the buyer confirms", async () => {
    const create = vi.spyOn(api, "createSupplier").mockRejectedValueOnce(new ApiError(409, "supplier_possible_duplicate")).mockResolvedValueOnce(sup());
    render(<SupplierForm onSaved={() => undefined} onCancel={() => undefined} />);
    type("Nombre comercial", "Proveedor Sintético Uno");
    fireEvent.click(screen.getByRole("button", { name: "Guardar proveedor" }));
    expect(await screen.findByText(/nombre muy parecido/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Crear de todos modos" }));
    await waitFor(() => expect(create).toHaveBeenCalledTimes(2));
    expect(create.mock.calls[1]?.[1]).toBe(true);
  });

  it("edits with the supplier version and reports a version conflict", async () => {
    const update = vi.spyOn(api, "updateSupplier").mockRejectedValue(new ApiError(412, "supplier_version_conflict", 4));
    render(<SupplierForm supplier={sup()} onSaved={() => undefined} onCancel={() => undefined} />);
    type("Plazo de pago (días)", "45");
    fireEvent.click(screen.getByRole("button", { name: "Guardar proveedor" }));
    await waitFor(() => expect(update).toHaveBeenCalledWith("s1", { payment_terms_days: 45 }, 3, false));
    expect(await screen.findByText(/Otra persona ha modificado este proveedor/)).toBeTruthy();
  });

  it("does not call the server when nothing changed", async () => {
    const update = vi.spyOn(api, "updateSupplier");
    render(<SupplierForm supplier={sup()} onSaved={() => undefined} onCancel={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "Guardar proveedor" }));
    expect(await screen.findByText("No hay cambios que guardar.")).toBeTruthy();
    expect(update).not.toHaveBeenCalled();
  });
});

describe("SuppliersScreen management", () => {
  const open = async (roles: string[], list = [sup()]) => {
    vi.spyOn(api, "getSuppliers").mockResolvedValue(list);
    vi.spyOn(api, "getSupplierTerms").mockResolvedValue({ supplier_id: "s1", version: 0, current: null, history: [] } as never);
    vi.spyOn(api, "getOverrideTerms").mockResolvedValue({} as never);
    render(<SuppliersScreen userRoles={roles} />);
    return screen.findByRole("button", { name: list[0]?.name ?? "" });
  };

  it("offers no management actions to a viewer", async () => {
    fireEvent.click(await open(["viewer"]));
    expect(screen.queryByRole("button", { name: "Nuevo proveedor" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Desactivar proveedor" })).toBeNull();
    expect(screen.queryByLabelText("Lista de SKU (uno por línea)")).toBeNull();
  });

  it("shows the deactivation dialog with the affected proposal lines and deactivates after confirming", async () => {
    const call = vi.spyOn(api, "deactivateSupplier")
      .mockResolvedValueOnce({ deactivated: false, open_proposal_lines: 4, lines: [] })
      .mockResolvedValueOnce({ deactivated: true, open_proposal_lines: 4, lines: [] });
    fireEvent.click(await open(["viewer", "buyer"]));
    fireEvent.click(await screen.findByRole("button", { name: "Desactivar proveedor" }));
    expect(await screen.findByText(/Tiene 4 líneas en propuestas abiertas/)).toBeTruthy();
    expect(call).toHaveBeenCalledWith("s1", false);
    confirmAction();
    await waitFor(() => expect(call).toHaveBeenCalledWith("s1", true));
  });

  it("lets an admin without the buyer role create a supplier, but keeps the terms editor read-only", async () => {
    await open(["viewer", "admin"]);
    expect(screen.getByRole("button", { name: "Nuevo proveedor" })).toBeTruthy();
  });

  it("shows deactivated and non-purchasing badges and applies the filters", async () => {
    const list = [sup({ id: "s1", name: "Alfa Sintética", status: "deactivated" }), sup({ id: "s2", name: "Beta Sintética", classification: "non_purchasing" })];
    const filtered = vi.spyOn(api, "getSuppliersFiltered").mockResolvedValue([list[1] as SupplierSummary]);
    await open(["viewer", "buyer"], list);
    expect(screen.getAllByText("Desactivado").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Sin compras").length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText("Clasificación"), { target: { value: "non_purchasing" } });
    await waitFor(() => expect(filtered).toHaveBeenCalledWith({ classification: "non_purchasing" }));
  });
});

describe("LinksPanel", () => {
  it("lists links by SKU with the provenance badge and the pending-ERP badge", async () => {
    vi.spyOn(api, "getSupplierLinks").mockResolvedValue([link()]);
    render(<LinksPanel supplier={sup()} canManage />);
    expect(await screen.findByText("SYN-000001")).toBeTruthy();
    expect(screen.getByText("Exportación de inventario")).toBeTruthy();
    expect(screen.getByText("Pendiente de enlace en el ERP")).toBeTruthy();
  });

  it("saves a link with a Spanish decimal and the recargo choice", async () => {
    const put = vi.spyOn(api, "putSupplierLink").mockResolvedValue({ cost: "10.5200", erp_link: "no_link", write_case: "pending_link", warnings: [] });
    render(<LinksPanel supplier={sup()} canManage />);
    type("SKU", "SYN-000009");
    type(/Coste \(opcional\)/, "10,50");
    fireEvent.click(screen.getByLabelText("El coste ya incluye el recargo de equivalencia"));
    type("Múltiplo de pedido", "6");
    fireEvent.click(screen.getByRole("button", { name: "Guardar producto" }));
    await waitFor(() => expect(put).toHaveBeenCalledWith("s1", "SYN-000009", { includes_recargo: false, cost: "10.50", pack_size: 6 }));
    expect(await screen.findByText("Producto guardado.")).toBeTruthy();
  });

  it("uses the export cost when the cost is left empty and checks the input first", async () => {
    const put = vi.spyOn(api, "putSupplierLink").mockResolvedValue({ cost: "2", erp_link: "no_link", write_case: null, warnings: ["abnormal_jump"] });
    render(<LinksPanel supplier={sup()} canManage />);
    fireEvent.click(screen.getByRole("button", { name: "Guardar producto" }));
    expect(await screen.findByText("Indique el SKU.")).toBeTruthy();
    type("SKU", "SYN-1");
    type(/Coste \(opcional\)/, "abc");
    fireEvent.click(screen.getByRole("button", { name: "Guardar producto" }));
    expect(await screen.findByText(/Indique un coste válido/)).toBeTruthy();
    type(/Coste \(opcional\)/, "");
    fireEvent.click(screen.getByRole("button", { name: "Guardar producto" }));
    await waitFor(() => expect(put).toHaveBeenCalledWith("s1", "SYN-1", { includes_recargo: true, cost_source: "inventory_export" }));
    expect(await screen.findByText(/revíselo en Costes/)).toBeTruthy();
  });

  it("removes a link only after confirming", async () => {
    vi.spyOn(api, "getSupplierLinks").mockResolvedValue([link()]);
    const del = vi.spyOn(api, "deleteSupplierLink").mockResolvedValue();
    render(<LinksPanel supplier={sup()} canManage />);
    fireEvent.click(await screen.findByRole("button", { name: "Quitar" }));
    expect(del).not.toHaveBeenCalled();
    confirmAction();
    await waitFor(() => expect(del).toHaveBeenCalledWith("s1", "SYN-000001"));
  });

  it("is read-only for viewers and for a deactivated supplier", async () => {
    vi.spyOn(api, "getSupplierLinks").mockResolvedValue([link()]);
    const { rerender } = render(<LinksPanel supplier={sup()} canManage={false} />);
    await screen.findByText("SYN-000001");
    expect(screen.queryByRole("button", { name: "Guardar producto" })).toBeNull();
    rerender(<LinksPanel supplier={sup({ status: "deactivated" })} canManage />);
    expect(screen.queryByRole("button", { name: "Guardar producto" })).toBeNull();
  });
});

describe("BulkAssign", () => {
  it("needs input before it previews", async () => {
    const p = vi.spyOn(api, "previewBulkLinks");
    render(<BulkAssign supplier={sup()} onDone={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "Vista previa" }));
    expect(await screen.findByText(/Indique una lista de SKU/)).toBeTruthy();
    expect(p).not.toHaveBeenCalled();
  });

  it("previews a pasted list, shows the counts and applies the same preview", async () => {
    const p = vi.spyOn(api, "previewBulkLinks").mockResolvedValue(preview({ unknown: ["SYN-404"] }));
    const apply = vi.spyOn(api, "applyBulkLinks").mockResolvedValue({ changed: 2, skipped_conflicts: 0, no_cost: 0 });
    const done = vi.fn();
    render(<BulkAssign supplier={sup()} onDone={done} />);
    type("Lista de SKU (uno por línea)", "SYN-1\nsyn-1\nSYN-2");
    fireEvent.click(screen.getByRole("button", { name: "Vista previa" }));
    expect(await screen.findByText("Coinciden")).toBeTruthy();
    expect(p).toHaveBeenCalledWith("s1", { skus: ["SYN-1", "SYN-2"] });
    expect(screen.getByText(/SKU desconocidos: SYN-404/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Aplicar asignación" }));
    await waitFor(() => expect(apply).toHaveBeenCalledWith("s1", "b1", false));
    expect(await screen.findByText(/Se asignaron 2 productos/)).toBeTruthy();
    expect(done).toHaveBeenCalled();
  });

  it("blocks applying until conflicts are explicitly skipped", async () => {
    vi.spyOn(api, "previewBulkLinks").mockResolvedValue(preview({ conflicts: 1, conflict_skus: ["SYN-1"] }));
    const apply = vi.spyOn(api, "applyBulkLinks").mockResolvedValue({ changed: 1, skipped_conflicts: 1, no_cost: 0 });
    render(<BulkAssign supplier={sup()} onDone={() => undefined} />);
    type(/buscar por texto/, "pienso");
    fireEvent.click(screen.getByRole("button", { name: "Vista previa" }));
    const button = (await screen.findByRole("button", { name: "Aplicar asignación" })) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(screen.getByText(/otro proveedor preferente: SYN-1/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Omitir los productos que tienen otro proveedor preferente"));
    expect(button.disabled).toBe(false);
    fireEvent.click(button);
    await waitFor(() => expect(apply).toHaveBeenCalledWith("s1", "b1", true));
  });

  it("loads the SKUs of this supplier from an assignment file and reports the rest", async () => {
    vi.spyOn(api, "parseAssignmentFile").mockResolvedValue({ groups: { s1: ["SYN-1", "SYN-2"], s9: ["SYN-3"] }, errors: [{ row: 5, code: "link_no_match" }], rows: 5 });
    render(<BulkAssign supplier={sup()} onDone={() => undefined} />);
    fireEvent.change(screen.getByLabelText(/archivo de dos columnas/), { target: { files: [new File(["x"], "a.csv", { type: "text/csv" })] } });
    expect(await screen.findByText(/Se cargaron 2 SKU de este proveedor/)).toBeTruthy();
    expect((screen.getByLabelText("Lista de SKU (uno por línea)") as HTMLTextAreaElement).value).toBe("SYN-1\nSYN-2");
    expect(screen.getByText(/1 filas del archivo son de otros proveedores/)).toBeTruthy();
  });

  it("shows nothing for a deactivated supplier", () => {
    const { container } = render(<BulkAssign supplier={sup({ status: "deactivated" })} onDone={() => undefined} />);
    expect(container.textContent).toBe("");
  });
});

describe("SupplierReview", () => {
  it("merges a duplicate only after the buyer picks the supplier to keep", async () => {
    vi.spyOn(api, "getSupplierReviewItems").mockResolvedValue([{ id: "i1", kind: "possible_duplicate", supplier_id: "s2", detail: "", status: "open", created_at: "x" }]);
    const resolve = vi.spyOn(api, "resolveSupplierReviewItem").mockResolvedValue();
    render(<SupplierReview suppliers={[sup(), sup({ id: "s2", name: "Proveedor sintético uno" })]} onChanged={() => undefined} />);
    expect(await screen.findByText("Posible duplicado")).toBeTruthy();
    const merge = screen.getByRole("button", { name: "Fusionar" }) as HTMLButtonElement;
    expect(merge.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Fusionar en"), { target: { value: "s1" } });
    fireEvent.click(merge);
    await waitFor(() => expect(resolve).toHaveBeenCalledWith("i1", "merge_into", "s1"));
  });

  it("shows an empty state", async () => {
    render(<SupplierReview suppliers={[]} onChanged={() => undefined} />);
    expect(await screen.findByText("No hay proveedores pendientes de revisión.")).toBeTruthy();
  });
});
