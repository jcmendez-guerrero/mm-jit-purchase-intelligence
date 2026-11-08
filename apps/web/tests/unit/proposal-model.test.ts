import { describe, expect, it } from "vitest";
import { canApprove, canEditLines, canSubmit, parseQty } from "../../src/features/proposals/proposalModel";

describe("proposal permissions", () => {
  it("only buyers edit and submit drafts", () => {
    expect(canEditLines(["viewer", "buyer"], "draft")).toBe(true);
    expect(canSubmit(["buyer"], "draft")).toBe(true);
    expect(canEditLines(["buyer"], "submitted")).toBe(false);
    expect(canEditLines(["admin", "approver"], "draft")).toBe(false);
  });
  it("only approvers approve submitted proposals; admin alone cannot", () => {
    expect(canApprove(["approver"], "submitted")).toBe(true);
    expect(canApprove(["admin"], "submitted")).toBe(false);
    expect(canApprove(["approver"], "draft")).toBe(false);
  });
});

describe("parseQty", () => {
  it("accepts whole non-negative numbers", () => {
    expect(parseQty(" 12 ")).toBe(12);
    expect(parseQty("0")).toBe(0);
  });
  it("rejects anything else", () => {
    for (const bad of ["", "-1", "1.5", "1,5", "abc", "1e3", "99999999999999999999"]) expect(parseQty(bad)).toBeNull();
  });
});

import { groupLinesBySupplier } from "../../src/features/proposals/proposalModel";

describe("lines grouped by supplier", () => {
  const lines = [
    { id: "a", supplier_id: "s2", supplier_name: "Proveedor B" },
    { id: "b", supplier_id: "s1", supplier_name: "Proveedor A" },
    { id: "c", supplier_id: "s2", supplier_name: "Proveedor B" },
    { id: "d", supplier_id: "s3", supplier_name: null },
  ];

  it("keeps the order in which suppliers first appear and the order of lines within each", () => {
    const groups = groupLinesBySupplier(lines, []);
    expect(groups.map((g) => g.id)).toEqual(["s2", "s1", "s3"]);
    expect(groups[0]!.lines.map((l) => l.id)).toEqual(["a", "c"]);
  });

  it("uses the supplier name, falling back to its id", () => {
    const groups = groupLinesBySupplier(lines, []);
    expect(groups.map((g) => g.name)).toEqual(["Proveedor B", "Proveedor A", "s3"]);
  });

  it("takes each subtotal from the server's group and never adds money itself", () => {
    const groups = groupLinesBySupplier(lines, [{ supplier_id: "s1", subtotal: "52.60" }]);
    expect(groups.find((g) => g.id === "s1")!.subtotal).toBe("52.60");
    expect(groups.find((g) => g.id === "s2")!.subtotal).toBeNull();
  });
});

import { pageLineGroups } from "../../src/features/proposals/proposalModel";

describe("paging grouped lines", () => {
  const make = (id: string, n: number, subtotal: string | null = "10.00") => ({ id, name: id, subtotal, lines: Array.from({ length: n }, (_, i) => ({ id: `${id}${i}` })) });
  const groups = [make("A", 3), make("B", 5), make("C", 2, null)];

  it("returns everything on one page when it fits", () => {
    const p = pageLineGroups(groups, 0, 50);
    expect(p.pages).toBe(1);
    expect(p.total).toBe(10);
    expect(p.groups.map((g) => [g.id, g.lines.length, g.continued, g.complete])).toEqual([["A", 3, false, true], ["B", 5, false, true], ["C", 2, false, true]]);
  });

  it("splits a group across pages and shows its subtotal only where it ends", () => {
    const first = pageLineGroups(groups, 0, 5);
    expect(first.pages).toBe(2);
    expect(first.groups.map((g) => [g.id, g.lines.length, g.continued, g.complete])).toEqual([["A", 3, false, true], ["B", 2, false, false]]);
    const second = pageLineGroups(groups, 1, 5);
    expect(second.groups.map((g) => [g.id, g.lines.length, g.continued, g.complete])).toEqual([["B", 3, true, true], ["C", 2, false, true]]);
  });

  it("keeps every line exactly once across pages and clamps the page number", () => {
    const seen = [0, 1, 2].flatMap((n) => pageLineGroups(groups, n, 4).groups.flatMap((g) => g.lines.map((l) => l.id)));
    expect(seen.sort()).toEqual(groups.flatMap((g) => g.lines.map((l) => l.id)).sort());
    expect(pageLineGroups(groups, 99, 4).groups.at(-1)!.id).toBe("C");
    expect(pageLineGroups(groups, -3, 4).groups[0]!.id).toBe("A");
  });
});
