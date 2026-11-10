import type { DashTrend } from "../../api/client";

export const DEFAULT_DAYS = 60;

/** Whole days between the figures' day and today (UTC date strings); never negative. */
export function ageInDays(day: string, today: Date = new Date()): number {
  const d = new Date(`${day}T00:00:00Z`);
  const t = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  return Math.max(0, Math.round((t - d.getTime()) / 86_400_000));
}

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

/** Stockout severity split from the existing risk list (design.md §6). */
export type StockoutSeverity = "out_of_stock" | "imminent" | "below_reorder_point";

export function stockoutSeverityCounts(risks: Array<{ risk_type: string; explanation_key: string }>): Record<StockoutSeverity, number> {
  const counts: Record<StockoutSeverity, number> = { out_of_stock: 0, imminent: 0, below_reorder_point: 0 };
  for (const r of risks) {
    if (r.risk_type !== "stockout") continue;
    const key = r.explanation_key.replace("risk.stockout.", "") as StockoutSeverity;
    if (key in counts) counts[key] += 1;
  }
  return counts;
}

/**
 * The risk list ignores the category and family filters while the summary count respects them, so the split is shown
 * only when both agree; otherwise the ruler shows the summary count alone.
 */
export function severitySplitIsReliable(counts: Record<StockoutSeverity, number>, summaryStockoutRisk: number | undefined): boolean {
  const sum = counts.out_of_stock + counts.imminent + counts.below_reorder_point;
  return summaryStockoutRisk !== undefined && sum === summaryStockoutRisk;
}

/** The range the dashboard shows: the chosen dates, with a missing end filled by today (UTC) and a missing start by the default span before the end. */
export function periodFor(from?: string, to?: string, today: Date = new Date()): { from: string; to: string } {
  const end = to ?? new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate())).toISOString().slice(0, 10);
  const start = from ?? new Date(new Date(`${end}T00:00:00Z`).getTime() - (DEFAULT_DAYS - 1) * 86_400_000).toISOString().slice(0, 10);
  return { from: start, to: end };
}
