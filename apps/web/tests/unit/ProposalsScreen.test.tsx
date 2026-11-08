// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, Proposal } from "../../src/api/client";
import { ProposalsScreen } from "../../src/features/proposals/ProposalsScreen";
import "../../src/i18n";
import { confirmAction } from "./confirm";

const proposal = (over: Partial<Proposal> = {}): Proposal => ({
  id: "p1", week: "2026-W45", status: "draft", version: 3, created_by: "buyer-1", last_edited_by: null, terms_version_ids: null, approval: null,
  supplier_groups: [
    { supplier_id: "s1", supplier_name: "Proveedor Sintético A", subtotal: "100.0000", discount: "5.0000", delivery_charge: "0.0000", total_cost: "95.0000", expected_delivery_date: "2026-11-12", minimum_status: "met", free_delivery: true },
  ],
  lines: [
    {
      id: "l1", variant_id: 9001, sku: "SYN-001", product_name: "Producto Sintético", supplier_id: "s1", supplier_name: "Proveedor Sintético A", qty: 10,
      unit_cost_with_recargo: "10.0000", line_total: "100.0000", risk: "low", confidence: "high", manual_override: false, topup: false, constraints_applied: ["pack_multiple"],
      explanation: {
        policy: "forecast", forecast_eligible: true, service_level: "95", horizon_days: 14, expected_demand: 8, safety_stock: 2, order_up_to: 12, reorder_point: 5, need: 10, top_up: false,
        clinical_critical: false, position: { on_hand: 0, expiring: 0, usable: 0, inbound: 0, total: 0 },
        supplier: { chosen: "s1", reason: "lower_total_with_supplier_terms", alternatives: [], rejected: [] },
        cost: { unit: "10.0000", source: "manual", status: "ok" }, constraints: ["pack_multiple"],
        terms: { supplier_version: 2, override_version: 1, sources: { pack_multiple: "override", lead_time_days: "supplier" },
          conflicts: [{ field: "pack_multiple", erp_value: 6, local_value: 12, winner: "local" }], preferred: true, supplier_discount: "5.0000" },
      },
    },
  ],
  ...over,
});

beforeEach(() => {
  vi.spyOn(api, "getProposals").mockResolvedValue([{ id: "p1", week: "2026-W45", status: "draft", version: 3, created_by: "buyer-1", updated_at: "2026-11-05T10:00:00Z" }]);
  vi.spyOn(api, "getProposal").mockResolvedValue(proposal());
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ProposalsScreen", () => {
  it("lists the lines from the real shape and groups orders by supplier", async () => {
    render(<ProposalsScreen userRoles={["viewer"]} />);
    expect(await screen.findByText(/SYN-001/)).toBeTruthy();
    expect(screen.getAllByText("Proveedor Sintético A").length).toBeGreaterThan(0);
    expect(screen.getByText("Envío gratuito", { exact: false })).toBeTruthy();
  });

  it("explains terms versions, value sources, ERP conflicts and the discount in Spanish", async () => {
    render(<ProposalsScreen userRoles={["viewer"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Ver justificación" }));
    expect(screen.getByText(/proveedor v2, excepción de producto 1/)).toBeTruthy();
    expect(screen.getByText(/Conflicto con el ERP/)).toBeTruthy();
    expect(screen.getByText(/Descuento del proveedor en el pedido/)).toBeTruthy();
    expect(screen.getByText("menor coste total con las condiciones del proveedor", { exact: false })).toBeTruthy();
  });

  it("labels a line whose forecast rests on imported estimates, in the row and in the explanation, and not an ordinary one", async () => {
    const base = proposal();
    const line = base.lines[0]!;
    vi.spyOn(api, "getProposal").mockResolvedValue({ ...base, lines: [{ ...line, explanation: { ...line.explanation, forecast_basis: "imported_estimates" } }] });
    const first = render(<ProposalsScreen userRoles={["viewer"]} />);
    expect(await screen.findByText(/previsión con datos importados/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ver justificación" }));
    expect(screen.getByText(/se apoya en datos importados/)).toBeTruthy();
    expect(screen.getByText(/La cantidad es la calculada/)).toBeTruthy();
    first.unmount();
    vi.spyOn(api, "getProposal").mockResolvedValue({ ...base, lines: [{ ...line, explanation: { ...line.explanation, forecast_basis: "actual_demand" } }] });
    render(<ProposalsScreen userRoles={["viewer"]} />);
    await screen.findByText(/SYN-001/);
    expect(screen.queryByText(/previsión con datos importados/)).toBeNull();
  });

  it("shows the forecast run and the imported dataset behind the proposal, or says there is none", async () => {
    vi.spyOn(api, "getProposal").mockResolvedValue(proposal({ forecast_run_id: "abcdef12-0000-4000-8000-000000000000", dataset_version_id: "12345678-0000-4000-8000-000000000000" }));
    const first = render(<ProposalsScreen userRoles={["viewer"]} />);
    expect((await screen.findByLabelText("Datos usados")).textContent).toContain("ejecución de previsión abcdef12 · conjunto de datos importados 12345678");
    first.unmount();
    vi.spyOn(api, "getProposal").mockResolvedValue(proposal({ forecast_run_id: "abcdef12-0000-4000-8000-000000000000", dataset_version_id: null }));
    render(<ProposalsScreen userRoles={["viewer"]} />);
    expect((await screen.findByLabelText("Datos usados")).textContent).toContain("sin datos importados (solo ventas reales del ERP)");
  });

  it("offers both the CSV and the Excel export of the proposal", async () => {
    render(<ProposalsScreen userRoles={["viewer"]} />);
    const csv = await screen.findByRole("link", { name: "Exportar CSV (formato es-ES)" });
    const xlsx = screen.getByRole("link", { name: "Exportar Excel" });
    expect(csv.getAttribute("href")).toBe("/api/proposals/p1/export?format=csv");
    expect(xlsx.getAttribute("href")).toBe("/api/proposals/p1/export?format=xlsx");
    expect(xlsx.hasAttribute("download")).toBe(true);
  });

  it("edits a quantity with the version on screen", async () => {
    const edit = vi.spyOn(api, "editProposalLine").mockResolvedValue(proposal());
    render(<ProposalsScreen userRoles={["viewer", "buyer"]} />);
    const input = await screen.findByLabelText("Cantidad para Producto Sintético");
    fireEvent.change(input, { target: { value: "14" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cantidad" }));
    await waitFor(() => expect(edit).toHaveBeenCalledWith("p1", "l1", 14, 3));
  });

  it("refuses a non-numeric quantity locally with a Spanish message", async () => {
    const edit = vi.spyOn(api, "editProposalLine");
    render(<ProposalsScreen userRoles={["buyer"]} />);
    fireEvent.change(await screen.findByLabelText("Cantidad para Producto Sintético"), { target: { value: "1,5" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cantidad" }));
    expect((await screen.findByRole("alert")).textContent).toContain("número entero");
    expect(edit).not.toHaveBeenCalled();
  });

  it("approves the version that was reviewed, only for approvers", async () => {
    vi.spyOn(api, "getProposal").mockResolvedValue(proposal({ status: "submitted", version: 5 }));
    const approve = vi.spyOn(api, "approveProposal").mockResolvedValue({});
    const { unmount } = render(<ProposalsScreen userRoles={["viewer", "admin"]} />);
    await screen.findByText(/SYN-001/);
    expect(screen.queryByRole("button", { name: /Aprobar propuesta/ })).toBeNull();
    unmount();
    render(<ProposalsScreen userRoles={["viewer", "approver"]} />);
    fireEvent.click(await screen.findByRole("button", { name: /Aprobar propuesta/ }));
    confirmAction();
    await waitFor(() => expect(approve).toHaveBeenCalledWith("p1", 5));
  });

  it("shows a Spanish message when the proposal changed meanwhile and reloads", async () => {
    vi.spyOn(api, "submitProposal").mockRejectedValue(new ApiError(409, "version_conflict", 4));
    render(<ProposalsScreen userRoles={["buyer"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Enviar a aprobación" }));
    confirmAction();
    expect((await screen.findByRole("alert")).textContent).toContain("Otra persona ha modificado");
    await waitFor(() => expect(api.getProposal).toHaveBeenCalledTimes(2));
  });
});
