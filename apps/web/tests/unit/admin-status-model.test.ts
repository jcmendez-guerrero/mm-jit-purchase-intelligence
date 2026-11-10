import { describe, expect, it } from "vitest";
import { ageHours, canRerunJob, freshness, spendShare } from "../../src/features/admin/statusModel";

const now = new Date("2026-11-10T12:00:00Z");

describe("admin status model", () => {
  it("measures age and flags stale sources after 36 hours", () => {
    expect(ageHours("2026-11-10T00:00:00Z", now)).toBe(12);
    expect(freshness("2026-11-10T00:00:00Z", now)).toBe("fresh");
    expect(freshness("2026-11-08T00:00:00Z", now)).toBe("stale");
    expect(freshness("2026-11-09", now)).toBe("fresh");
    expect(freshness(null, now)).toBe("none");
    expect(freshness("garbage", now)).toBe("none");
  });
  it("uses the configured limit when given", () => {
    expect(freshness("2026-11-10T00:00:00Z", now, 6)).toBe("stale");
    expect(freshness("2026-11-08T00:00:00Z", now, 72)).toBe("fresh");
  });
  it("re-runs only failed jobs", () => {
    expect(canRerunJob("failed")).toBe(true);
    for (const s of ["queued", "running", "done"]) expect(canRerunJob(s)).toBe(false);
  });
  it("keeps the spend share between 0 and 1", () => {
    expect(spendShare(30, 120)).toBe(0.25);
    expect(spendShare(500, 120)).toBe(1);
    expect(spendShare(-1, 120)).toBe(0);
    expect(spendShare(5, 0)).toBe(0);
  });
});
