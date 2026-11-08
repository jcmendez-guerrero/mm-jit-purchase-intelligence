import { api, DashOverview, DrillResponse } from "./client";

/** Typed dashboard calls for the executive dashboard (T014). More routes are added here as the backend ones land (charts, freshness, export, sku). */
export interface DashboardQuery {
  warehouse_id?: number;
  supplier_id?: string;
  category?: string;
  family?: string;
  days?: number;
}

export function dashboardQueryString(q: DashboardQuery, extra: Record<string, string | undefined> = {}): string {
  const p = new URLSearchParams();
  if (q.warehouse_id !== undefined) p.set("warehouse_id", String(q.warehouse_id));
  if (q.supplier_id) p.set("supplier_id", q.supplier_id);
  if (q.category) p.set("category", q.category);
  if (q.family) p.set("family", q.family);
  if (q.days) p.set("days", String(q.days));
  Object.entries(extra).forEach(([k, v]) => v !== undefined && p.set(k, v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const getOverview = (q: DashboardQuery): Promise<DashOverview> => api.getJson<DashOverview>(`/dashboard/overview${dashboardQueryString(q)}`);

export const getDrill = (q: DashboardQuery, kind: string, extra: { abc?: string; xyz?: string; day?: string } = {}): Promise<DrillResponse> => {
  const scope = { ...q }; // a drill-down has no trend window
  delete scope.days;
  return api.getJson<DrillResponse>(`/dashboard/drilldown${dashboardQueryString(scope, { kind, ...extra })}`);
};
