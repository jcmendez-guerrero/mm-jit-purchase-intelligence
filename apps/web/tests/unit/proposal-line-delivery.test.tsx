// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { ProposalLine } from "../../src/api/client";
import { ProposalLineExplanation } from "../../src/features/proposals/ProposalLineExplanation";
import "../../src/i18n";

/** T029 (FR-020, FR-021): a proposal line says when its supplier's order is expected and which terms versions produced it. */

const line = (terms: Record<string, unknown> | undefined): ProposalLine =>
  ({
    id: "l1", variant_id: 9001, sku: "SYN-001", qty: 10,
    explanation: {
      policy: "forecast", forecast_eligible: true, forecast_basis: "actual_demand", service_level: "95", horizon_days: 14, expected_demand: 8, safety_stock: 2,
      order_up_to: 12, reorder_point: 5, need: 6, clinical_critical: false, position: { on_hand: 0, expiring: 0, usable: 0, inbound: 0, total: 0 },
      supplier: { chosen: "s1", reason: "lowest_cost", alternatives: [], rejected: [] }, cost: { unit: "10.0000", source: "manual", status: "ok" }, constraints: [],
      terms,
    },
  }) as unknown as ProposalLine;

const base = { supplier_version: 3, override_version: null, sources: {}, conflicts: [], preferred: false, supplier_discount: "0" };

afterEach(cleanup);

describe("ProposalLineExplanation delivery", () => {
  it("shows the expected delivery date in Spanish format next to the terms versions", () => {
    render(<ProposalLineExplanation line={line({ ...base, expected_delivery_date: "2026-11-17" })} />);
    expect(screen.getByText(/Entrega prevista: 17\/11\/2026/)).toBeTruthy();
    expect(screen.getByText(/proveedor v3/)).toBeTruthy();
  });

  it("shows no delivery sentence for a proposal that has no date (older proposals)", () => {
    render(<ProposalLineExplanation line={line(base)} />);
    expect(screen.queryByText(/Entrega prevista/)).toBeNull();
    expect(screen.getByText(/proveedor v3/)).toBeTruthy();
  });
});
