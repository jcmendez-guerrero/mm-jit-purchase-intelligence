// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { ProposalLine } from "../../src/api/client";
import { ProposalLineExplanation } from "../../src/features/proposals/ProposalLineExplanation";
import "../../src/i18n";

afterEach(cleanup);

const line = (policy_applied?: Record<string, { source: string; revision: number } | string>): ProposalLine => ({
  id: "l1", variant_id: 9001, sku: "SYN-001", product_name: "Producto Sintético", supplier_id: "s1", supplier_name: "Proveedor A", qty: 10,
  unit_cost_with_recargo: "10.0000", line_total: "100.0000", risk: "low", confidence: "high", manual_override: false, topup: false, constraints_applied: [],
  explanation: {
    policy: "forecast", forecast_eligible: true, service_level: "95", horizon_days: 14, expected_demand: 8, safety_stock: 2, order_up_to: 12, reorder_point: 5, need: 10, top_up: false,
    clinical_critical: false, position: { on_hand: 0, expiring: 0, usable: 0, inbound: 0, total: 0 },
    supplier: { chosen: "s1", reason: "lowest_cost", alternatives: [], rejected: [] }, cost: { unit: "10.0000", source: "manual", status: "ok" }, constraints: [],
    ...(policy_applied ? { policy_applied } : {}),
  },
} as ProposalLine);

describe("ProposalLineExplanation: the policy behind each rule (feature 011, FR-004)", () => {
  it("names the scope and the version that supplied each rule, in Spanish", () => {
    render(<ProposalLineExplanation line={line({
      service_level: { source: "segment:A", revision: 3 }, min_units: { source: "global:*", revision: 2 }, max_units: { source: "product:77", revision: 1 },
    })} />);
    const list = screen.getByRole("list", { name: /Reglas aplicadas/ });
    expect(within(list).getByText("Nivel de servicio: segmento clase A (versión 3)")).toBeTruthy();
    expect(within(list).getByText("Mínimo: global (versión 2)")).toBeTruthy();
    expect(within(list).getByText("Máximo: producto (versión 1)")).toBeTruthy();
    expect(list.textContent).not.toContain("77");                                                   // the product key is the ERP id: never shown
  });

  it("ignores the stocking mode and records that carry no revision, and shows nothing when no policy applied", () => {
    render(<ProposalLineExplanation line={line({ stocking: "always_stocked", service_level: "segment:A" })} />);
    expect(screen.queryByRole("list", { name: /Reglas aplicadas/ })).toBeNull();
    cleanup();
    render(<ProposalLineExplanation line={line()} />);
    expect(screen.queryByText(/Reglas aplicadas/)).toBeNull();
  });
});
