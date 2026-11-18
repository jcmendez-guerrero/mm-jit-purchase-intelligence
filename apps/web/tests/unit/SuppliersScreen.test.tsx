// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, OverrideView, SupplierSummary, SupplierTermsView, TermsDoc } from "../../src/api/client";
import { SuppliersScreen } from "../../src/features/suppliers/SuppliersScreen";
import "../../src/i18n";

const terms: TermsDoc = {
  min_order_value: "150.0000", min_qty_for_delivery: null, free_delivery_threshold: null, delivery_charge: "9.5000", order_days: [1], delivery_schedule: null,
  lead_time_days: 3, order_cutoff_time: null, delivery_weekdays: [], discounts: [], payment_terms_days: null, preferred: true, reliability: null, disabled: false, valid_to: null,
};
const suppliers: SupplierSummary[] = [
  { id: "s1", name: "Proveedor Sintético A", terms, version: 2 },
  { id: "s2", name: "Proveedor Sintético B", terms: null, version: 0 },
];
const view = (version = 2): SupplierTermsView => ({
  supplier_id: "s1", version, current: terms,
  history: [
    { version: 1, valid_from: "2026-01-01T00:00:00Z", valid_to: null, source: "erp", reason: "alta inicial", changed_by: "buyer-1", terms },
    { version: 2, valid_from: "2026-06-01T00:00:00Z", valid_to: null, source: "manual", reason: "nuevo transportista", changed_by: "buyer-2", terms },
  ],
});
const override: OverrideView = {
  sku: "SYN-0001", supplier_id: "s1", version: 1, history: [],
  override: { pack_multiple: 12, min_qty_units: null, lead_time_days: null, payment_terms_days: null, preferred: null, reliability: null, disabled: null },
  effective: {
    lead_time_days: 3, pack_multiple: 12, min_qty_units: null, payment_terms_days: null, preferred: true, reliability: null, disabled: false,
    sources: { lead_time_days: "supplier", pack_multiple: "override", preferred: "supplier", disabled: "default" },
    conflicts: [{ field: "pack_multiple", erp_value: 6, local_value: 12, winner: "local" }], supplier_version: 2, override_version: 1, flags: [],
  },
};

beforeEach(() => {
  vi.spyOn(api, "getSuppliers").mockResolvedValue(suppliers);
  vi.spyOn(api, "getSupplierTerms").mockResolvedValue(view());
  vi.spyOn(api, "getOverrideTerms").mockResolvedValue(override);
  vi.spyOn(api, "getSupplierLinks").mockResolvedValue([]);
  vi.spyOn(api, "getSupplierReviewItems").mockResolvedValue([]);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const open = async (roles = ["viewer", "buyer"]) => {
  render(<SuppliersScreen userRoles={roles} />);
  fireEvent.click(await screen.findByRole("button", { name: "Proveedor Sintético A" }));
  await screen.findByText("Condiciones de Proveedor Sintético A");
};

describe("SuppliersScreen (Spanish)", () => {
  it("lists suppliers with lead time, minimum order in euros, version and badges", async () => {
    render(<SuppliersScreen userRoles={["viewer"]} />);
    expect(await screen.findByText("Proveedor Sintético A")).toBeTruthy();
    expect(screen.getByText("Preferido")).toBeTruthy();
    expect(screen.getByText("Sin condiciones")).toBeTruthy();
    expect(document.body.textContent).toMatch(/150,00\s*€/);
  });

  it("offers help on the lead time next to its field (feature 012)", async () => {
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Qué significa plazo de entrega" }));
    expect(screen.getByRole("note").textContent).toContain("hasta que la mercancía está disponible");
    expect((screen.getByLabelText("Plazo de entrega (días)") as HTMLInputElement).value).toBe("3");
  });

  it("names the field and the rule, focuses the first invalid field, and clears the message once the value is corrected (feature 012)", async () => {
    const put = vi.spyOn(api, "putSupplierTerms").mockResolvedValue({ version: 2 });
    await open();
    const lead = screen.getByLabelText("Plazo de entrega (días)") as HTMLInputElement;
    fireEvent.change(lead, { target: { value: "abc" } });
    fireEvent.change(screen.getByLabelText("Motivo del cambio"), { target: { value: "prueba" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar nueva versión" }));
    expect(await screen.findByText("Introduce un número entero igual o mayor que cero.")).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(lead));
    expect(put).not.toHaveBeenCalled();
    fireEvent.change(lead, { target: { value: "7" } });
    await waitFor(() => expect(screen.queryByText("Introduce un número entero igual o mayor que cero.")).toBeNull());
  });

  it("loads the saved terms into the form and shows the version history with source badges", async () => {
    await open();
    expect((screen.getByLabelText("Plazo de entrega (días)") as HTMLInputElement).value).toBe("3");
    expect((screen.getByLabelText("Pedido mínimo (€)") as HTMLInputElement).value).toBe("150");
    expect(screen.getByText("nuevo transportista")).toBeTruthy();
    expect(screen.getByText("ERP")).toBeTruthy();
    expect(screen.getByText("Manual")).toBeTruthy();
  });

  it("saves a new version with the version it was based on, accepting a decimal comma", async () => {
    const put = vi.spyOn(api, "putSupplierTerms").mockResolvedValue({ version: 3 });
    await open();
    fireEvent.change(screen.getByLabelText("Gastos de envío (€)"), { target: { value: "12,50" } });
    fireEvent.change(screen.getByLabelText("Motivo del cambio"), { target: { value: "tarifa nueva" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar nueva versión" }));
    await waitFor(() => expect(put).toHaveBeenCalled());
    const [id, payload, version] = put.mock.calls[0]!;
    expect(id).toBe("s1");
    expect(version).toBe(2);
    expect(payload).toMatchObject({ delivery_charge: "12.50", reason: "tarifa nueva", lead_time_days: 3 });
    expect((await screen.findByRole("status")).textContent).toBe("Condiciones guardadas (versión 3).");
  });

  it("adds and removes discount tiers, then saves the remaining one", async () => {
    const put = vi.spyOn(api, "putSupplierTerms").mockResolvedValue({ version: 3 });
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Añadir descuento" }));
    expect(screen.getByLabelText("A partir de 1")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Quitar descuento 1" }));
    expect(screen.queryByLabelText("A partir de 1")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Añadir descuento" }));
    fireEvent.change(screen.getByLabelText("A partir de 1"), { target: { value: "500" } });
    fireEvent.change(screen.getByLabelText("Descuento 1"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar nueva versión" }));
    await waitFor(() => expect(put).toHaveBeenCalled());
    expect(put.mock.calls[0]![1]).toMatchObject({ discounts: [{ kind: "percent", basis: "order_value", threshold: "500", value: "3" }] });
  });

  it("explains a stale save in Spanish and offers to load the current version", async () => {
    vi.spyOn(api, "putSupplierTerms").mockRejectedValue(new ApiError(412, "revision_conflict", 5));
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Guardar nueva versión" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("versión más reciente (versión 5)");
    vi.mocked(api.getSupplierTerms).mockResolvedValue(view(5));
    fireEvent.click(within(alert).getByRole("button", { name: "Cargar versión actual" }));
    await waitFor(() => expect(api.getSupplierTerms).toHaveBeenCalledTimes(2));
  });

  it("shows a validation refusal in Spanish, never the code", async () => {
    vi.spyOn(api, "putSupplierTerms").mockRejectedValue(new ApiError(422, "terms_threshold_below_minimum"));
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Guardar nueva versión" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("umbral de envío gratuito");
    expect(document.body.textContent).not.toContain("terms_threshold_below_minimum");
  });

  it("is read-only without the buyer role", async () => {
    await open(["viewer"]);
    expect((screen.getByLabelText("Plazo de entrega (días)") as HTMLInputElement).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "Guardar nueva versión" })).toBeNull();
    expect(screen.getByText("Solo lectura: editar condiciones requiere el rol de comprador.")).toBeTruthy();
  });

  it("keeps the fields locked until the saved terms load, then keeps what is typed (MMI-12)", async () => {
    let release: (v: SupplierTermsView) => void = () => {};
    vi.spyOn(api, "getSupplierTerms").mockReturnValue(new Promise<SupplierTermsView>((resolve) => (release = resolve)));
    render(<SuppliersScreen userRoles={["viewer", "buyer"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Proveedor Sintético A" }));
    const lead = (await screen.findByLabelText("Plazo de entrega (días)")) as HTMLInputElement;
    expect(lead.disabled).toBe(true);
    release(view());
    await waitFor(() => expect(lead.disabled).toBe(false));
    expect(lead.value).toBe("3");
    fireEvent.change(lead, { target: { value: "7" } });
    expect(lead.value).toBe("7");
  });

  it("shows where each effective product value comes from and flags the ERP conflict", async () => {
    await open();
    fireEvent.change(screen.getByLabelText("SKU del producto"), { target: { value: "SYN-0001" } });
    fireEvent.click(screen.getByRole("button", { name: "Ver condiciones aplicadas" }));
    const table = await screen.findByRole("table", { name: "Condiciones aplicadas a un producto" });
    const pack = within(table).getByText("Múltiplo de caja").closest("tr")!;
    expect(within(pack).getByText("12")).toBeTruthy();
    expect(within(pack).getByText("Excepción del producto")).toBeTruthy();
    expect(within(within(table).getByText("Plazo (días)").closest("tr")!).getByText("Proveedor")).toBeTruthy();
    expect(screen.getByText("Múltiplo de caja: el ERP indica 6, se aplica el valor local 12.")).toBeTruthy();
  });

  it("saves a product exception with the version it was based on", async () => {
    const put = vi.spyOn(api, "putOverrideTerms").mockResolvedValue({ version: 2 });
    await open();
    fireEvent.change(screen.getByLabelText("SKU del producto"), { target: { value: " SYN-0001 " } });
    fireEvent.click(screen.getByRole("button", { name: "Ver condiciones aplicadas" }));
    await screen.findByRole("table", { name: "Condiciones aplicadas a un producto" });
    fireEvent.change(screen.getAllByLabelText("Múltiplo de caja")[0]!, { target: { value: "24" } });
    fireEvent.change(screen.getByLabelText("Desactivado", { selector: "select" }), { target: { value: "yes" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar excepción" }));
    await waitFor(() => expect(put).toHaveBeenCalled());
    expect(put.mock.calls[0]!.slice(0, 2)).toEqual(["SYN-0001", "s1"]);
    expect(put.mock.calls[0]![2]).toMatchObject({ pack_multiple: 24, disabled: true, preferred: null });
    expect(put.mock.calls[0]![3]).toBe(1);
  });
  it("asks for the SKU, keeps the load button off until one is typed and never asks for a numeric id", async () => {
    await open();
    const load = screen.getByRole("button", { name: "Ver condiciones aplicadas" }) as HTMLButtonElement;
    expect(load.disabled).toBe(true);
    expect(screen.queryByLabelText(/variante/i)).toBeNull();
    fireEvent.change(screen.getByLabelText("SKU del producto"), { target: { value: "SYN-0001" } });
    expect(load.disabled).toBe(false);
  });

  it("hides the loaded terms and the save button as soon as the SKU box no longer matches them", async () => {
    await open();
    fireEvent.change(screen.getByLabelText("SKU del producto"), { target: { value: "SYN-0001" } });
    fireEvent.click(screen.getByRole("button", { name: "Ver condiciones aplicadas" }));
    await screen.findByRole("table", { name: "Condiciones aplicadas a un producto" });
    expect(screen.getByRole("button", { name: "Guardar excepción" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("SKU del producto"), { target: { value: "SYN-0002" } });
    expect(screen.queryByRole("table", { name: "Condiciones aplicadas a un producto" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Guardar excepción" })).toBeNull();
    fireEvent.change(screen.getByLabelText("SKU del producto"), { target: { value: " SYN-0001 " } });
    expect(screen.getByRole("button", { name: "Guardar excepción" })).toBeTruthy();   // typing the loaded SKU again (trimmed) shows it again
  });

  it("shows the Spanish message for an unknown or ambiguous SKU, never the code", async () => {
    vi.spyOn(api, "getOverrideTerms").mockRejectedValueOnce(new ApiError(422, "sku_unknown")).mockRejectedValueOnce(new ApiError(422, "sku_ambiguous"));
    await open();
    fireEvent.change(screen.getByLabelText("SKU del producto"), { target: { value: "SYN-NO-EXISTE" } });
    fireEvent.click(screen.getByRole("button", { name: "Ver condiciones aplicadas" }));
    expect((await screen.findByRole("alert")).textContent).toContain("El SKU no existe en el catálogo cargado");
    fireEvent.click(screen.getByRole("button", { name: "Ver condiciones aplicadas" }));
    await waitFor(() => expect(document.body.textContent).toContain("corresponde a más de un producto"));
    expect(document.body.textContent).not.toContain("sku_unknown");
  });
});
