import type { CostWriteRecord } from "../../api/client";

const OPEN = ["pending_review", "pending_link", "failed"];

/** Only a buyer releases, never the person who set the override; the server enforces the same rules. */
export function canRelease(roles: string[], userId: string | undefined, w: CostWriteRecord): boolean {
  if (!roles.includes("buyer") || !OPEN.includes(w.status) || w.status === "pending_link") return false;
  if ((w.rule_flags.includes("margin_below_minimum") || w.rule_flags.includes("margin_unavailable")) && !w.override) return false;
  return !(w.override && userId !== undefined && w.override.by === userId);
}

export function canOverride(roles: string[], w: CostWriteRecord): boolean {
  return roles.includes("admin") && OPEN.includes(w.status);
}

/** Decimal text with a dot or a comma, up to 4 decimals; the API receives it with a dot. */
export function parseAmount(raw: string): string | null {
  const text = raw.trim().replace(",", ".");
  return /^\d{1,10}(\.\d{1,4})?$/.test(text) ? text : null;
}

export function flagKey(flag: string): string {
  return `costs.flag.${flag}`;
}

export const canRequestUpdate = (roles: string[]): boolean => roles.includes("buyer");

/** What the buyer typed for the opening cost, or the name of the first field that is not valid. */
export function parseOpening(product: string, variant: string, amount: string): { productId: number; variantId: number; amount: string } | { invalid: "product" | "variant" | "amount" } {
  const id = (t: string) => (/^[1-9]\d*$/.test(t.trim()) && Number.isSafeInteger(Number(t.trim())) ? Number(t.trim()) : null);
  const productId = id(product);
  if (productId === null) return { invalid: "product" };
  const variantId = id(variant);
  if (variantId === null) return { invalid: "variant" };
  const a = parseAmount(amount);
  return a === null ? { invalid: "amount" } : { productId, variantId, amount: a };
}
