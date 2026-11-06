import { describe, expect, it } from "vitest";
import { ageInDays, coverageDays, isStale, trendStats } from "../../src/features/dashboard/dashboardModel";

const today = new Date(Date.UTC(2026, 10, 9, 15));

describe("dashboard model", () => {
  it("counts whole days and never goes negative", () => {
    expect(ageInDays("2026-11-09", today)).toBe(0);
    expect(ageInDays("2026-11-06", today)).toBe(3);
    expect(ageInDays("2026-11-20", today)).toBe(0);
  });
  it("marks figures stale after two days", () => {
    expect(isStale({ day: "2026-11-07" }, today)).toBe(false);
    expect(isStale({ day: "2026-11-06" }, today)).toBe(true);
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
  it("rounds coverage to one decimal and keeps 'no demand' as null", () => {
    const base = { coverage_days_avg: "5.75" } as Parameters<typeof coverageDays>[0];
    expect(coverageDays(base)).toBe(5.8);
    expect(coverageDays({ ...base, coverage_days_avg: null })).toBeNull();
  });
});
