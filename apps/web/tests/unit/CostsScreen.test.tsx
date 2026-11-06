// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, CostWriteRecord } from "../../src/api/client";
import { CostsScreen } from "../../src/features/costs/CostsScreen";
import { canOverride, canRelease, parseAmount } from "../../src/features/costs/costsModel";
import "../../src/i18n";

const write = (over: Partial<CostWriteRecord> = {}): CostWriteRecord => ({
  id: "w1", product_id: 10, supplier_id: "s1", trigger: "receipt_matched", proposed_value: "9.0000", previous_siweb_value: "8.0000", status: "pending_review", attempts: 0,
  last_error: null, median_cost: "9.00", lots: [{ variant_id: 1, lot: "L1", quantity: 3, unit_cost: "9.0000" }], pvp_used: "10.00", pvp_source: "stock_movement_price",
  margin_before: "0.2000", margin_after: "0.1000", rule_flags: ["margin_below_minimum"], tips: { cap: "0.30", cost_at_minimum: "8.50", cost_at_cap: "7.00" }, override: null, ...over,
});

beforeEach(() => {
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

  it("lets an admin set a value with a reason and shows the other-buyer requirement afterwards", async () => {
    const spy = vi.spyOn(api, "overrideCostWrite").mockResolvedValue({});
    render(<CostsScreen userRoles={["viewer", "admin"]} userId="admin-1" />);
    fireEvent.change(await screen.findByLabelText("Coste (€)"), { target: { value: "8,5" } });
    fireEvent.change(screen.getByLabelText("Motivo"), { target: { value: "oferta puntual" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar valor propio" }));
    await waitFor(() => expect(spy).toHaveBeenCalledWith("w1", "8.5", "oferta puntual"));
    expect((await screen.findByRole("status")).textContent).toContain("Otra persona con rol de comprador");
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
    expect((await screen.findByRole("alert")).textContent).toContain("segundo factor");
    expect(spy).toHaveBeenCalledWith("w1");
  });
});
