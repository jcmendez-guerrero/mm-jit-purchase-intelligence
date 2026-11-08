// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, CostWriteRecord } from "../../src/api/client";
import { CostsScreen } from "../../src/features/costs/CostsScreen";
import { canOverride, canRelease, parseAmount, parseOpening } from "../../src/features/costs/costsModel";
import "../../src/i18n";
import { confirmAction } from "./confirm";

const write = (over: Partial<CostWriteRecord> = {}): CostWriteRecord => ({
  id: "w1", product_id: 10, supplier_id: "s1", trigger: "receipt_matched", proposed_value: "9.0000", previous_siweb_value: "8.0000", status: "pending_review", attempts: 0,
  last_error: null, median_cost: "9.00", lots: [{ variant_id: 1, lot: "L1", quantity: 3, unit_cost: "9.0000" }], pvp_used: "10.00", pvp_source: "stock_movement_price",
  margin_before: "0.2000", margin_after: "0.1000", rule_flags: ["margin_below_minimum"], tips: { cap: "0.30", cost_at_minimum: "8.50", cost_at_cap: "7.00" }, override: null, ...over,
});

beforeEach(() => {
  vi.spyOn(api, "getSuppliers").mockResolvedValue([{ id: "s1", name: "Proveedor Sintético A", terms: null, version: 0 }]);
  vi.spyOn(api, "getCosts").mockResolvedValue([]);
  vi.spyOn(api, "getCostWrites").mockResolvedValue([write()]);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("cost permissions", () => {
  it("blocks release below 15 % until an override exists and never lets the override's author release", () => {
    expect(canRelease(["buyer"], "b1", write())).toBe(false);
    const o = write({ override: { value: "8.50", reason: "oferta", by: "admin-1", at: null }, rule_flags: ["override"] });
    expect(canRelease(["buyer"], "b1", o)).toBe(true);
    expect(canRelease(["buyer", "admin"], "admin-1", o)).toBe(false);
    expect(canRelease(["admin"], "admin-1", o)).toBe(false);
    expect(canRelease(["buyer"], "b1", write({ status: "pending_link", rule_flags: [] }))).toBe(false);
    expect(canRelease(["buyer"], "b1", write({ rule_flags: ["margin_unavailable"], pvp_used: null, margin_after: null }))).toBe(false);
  });
  it("only an admin overrides", () => {
    expect(canOverride(["admin"], write())).toBe(true);
    expect(canOverride(["buyer"], write())).toBe(false);
  });
  it("parses amounts with a comma or a dot and refuses the rest", () => {
    expect(parseAmount("8,5")).toBe("8.5");
    for (const bad of ["", "-1", "1.23456", "abc"]) expect(parseAmount(bad)).toBeNull();
  });
});

describe("CostsScreen", () => {
  it("shows the median, the lots behind it, the PVP, both margins, the flag and the tips in Spanish", async () => {
    render(<CostsScreen userRoles={["viewer", "buyer"]} userId="b1" />);
    expect(await screen.findByText(/Lotes que forman la mediana/)).toBeTruthy();
    expect(screen.getByText("L1")).toBeTruthy();
    expect(screen.getByText(/PVP utilizado/).textContent).toContain("10,00");
    expect(screen.getByText(/Margen con el nuevo coste: 10,0\s?%/)).toBeTruthy();
    expect(screen.getByText(/por debajo del 15 %/)).toBeTruthy();
    expect(screen.getByText(/exactamente el 15 %: 8,50/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Liberar coste/ })).toBeNull();           // blocked
  });

  it("shows the price age next to the PVP, and a stale price as unavailable with its reason", async () => {
    vi.spyOn(api, "getCostWrites").mockResolvedValue([write({ pvp_used: null, pvp_age_days: 9, margin_before: null, margin_after: null, rule_flags: ["margin_unavailable", "pvp_stale"], tips: null })]);
    render(<CostsScreen userRoles={["viewer", "buyer"]} userId="b1" />);
    expect((await screen.findByText(/Precio confirmado por la última sincronización/)).textContent).toContain("9");
    expect(screen.getByText(/más de 7 días sin confirmarse/)).toBeTruthy();
    expect(screen.getByText(/PVP utilizado/).textContent).toContain("no disponible");
    expect(screen.queryByRole("button", { name: /Liberar coste/ })).toBeNull();
  });

  it("lets an admin set a value with a reason and shows the other-buyer requirement afterwards", async () => {
    const spy = vi.spyOn(api, "overrideCostWrite").mockResolvedValue({});
    render(<CostsScreen userRoles={["viewer", "admin"]} userId="admin-1" />);
    fireEvent.change(await screen.findByLabelText("Coste (€)"), { target: { value: "8,5" } });
    fireEvent.change(screen.getByLabelText("Motivo"), { target: { value: "oferta puntual" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar valor propio" }));
    expect(spy).not.toHaveBeenCalled(); // asks first
    expect(screen.getByRole("dialog", { name: "Sustituir el valor propuesto del coste" })).toBeTruthy();
    confirmAction();
    await waitFor(() => expect(spy).toHaveBeenCalledWith("w1", "8.5", "oferta puntual"));
    expect((await screen.findByRole("status")).textContent).toContain("Otra persona con rol de comprador");
  });

  it("does not open the confirmation for a value the screen would refuse", async () => {
    const spy = vi.spyOn(api, "overrideCostWrite").mockResolvedValue({});
    render(<CostsScreen userRoles={["viewer", "admin"]} userId="admin-1" />);
    fireEvent.change(await screen.findByLabelText("Coste (€)"), { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar valor propio" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(spy).not.toHaveBeenCalled();
  });

  it("corrects a lot cost on arrival and has no free supplier-cost entry", async () => {
    const spy = vi.spyOn(api, "correctLotCost").mockResolvedValue({});
    render(<CostsScreen userRoles={["viewer", "buyer"]} userId="b1" />);
    fireEvent.change(await screen.findByLabelText("Coste corregido del lote L1"), { target: { value: "9,5" } });
    fireEvent.click(screen.getByRole("button", { name: "Corregir coste del lote" }));
    await waitFor(() => expect(spy).toHaveBeenCalledWith({ variant_id: 1, supplier_id: "s1", lot: "L1", amount: "9.5", includes_recargo: true, source: "receipt_correction" }));
    expect(screen.queryByLabelText(/coste del proveedor/i)).toBeNull();
  });

  it("releases an unblocked request and translates a refusal", async () => {
    vi.spyOn(api, "getCostWrites").mockResolvedValue([write({ rule_flags: [], margin_after: "0.2000" })]);
    const spy = vi.spyOn(api, "approveCostWrite").mockRejectedValue(new ApiError(403, "auth_mfa_stale"));
    render(<CostsScreen userRoles={["viewer", "buyer"]} userId="b1" />);
    fireEvent.click(await screen.findByRole("button", { name: /Liberar coste/ }));
    confirmAction();
    expect((await screen.findByRole("alert")).textContent).toContain("segundo factor");
    expect(spy).toHaveBeenCalledWith("w1");
  });
});


describe("opening cost and update request", () => {
  const fill = async (over: Partial<Record<string, string>> = {}) => {
    render(<CostsScreen userRoles={["viewer", "buyer"]} userId="b1" />);
    await screen.findByLabelText("Proveedor");
    await waitFor(() => expect(screen.getByRole("option", { name: "Proveedor Sintético A" })).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Proveedor"), { target: { value: over.supplier ?? "s1" } });
    fireEvent.change(screen.getByLabelText("Producto (número)"), { target: { value: over.product ?? "10" } });
    fireEvent.change(screen.getByLabelText("Variante (número)"), { target: { value: over.variant ?? "1" } });
    fireEvent.change(screen.getByLabelText("Coste (€)"), { target: { value: over.amount ?? "1,5" } });
  };

  it("parses the typed values and names the first invalid field", () => {
    expect(parseOpening("10", "1", "1,5")).toEqual({ productId: 10, variantId: 1, amount: "1.5" });
    expect(parseOpening("x", "1", "1")).toEqual({ invalid: "product" });
    expect(parseOpening("1", "0", "1")).toEqual({ invalid: "variant" });
    expect(parseOpening("1", "1", "-2")).toEqual({ invalid: "amount" });
  });

  it("saves the opening cost as a lot entry and then requests the update, which stays a review request", async () => {
    const add = vi.spyOn(api, "addOpeningCost").mockResolvedValue({});
    const req = vi.spyOn(api, "requestCostUpdate").mockResolvedValue({ status: "pending_review", warnings: [], request_id: "w1" });
    await fill();
    fireEvent.click(screen.getByRole("button", { name: "Guardar coste inicial" }));
    await waitFor(() => expect(add).toHaveBeenCalledWith({ variant_id: 1, supplier_id: "s1", amount: "1.5", includes_recargo: true }));
    fireEvent.click(screen.getByRole("button", { name: "Solicitar actualización de coste" }));
    await waitFor(() => expect(req).toHaveBeenCalledWith(10, "s1"));
    expect((await screen.findByRole("status")).textContent).toContain("revísela y libérela más abajo");
  });

  it("says so when nothing qualifies and refuses invalid input without calling the server", async () => {
    const req = vi.spyOn(api, "requestCostUpdate").mockResolvedValue({ status: "not_applicable", warnings: ["no_lots_in_stock"], request_id: null });
    await fill({ amount: "abc" });
    fireEvent.click(screen.getByRole("button", { name: "Solicitar actualización de coste" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Coste");
    expect(req).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Coste (€)"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Solicitar actualización de coste" }));
    expect((await screen.findByRole("status")).textContent).toContain("No hay lotes con stock ni coste inicial");
  });

  it("is not offered to someone who is not a buyer", async () => {
    render(<CostsScreen userRoles={["viewer", "admin"]} userId="a1" />);
    await screen.findByText(/Costes registrados/);
    expect(screen.queryByRole("button", { name: "Solicitar actualización de coste" })).toBeNull();
  });
});
