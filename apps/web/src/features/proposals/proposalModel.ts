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

export interface LineGroup<L> {
  id: string;
  name: string;
  lines: L[];
  /** The supplier group's subtotal as the server computed it (money is never summed in the browser); null when the proposal has no group for it. */
  subtotal: string | null;
}

/** Lines of a proposal grouped by supplier, in the order each supplier first appears. */
export function groupLinesBySupplier<L extends { supplier_id: string; supplier_name?: string | null }>(
  lines: L[],
  groups: Array<{ supplier_id: string; subtotal: string }>,
): Array<LineGroup<L>> {
  const out = new Map<string, LineGroup<L>>();
  for (const line of lines) {
    const existing = out.get(line.supplier_id);
    if (existing) {
      existing.lines.push(line);
      if (existing.name === line.supplier_id && line.supplier_name) existing.name = line.supplier_name;
    } else {
      out.set(line.supplier_id, { id: line.supplier_id, name: line.supplier_name ?? line.supplier_id, lines: [line], subtotal: groups.find((g) => g.supplier_id === line.supplier_id)?.subtotal ?? null });
    }
  }
  return [...out.values()];
}

export interface LinePage<L> {
  groups: Array<LineGroup<L> & { /** The group started on an earlier page. */ continued: boolean; /** The group's last line is on this page, so its subtotal belongs here. */ complete: boolean }>;
  pages: number;
  total: number;
}

/** One page of grouped lines: pages count lines, a group may span pages, and a group shows its subtotal on the page where it ends (FR-012). */
export function pageLineGroups<L>(groups: Array<LineGroup<L>>, page: number, pageSize: number): LinePage<L> {
  const total = groups.reduce((n, g) => n + g.lines.length, 0);
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const current = Math.min(Math.max(page, 0), pages - 1);
  const start = current * pageSize;
  const end = start + pageSize;
  const out: LinePage<L>["groups"] = [];
  let offset = 0;
  for (const g of groups) {
    const from = Math.max(start, offset) - offset;
    const to = Math.min(end, offset + g.lines.length) - offset;
    if (to > from) out.push({ ...g, lines: g.lines.slice(from, to), continued: from > 0, complete: to === g.lines.length });
    offset += g.lines.length;
  }
  return { groups: out, pages, total };
}
