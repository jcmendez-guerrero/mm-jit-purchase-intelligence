import { describe, expect, it } from "vitest";
import type { AlertRow, QueueItem } from "../../src/api/client";
import { canAcknowledge, canRetryItem, openAlertCount, sortAlerts, validateThresholds } from "../../src/features/admin/opsModel";

const alert = (id: number, state: AlertRow["state"], severity: AlertRow["severity"], seen: string): AlertRow => ({
  id, condition_key: "mirror_lag", subject: "s", severity, state, opened_at: seen, last_seen_at: seen, acknowledged_by: null, acknowledged_at: null, reason_code: "mirror_lag",
});
const item = (kind: QueueItem["kind"], state: QueueItem["state"]): QueueItem => ({ kind, id: "1", state, attempts: 0, reason_code: null });

describe("ops model", () => {
  it("retries only failed or dead-lettered items that are not platform messages", () => {
    expect(canRetryItem(item("import", "failed"))).toBe(true);
    expect(canRetryItem(item("mirror", "dead_lettered"))).toBe(true);
    expect(canRetryItem(item("forecast", "running"))).toBe(false);
    expect(canRetryItem(item("message", "dead_lettered"))).toBe(false);
  });
  it("orders alerts: open critical, open warning, acknowledged, closed", () => {
    const rows = [alert(1, "closed", "critical", "2026-11-10T10:00:00Z"), alert(2, "open", "warning", "2026-11-10T09:00:00Z"),
      alert(3, "acknowledged", "critical", "2026-11-10T11:00:00Z"), alert(4, "open", "critical", "2026-11-10T08:00:00Z")];
    expect(sortAlerts(rows).map((a) => a.id)).toEqual([4, 2, 3, 1]);
    expect(rows.map((a) => a.id)).toEqual([1, 2, 3, 4]);          // the input is not reordered
  });
  it("lets only open alerts be acknowledged and counts the live ones", () => {
    expect(canAcknowledge(alert(1, "open", "warning", "x"))).toBe(true);
    expect(canAcknowledge(alert(1, "acknowledged", "warning", "x"))).toBe(false);
    expect(openAlertCount([alert(1, "open", "warning", "x"), alert(2, "closed", "warning", "x"), alert(3, "acknowledged", "warning", "x")])).toBe(2);
  });
  it("validates thresholds like the server does", () => {
    expect(validateThresholds({ source_stale_hours: 36, budget_warn_pct: 80, budget_critical_pct: 100 })).toBeNull();
    expect(validateThresholds({ source_stale_hours: 0 })).toBe("errors.ops_settings_invalid");
    expect(validateThresholds({ source_stale_hours: 1.5 })).toBe("errors.ops_settings_invalid");
    expect(validateThresholds({ budget_warn_pct: 100, budget_critical_pct: 100 })).toBe("errors.ops_settings_invalid");
  });
});
