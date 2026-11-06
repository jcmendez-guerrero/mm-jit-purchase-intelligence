import { describe, expect, it } from "vitest";
import { canImport, fileProblem, missingFields, setMapping } from "../../src/features/imports/importsModel";

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
    expect(missingFields({ A: "day" })).toEqual(["variant_id", "quantity", "kind", "provenance", "origin"]);
    expect(missingFields({ a: "variant_id", b: "day", c: "quantity", d: "kind", e: "provenance", f: "origin" })).toEqual([]);
  });
  it("keeps one header per field", () => {
    expect(setMapping({ A: "day", B: "quantity" }, "C", "day")).toEqual({ B: "quantity", C: "day" });
    expect(setMapping({ A: "day" }, "A", "")).toEqual({});
    expect(setMapping({ A: "day" }, "A", "quantity")).toEqual({ A: "quantity" });
  });
});
