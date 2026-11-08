// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { DataTable, type Column } from "../../../src/ui/DataTable";
import { preferencesStore } from "../../../src/ui/usePreferences";
import "../../../src/i18n";

/** T034 — DataTable behavioural contract (contracts/ui-contracts.md §5). */

interface Row { id: number; name: string; qty: number }
const columns: Column<Row>[] = [
  { id: "name", header: "Producto", cell: (r) => r.name, sortValue: (r) => r.name },
  { id: "qty", header: "Cantidad", cell: (r) => r.qty, sortValue: (r) => r.qty, align: "end" },
  { id: "note", header: "Nota", cell: () => "—" },
];
const rows: Row[] = [
  { id: 1, name: "Beta", qty: 5 },
  { id: 2, name: "Alfa", qty: 20 },
  { id: 3, name: "Gamma", qty: 1 },
];

beforeEach(() => {
  localStorage.clear();
  preferencesStore.setDensity("comfortable");
});
afterEach(cleanup);

const names = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0]?.textContent ?? within(r).getAllByRole("rowheader")[0]?.textContent);

describe("DataTable", () => {
  it("renders real table semantics inside a labelled, focusable scroll region", () => {
    render(<DataTable ariaLabel="Productos" columns={columns} rows={rows} rowKey={(r) => r.id} />);
    expect(screen.getByRole("table", { name: "Productos" })).toBeTruthy();
    const region = screen.getByRole("region", { name: "Tabla desplazable: Productos" });
    expect(region.getAttribute("tabindex")).toBe("0");
    expect(screen.getAllByRole("columnheader")).toHaveLength(3);
  });

  it("has a sticky header", () => {
    const { container } = render(<DataTable ariaLabel="Productos" columns={columns} rows={rows} rowKey={(r) => r.id} />);
    expect(container.querySelector("thead.mmi-table__head")).toBeTruthy();
  });

  it("sorts on header activation, sets aria-sort and keeps the choice while mounted", () => {
    const { rerender } = render(<DataTable ariaLabel="Productos" columns={columns} rows={rows} rowKey={(r) => r.id} />);
    const header = screen.getByRole("columnheader", { name: /Producto/ });
    expect(header.getAttribute("aria-sort")).toBe("none");
    expect(screen.getByRole("button", { name: "Producto" }).getAttribute("title")).toBe("Ordenar por Producto"); // the hint, without taking part in label lookups
    fireEvent.click(screen.getByRole("button", { name: "Producto" }));
    expect(header.getAttribute("aria-sort")).toBe("ascending");
    expect(names()).toEqual(["Alfa", "Beta", "Gamma"]);
    fireEvent.click(screen.getByRole("button", { name: "Producto" }));
    expect(header.getAttribute("aria-sort")).toBe("descending");
    expect(names()).toEqual(["Gamma", "Beta", "Alfa"]);
    rerender(<DataTable ariaLabel="Productos" columns={columns} rows={[...rows]} rowKey={(r) => r.id} />);
    expect(screen.getByRole("columnheader", { name: /Producto/ }).getAttribute("aria-sort")).toBe("descending");
  });

  it("sorts numbers numerically and leaves non-sortable columns without a button", () => {
    render(<DataTable ariaLabel="Productos" columns={columns} rows={rows} rowKey={(r) => r.id} />);
    fireEvent.click(screen.getByRole("button", { name: "Cantidad" }));
    expect(names()).toEqual(["Gamma", "Beta", "Alfa"]);
    expect(screen.queryByRole("button", { name: "Nota" })).toBeNull();
  });

  it("applies the density preference", () => {
    const { container } = render(<DataTable ariaLabel="Productos" columns={columns} rows={rows} rowKey={(r) => r.id} />);
    expect(container.querySelector(".mmi-table--compact")).toBeNull();
    act(() => preferencesStore.setDensity("compact"));
    expect(container.querySelector(".mmi-table--compact")).toBeTruthy();
  });

  it("paginates with labelled controls and announces the row count", () => {
    const many = Array.from({ length: 120 }, (_, i) => ({ id: i, name: `P${String(i).padStart(3, "0")}`, qty: i }));
    render(<DataTable ariaLabel="Productos" columns={columns} rows={many} rowKey={(r) => r.id} pageSize={50} />);
    expect(screen.getAllByRole("row")).toHaveLength(51);
    expect(screen.getByText("Filas: 120")).toBeTruthy();
    expect(screen.getByText("Página 1 de 3")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByText("Página 2 de 3")).toBeTruthy();
    expect(names()[0]).toBe("P050");
    expect(screen.getByRole("navigation", { name: "Paginación de la tabla" })).toBeTruthy();
  });

  it("renders only the first page of a 5,000-row dataset", () => {
    const huge = Array.from({ length: 5000 }, (_, i) => ({ id: i, name: `P${i}`, qty: i }));
    const t0 = performance.now();
    render(<DataTable ariaLabel="Productos" columns={columns} rows={huge} rowKey={(r) => r.id} />);
    expect(screen.getAllByRole("row")).toHaveLength(51);
    expect(performance.now() - t0).toBeLessThan(1500);
  });

  it("shows the empty state when there are no rows", () => {
    render(<DataTable ariaLabel="Productos" columns={columns} rows={[]} rowKey={(r: Row) => r.id} />);
    expect(screen.getByText("No hay datos que mostrar.")).toBeTruthy();
  });

  it("marks a row's leading edge with its tone and keeps long text from breaking layout", () => {
    const long = { id: 9, name: "X".repeat(300), qty: 1 };
    const { container } = render(<DataTable ariaLabel="Productos" columns={columns} rows={[long]} rowKey={(r) => r.id} rowTone={() => "danger"} />);
    expect(container.querySelector("tr.mmi-row--danger")).toBeTruthy();
    expect(container.querySelector(".mmi-table__cell")).toBeTruthy();
  });
});
