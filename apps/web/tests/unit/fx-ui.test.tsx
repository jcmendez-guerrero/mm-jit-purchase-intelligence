// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ProposalLine, SupplierLinkRow, SupplierReviewItem, SupplierSummary } from "../../src/api/client";
import { LinksPanel } from "../../src/features/suppliers/LinksPanel";
import { SupplierReview } from "../../src/features/suppliers/SupplierReview";
import { ProposalLineExplanation } from "../../src/features/proposals/ProposalLineExplanation";
import "../../src/i18n";

/** T040 (FR-035): the exchange rate behind a converted cost, and the suppliers left out for lack of one, are on screen. */

const sup = (over: Partial<SupplierSummary> = {}): SupplierSummary => ({
  id: "s1", name: "Proveedor Sintético Dólar", terms: null, version: 0, supplier_version: 3, status: "active", classification: "purchasing", origin: "platform",
  erp_link_state: "none", fiscal_type: "foreign", country: "US", currency: "USD", payment_terms_days: 30, order_channel: "email", ...over,
});
const usdLink = (over: Partial<SupplierLinkRow> = {}): SupplierLinkRow => ({
  sku: "SYN-000001", name: "Pienso sintético", cost: "1.1000", currency: "USD", cost_source: "siweb_product_supplier", includes_recargo: false, pack_size: null, min_qty: null,
  verified_at: "2026-11-08T10:00:00Z", erp_link: "link_with_cost", fx_state: "ok", eur_equivalent: "0.8800", fx_rate: "0.8", fx_date: "2026-11-06", ...over,
});
const review = (kind: string): SupplierReviewItem => ({ id: "r1", kind, supplier_id: "s1", detail: "USD", status: "open", created_at: "x" });

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("review list", () => {
  it("explains a supplier left out for lack of an exchange rate, with the currency", async () => {
    vi.spyOn(api, "getSupplierReviewItems").mockResolvedValue([review("fx_rate_missing")]);
    render(<SupplierReview suppliers={[sup()]} onChanged={() => undefined} />);
    expect(await screen.findByText(/Sin tipo de cambio guardado/)).toBeTruthy();
    expect(screen.getByText(/Proveedor Sintético Dólar/)).toBeTruthy();
    expect(screen.getByText(/USD/)).toBeTruthy();
  });

  it("explains a rate older than seven days", async () => {
    vi.spyOn(api, "getSupplierReviewItems").mockResolvedValue([review("fx_rate_stale")]);
    render(<SupplierReview suppliers={[sup()]} onChanged={() => undefined} />);
    expect(await screen.findByText(/más de 7 días/)).toBeTruthy();
  });
});

describe("links of a foreign supplier", () => {
  it("shows the cost in its own currency with the euro equivalent, the rate and its day", async () => {
    vi.spyOn(api, "getSupplierLinks").mockResolvedValue([usdLink()]);
    render(<LinksPanel supplier={sup()} canManage={false} />);
    expect(await screen.findByText("SYN-000001")).toBeTruthy();
    expect(screen.getByText(/1,10\s*US\$/)).toBeTruthy();                               // never shown as euros
    expect(screen.getByText(/0,88 €.*tipo 0,8 del 06\/11\/2026/)).toBeTruthy();
  });

  it("says why there is no equivalent when the rate is missing or old", async () => {
    vi.spyOn(api, "getSupplierLinks").mockResolvedValue([usdLink({ fx_state: "missing", eur_equivalent: null, fx_rate: null, fx_date: null })]);
    const first = render(<LinksPanel supplier={sup()} canManage={false} />);
    expect(await screen.findByText(/Sin tipo de cambio válido/)).toBeTruthy();
    first.unmount();
    vi.spyOn(api, "getSupplierLinks").mockResolvedValue([usdLink({ fx_state: "stale", eur_equivalent: null })]);
    render(<LinksPanel supplier={sup()} canManage={false} />);
    expect(await screen.findByText(/tipo de cambio de más de 7 días \(06\/11\/2026\)/i)).toBeTruthy();
  });

  it("keeps euro costs exactly as before", async () => {
    vi.spyOn(api, "getSupplierLinks").mockResolvedValue([usdLink({ currency: "EUR", cost: "2.5000", fx_state: null, eur_equivalent: null, fx_rate: null, fx_date: null })]);
    render(<LinksPanel supplier={sup({ currency: "EUR" })} canManage={false} />);
    expect(await screen.findByText("2,50 €")).toBeTruthy();
    expect(screen.queryByText(/tipo/)).toBeNull();
  });
});

describe("proposal line", () => {
  const line = (fx: Record<string, string> | undefined): ProposalLine =>
    ({
      id: "l1", variant_id: 9001, sku: "SYN-001", qty: 10,
      explanation: {
        policy: "forecast", forecast_eligible: true, forecast_basis: "actual_demand", service_level: "95", horizon_days: 14, expected_demand: 8, safety_stock: 2,
        order_up_to: 12, reorder_point: 5, need: 6, clinical_critical: false, position: { on_hand: 0, expiring: 0, usable: 0, inbound: 0, total: 0 },
        supplier: { chosen: "s1", reason: "lowest_cost", alternatives: [], rejected: [] }, cost: { unit: "0.8800", source: "siweb_product_supplier", status: "ok" }, constraints: [],
        terms: { supplier_version: 1, override_version: null, sources: {}, conflicts: [], preferred: false, supplier_discount: "0", fx },
      },
    }) as unknown as ProposalLine;

  it("names the original cost, the rate and its day when a cost was converted", () => {
    render(<ProposalLineExplanation line={line({ currency: "USD", original_cost: "1.1000", eur_per_unit: "0.8", published_on: "2026-11-06" })} />);
    expect(screen.getByText(/Coste convertido de 1,10 USD a euros con el tipo 0,8 del 06\/11\/2026/)).toBeTruthy();
  });

  it("says nothing about exchange rates for a euro cost", () => {
    render(<ProposalLineExplanation line={line(undefined)} />);
    expect(screen.queryByText(/convertido/)).toBeNull();
  });
});
