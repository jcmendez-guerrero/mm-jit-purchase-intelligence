// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AdminStatus, api } from "../../src/api/client";
import { AdminStatusScreen } from "../../src/features/admin/AdminStatusScreen";

// MMI-14 (rule 5): the policy history shows the SKU; a row without one stays listed with "No aplica"; no variant id is shown.

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const status = (rows: AdminStatus["policy_history"]): AdminStatus => ({
  freshness: { ok: false, error: "downstream_unavailable" },
  import_jobs: { ok: false, error: "downstream_unavailable" },
  model_runs: { ok: false, error: "downstream_unavailable" },
  policy_history: rows,
  role_mirror: { ok: false, error: "downstream_unavailable" },
  cost: { budget_eur: 120, guardrails: { min_replicas: 0, max_replicas: 1, job_parallelism: 1 } },
});

describe("administration status: policy history", () => {
  it("shows each SKU and keeps a row without SKU", async () => {
    vi.spyOn(api, "getAdminStatus").mockResolvedValue(status({ ok: true, data: [
      { id: "o1", status: "approved", sku: "SYN-0001" },
      { id: "o2", status: "pending", sku: null },
    ] }));
    vi.spyOn(api, "getOpsSettings").mockRejectedValue(new Error("no thresholds"));
    render(<AdminStatusScreen />);
    expect(await screen.findByText("SYN-0001")).toBeTruthy();
    expect(screen.getByText("No aplica")).toBeTruthy();
    expect(screen.getAllByRole("row").filter((r) => /Aprobado|Pendiente/.test(r.textContent ?? "")).length).toBe(2);
  });
});
