import type { LinkInputDoc, SupplierInputDoc, SupplierSummary } from "../../api/client";

/** Rules of the supplier forms, kept apart from the components so they can be tested without a browser (MMI 004). */
export const FISCAL_TYPES = ["national", "intracommunity", "foreign"] as const;
export const CLASSIFICATIONS = ["purchasing", "non_purchasing", "unclassified"] as const;
export const CHANNELS = ["email", "phone", "web", "other"] as const;

export interface SupplierForm {
  name: string;
  fiscal_type: string;
  country: string;
  currency: string;
  payment_terms_days: string;
  order_channel: string;
  classification: string;
}

export const EMPTY_FORM: SupplierForm = { name: "", fiscal_type: "national", country: "ES", currency: "EUR", payment_terms_days: "", order_channel: "", classification: "purchasing" };

export function canManage(roles: readonly string[]): boolean {
  return roles.includes("buyer") || roles.includes("admin");
}

export function formFrom(s: SupplierSummary): SupplierForm {
  return {
    name: s.name, fiscal_type: s.fiscal_type ?? "national", country: s.country ?? "ES", currency: s.currency ?? "EUR",
    payment_terms_days: s.payment_terms_days == null ? "" : String(s.payment_terms_days), order_channel: s.order_channel ?? "", classification: s.classification ?? "purchasing",
  };
}

/** Field → i18n key of the problem; empty when the form can be sent. */
export function validate(f: SupplierForm): Partial<Record<keyof SupplierForm, string>> {
  const out: Partial<Record<keyof SupplierForm, string>> = {};
  const name = f.name.trim();
  if (!name) out.name = "suppliers.form.err.name_required";
  else if (name.length > 200) out.name = "suppliers.form.err.name_long";
  if (!/^[A-Z]{2}$/.test(f.country.trim())) out.country = "suppliers.form.err.country";
  if (!/^[A-Z]{3}$/.test(f.currency.trim())) out.currency = "suppliers.form.err.currency";
  const days = f.payment_terms_days.trim();
  if (days !== "" && !(/^\d+$/.test(days) && Number(days) <= 365)) out.payment_terms_days = "suppliers.form.err.days";
  return out;
}

export function toPayload(f: SupplierForm): SupplierInputDoc {
  const days = f.payment_terms_days.trim();
  return {
    name: f.name.trim(), fiscal_type: f.fiscal_type, country: f.country.trim(), currency: f.currency.trim(),
    payment_terms_days: days === "" ? null : Number(days), order_channel: f.order_channel === "" ? null : f.order_channel, classification: f.classification,
  };
}

/** Only the fields that changed, so an edit never resends what the buyer did not touch. */
export function diff(before: SupplierForm, after: SupplierForm): Partial<SupplierInputDoc> {
  const b = toPayload(before) as unknown as Record<string, unknown>;
  const a = toPayload(after) as unknown as Record<string, unknown>;
  return Object.fromEntries(Object.keys(a).filter((k) => a[k] !== b[k]).map((k) => [k, a[k]])) as Partial<SupplierInputDoc>;
}

/** A pasted list of SKUs: separated by line breaks, commas, semicolons or tabs; blanks and repeats (any case) are dropped. */
export function parseSkuList(text: string): string[] {
  const seen = new Map<string, string>();
  for (const part of text.split(/[\n\r,;\t]+/)) {
    const sku = part.trim();
    if (sku && !seen.has(sku.toLowerCase())) seen.set(sku.toLowerCase(), sku);
  }
  return [...seen.values()];
}

/** Spanish and plain decimal input ("12,50", "12.5") → the decimal string the API expects, or null when it is not a valid cost. */
export function parseCost(text: string): string | null {
  const t = text.trim().replace(/\s/g, "");
  if (!/^\d+([.,]\d{1,4})?$/.test(t)) return null;
  return t.replace(",", ".");
}

export function linkPayload(f: { cost: string; includesRecargo: boolean; pack: string; minQty: string }): LinkInputDoc | null {
  const body: LinkInputDoc = { includes_recargo: f.includesRecargo };
  if (f.cost.trim() !== "") {
    const cost = parseCost(f.cost);
    if (cost === null) return null;
    body.cost = cost;
  }
  for (const [key, raw] of [["pack_size", f.pack], ["min_qty", f.minQty]] as const) {
    if (raw.trim() === "") continue;
    if (!/^\d+$/.test(raw.trim()) || Number(raw) < 1) return null;
    body[key] = Number(raw);
  }
  return body;
}

export function isMerged(s: SupplierSummary): boolean {
  return !!s.merged_into;
}
