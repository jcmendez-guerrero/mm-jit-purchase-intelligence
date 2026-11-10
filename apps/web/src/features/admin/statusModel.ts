export const STALE_AFTER_HOURS = 36;                 // default only; the console reads the configured limit (admin thresholds)

export function ageHours(iso: string | null, now: Date): number | null {
  if (!iso) return null;
  const t = Date.parse(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  return Number.isNaN(t) ? null : Math.max(0, (now.getTime() - t) / 3_600_000);
}

export type Freshness = "fresh" | "stale" | "none";

export function freshness(iso: string | null, now: Date, limitHours: number = STALE_AFTER_HOURS): Freshness {
  const h = ageHours(iso, now);
  if (h === null) return "none";
  return h > limitHours ? "stale" : "fresh";
}

/** Only a failed job can be re-run; the service enforces it again. */
export const canRerunJob = (state: string): boolean => state === "failed";

export const spendShare = (estimate: number, budget: number): number => (budget > 0 ? Math.min(1, Math.max(0, estimate / budget)) : 0);
