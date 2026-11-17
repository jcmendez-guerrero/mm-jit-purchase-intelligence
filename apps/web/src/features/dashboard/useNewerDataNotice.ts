import { useCallback, useEffect, useRef, useState } from "react";
import { api, DashboardFreshness } from "../../api/client";

/** How often the screen asks whether newer data exists (feature 014, FR-015). One small read-only request a minute; nothing is pushed and nothing runs while the screen is closed. */
export const NEWER_DATA_POLL_MS = 60_000;

/** The newest refresh time among the sources (ISO strings compare in time order), or null when none has data. */
export function latestRefresh(f: DashboardFreshness): string | null {
  return f.sources.reduce<string | null>((best, s) => (s.refreshed_at !== null && (best === null || s.refreshed_at > best) ? s.refreshed_at : best), null);
}

/**
 * Tells the screen when data newer than what it shows exists, without ever changing what it shows: the figures move only when the user accepts and the screen reloads.
 * `loadedKey` changes whenever the screen has loaded its figures; the newest refresh seen right then becomes the baseline. A failing poll is ignored (the last answer stays).
 */
export function useNewerDataNotice(loadedKey: unknown, pollMs: number = NEWER_DATA_POLL_MS): { freshness: DashboardFreshness | null; newer: boolean } {
  const [freshness, setFreshness] = useState<DashboardFreshness | null>(null);
  const [newer, setNewer] = useState(false);
  const baseline = useRef<{ at: string | null } | null>(null);

  const poll = useCallback(() => {
    api
      .getDashboardFreshness()
      .then((f) => {
        setFreshness(f);
        const latest = latestRefresh(f);
        if (baseline.current === null) baseline.current = { at: latest };
        else if (latest !== null && (baseline.current.at === null || latest > baseline.current.at)) setNewer(true);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    baseline.current = null;                       // the screen just loaded: what it shows is what exists now
    setNewer(false);
    poll();
    const id = window.setInterval(poll, pollMs);
    return () => window.clearInterval(id);
  }, [loadedKey, poll, pollMs]);

  return { freshness, newer };
}
