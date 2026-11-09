import { describe, expect, it } from "vitest";
import { ageInDays, forecastStats, mergeTrend, periodFor, trendStats } from "../../src/features/dashboard/dashboardModel";

const today = new Date(Date.UTC(2026, 10, 9, 15));

describe("dashboard model", () => {
  it("counts whole days and never goes negative", () => {
    expect(ageInDays("2026-11-09", today)).toBe(0);
    expect(ageInDays("2026-11-06", today)).toBe(3);
    expect(ageInDays("2026-11-20", today)).toBe(0);
  });
  it("gives the date range of a last-N-days choice, ending today", () => {
    expect(periodFor(60, today)).toEqual({ from: "2026-09-11", to: "2026-11-09" });
    expect(periodFor(1, today)).toEqual({ from: "2026-11-09", to: "2026-11-09" });
  });
  it("summarises a trend: total, peak day and span", () => {
    const series = [
      { day: "2026-11-01", actual: 3, censored_rows: 0, kind: "actual_erp" },
      { day: "2026-11-02", actual: 9, censored_rows: 1, kind: "actual_erp" },
      { day: "2026-11-03", actual: 4, censored_rows: 0, kind: "actual_erp" },
    ];
    expect(trendStats(series)).toEqual({ total: 16, max: 9, maxDay: "2026-11-02", days: 3 });
    expect(trendStats([])).toBeNull();
  });
  it("merges actual days and forecast days into one ordered list without mixing them", () => {
    const rows = mergeTrend({
      series: [{ day: "2026-11-08", actual: 5, censored_rows: 0, kind: "actual_erp" }, { day: "2026-11-09", actual: 7, censored_rows: 0, kind: "actual_erp" }],
      estimated: [{ day: "2026-11-10", mean: "3.50", upper: "5.00", kind: "forecast" }, { day: "2026-11-11", mean: "3.50", upper: "2.00", kind: "forecast" }],
    });
    expect(rows.map((r) => r.day)).toEqual(["2026-11-08", "2026-11-09", "2026-11-10", "2026-11-11"]);
    expect(rows[1]).toEqual({ day: "2026-11-09", actual: 7 });                                  // an actual day carries no forecast
    expect(rows[2]).toEqual({ day: "2026-11-10", mean: 3.5, upper: 5, band: [3.5, 5] });         // a forecast day carries no actual
    expect(rows[3]?.upper).toBe(3.5);                                                           // an inverted upper bound is lifted to the mean
  });
  it("summarises the forecast or says there is none", () => {
    expect(forecastStats([])).toBeNull();
    expect(forecastStats([{ day: "2026-11-10", mean: "3.50", upper: "5.00", kind: "forecast" }, { day: "2026-11-11", mean: "3.50", upper: "5.00", kind: "forecast" }])).toEqual({ mean: 3.5, upper: 5, days: 2 });
  });
});

import { severitySplitIsReliable, stockoutSeverityCounts } from "../../src/features/dashboard/dashboardModel";

describe("stockout severity split (ruler)", () => {
  const risks = [
    { risk_type: "stockout", explanation_key: "risk.stockout.out_of_stock" },
    { risk_type: "stockout", explanation_key: "risk.stockout.imminent" },
    { risk_type: "stockout", explanation_key: "risk.stockout.imminent" },
    { risk_type: "stockout", explanation_key: "risk.stockout.below_reorder_point" },
    { risk_type: "expiry", explanation_key: "risk.expiry.near" },
    { risk_type: "data_quality", explanation_key: "risk.data_quality.missing_vat" },
  ];

  it("counts only stockout items, by severity", () => {
    expect(stockoutSeverityCounts(risks)).toEqual({ out_of_stock: 1, imminent: 2, below_reorder_point: 1 });
  });

  it("ignores stockout items with an unknown severity key", () => {
    expect(stockoutSeverityCounts([{ risk_type: "stockout", explanation_key: "risk.stockout.something_new" }])).toEqual({ out_of_stock: 0, imminent: 0, below_reorder_point: 0 });
  });

  it("trusts the split only when it adds up to the summary's stockout count", () => {
    const counts = stockoutSeverityCounts(risks);
    expect(severitySplitIsReliable(counts, 4)).toBe(true);
    expect(severitySplitIsReliable(counts, 7)).toBe(false); // the list ignores the category filter
    expect(severitySplitIsReliable(counts, undefined)).toBe(false);
  });
});
