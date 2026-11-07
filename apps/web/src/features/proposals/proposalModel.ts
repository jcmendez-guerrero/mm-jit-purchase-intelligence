import type { Proposal, ProposalLine, ProposalStatus } from "../../api/client";

/** Pure rules for what the signed-in user may do with a proposal; the server enforces them again. */
export function canEditLines(roles: string[], status: ProposalStatus): boolean {
  return roles.includes("buyer") && status === "draft";
}

export function canSubmit(roles: string[], status: ProposalStatus): boolean {
  return roles.includes("buyer") && status === "draft";
}

/** Only approvers decide; an admin role alone does not approve. */
export function canApprove(roles: string[], status: ProposalStatus): boolean {
  return roles.includes("approver") && status === "submitted";
}

/** Whole non-negative units only. */
export function parseQty(raw: string): number | null {
  const text = raw.trim();
  if (!/^\d+$/.test(text)) return null;
  const n = Number(text);
  return Number.isSafeInteger(n) ? n : null;
}

export function linesBySupplier(p: Proposal): Array<{ supplierId: string; lines: ProposalLine[] }> {
  const out = new Map<string, ProposalLine[]>();
  for (const l of p.lines) out.set(l.supplier_id, [...(out.get(l.supplier_id) ?? []), l]);
  return [...out.entries()].map(([supplierId, lines]) => ({ supplierId, lines }));
}
