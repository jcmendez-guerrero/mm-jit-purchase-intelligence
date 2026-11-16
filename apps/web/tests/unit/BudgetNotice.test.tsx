// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { BudgetNotice } from "../../src/features/proposals/BudgetNotice";
import "../../src/i18n";

afterEach(cleanup);

describe("BudgetNotice (feature 011)", () => {
  it("shows nothing when no cap changed anything", () => {
    const { container } = render(<BudgetNotice flags={{ over_budget: "0.00", notes: [] }} />);
    expect(container.textContent).toBe("");
    cleanup();
    expect(render(<BudgetNotice flags={null} />).container.textContent).toBe("");
  });

  it("lists the deferred lines by SKU and product with the cap that bound, in Spanish", () => {
    render(
      <BudgetNotice
        flags={{
          over_budget: "0.00",
          notes: ["budget_bound:global_month"],
          deferred: [{ sku: "SYN-0002", product_name: "Producto 2", needed_qty: 22, estimated_cost: "22.00", reason: "budget_cap", bound_by: [{ kind: "global_month" }] }],
        }}
      />,
    );
    const box = screen.getByRole("region", { name: "Efecto del presupuesto en esta propuesta" });
    expect(within(box).getByText(/Límite que se ha aplicado: presupuesto mensual global/)).toBeTruthy();
    expect(within(box).getByText(/1 línea\(s\) necesaria\(s\) se han aplazado/)).toBeTruthy();
    expect(within(box).getByText(/SYN-0002 · Producto 2: 22 unidades \(22,00/)).toBeTruthy();
    expect(within(box).getByText(/aplazada por el límite de presupuesto mensual global/)).toBeTruthy();
    expect(within(box).queryByRole("alert")).toBeNull();
  });

  it("names a supplier cap by the supplier and asks a person to decide on a critical excess", () => {
    render(
      <BudgetNotice
        flags={{
          over_budget: "15.50",
          notes: ["budget_bound:supplier:Proveedor A", "critical_over_budget"],
          deferred: [{ sku: "SYN-0003", product_name: "Producto 3", needed_qty: 5, estimated_cost: "5.00", reason: "budget_cap", bound_by: [{ kind: "supplier", supplier_name: "Proveedor A" }] }],
        }}
      />,
    );
    expect(screen.getByText(/Límite que se ha aplicado: presupuesto semanal del proveedor Proveedor A/)).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("supera el presupuesto en");
    expect(screen.getByRole("alert").textContent).toContain("clínicamente críticos que se mantienen aunque superen el presupuesto");
  });
});
