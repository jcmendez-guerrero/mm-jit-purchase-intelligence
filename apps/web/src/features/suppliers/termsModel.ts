import type { DiscountDoc, OverrideDoc, TermsDoc } from "../../api/client";

/** The editor keeps every input as text; the payload parses it. Spanish users type "12,50": accept it, send "12.50". */
export interface DiscountForm {
  kind: "percent" | "amount";
  basis: "order_value" | "order_units";
  threshold: string;
  value: string;
}

export interface TermsForm {
  lead_time_days: string;
  order_days: number[];
  order_cutoff_time: string;
  delivery_weekdays: number[];
  min_order_value: string;
  min_qty_for_delivery: string;
  free_delivery_threshold: string;
  delivery_charge: string;
  delivery_schedule: string;
  discounts: DiscountForm[];
  payment_terms_days: string;
  preferred: boolean;
  reliability: string;
  disabled: boolean;
  valid_from: string;
  valid_to: string;
  reason: string;
}

export const WEEKDAYS = [1, 2, 3, 4, 5, 6, 7] as const;
export const MAX_DISCOUNT_TIERS = 5;

export function emptyForm(): TermsForm {
  return {
    lead_time_days: "", order_days: [], order_cutoff_time: "", delivery_weekdays: [], min_order_value: "", min_qty_for_delivery: "",
    free_delivery_threshold: "", delivery_charge: "", delivery_schedule: "", discounts: [], payment_terms_days: "", preferred: false,
    reliability: "", disabled: false, valid_from: "", valid_to: "", reason: "",
  };
}

const text = (v: string | number | null | undefined): string => (v === null || v === undefined ? "" : String(v));

/** Money comes back as "150.0000"; show it without trailing zeros but keep what the buyer typed otherwise. */
function trimMoney(v: string | null): string {
  if (v === null) return "";
  return v.includes(".") ? v.replace(/0+$/, "").replace(/\.$/, "") : v;
}

export function toForm(t: TermsDoc | null): TermsForm {
  if (!t) return emptyForm();
  return {
    ...emptyForm(),
    lead_time_days: text(t.lead_time_days),
    order_days: [...t.order_days],
    order_cutoff_time: text(t.order_cutoff_time),
    delivery_weekdays: [...t.delivery_weekdays],
    min_order_value: trimMoney(t.min_order_value),
    min_qty_for_delivery: text(t.min_qty_for_delivery),
    free_delivery_threshold: trimMoney(t.free_delivery_threshold),
    delivery_charge: trimMoney(t.delivery_charge),
    delivery_schedule: text(t.delivery_schedule),
    discounts: t.discounts.map((d: DiscountDoc) => ({ kind: d.kind, basis: d.basis, threshold: trimMoney(d.threshold), value: trimMoney(d.value) })),
    payment_terms_days: text(t.payment_terms_days),
    preferred: t.preferred,
    reliability: text(t.reliability),
    disabled: t.disabled,
    valid_to: t.valid_to ? t.valid_to.slice(0, 10) : "",
  };
}

/** "12,50" -> "12.50"; "" -> null. Anything else is passed through for the server to validate (it owns the rules). */
export function decimalOrNull(input: string): string | null {
  const s = input.trim().replace(",", ".");
  return s === "" ? null : s;
}

export function intOrNull(input: string): number | null {
  const s = input.trim();
  return s === "" ? null : Number(s);
}

const dateOrNull = (s: string): string | null => (s ? `${s}T00:00:00Z` : null);

export function toPayload(f: TermsForm): Record<string, unknown> {
  return {
    lead_time_days: intOrNull(f.lead_time_days),
    order_days: f.order_days,
    order_cutoff_time: f.order_cutoff_time.trim() || null,
    delivery_weekdays: f.delivery_weekdays,
    min_order_value: decimalOrNull(f.min_order_value),
    min_qty_for_delivery: intOrNull(f.min_qty_for_delivery),
    free_delivery_threshold: decimalOrNull(f.free_delivery_threshold),
    delivery_charge: decimalOrNull(f.delivery_charge),
    delivery_schedule: f.delivery_schedule.trim() || null,
    discounts: f.discounts.map((d) => ({ kind: d.kind, basis: d.basis, threshold: decimalOrNull(d.threshold) ?? "0", value: decimalOrNull(d.value) ?? "0" })),
    payment_terms_days: intOrNull(f.payment_terms_days),
    preferred: f.preferred,
    reliability: intOrNull(f.reliability),
    disabled: f.disabled,
    valid_from: dateOrNull(f.valid_from),
    valid_to: dateOrNull(f.valid_to),
    reason: f.reason.trim() || null,
  };
}

export function toggleDay(days: number[], day: number): number[] {
  return (days.includes(day) ? days.filter((d) => d !== day) : [...days, day]).sort((a, b) => a - b);
}

/* ---- product-supplier override: tri-state choices (inherit / yes / no) ---- */
export type Tri = "inherit" | "yes" | "no";
export interface OverrideForm {
  pack_multiple: string;
  min_qty_units: string;
  lead_time_days: string;
  payment_terms_days: string;
  reliability: string;
  preferred: Tri;
  disabled: Tri;
  reason: string;
}

const triFrom = (v: boolean | null | undefined): Tri => (v === null || v === undefined ? "inherit" : v ? "yes" : "no");
const triTo = (t: Tri): boolean | null => (t === "inherit" ? null : t === "yes");

export function overrideToForm(o: OverrideDoc | null): OverrideForm {
  return {
    pack_multiple: text(o?.pack_multiple), min_qty_units: text(o?.min_qty_units), lead_time_days: text(o?.lead_time_days),
    payment_terms_days: text(o?.payment_terms_days), reliability: text(o?.reliability), preferred: triFrom(o?.preferred), disabled: triFrom(o?.disabled), reason: "",
  };
}

export function overrideToPayload(f: OverrideForm): Record<string, unknown> {
  return {
    pack_multiple: intOrNull(f.pack_multiple), min_qty_units: intOrNull(f.min_qty_units), lead_time_days: intOrNull(f.lead_time_days),
    payment_terms_days: intOrNull(f.payment_terms_days), reliability: intOrNull(f.reliability), preferred: triTo(f.preferred), disabled: triTo(f.disabled),
    reason: f.reason.trim() || null,
  };
}

/** The badge shown next to each effective value: where it comes from (FR-012 source badges). */
export function sourceKey(source: string | undefined): string {
  return ["override", "supplier", "cost", "default"].includes(source ?? "") ? `suppliers.source.${source}` : "suppliers.source.default";
}
