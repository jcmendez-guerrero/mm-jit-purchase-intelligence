// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, type AnomalyFlag, type QualitySummaryData } from "../../src/api/client";
import { QualitySummary, groupByDay } from "../../src/features/quality/QualitySummary";
import "../../src/i18n";
import { confirmAction } from "./confirm";

/** T027: the per-product quality summary and the anomaly decisions, in Spanish, with the roles that may decide. */

const summary: QualitySummaryData = {
  sku: "EJ-9104",
  period_start: "2026-01-01",
  period_end: "2026-04-30",
  days_in_period: 120,
  days_with_data: 115,
  coverage_ratio: "0.958333",
  gap_days: [{ from: "2026-01-11", to: "2026-01-15" }],
  rejected_count: 1,
  quarantined_count: 2,
  ambiguous_count: 1,
  reason_counts: [{ key: "ambiguous_sku", count: 1 }],
  excluded_by_type: [{ key: "transfer_out", count: 3 }],
  anomaly_count: 1,
  censored_days: 16,
  origin: "erp",
  config_version_id: "defaults-abc",
  built_at: "2026-11-15T10:00:00Z",
};

const flag = (rule_id: AnomalyFlag["rule_id"], decision: AnomalyFlag["decision"] = "pending"): AnomalyFlag => ({
  sku: "EJ-9104", day: "2026-03-12", rule_id, original_value: "90", decision, decided_by: null, decided_at: null, reason_code: null,
});

beforeEach(() => {
  vi.spyOn(api, "getQualitySummary").mockResolvedValue(summary);
  vi.spyOn(api, "getQualityAnomalies").mockResolvedValue([flag("mad_outlier"), flag("p95_cap")]);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

async function open(roles: string[]) {
  render(<QualitySummary userRoles={roles} />);
  fireEvent.change(screen.getByLabelText("SKU"), { target: { value: "EJ-9104" } });
  fireEvent.click(screen.getByRole("button", { name: "Ver calidad" }));
  await screen.findByText(/Cobertura del historial/);
}

describe("groupByDay", () => {
  it("merges the rules of one day and reports the strongest decision", () => {
    expect(groupByDay([flag("mad_outlier"), flag("p95_cap")])).toEqual([{ day: "2026-03-12", rules: ["mad_outlier", "p95_cap"], value: "90", decision: "pending" }]);
    expect(groupByDay([flag("mad_outlier", "accepted"), flag("p95_cap", "accepted")])[0]?.decision).toBe("accepted");
    expect(groupByDay([flag("mad_outlier", "excluded"), flag("p95_cap", "accepted")])[0]?.decision).toBe("excluded");
  });
});

describe("QualitySummary", () => {
  it("shows coverage with Spanish formats, the gap range and the counts", async () => {
    await open(["viewer"]);
    expect(screen.getByText(/95,8\s?%/)).toBeTruthy();
    expect(screen.getByText(/115 de 120 días con datos/)).toBeTruthy();
    expect(screen.getByText(/Del 11\/01\/2026 al 15\/01\/2026/)).toBeTruthy();
    expect(screen.getByText("Datos del ERP", { exact: false })).toBeTruthy();
    expect(api.getQualitySummary).toHaveBeenCalledWith("EJ-9104");
  });

  it("lists each anomalous day once with its rules in words and the original value", async () => {
    await open(["viewer"]);
    expect(screen.getByText("Muy por encima de lo habitual, Supera el límite del percentil 95")).toBeTruthy();
    expect(screen.getAllByText("90").length).toBeGreaterThan(0);
  });

  it("offers no decision buttons to a viewer", async () => {
    await open(["viewer"]);
    expect(screen.queryByRole("button", { name: "Excluir del cálculo" })).toBeNull();
  });

  it("asks before excluding, sends the chosen reason, and reloads", async () => {
    const decide = vi.spyOn(api, "decideAnomaly").mockResolvedValue();
    await open(["viewer", "buyer"]);
    fireEvent.change(screen.getByLabelText("Motivo de la exclusión"), { target: { value: "one_off_event" } });
    fireEvent.click(screen.getByRole("button", { name: "Excluir del cálculo" }));
    const dialog = screen.getByRole("dialog", { name: "Excluir este día del cálculo" });
    expect(dialog.textContent).toContain("segundo factor");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancelar" }));
    expect(decide).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Excluir del cálculo" }));
    confirmAction();
    await waitFor(() => expect(decide).toHaveBeenCalledWith("EJ-9104", "2026-03-12", "excluded", "one_off_event"));
    await waitFor(() => expect(api.getQualityAnomalies).toHaveBeenCalledTimes(2));
  });

  it("accepting sends no reason", async () => {
    const decide = vi.spyOn(api, "decideAnomaly").mockResolvedValue();
    await open(["viewer", "admin"]);
    fireEvent.click(screen.getByRole("button", { name: "Aceptar como normal" }));
    confirmAction();
    await waitFor(() => expect(decide).toHaveBeenCalledWith("EJ-9104", "2026-03-12", "accepted", undefined));
  });

  it("shows the Spanish second-factor message when the BFF refuses a stale one", async () => {
    vi.spyOn(api, "decideAnomaly").mockRejectedValue(new ApiError(403, "auth_mfa_stale"));
    await open(["viewer", "buyer"]);
    fireEvent.click(screen.getByRole("button", { name: "Excluir del cálculo" }));
    confirmAction();
    expect((await screen.findByRole("alert")).textContent).toContain("segundo factor");
  });

  it("shows a Spanish error for an unknown SKU and keeps the form usable", async () => {
    vi.spyOn(api, "getQualitySummary").mockRejectedValue(new ApiError(404, "quality_product_not_found"));
    render(<QualitySummary userRoles={["viewer"]} />);
    fireEvent.change(screen.getByLabelText("SKU"), { target: { value: "NOPE" } });
    fireEvent.click(screen.getByRole("button", { name: "Ver calidad" }));
    expect(await screen.findByText(/No se encuentra el producto/)).toBeTruthy();
    expect((screen.getByLabelText("SKU") as HTMLInputElement).value).toBe("NOPE");
  });
});
