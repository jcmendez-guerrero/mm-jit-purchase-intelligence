import { describe, expect, it } from "vitest";
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
