import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

/** The dashboard filters as the address carries them (research R11): a link reproduces the view. Invalid values are ignored and reported, never guessed. */
export interface DashboardFilters {
  warehouse?: number;
  supplier?: string;
  category?: "A" | "B" | "C" | "critical";
  family?: string;
  from?: string; // ISO date
  to?: string; // ISO date
}

export const PARAM = { warehouse: "almacen", supplier: "proveedor", category: "categoria", family: "familia", from: "desde", to: "hasta" } as const;
const CATEGORIES = ["A", "B", "C", "critical"] as const;

const isIsoDate = (v: string): boolean => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return false;
  const d = new Date(`${v}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === v;
};

export function parseDashboardFilters(params: URLSearchParams): { filters: DashboardFilters; ignored: string[] } {
  const filters: DashboardFilters = {};
  const ignored: string[] = [];
  const take = (key: keyof typeof PARAM, ok: (v: string) => boolean, set: (v: string) => void) => {
    const raw = params.get(PARAM[key]);
    if (raw === null) return;
    if (ok(raw)) set(raw);
    else ignored.push(PARAM[key]);
  };
  take("warehouse", (v) => /^\d{1,9}$/.test(v), (v) => (filters.warehouse = parseInt(v, 10)));
  take("supplier", (v) => /^[A-Za-z0-9_-]{1,36}$/.test(v), (v) => (filters.supplier = v));
  take("category", (v) => (CATEGORIES as readonly string[]).includes(v), (v) => (filters.category = v as NonNullable<DashboardFilters["category"]>));
  take("family", (v) => v.length > 0 && v.length <= 120, (v) => (filters.family = v));
  take("from", isIsoDate, (v) => (filters.from = v));
  take("to", isIsoDate, (v) => (filters.to = v));
  if (filters.from && filters.to && filters.from > filters.to) {
    ignored.push(PARAM.from, PARAM.to);
    delete filters.from;
    delete filters.to;
  }
  return { filters, ignored };
}

/** Writes the filters into a copy of the current parameters, leaving every other parameter untouched. */
export function writeDashboardFilters(filters: DashboardFilters, prev: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(prev);
  (Object.keys(PARAM) as (keyof typeof PARAM)[]).forEach((k) => {
    const v = filters[k];
    if (v === undefined || v === "") next.delete(PARAM[k]);
    else next.set(PARAM[k], String(v));
  });
  return next;
}

export function useDashboardFilters() {
  const [params, setParams] = useSearchParams();
  const { filters, ignored } = useMemo(() => parseDashboardFilters(params), [params]);
  const set = useCallback((patch: Partial<DashboardFilters>) => setParams((prev) => writeDashboardFilters({ ...parseDashboardFilters(prev).filters, ...patch }, prev), { replace: true }), [setParams]);
  const clear = useCallback(() => setParams((prev) => writeDashboardFilters({}, prev), { replace: true }), [setParams]);
  return { filters, ignored, set, clear };
}
