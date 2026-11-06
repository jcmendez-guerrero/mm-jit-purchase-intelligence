import { describe, expect, it } from "vitest";
import { canDecideOverrides, canEditPolicies, parseId, scopeKeyValid, toForm, toPayload } from "../../src/features/policies/policiesModel";

describe("policy form", () => {
  it("shows the stored fraction as a Spanish percentage and sends a dot decimal", () => {
    const form = toForm({ service_level: "0.9750", safety_stock_units: null, min_units: "2", max_units: null, replenishment_cadence_days: null, valid_from: "2026-11-09" });
    expect(form.service_level_pct).toBe("97,5");
    expect(toPayload({ ...form, safety_stock_units: "3" })).toEqual({ body: { service_level_pct: "97.5", safety_stock_units: 3, min_units: 2 } });
  });
  it("names the first field that is not a number", () => {
    const base = toForm(null);
    expect(toPayload({ ...base, service_level_pct: "abc" })).toEqual({ invalid: "service_level_pct" });
    expect(toPayload({ ...base, min_units: "-1" })).toEqual({ invalid: "min_units" });
    expect(toPayload({ ...base, max_units: "1,5" })).toEqual({ invalid: "max_units" });
    expect(toPayload({ ...base, service_level_pct: "97.555" })).toEqual({ invalid: "service_level_pct" });
  });
  it("sends the start date only when given", () => {
    expect(toPayload({ ...toForm(null), min_units: "1", valid_from: "2026-12-01" })).toEqual({ body: { min_units: 1, valid_from: "2026-12-01" } });
  });
});

describe("keys, ids and roles", () => {
  it("validates the key for each scope", () => {
    expect(scopeKeyValid("global", "*")).toBe(true);
    expect(scopeKeyValid("global", "A")).toBe(false);
    expect(scopeKeyValid("segment", "critical")).toBe(true);
    expect(scopeKeyValid("segment", "Z")).toBe(false);
    expect(scopeKeyValid("product", "123")).toBe(true);
    expect(scopeKeyValid("product", "0")).toBe(false);
  });
  it("parses whole positive ids only", () => {
    expect(parseId(" 42 ")).toBe(42);
    for (const bad of ["", "0", "-3", "4.5", "x", "99999999999999999999"]) expect(parseId(bad)).toBeNull();
  });
  it("only buyers edit and only approvers decide", () => {
    expect(canEditPolicies(["buyer"])).toBe(true);
    expect(canEditPolicies(["admin", "approver"])).toBe(false);
    expect(canDecideOverrides(["approver"])).toBe(true);
    expect(canDecideOverrides(["buyer", "admin"])).toBe(false);
  });
});
