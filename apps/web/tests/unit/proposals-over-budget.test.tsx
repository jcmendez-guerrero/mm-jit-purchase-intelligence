// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, Proposal } from "../../src/api/client";
import { ProposalsScreen } from "../../src/features/proposals/ProposalsScreen";
import "../../src/i18n";

const base = (over: Partial<Proposal> = {}): Proposal => ({
  id: "p1", week: "2026-W45", status: "draft", version: 1, created_by: "buyer-1", last_edited_by: null, terms_version_ids: null, approval: null, supplier_groups: [], lines: [], ...over,
});
const row = (id: string, status: Proposal["status"]) => ({ id, week: "2026-W45", status, version: 1, created_by: "buyer-1", updated_at: "2026-11-05T10:00:00Z" });

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("budget excess and the newer version (US4/AC1, US2/AC6)", () => {
  it("states the excess over the cap in euros and that quantities are kept", async () => {
    vi.spyOn(api, "getProposals").mockResolvedValue([row("p1", "draft")]);
    vi.spyOn(api, "getProposal").mockResolvedValue(base({ over_budget: "18.0000" }));
    render(<ProposalsScreen userRoles={["viewer", "buyer"]} />);
    expect(await screen.findByText(/supera el presupuesto en 18,00/)).toBeTruthy();
    expect(screen.getByText(/Se mantienen todas las cantidades necesarias/)).toBeTruthy();
  });

  it("shows nothing when the plan is within the cap", async () => {
    vi.spyOn(api, "getProposals").mockResolvedValue([row("p1", "draft")]);
    vi.spyOn(api, "getProposal").mockResolvedValue(base({ over_budget: "0.0000" }));
    render(<ProposalsScreen userRoles={["viewer", "buyer"]} />);
    await screen.findByRole("heading", { name: /2026-W45/ });
    expect(screen.queryByText(/supera el presupuesto/)).toBeNull();
  });

  it("links a superseded proposal to the current version of the same week", async () => {
    vi.spyOn(api, "getProposals").mockResolvedValue([row("p1", "superseded"), row("p2", "draft")]);
    const get = vi.spyOn(api, "getProposal").mockImplementation(async (id: string) => base({ id, status: id === "p1" ? "superseded" : "draft" }));
    render(<ProposalsScreen userRoles={["viewer", "buyer"]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Ver la versión vigente de la semana" }));
    await screen.findByRole("heading", { name: /2026-W45/ });
    expect(get).toHaveBeenLastCalledWith("p2");
  });
});
