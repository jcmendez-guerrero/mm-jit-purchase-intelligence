import { describe, expect, it, vi } from "vitest";
import i18n from "../../src/i18n";
import esJson from "../../src/i18n/es-ES.json";
import { formatCurrencyEUR, formatDate, formatNumber, formatPercent } from "../../src/i18n/formatters";

describe("i18n formatting (es-ES standard)", () => {
  it("formats currency in EUR with comma decimal separator and EUR symbol", () => {
    const formatted = formatCurrencyEUR(1234.56);
    // Spanish formatting uses dot for thousands and comma for decimals: 1.234,56 € (with non-breaking or normal space)
    expect(formatted).toMatch(/1\.234,56\s*€/);
  });

  it("formats numbers with Spanish comma decimal and dot thousands separator", () => {
    const formatted = formatNumber(10500.75, 2);
    expect(formatted).toMatch(/10\.500,75/);
  });

  it("formats dates in DD/MM/YYYY format", () => {
    // 2026-11-04 -> 04/11/2026
    const formatted = formatDate(new Date(2026, 10, 4));
    expect(formatted).toBe("04/11/2026");
  });

  it("formats percentages with percent sign and comma decimal", () => {
    const formatted = formatPercent(0.985, 1);
    expect(formatted).toMatch(/98,5\s*%/);
  });
});

describe("i18n formatting, feature 012 additions", () => {
  it("keeps a service level without a trailing zero: 97,5 % and 95 %", () => {
    expect(formatPercent("0.9750", 2, 0)).toMatch(/^97,5\s*%$/);
    expect(formatPercent("0.9500", 2, 0)).toMatch(/^95\s*%$/);
    expect(formatPercent("0.9725", 2, 0)).toMatch(/^97,25\s*%$/);
  });

  it("formats a date-only value at midday so no time zone moves the day", () => {
    expect(formatDate(new Date("2026-11-01T12:00:00"))).toBe("01/11/2026");
    // Around the October daylight-saving change (Madrid goes back on 2026-10-25) the day is still the same one.
    expect(formatDate(new Date("2026-10-25T12:00:00"))).toBe("25/10/2026");
    expect(formatDate(new Date("2026-03-29T12:00:00"))).toBe("29/03/2026");
  });

  it("a key missing at run time shows readable Spanish, never the raw key", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    expect(i18n.t("no.such.key")).toBe(esJson["common.text_unavailable" as keyof typeof esJson]);
    expect(i18n.t("no.such.key")).not.toContain("no.such.key");
    expect(i18n.t("no.such.key", { defaultValue: "Texto propio" })).toBe("Texto propio");
    warn.mockRestore();
  });

  it("shows an empty string for an invalid date and a zero percent for a non-number", () => {
    expect(formatDate("not a date")).toBe("");
    expect(formatPercent("x")).toMatch(/^0\s*%$/);
  });
});

describe("Translation dictionary completeness (es-ES.json)", () => {
  it("contains all critical app navigation, risk, proposal, and a11y keys", () => {
    const requiredKeys = [
      "app.title",
      "nav.dashboard",
      "nav.quality",
      "nav.costs",
      "nav.proposals",
      "nav.config",
      "roles.viewer",
      "roles.buyer",
      "roles.approver",
      "roles.admin",
      "dashboard.risk_stockout",
      "dashboard.risk_expiry",
      "risk.stockout.imminent",
      "risk.expiry.near",
      "proposals.submit",
      "proposals.approve",
      "a11y.menu",
      "a11y.risk_table",
    ];

    for (const key of requiredKeys) {
      expect(esJson).toHaveProperty(key);
      expect((esJson as Record<string, string>)[key]).toBeTruthy();
      // Ensure no untranslated English placeholders like "[TODO]" or "[UNTRANSLATED]"
      expect((esJson as Record<string, string>)[key]).not.toMatch(/\[TODO\]|\[UNTRANSLATED\]/);
    }
  });

  it("fails when an undefined translation key is requested", () => {
    const dict = esJson as Record<string, string>;
    const missingKey = "non_existent_key_xyz";
    expect(dict[missingKey]).toBeUndefined();
  });
});
