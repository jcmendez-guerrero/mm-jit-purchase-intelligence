// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, type ForecastExplanation, type ProposalLine } from "../../src/api/client";
import { ExplanationPanel } from "../../src/features/quality/ExplanationPanel";
import { ProposalLineExplanation } from "../../src/features/proposals/ProposalLineExplanation";
import "../../src/i18n";

/** T039: why a forecast is what it is, in Spanish, reachable from the proposal line; and the "not a forecast" label (T037). */

const explanation = (over: Partial<ForecastExplanation> = {}): ForecastExplanation => ({
  run_id: "r1", sku: "EJ-1", model_version: "minmax_poisson@v1", dataset_version_id: null, config_version_id: "defaults-abc", history_start: "2026-01-01", history_end: "2026-03-01",
  abc: "A", xyz: "X", pattern: "smooth", intermittent: false, method: "minmax_poisson", method_reason_code: "backtest_adopted", censored_days: 16, anomaly_days_excluded: 2,
  provenance_mix: { observed: 70, estimated: 30, manual: 0 }, low: null, expected: "12.5000", high: null, confidence: null, confidence_reason_codes: [],
  eligibility: "eligible", eligibility_reason_codes: [], ...over,
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ExplanationPanel", () => {
  it("shows versions, window, class, method and its reason, the figure, the left-out days and the data origin", async () => {
    vi.spyOn(api, "getForecastExplanation").mockResolvedValue(explanation());
    render(<ExplanationPanel sku="EJ-1" />);
    expect(await screen.findByText(/minmax_poisson@v1/)).toBeTruthy();
    expect(screen.getByText(/Configuración de clases: defaults-abc/)).toBeTruthy();
    expect(screen.getByText(/Conjunto de datos de apoyo: Ninguno/)).toBeTruthy();
    expect(screen.getByText("Del 01/01/2026 al 01/03/2026")).toBeTruthy();
    expect(screen.getByText(/AX · Demanda regular/)).toBeTruthy();
    expect(screen.getByText(/menor coste en la prueba retrospectiva/)).toBeTruthy();
    expect(screen.getByText("12,5")).toBeTruthy();
    expect(screen.getByText(/Días sin existencias que no se usan para aprender: 16/)).toBeTruthy();
    expect(screen.getByText(/Días excluidos por el comprador: 2/)).toBeTruthy();
    expect(screen.getByText(/Observado \(ERP\): 70; Estimado: 30/)).toBeTruthy();
    expect(screen.queryByText(/No es una previsión/)).toBeNull();
  });

  it("says a not-eligible product has no forecast: no figure, a reason in words and the fallback", async () => {
    vi.spyOn(api, "getForecastExplanation").mockResolvedValue(
      explanation({ eligibility: "not_eligible", eligibility_reason_codes: ["new"], expected: null, method: "minmax_conservative", method_reason_code: "min_max_fallback", pattern: "new" }),
    );
    render(<ExplanationPanel sku="EJ-100" />);
    expect(await screen.findByText(/Producto nuevo con poco historial/)).toBeTruthy();
    expect(screen.getByText(/No es una previsión/)).toBeTruthy();
    expect(screen.getByText(/mínimo y un máximo prudentes/)).toBeTruthy();
    expect(screen.queryByText("Demanda esperada")).toBeNull();
  });

  it("notes that intermittent demand uses a method for sporadic sales", async () => {
    vi.spyOn(api, "getForecastExplanation").mockResolvedValue(explanation({ pattern: "intermittent", intermittent: true }));
    render(<ExplanationPanel sku="EJ-1" />);
    expect(await screen.findByText(/método pensado para ventas esporádicas/)).toBeTruthy();
  });

  it("shows a Spanish message when there is no explanation yet", async () => {
    vi.spyOn(api, "getForecastExplanation").mockRejectedValue(new ApiError(404, "forecast_explanation_not_available"));
    render(<ExplanationPanel sku="EJ-1" />);
    expect(await screen.findByText(/Todavía no hay una explicación de previsión/)).toBeTruthy();
  });
});

describe("ProposalLineExplanation", () => {
  const line = (eligible: boolean): ProposalLine =>
    ({
      id: "l1", sku: "EJ-1", variant_id: 1, qty: 10,
      explanation: {
        policy: "forecast", forecast_eligible: eligible, service_level: "95", horizon_days: 14, expected_demand: 8, safety_stock: 2, order_up_to: 12, reorder_point: 5, need: 10, top_up: false,
        clinical_critical: false, position: { on_hand: 0, expiring: 0, usable: 0, inbound: 0, total: 0 }, supplier: { chosen: "s1", reason: "lower_total_with_supplier_terms", alternatives: [], rejected: [] },
        cost: { unit: "10.0000", source: "manual", status: "ok" }, constraints: [],
      },
    }) as unknown as ProposalLine;

  it("opens and closes the detailed explanation for the line's SKU", async () => {
    const spy = vi.spyOn(api, "getForecastExplanation").mockResolvedValue(explanation());
    render(<ProposalLineExplanation line={line(true)} />);
    expect(spy).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Ver explicación detallada" }));
    await waitFor(() => expect(spy).toHaveBeenCalledWith("EJ-1"));
    expect(await screen.findByText(/minmax_poisson@v1/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ocultar explicación detallada" }));
    expect(screen.queryByText(/minmax_poisson@v1/)).toBeNull();
  });

  it("labels a line without a forecast as not a forecast", () => {
    render(<ProposalLineExplanation line={line(false)} />);
    expect(screen.getByText(/No es una previsión/)).toBeTruthy();
    cleanup();
    render(<ProposalLineExplanation line={line(true)} />);
    expect(screen.queryByText(/No es una previsión/)).toBeNull();
  });
});
