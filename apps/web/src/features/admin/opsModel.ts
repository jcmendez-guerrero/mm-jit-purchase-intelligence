import type { AlertRow, QueueItem } from "../../api/client";

/** Only a failed job or a dead-lettered role-mirror item can be retried here; message dead letters come from platform figures. */
export const canRetryItem = (i: QueueItem): i is QueueItem & { kind: "mirror" | "import" | "forecast" } =>
  i.kind !== "message" && (i.state === "failed" || i.state === "dead_lettered");

const STATE_ORDER: Record<AlertRow["state"], number> = { open: 0, acknowledged: 1, closed: 2 };

/** Open critical alerts first, then open warnings, then acknowledged, then closed; newest first inside a group. */
export function sortAlerts(rows: AlertRow[]): AlertRow[] {
  return [...rows].sort((a, b) =>
    STATE_ORDER[a.state] - STATE_ORDER[b.state]
    || Number(b.severity === "critical") - Number(a.severity === "critical")
    || Date.parse(b.last_seen_at) - Date.parse(a.last_seen_at));
}

export const canAcknowledge = (a: AlertRow): boolean => a.state === "open";

export const openAlertCount = (rows: AlertRow[]): number => rows.filter((a) => a.state !== "closed").length;

/** Whole numbers only, inside the server's range, and the warning must stay below the critical limit. Returns an error key or null. */
export function validateThresholds(v: Record<string, number>): string | null {
  for (const n of Object.values(v)) if (!Number.isInteger(n) || n < 1) return "errors.ops_settings_invalid";
  if ((v.budget_warn_pct ?? 0) >= (v.budget_critical_pct ?? Infinity)) return "errors.ops_settings_invalid";
  return null;
}

export const SETTING_KEYS = ["source_stale_hours", "backup_max_age_hours", "budget_warn_pct", "budget_critical_pct", "mirror_lag_minutes", "alert_repeat_hours"] as const;
