// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, Proposal } from "../../src/api/client";
import { canExport } from "../../src/features/proposals/proposalModel";
import { ProposalsScreen } from "../../src/features/proposals/ProposalsScreen";
import "../../src/i18n";

const base = (over: Partial<Proposal> = {}): Proposal => ({
  id: "p1", week: "2026-W45", status: "draft", version: 3, created_by: "buyer-1", last_edited_by: null, terms_version_ids: null, approval: null, supplier_groups: [], lines: [], ...over,
});
const summary = (status: Proposal["status"]) => [{ id: "p1", week: "2026-W45", status, version: 3, created_by: "buyer-1", updated_at: "2026-11-05T10:00:00Z" }];

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("superseded proposals, export roles and review notes (FR-008, FR-010, FR-014)", () => {
  it("shows a superseded proposal as read-only in Spanish: no edit, submit, approve or export", async () => {
    vi.spyOn(api, "getProposals").mockResolvedValue(summary("superseded"));
    vi.spyOn(api, "getProposal").mockResolvedValue(base({ status: "superseded" }));
    render(<ProposalsScreen userRoles={["viewer", "buyer", "approver", "admin"]} />);
    expect(await screen.findByText(/sustituida por una versión más reciente/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Enviar a aprobación" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Aprobar propuesta (MFA)" })).toBeNull();
    expect(screen.queryByRole("link", { name: /Exportar/ })).toBeNull();
  });

  it("offers the export to buyers, approvers and admins on an approved proposal, never to a viewer", async () => {
    vi.spyOn(api, "getProposals").mockResolvedValue(summary("approved"));
    vi.spyOn(api, "getProposal").mockResolvedValue(base({ status: "approved" }));
    const { unmount } = render(<ProposalsScreen userRoles={["viewer"]} />);
    await screen.findByRole("heading", { name: /2026-W45/ });
    expect(screen.queryByRole("link", { name: /Exportar/ })).toBeNull();
    unmount();
    render(<ProposalsScreen userRoles={["viewer", "approver"]} />);
    expect(await screen.findByRole("link", { name: "Exportar Excel" })).toBeTruthy();
  });

  it("canExport follows the role and status rules", () => {
    expect(canExport(["viewer"], "approved")).toBe(false);
    expect(canExport(["viewer", "admin"], "exported")).toBe(true);
    expect(canExport(["viewer", "buyer"], "draft")).toBe(false);
    expect(canExport(["viewer", "buyer"], "superseded")).toBe(false);
  });

  it("lists a needed variant with no usable supplier instead of hiding it", async () => {
    vi.spyOn(api, "getProposals").mockResolvedValue(summary("draft"));
    vi.spyOn(api, "getProposal").mockResolvedValue(base({ review_notes: [{ code: "no_eligible_supplier", sku: "SYN-007", product_name: "Producto Sintético" }] }));
    render(<ProposalsScreen userRoles={["viewer", "buyer"]} />);
    expect(await screen.findByText(/SYN-007 — Producto Sintético: ninguna oferta es utilizable/)).toBeTruthy();
  });
});
