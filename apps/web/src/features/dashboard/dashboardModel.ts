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
