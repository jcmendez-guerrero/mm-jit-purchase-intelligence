import type { Page } from "@playwright/test";

export const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });

export const today = new Date().toISOString().slice(0, 10);

const UNITS: Record<string, string> = { stock_value: "EUR", coverage_days: "days", demand: "units", forecast: "units", stockout_risk: "count", expiry_exposure: "EUR", capital_tied_up: "EUR", purchasing_budget: "EUR", wape: "percent", bias: "percent" };
const VALUES: Record<string, string> = { stock_value: "1234.50", coverage_days: "5.75", demand: "239", forecast: "98.00", stockout_risk: "3", expiry_exposure: "20.00", capital_tied_up: "1264.50", purchasing_budget: "250.00", wape: "25.00", bias: "-5.00" };
export const MONEY_KEYS = ["stock_value", "expiry_exposure", "capital_tied_up", "purchasing_budget"];

/** The ten indicators as the BFF sends them; a viewer gets the money ones hidden with no value. */
export function indicators(hideMoney = false) {
  return Object.keys(UNITS).map((key) => {
    const hidden = hideMoney && MONEY_KEYS.includes(key);
    return { key, value: hidden ? null : VALUES[key], unit: UNITS[key], state: hidden ? "hidden_by_role" : "ok", basis: "dashboard.basis.lot_cost", definition_key: `dashboard.def.${key}`,
      freshness: { source: "inventory_snapshot", refreshed_at: `${today}T08:00:00Z`, refreshed_at_original: null, origin: "erp_sync", state: "ok", stale_after_hours: 48 } };
  });
}

export function overview(risks = 1, over: Record<string, unknown> = {}) {
  return {
    indicators: indicators(),
    summary: { ok: true, data: { day: today, inventory_value: "1234.50", valued_with_estimate: 2, unvalued_lots: 1, value_basis: "lot_acquisition_cost", expiring_value: "20.00", stockout_risk: 3, expiry_risk: 1,
      coverage_days_avg: "5.75", variants_without_demand: 4, coverage_basis: { forecast: 6, actual_90d: 9 }, variant_count: risks, forecast_available: true } },
    trend: { ok: true, data: { from: "2026-09-10", to: today, estimated: [], series: Array.from({ length: 60 }, (_, i) => ({ day: `2026-10-${String((i % 28) + 1).padStart(2, "0")}`, actual: (i * 7) % 11, censored_rows: 0, kind: "actual_erp" })) } },
    abc_xyz: { ok: true, data: { cells: [{ abc: "A", xyz: "X", variant_count: 4, value: "100.00" }, { abc: "B", xyz: "Y", variant_count: 6, value: "50.00" }] } },
    risks: { ok: true, data: Array.from({ length: risks }, (_, i) => ({ variant_id: 100 + i, risk_type: "stockout", explanation_key: "risk.stockout.imminent", params: { sku: `SYN-${100 + i}`, available: 2 } })) },
    options: { ok: true, data: { warehouses: [{ id: 1, name: "Almacén sintético A" }, { id: 2, name: "Almacén sintético B" }], categories: [{ id: "A", kind: "demand_group" }], family_available: false } },
    accuracy: { ok: true, data: { run_id: null, window_days: 7, metrics: {} } },
    spend: { ok: true, data: { proposal_id: null, week: null, status: null, total: "0.00", by_supplier: [], budget: null, over_budget: false } },
    suppliers: { ok: true, data: [{ id: "s1", name: "Proveedor Sintético A" }] },
    ...over,
  };
}

/** The chart tables as the BFF sends them (feature 014): a viewer gets no money column. */
export function charts(hideMoney = false) {
  const money = !hideMoney;
  const cols = (c: string[]) => (money ? c : c.filter((x) => x !== "value"));
  const row = (cells: Array<string | number>, at: number) => (money ? cells : cells.filter((_, i) => i !== at));
  return {
    charts: [
      { key: "expiry_bands", title_key: "dashboard.chart.title.expiry_bands", summary_params: { horizon_days: 60 }, columns: cols(["band", "products", "value"]), state: "ok",
        rows: [row(["expired", 0, "0.00"], 2), row(["d0_30", 1, "20.00"], 2), row(["d31_60", 1, "40.00"], 2)] },
      { key: "coverage_buckets", title_key: "dashboard.chart.title.coverage_buckets", summary_params: {}, columns: ["bucket", "products"], state: "ok",
        rows: [["d0_7", 2], ["d8_14", 0], ["d15_30", 0], ["d31_60", 0], ["d61_plus", 0], ["no_demand", 3]] },
      { key: "capital_by_group", title_key: "dashboard.chart.title.capital_by_group", summary_params: { part: "stock_at_cost" }, columns: cols(["group", "products", "value"]), state: "ok",
        rows: [row(["A", 1, "40.00"], 2), row(["B", 2, "20.00"], 2), row(["C", 1, "40.00"], 2)] },
      { key: "stock_value_history", title_key: "dashboard.chart.title.stock_value_history", summary_params: money ? {} : { reason: "hidden_by_role" }, columns: ["day", "value"],
        state: money ? "ok" : "no_data", rows: money ? [["2026-11-08", "90.00"], ["2026-11-09", "100.00"]] : [], range_available: { from: "2026-10-01", to: "2026-11-09" } },
    ],
  };
}

/** The freshness answer as the BFF sends it (feature 014): every source fresh, nothing left out. */
export function freshness(over: Record<string, unknown> = {}, refreshedAt = `${today}T08:00:00Z`) {
  return {
    sources: ["inventory_snapshot", "movements"].map((source) => ({ source, refreshed_at: refreshedAt, refreshed_at_original: null, origin: "erp_sync", state: "ok", stale_after_hours: 48 })),
    excluded_records: 0, local_load_excluded: 0, review_list_link: "/calidad", ...over,
  };
}

export async function signIn(page: Page, roles = ["viewer", "buyer"]) {
  await page.route("**/api/me", (r) => r.fulfill(json({ user_id: "buyer-1", roles, mfa_auth_time: new Date().toISOString(), csrf_token: "csrf" })));
  await page.route("**/api/dashboard/freshness*", (r) => r.fulfill(json(freshness())));
  await page.route("**/api/dashboard/charts*", (r) => r.fulfill(json(charts(!roles.some((x) => ["buyer", "approver", "admin"].includes(x))))));
}
