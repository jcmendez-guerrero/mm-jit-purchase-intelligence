import { describe, expect, it } from "vitest";
import { dashboardQueryString } from "../../src/api/dashboard";
import { parseDashboardFilters, writeDashboardFilters } from "../../src/features/dashboard/useDashboardFilters";

const p = (q: string) => new URLSearchParams(q);

describe("dashboard filters in the address", () => {
  it("reads every filter from a shared link", () => {
    const { filters, ignored } = parseDashboardFilters(p("almacen=2&proveedor=sup-a&categoria=critical&familia=Fam&desde=2026-10-01&hasta=2026-11-09"));
    expect(filters).toEqual({ warehouse: 2, supplier: "sup-a", category: "critical", family: "Fam", from: "2026-10-01", to: "2026-11-09" });
    expect(ignored).toEqual([]);
  });

  it("ignores invalid values and reports them instead of guessing", () => {
    const { filters, ignored } = parseDashboardFilters(p("almacen=abc&proveedor=a%20b&categoria=Z&desde=2026-02-30&hasta=ayer"));
    expect(filters).toEqual({});
    expect(ignored).toEqual(["almacen", "proveedor", "categoria", "desde", "hasta"]);
  });

  it("drops an inverted date range", () => {
    const { filters, ignored } = parseDashboardFilters(p("desde=2026-11-09&hasta=2026-11-01"));
    expect(filters).toEqual({});
    expect(ignored).toEqual(["desde", "hasta"]);
  });

  it("writes filters and leaves other parameters alone; clearing removes only the filters", () => {
    const next = writeDashboardFilters({ warehouse: 1, category: "A" }, p("tab=x&proveedor=old"));
    expect(next.get("almacen")).toBe("1");
    expect(next.get("categoria")).toBe("A");
    expect(next.has("proveedor")).toBe(false);
    expect(next.get("tab")).toBe("x");
    expect(writeDashboardFilters({}, next).toString()).toBe("tab=x");
  });

  it("round-trips through the address", () => {
    const f = { warehouse: 3, supplier: "sup-b", from: "2026-10-01", to: "2026-10-31" };
    expect(parseDashboardFilters(writeDashboardFilters(f, p(""))).filters).toEqual(f);
  });

  it("builds the API query with the supplier and no empty values", () => {
    expect(dashboardQueryString({})).toBe("");
    expect(dashboardQueryString({ warehouse_id: 0, supplier_id: "sup-a", days: 30 })).toBe("?warehouse_id=0&supplier_id=sup-a&days=30");
  });
});
