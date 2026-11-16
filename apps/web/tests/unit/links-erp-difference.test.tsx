// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, SupplierLinkRow, SupplierSummary } from "../../src/api/client";
import { LinksPanel } from "../../src/features/suppliers/LinksPanel";
import i18n from "../../src/i18n";

/** T034 (FR-016): a manual cost never hides the ERP cost: who set it, and the difference against the ERP value, are on screen. */

const sup = (): SupplierSummary => ({
  id: "s1", name: "Proveedor Sintético Uno", terms: null, version: 0, supplier_version: 3, status: "active", classification: "purchasing", origin: "platform",
  erp_link_state: "none", fiscal_type: "national", country: "ES", currency: "EUR", payment_terms_days: 30, order_channel: "email",
});
const link = (over: Partial<SupplierLinkRow> = {}): SupplierLinkRow => ({
  sku: "SYN-000001", name: "Pienso sintético", cost: "2.5000", currency: "EUR", cost_source: "manual", includes_recargo: true, pack_size: null, min_qty: null,
  verified_at: "2026-11-08T10:00:00Z", erp_link: "link_with_cost", created_by: "buyer-2", erp_cost: "2.0000", erp_verified_at: "2026-11-07T09:00:00Z",
  cost_difference: "0.5000", cost_difference_pct: "25.0", ...over,
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("links against the ERP cost", () => {
  it("shows the ERP cost, the difference and who set the current cost", async () => {
    vi.spyOn(api, "getSupplierLinks").mockResolvedValue([link()]);
    render(<LinksPanel supplier={sup()} canManage={false} />);
    expect(await screen.findByText("SYN-000001")).toBeTruthy();
    expect(screen.getByText("buyer-2")).toBeTruthy();
    expect(screen.getByText(/ERP 2,00 €.*\+0,50 €.*\+25,0 ?%/)).toBeTruthy();
  });

  it("says when the manual cost equals the ERP cost", async () => {
    vi.spyOn(api, "getSupplierLinks").mockResolvedValue([link({ cost: "2.0000", cost_difference: "0.0000", cost_difference_pct: "0.0" })]);
    render(<LinksPanel supplier={sup()} canManage={false} />);
    expect(await screen.findByText(/Igual que el ERP \(2,00 €\)/)).toBeTruthy();
  });

  it("shows a negative difference with its sign", async () => {
    vi.spyOn(api, "getSupplierLinks").mockResolvedValue([link({ cost: "1.5000", cost_difference: "-0.5000", cost_difference_pct: "-25.0" })]);
    render(<LinksPanel supplier={sup()} canManage={false} />);
    expect(await screen.findByText(/ERP 2,00 €.*-0,50 €.*-25,0 ?%/)).toBeTruthy();
  });

  it("shows nothing to compare when there is no ERP cost", async () => {
    vi.spyOn(api, "getSupplierLinks").mockResolvedValue([link({ erp_cost: null, erp_verified_at: null, cost_difference: null, cost_difference_pct: null })]);
    render(<LinksPanel supplier={sup()} canManage={false} />);
    expect(await screen.findByText("SYN-000001")).toBeTruthy();
    expect(screen.queryByText(/ERP 2,00/)).toBeNull();
    expect(screen.queryByText(/Igual que el ERP/)).toBeNull();
  });

  it("does not reload the links when the translation function changes", async () => {
    // T084: a new `t` (the language is applied again) used to re-run the loader
    const links = vi.spyOn(api, "getSupplierLinks").mockResolvedValue([link()]);
    render(<LinksPanel supplier={sup()} canManage={false} />);
    expect(await screen.findByText("SYN-000001")).toBeTruthy();
    await act(async () => {
      await i18n.changeLanguage("es-ES");
    });
    expect(links).toHaveBeenCalledTimes(1);
  });
});
