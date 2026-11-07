import { describe, expect, it } from "vitest";
import { canCreate, constraintLabel, emptyForm, emptySupplier, toRequest } from "./scenariosModel";

describe("scenario form", () => {
  it("needs a name and treats blank fields as no change", () => {
    expect(toRequest(emptyForm())).toEqual({ invalid: "name" });
    const r = toRequest({ ...emptyForm(), name: " Prueba " });
    expect(r).toEqual({ body: { name: "Prueba", disabled_suppliers: [], supplier_deltas: {}, service_level_delta: "0" } });
  });
  it("accepts Spanish decimals and converts points to a fraction", () => {
    const r = toRequest({ ...emptyForm(), name: "a", budget: "1500,50", service_level_pp: "-1,5" });
    expect(r).toMatchObject({ body: { budget: "1500.50", service_level_delta: "-0.0150" } });
  });
  it("rejects bad values and names the supplier", () => {
    expect(toRequest({ ...emptyForm(), name: "a", budget: "abc" })).toEqual({ invalid: "budget" });
    expect(toRequest({ ...emptyForm(), name: "a", service_level_pp: "90" })).toEqual({ invalid: "service_level" });
    const f = { ...emptyForm(), name: "a", suppliers: { s1: { ...emptySupplier(), lead_time_days: "x" } } };
    expect(toRequest(f)).toEqual({ invalid: "lead_time_days", supplier: "s1" });
  });
  it("collects disabled suppliers and per-supplier changes", () => {
    const f = { ...emptyForm(), name: "a", suppliers: { s1: { ...emptySupplier(), disabled: true }, s2: { ...emptySupplier(), min_order_value: "100", pack_multiple: "6" } } };
    expect(toRequest(f)).toMatchObject({ body: { disabled_suppliers: ["s1"], supplier_deltas: { s2: { min_order_value: "100", pack_multiple: 6 } } } });
  });
  it("only buyers create", () => {
    expect(canCreate(["buyer"])).toBe(true);
    expect(canCreate(["viewer", "approver"])).toBe(false);
  });
  it("splits constraint keys", () => {
    expect(constraintLabel("min_order:s1")).toEqual({ kind: "min_order", supplier: "s1" });
    expect(constraintLabel("budget")).toEqual({ kind: "budget" });
  });
});
