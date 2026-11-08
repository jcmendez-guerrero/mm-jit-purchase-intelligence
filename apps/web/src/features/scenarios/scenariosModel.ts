import type { ScenarioRequest } from "../../api/client";

export interface SupplierForm {
  disabled: boolean;
  min_order_value: string;
  delivery_charge: string;
  free_delivery_threshold: string;
  lead_time_days: string;
  pack_multiple: string;
  min_order_qty: string;
}

export interface ScenarioForm {
  name: string;
  budget: string;
  service_level_pp: string;          // percentage points, e.g. "2" or "-1,5"
  suppliers: Record<string, SupplierForm>;
}

export const emptySupplier = (): SupplierForm => ({ disabled: false, min_order_value: "", delivery_charge: "", free_delivery_threshold: "", lead_time_days: "", pack_multiple: "", min_order_qty: "" });
export const emptyForm = (): ScenarioForm => ({ name: "", budget: "", service_level_pp: "", suppliers: {} });

const money = (t: string): string | null => {
  const v = t.trim().replace(",", ".");
  return /^\d{1,10}(\.\d{1,4})?$/.test(v) ? v : null;
};
const whole = (t: string, min: number, max: number): number | null => {
  const v = t.trim();
  if (!/^\d+$/.test(v)) return null;
  const n = Number(v);
  return n >= min && n <= max ? n : null;
};

export const canCreate = (roles: string[]): boolean => roles.includes("buyer");

/** The request body, or the label of the first field that is not valid. Blank fields mean "no change". */
export function toRequest(f: ScenarioForm): { body: ScenarioRequest } | { invalid: string; supplier?: string } {
  if (f.name.trim() === "") return { invalid: "name" };
  const body: ScenarioRequest = { name: f.name.trim(), disabled_suppliers: [], supplier_deltas: {}, service_level_delta: "0" };
  if (f.budget.trim() !== "") {
    const b = money(f.budget);
    if (b === null) return { invalid: "budget" };
    body.budget = b;
  }
  if (f.service_level_pp.trim() !== "") {
    const t = f.service_level_pp.trim().replace(",", ".");
    if (!/^-?\d{1,2}(\.\d{1,2})?$/.test(t) || Math.abs(Number(t)) > 40) return { invalid: "service_level" };
    body.service_level_delta = (Number(t) / 100).toFixed(4);
  }
  for (const [sid, s] of Object.entries(f.suppliers)) {
    if (s.disabled) body.disabled_suppliers.push(sid);
    const d: Record<string, string | number> = {};
    for (const name of ["min_order_value", "delivery_charge", "free_delivery_threshold"] as const) {
      if (s[name].trim() === "") continue;
      const v = money(s[name]);
      if (v === null) return { invalid: name, supplier: sid };
      d[name] = v;
    }
    const ints: Array<["lead_time_days" | "pack_multiple" | "min_order_qty", number, number]> = [["lead_time_days", 0, 365], ["pack_multiple", 1, 10000], ["min_order_qty", 0, 1000000]];
    for (const [name, lo, hi] of ints) {
      if (s[name].trim() === "") continue;
      const v = whole(s[name], lo, hi);
      if (v === null) return { invalid: name, supplier: sid };
      d[name] = v;
    }
    if (Object.keys(d).length > 0) body.supplier_deltas[sid] = d;
  }
  return { body };
}

/** The reason keys shown for a change; unknown ones fall back to the generic key. */
export const reasonKey = (r: string): string => `scenarios.reason.${r}`;

export function constraintLabel(key: string): { kind: string; supplier?: string } {
  const [kind, supplier] = key.split(":", 2);
  return supplier === undefined ? { kind: kind ?? key } : { kind: kind ?? key, supplier };
}
