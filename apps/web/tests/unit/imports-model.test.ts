import { describe, expect, it } from "vitest";
import { canImport, canSelfActivate, detailProblem, fileProblem, MAX_DETAIL, missingFields, ROLLBACK_REASONS, SELF_ACTIVATION_REASONS, setMapping, tidyDetail } from "../../src/features/imports/importsModel";

describe("import model", () => {
  it("only buyers and admins import", () => {
    expect(canImport(["buyer"])).toBe(true);
    expect(canImport(["admin"])).toBe(true);
    expect(canImport(["viewer", "approver"])).toBe(false);
  });
  it("refuses wrong types and oversized files before sending", () => {
    expect(fileProblem("datos.csv", 10, 100)).toBeNull();
    expect(fileProblem("DATOS.XLSX", 10, 100)).toBeNull();
    for (const bad of ["datos.xlsm", "datos.pdf", "datos", "datos.csv.exe"]) expect(fileProblem(bad, 10, 100)).toBe("type");
    expect(fileProblem("datos.csv", 101, 100)).toBe("size");
  });
  it("lists the required fields that are not mapped", () => {
    expect(missingFields({ A: "day" })).toEqual(["sku", "quantity", "kind", "provenance", "origin"]);
    expect(missingFields({ a: "sku", b: "day", c: "quantity", d: "kind", e: "provenance", f: "origin" })).toEqual([]);
  });
  it("keeps one header per field", () => {
    expect(setMapping({ A: "day", B: "quantity" }, "C", "day")).toEqual({ B: "quantity", C: "day" });
    expect(setMapping({ A: "day" }, "A", "")).toEqual({});
    expect(setMapping({ A: "day" }, "A", "quantity")).toEqual({ A: "quantity" });
  });
  it("limits the free-text detail of a reason to 100 characters once blanks are collapsed, and treats an empty detail as none", () => {
    expect(MAX_DETAIL).toBe(100);
    expect(detailProblem("")).toBe(false);
    expect(detailProblem("x".repeat(100))).toBe(false);
    expect(detailProblem("x".repeat(101))).toBe(true);
    expect(detailProblem(`${"x".repeat(60)}   ${"y".repeat(39)}`)).toBe(false);       // 100 characters after collapsing
    expect(tidyDetail("  Cifras   erróneas ")).toBe("Cifras erróneas");
    expect(tidyDetail("   ")).toBeUndefined();
  });
  it("offers the fixed reason lists of the contract", () => {
    expect([...ROLLBACK_REASONS]).toEqual(["wrong_figures", "wrong_file", "test", "replaced_by_newer", "other"]);
    expect([...SELF_ACTIVATION_REASONS]).toEqual(["only_person", "urgent", "other"]);
  });
  it("offers the self-activation reason only to admins", () => {
    expect(canSelfActivate(["admin"])).toBe(true);
    expect(canSelfActivate(["buyer"])).toBe(false);
  });
});
