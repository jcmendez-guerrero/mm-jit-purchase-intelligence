import type { PolicyFields } from "../../api/client";

export const SEGMENT_KEYS = ["A", "B", "C", "critical", "sparse"] as const;
export type Scope = "global" | "segment" | "product";

export interface PolicyForm {
  service_level_pct: string;
  safety_stock_units: string;
  min_units: string;
  max_units: string;
  replenishment_cadence_days: string;
  valid_from: string;
}

export const emptyForm = (): PolicyForm => ({ service_level_pct: "", safety_stock_units: "", min_units: "", max_units: "", replenishment_cadence_days: "", valid_from: "" });

/** Fraction from the API ("0.9700") shown as a Spanish percentage input ("97"). */
export function toForm(f: (PolicyFields & { valid_from?: string }) | null): PolicyForm {
  if (!f) return emptyForm();
  const pct = f.service_level === null ? "" : String(Math.round(parseFloat(f.service_level) * 10000) / 100).replace(".", ",");
  return {
    service_level_pct: pct,
    safety_stock_units: f.safety_stock_units ?? "",
    min_units: f.min_units ?? "",
    max_units: f.max_units ?? "",
    replenishment_cadence_days: f.replenishment_cadence_days ?? "",
    valid_from: "",
  };
}

const intOrNull = (v: string): number | null | "bad" => {
  const t = v.trim();
  if (t === "") return null;
  return /^\d+$/.test(t) ? Number(t) : "bad";
};

/** Returns the request body, or the name of the first field that is not a valid number. Users type "97,5"; the API gets "97.5". */
export function toPayload(f: PolicyForm): { body: Record<string, unknown> } | { invalid: keyof PolicyForm } {
  const body: Record<string, unknown> = {};
  const pct = f.service_level_pct.trim().replace(",", ".");
  if (pct !== "") {
    if (!/^\d{1,3}(\.\d{1,2})?$/.test(pct)) return { invalid: "service_level_pct" };
    body.service_level_pct = pct;
  }
  for (const name of ["safety_stock_units", "min_units", "max_units", "replenishment_cadence_days"] as const) {
    const n = intOrNull(f[name]);
    if (n === "bad") return { invalid: name };
    if (n !== null) body[name] = n;
  }
  if (f.valid_from) body.valid_from = f.valid_from;
  return { body };
}

export const scopeKeyValid = (scope: Scope, key: string): boolean =>
  scope === "global" ? key === "*" : scope === "segment" ? (SEGMENT_KEYS as readonly string[]).includes(key) : /^[1-9]\d*$/.test(key);

export const canEditPolicies = (roles: string[]): boolean => roles.includes("buyer");
export const canDecideOverrides = (roles: string[]): boolean => roles.includes("approver");

/** Whole positive id typed by a person; null when it is not one. */
export function parseId(raw: string): number | null {
  const t = raw.trim();
  return /^[1-9]\d*$/.test(t) && Number.isSafeInteger(Number(t)) ? Number(t) : null;
}
