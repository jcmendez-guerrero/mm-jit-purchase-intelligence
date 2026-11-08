import type { LocalLoadKind, LocalLoadResult } from "../../api/client";

/** Rules of the local-load screen, kept apart from the component so they can be tested without a browser. */
export const KINDS: LocalLoadKind[] = ["suppliers", "inventory", "movements"];
export const MAX_BYTES = 5 * 1024 * 1024;
const EXTENSIONS = [".csv", ".xlsx"];

export function canUse(roles: readonly string[]): boolean {
  return roles.includes("buyer") || roles.includes("admin");
}

/** The i18n key of the problem with a chosen file, or null when it can be sent. */
export function fileProblem(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!EXTENSIONS.some((e) => name.endsWith(e))) return "localLoad.problem.type";
  if (file.size > MAX_BYTES) return "localLoad.problem.size";
  if (file.size === 0) return "localLoad.problem.empty";
  return null;
}

/** Inventory loads need the tax and price interpretation to be acknowledged; movements do not. */
export function canLoad(kind: LocalLoadKind, checked: LocalLoadResult | null, acknowledged: boolean): boolean {
  if (checked === null) return false;
  return kind !== "inventory" || acknowledged;
}

export function balanced(r: LocalLoadResult): boolean {
  return r.loaded + r.updated + r.unchanged + r.quarantined + r.excluded + r.services === r.rows;
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `k-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
