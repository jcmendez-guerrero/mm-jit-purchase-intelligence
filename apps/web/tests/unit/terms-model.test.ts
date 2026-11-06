import { describe, expect, it } from "vitest";
import type { TermsDoc } from "../../src/api/client";
import { decimalOrNull, emptyForm, intOrNull, overrideToForm, overrideToPayload, sourceKey, toForm, toPayload, toggleDay } from "../../src/features/suppliers/termsModel";

const doc: TermsDoc = {
  min_order_value: "150.0000", min_qty_for_delivery: 12, free_delivery_threshold: "300.0000", delivery_charge: "9.5000", order_days: [1, 4], delivery_schedule: "martes",
  lead_time_days: 3, order_cutoff_time: "13:30", delivery_weekdays: [2, 5], discounts: [{ kind: "percent", basis: "order_value", threshold: "500.0000", value: "3.0000" }],
  payment_terms_days: 30, preferred: true, reliability: 90, disabled: false, valid_to: null,
};

describe("Spanish number input", () => {
  it("accepts a decimal comma and sends a decimal point", () => {
    expect(decimalOrNull("12,50")).toBe("12.50");
    expect(decimalOrNull(" 7 ")).toBe("7");
    expect(decimalOrNull("")).toBeNull();
  });
  it("parses whole numbers and treats blank as none", () => {
    expect(intOrNull("14")).toBe(14);
    expect(intOrNull("  ")).toBeNull();
  });
});

describe("terms form", () => {
  it("shows stored money without trailing zeros", () => {
    const f = toForm(doc);
    expect([f.min_order_value, f.delivery_charge, f.discounts[0]!.threshold, f.discounts[0]!.value]).toEqual(["150", "9.5", "500", "3"]);
  });
  it("round-trips a full document to a payload the server accepts as is", () => {
    const p = toPayload({ ...toForm(doc), reason: "alta" });
    expect(p).toMatchObject({ lead_time_days: 3, order_days: [1, 4], delivery_weekdays: [2, 5], min_order_value: "150", preferred: true, reliability: 90, reason: "alta" });
    expect(p.discounts).toEqual([{ kind: "percent", basis: "order_value", threshold: "500", value: "3" }]);
  });
  it("an empty form sends nulls, not zeros or empty strings", () => {
    const p = toPayload(emptyForm());
    expect(p).toMatchObject({ lead_time_days: null, min_order_value: null, order_cutoff_time: null, valid_from: null, reason: null, discounts: [] });
  });
  it("turns dates into UTC midnight and leaves empty dates null", () => {
    expect(toPayload({ ...emptyForm(), valid_from: "2026-12-01" }).valid_from).toBe("2026-12-01T00:00:00Z");
  });
  it("toggles weekdays and keeps them sorted and unique", () => {
    expect(toggleDay([4], 1)).toEqual([1, 4]);
    expect(toggleDay([1, 4], 4)).toEqual([1]);
  });
  it("an absent document is an empty form", () => {
    expect(toForm(null)).toEqual(emptyForm());
  });
});

describe("product override form", () => {
  it("maps tri-state choices to null / true / false", () => {
    const f = { ...overrideToForm(null), preferred: "yes" as const, disabled: "no" as const, pack_multiple: "12" };
    expect(overrideToPayload(f)).toMatchObject({ preferred: true, disabled: false, pack_multiple: 12, lead_time_days: null });
    expect(overrideToPayload(overrideToForm(null))).toMatchObject({ preferred: null, disabled: null });
  });
  it("reads an existing override back into the form", () => {
    const f = overrideToForm({ pack_multiple: 6, min_qty_units: null, lead_time_days: 5, payment_terms_days: null, preferred: false, reliability: null, disabled: null });
    expect([f.pack_multiple, f.lead_time_days, f.preferred, f.disabled]).toEqual(["6", "5", "no", "inherit"]);
  });
  it("source badges fall back to the default label", () => {
    expect(sourceKey("override")).toBe("suppliers.source.override");
    expect(sourceKey("whatever")).toBe("suppliers.source.default");
  });
});
