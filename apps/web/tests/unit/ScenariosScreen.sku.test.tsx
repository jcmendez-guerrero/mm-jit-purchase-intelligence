// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ScenarioDetail } from "../../src/api/client";
import { ScenariosScreen } from "../../src/features/scenarios/ScenariosScreen";
import "../../src/i18n";

const detail = {
  id: "11111111-1111-4111-8111-111111111111", name: "Sin proveedor A", status: "ready", parameters: {}, input_versions: {}, result_hash: "h", created_by: "buyer",
  created_at: "2026-11-16T10:00:00Z", sensitivity: [],
  summary: {
    baseline: { total: "100.00", over_budget: "0.00", lines: 2 }, scenario: { total: "102.50", over_budget: "0.00", lines: 2, budget: null, utilisation: null },
    delta_total: "2.50", binding: [], infeasible: { over_by: "5.00", clinical_critical_variants: [9001, 9003], clinical_critical_skus: ["SYN-9001", null] }, notes: [],
    changes: [
      { variant_id: 9001, sku: "SYN-9001", supplier_before: "s1", supplier_after: "s2", qty_before: 12, qty_after: 12, reasons: ["supplier_disabled"] },
      { variant_id: 9002, sku: null, name: "Producto sin código", supplier_before: "s1", supplier_after: "s2", qty_before: 6, qty_after: 6, reasons: ["supplier_disabled"] },
    ],
  },
  results: [{
    supplier_id: "s2", supplier_name: "Proveedor B", order_total: "102.50", subtotal: "108.00", delivery_charge: null, discount: null, free_delivery: null, expected_delivery: null,
    budget_utilisation: null, binding_constraints: [],
    lines: [
      { variant_id: 9001, sku: "SYN-9001", qty: 12, unit_cost: "5.0000", line_total: "60.0000", clinical_critical: false },
      { variant_id: 9002, sku: null, name: "Producto sin código", qty: 6, unit_cost: "8.0000", line_total: "48.0000", clinical_critical: false },
    ],
  }],
} as unknown as ScenarioDetail;

beforeEach(() => {
  vi.spyOn(api, "getScenarios").mockResolvedValue({ scenarios: [{ id: detail.id, name: detail.name, status: "ready", created_by: "buyer", created_at: detail.created_at, result_hash: "h", delta_total: "2.50" }] } as never);
  vi.spyOn(api, "getSuppliers").mockResolvedValue([{ id: "s1", name: "Proveedor A" }, { id: "s2", name: "Proveedor B" }] as never);
  vi.spyOn(api, "getScenario").mockResolvedValue(detail);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

async function open() {
  render(<ScenariosScreen userRoles={["viewer", "buyer"]} />);
  const btn = await screen.findByRole("button", { name: "Abrir Sin proveedor A" });
  btn.click();
  await screen.findByText(/SYN-9001: Proveedor A/);
}

describe("ScenariosScreen shows the SKU, never the Siweb variant id", () => {
  it("shows the SKU in the change rows and the line table", async () => {
    await open();
    expect(screen.getByText(/SYN-9001: Proveedor A \(12\) → Proveedor B \(12\)/)).toBeTruthy();
    const table = screen.getByRole("table", { name: /Proveedor B/ });
    expect(within(table).getByText("SYN-9001")).toBeTruthy();
    expect(within(table).getByRole("columnheader", { name: "SKU" })).toBeTruthy();
  });

  it("never renders the variant id", async () => {
    await open();
    expect(document.body.textContent).not.toMatch(/(?<!SYN-)\b900[12]\b|#900|Variante/);      // the SKU "SYN-9001" is fine; the bare id is not
  });

  it("keeps rows with no SKU, with the Spanish marker", async () => {
    await open();
    expect(screen.getByText(/Sin SKU · Producto sin código: Proveedor A \(6\) → Proveedor B \(6\)/)).toBeTruthy();
    expect(within(screen.getByRole("table", { name: /Proveedor B/ })).getByText("Sin SKU · Producto sin código")).toBeTruthy();
    expect(within(screen.getByRole("table", { name: /Proveedor B/ })).getAllByRole("row")).toHaveLength(3);   // header + both lines
  });

  it("lists the critical products of an infeasible scenario by SKU, not by id", async () => {
    await open();
    expect(screen.getByText("Productos clínicamente críticos en el pedido: SYN-9001, Sin SKU")).toBeTruthy();
  });
});
