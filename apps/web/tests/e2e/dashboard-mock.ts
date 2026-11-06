import type { Page } from "@playwright/test";

export const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });

export const today = new Date().toISOString().slice(0, 10);

export function overview(risks = 1, over: Record<string, unknown> = {}) {
  return {
    summary: { ok: true, data: { day: today, inventory_value: "1234.50", valued_with_estimate: 2, unvalued_lots: 1, value_basis: "lot_acquisition_cost", expiring_value: "20.00", stockout_risk: 3, expiry_risk: 1,
      coverage_days_avg: "5.75", variants_without_demand: 4, coverage_basis: { forecast: 6, actual_90d: 9 }, variant_count: risks, forecast_available: true } },
    trend: { ok: true, data: { from: "2026-09-10", to: today, estimated: [], series: Array.from({ length: 60 }, (_, i) => ({ day: `2026-10-${String((i % 28) + 1).padStart(2, "0")}`, actual: (i * 7) % 11, censored_rows: 0, kind: "actual_erp" })) } },
    abc_xyz: { ok: true, data: { cells: [{ abc: "A", xyz: "X", variant_count: 4, value: "100.00" }, { abc: "B", xyz: "Y", variant_count: 6, value: "50.00" }] } },
    risks: { ok: true, data: Array.from({ length: risks }, (_, i) => ({ variant_id: 100 + i, risk_type: "stockout", explanation_key: "risk.stockout.imminent", params: { sku: `SYN-${100 + i}`, available: 2 } })) },
    options: { ok: true, data: { warehouses: [{ id: 1, name: "Almacén sintético A" }, { id: 2, name: "Almacén sintético B" }], categories: [{ id: "A", kind: "demand_group" }], family_available: false } },
    ...over,
  };
}

export async function signIn(page: Page, roles = ["viewer", "buyer"]) {
  await page.route("**/api/me", (r) => r.fulfill(json({ user_id: "buyer-1", roles, mfa_auth_time: new Date().toISOString(), csrf_token: "csrf" })));
}
