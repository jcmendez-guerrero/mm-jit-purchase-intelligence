import type { DashSummary, DashTrend } from "../../api/client";

export const STALE_AFTER_DAYS = 2;
export const PERIODS = [30, 60, 90, 180] as const;

/** Whole days between the figures' day and today (UTC date strings); never negative. */
export function ageInDays(day: string, today: Date = new Date()): number {
  const d = new Date(`${day}T00:00:00Z`);
  const t = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  return Math.max(0, Math.round((t - d.getTime()) / 86_400_000));
}

export const isStale = (s: Pick<DashSummary, "day">, today?: Date): boolean => ageInDays(s.day, today) > STALE_AFTER_DAYS;

export interface TrendStats {
  total: number;
  max: number;
  maxDay: string;
  days: number;
}

export function trendStats(series: DashTrend["series"]): TrendStats | null {
  if (series.length === 0) return null;
  let best = series[0]!;
  let total = 0;
  for (const p of series) {
    total += p.actual;
    if (p.actual > best.actual) best = p;
  }
  return { total, max: best.actual, maxDay: best.day, days: series.length };
}

export const coverageDays = (s: DashSummary): number | null => (s.coverage_days_avg === null ? null : Math.round(parseFloat(s.coverage_days_avg) * 10) / 10);

/** Column heading for the figure shown next to each product in a drill-down. */
export const figureColumnKey = (kind: string): string =>
  ({ inventory_value: "dashboard.drill.col.value", coverage: "dashboard.drill.col.days", trend_day: "dashboard.drill.col.units", abc_xyz: "dashboard.drill.col.value" })[kind] ?? "dashboard.drill.col.value";

export interface TrendRow {
  day: string;
  actual?: number;
  mean?: number;
  upper?: number;
  band?: [number, number];        // for the uncertainty area: from the forecast mean up to the upper bound
}

/** One row per day: actual ERP demand for past days, the forecast for coming days. The two series are never added or blended. */
export function mergeTrend(trend: Pick<DashTrend, "series" | "estimated">): TrendRow[] {
  const byDay = new Map<string, TrendRow>();
  for (const p of trend.series) byDay.set(p.day, { day: p.day, actual: p.actual });
  for (const p of trend.estimated) {
    const mean = Number(p.mean);
    const upper = Math.max(Number(p.upper), mean);
    byDay.set(p.day, { ...(byDay.get(p.day) ?? { day: p.day }), mean, upper, band: [mean, upper] });
  }
  return [...byDay.values()].sort((a, b) => a.day.localeCompare(b.day));
}

export interface ForecastStats {
  mean: number;
  upper: number;
  days: number;
}

export function forecastStats(estimated: DashTrend["estimated"]): ForecastStats | null {
  const first = estimated[0];
  if (!first) return null;
  return { mean: Number(first.mean), upper: Math.max(Number(first.upper), Number(first.mean)), days: estimated.length };
}
