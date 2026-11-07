import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, DashOverview, errorMessage } from "../../api/client";
import { formatCurrencyEUR, formatDate, formatNumber, formatPercent } from "../../i18n/formatters";
import { ChartWithTable } from "./ChartWithTable";
import { ageInDays, coverageDays, isStale, PERIODS, trendStats } from "./dashboardModel";
import { ProductDetail } from "./ProductDetail";

interface Props {
  selectedWarehouse?: number | undefined;
  onSelectWarehouse?: ((id: number | undefined) => void) | undefined;
}

const METRICS = ["wape", "bias", "stockout_rate"] as const;

const Unavailable: React.FC = () => {
  const { t } = useTranslation();
  return <p role="alert">{t("dashboard.card_unavailable")}</p>;
};

export const DashboardScreen: React.FC<Props> = ({ selectedWarehouse, onSelectWarehouse }) => {
  const { t } = useTranslation();
  const [data, setData] = useState<DashOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [warehouse, setWarehouse] = useState<number | undefined>(selectedWarehouse);
  const [category, setCategory] = useState<string>("");
  const [days, setDays] = useState<number>(60);
  const [supplier, setSupplier] = useState<string>("");
  const [detail, setDetail] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setData(await api.getDashboardOverview({ warehouse_id: warehouse, category: category || undefined, days, supplier_id: supplier || undefined }));
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    } finally {
      setLoading(false);
    }
  }, [warehouse, category, days, supplier, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const pickWarehouse = (v: string) => {
    const id = v === "all" ? undefined : parseInt(v, 10);
    setWarehouse(id);
    onSelectWarehouse?.(id);
  };

  const s = data?.summary.ok ? data.summary.data : undefined;
  const stats = data?.trend.ok && data.trend.data ? trendStats(data.trend.data.series) : null;
  const opts = data?.options.ok ? data.options.data : undefined;
  const risks = data?.risks.ok ? (data.risks.data ?? []) : [];
  const cells = data?.abc_xyz.ok ? (data.abc_xyz.data?.cells ?? []) : [];
  const cov = s ? coverageDays(s) : null;

  return (
    <section aria-labelledby="dashboard-title">
      <div className="mmi-card">
        <h2 id="dashboard-title">{t("dashboard.title")}</h2>
        <p className="mmi-muted">{t("dashboard.subtitle")}</p>

        <div role="group" aria-label={t("dashboard.filters")} style={{ display: "flex", gap: "1rem", flexWrap: "wrap", alignItems: "end" }}>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <label htmlFor="f-warehouse">{t("dashboard.filter.warehouse")}</label>
            <select id="f-warehouse" value={warehouse === undefined ? "all" : String(warehouse)} onChange={(e) => pickWarehouse(e.target.value)}>
              <option value="all">{t("common.all_warehouses")}</option>
              {(opts?.warehouses ?? []).map((w) => (
                <option key={w.id} value={String(w.id)}>
                  {w.name}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <label htmlFor="f-category">{t("dashboard.filter.category")}</label>
            <select id="f-category" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">{t("dashboard.filter.all_categories")}</option>
              {(opts?.categories ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {t(`dashboard.category.${c.id}`)}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <label htmlFor="f-supplier">{t("dashboard.filter.supplier")}</label>
            <select id="f-supplier" value={supplier} onChange={(e) => setSupplier(e.target.value)}>
              <option value="">{t("dashboard.filter.all_suppliers")}</option>
              {(data?.suppliers.ok ? (data.suppliers.data ?? []) : []).map((sp) => (
                <option key={sp.id} value={sp.id}>
                  {sp.name}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <label htmlFor="f-days">{t("dashboard.filter.days")}</label>
            <select id="f-days" value={days} onChange={(e) => setDays(parseInt(e.target.value, 10))}>
              {PERIODS.map((p) => (
                <option key={p} value={p}>
                  {t("dashboard.days", { n: p })}
                </option>
              ))}
            </select>
          </div>
        </div>
        <p className="mmi-muted">{t("dashboard.filter.supplier_note")}</p>
        {opts && !opts.family_available && <p className="mmi-muted">{t("dashboard.family_pending")}</p>}
        {loading && <p>{t("dashboard.loading_state")}</p>}
        {error && <p role="alert">{error}</p>}
        {s && (
          <p className="mmi-muted">
            {t("dashboard.freshness", { day: formatDate(s.day) })}
            {isStale(s) ? ` · ${t("dashboard.stale", { days: ageInDays(s.day) })}` : ""}
          </p>
        )}
      </div>

      {data && (
        <>
          <div className="mmi-stat-grid">
            <div className="mmi-stat-card" aria-label={t("dashboard.kpi.value")}>
              <h3 className="mmi-stat-card-title">{t("dashboard.kpi.value")}</h3>
              {s ? (
                <>
                  <div className="mmi-stat-card-value">{s.inventory_value === null ? "—" : formatCurrencyEUR(s.inventory_value)}</div>
                  <p className="mmi-stat-card-desc">{t("dashboard.kpi.value_basis")}</p>
                  {s.valued_with_estimate > 0 && <p className="mmi-stat-card-desc">{t("dashboard.kpi.value_estimated", { n: s.valued_with_estimate })}</p>}
                  {s.unvalued_lots > 0 && <p className="mmi-stat-card-desc">{t("dashboard.kpi.value_unvalued", { n: s.unvalued_lots })}</p>}
                </>
              ) : (
                <Unavailable />
              )}
            </div>
            <div className="mmi-stat-card" aria-label={t("dashboard.kpi.coverage")}>
              <h3 className="mmi-stat-card-title">{t("dashboard.kpi.coverage")}</h3>
              {s ? (
                <>
                  <div className="mmi-stat-card-value">{cov === null ? t("dashboard.kpi.coverage_none") : t("dashboard.kpi.coverage_days", { n: formatNumber(cov, 1) })}</div>
                  <p className="mmi-stat-card-desc">{t("dashboard.kpi.coverage_basis", { forecast: s.coverage_basis.forecast, actual: s.coverage_basis.actual_90d })}</p>
                  {s.variants_without_demand > 0 && <p className="mmi-stat-card-desc">{t("dashboard.kpi.coverage_no_demand", { n: s.variants_without_demand })}</p>}
                </>
              ) : (
                <Unavailable />
              )}
            </div>
            <div className="mmi-stat-card" aria-label={t("dashboard.kpi.stockout")}>
              <h3 className="mmi-stat-card-title">{t("dashboard.kpi.stockout")}</h3>
              {s ? <div className="mmi-stat-card-value">{s.stockout_risk}</div> : <Unavailable />}
            </div>
            <div className="mmi-stat-card" aria-label={t("dashboard.kpi.expiring")}>
              <h3 className="mmi-stat-card-title">{t("dashboard.kpi.expiring")}</h3>
              {s ? (
                <>
                  <div className="mmi-stat-card-value">{s.expiring_value === null ? "—" : formatCurrencyEUR(s.expiring_value)}</div>
                  <p className="mmi-stat-card-desc">{t("dashboard.kpi.expiry_count", { n: s.expiry_risk })}</p>
                </>
              ) : (
                <Unavailable />
              )}
            </div>
            <div className="mmi-stat-card" aria-label={t("dashboard.kpi.spend")}>
              <h3 className="mmi-stat-card-title">{t("dashboard.kpi.spend")}</h3>
              {data.spend.ok && data.spend.data ? (
                data.spend.data.proposal_id === null ? (
                  <p className="mmi-stat-card-desc">{t("dashboard.kpi.spend_none")}</p>
                ) : (
                  <>
                    <div className="mmi-stat-card-value">{formatCurrencyEUR(data.spend.data.total)}</div>
                    <p className="mmi-stat-card-desc">{t("dashboard.kpi.spend_week", { week: data.spend.data.week, status: t(`proposals.status.${data.spend.data.status}`, { defaultValue: String(data.spend.data.status) }) })}</p>
                    {data.spend.data.budget !== null && <p className="mmi-stat-card-desc">{t("dashboard.kpi.spend_budget", { value: formatCurrencyEUR(data.spend.data.budget) })}</p>}
                    {data.spend.data.over_budget && <p role="note">{t("dashboard.kpi.spend_over")}</p>}
                  </>
                )
              ) : (
                <Unavailable />
              )}
            </div>
          </div>

          <div className="mmi-card">
            <h3>{t("dashboard.accuracy")}</h3>
            {!data.accuracy.ok || !data.accuracy.data ? (
              <Unavailable />
            ) : Object.keys(data.accuracy.data.metrics).length === 0 ? (
              <p>{t("dashboard.accuracy_none")}</p>
            ) : (
              <table aria-label={t("dashboard.accuracy")} className="mmi-table">
                <thead>
                  <tr>
                    <th>{t("dashboard.chart.col.group")}</th>
                    {METRICS.map((m) => (
                      <th key={m}>{t(`dashboard.accuracy.${m}`)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.accuracy.data.metrics).map(([group, vals]) => (
                    <tr key={group}>
                      <td>{group === "all" ? t("dashboard.accuracy.all") : t("dashboard.accuracy.group", { g: group })}</td>
                      {METRICS.map((m) => (
                        <td key={m}>{vals[m] === undefined ? t("dashboard.accuracy.na") : formatPercent(vals[m], 1)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="mmi-muted">{t("dashboard.accuracy_note")}</p>
          </div>

          <div className="mmi-card">
            {data.trend.ok && data.trend.data ? (
              stats === null ? (
                <p>{t("dashboard.chart.trend_empty")}</p>
              ) : (
                <ChartWithTable
                  title={t("dashboard.chart.trend")}
                  summary={t("dashboard.chart.trend_summary", { total: stats.total, days: stats.days, max: stats.max, day: formatDate(stats.maxDay) })}
                  columns={[t("dashboard.chart.col.day"), t("dashboard.chart.col.units")]}
                  rows={data.trend.data.series.map((p) => [formatDate(p.day), p.actual])}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data.trend.data.series}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="day" tickFormatter={(d: string) => formatDate(d)} />
                      <YAxis allowDecimals={false} />
                      <Tooltip labelFormatter={(d) => formatDate(String(d))} />
                      <Bar dataKey="actual" fill="#1f5f6b" name={t("dashboard.chart.col.units")} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartWithTable>
              )
            ) : (
              <Unavailable />
            )}
            <p className="mmi-muted">{t("dashboard.chart.trend_note")}</p>
          </div>

          <div className="mmi-card">
            {data.abc_xyz.ok ? (
              cells.length === 0 ? (
                <p>{t("dashboard.chart.abc_empty")}</p>
              ) : (
                <ChartWithTable
                  title={t("dashboard.chart.abc")}
                  summary={t("dashboard.chart.abc_summary", { count: cells.reduce((n, c) => n + c.variant_count, 0), cells: cells.length })}
                  columns={[t("dashboard.chart.col.group"), t("dashboard.chart.col.variants"), t("dashboard.chart.col.value")]}
                  rows={cells.map((c) => [`${c.abc}${c.xyz}`, c.variant_count, formatCurrencyEUR(c.value)])}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={cells.map((c) => ({ group: `${c.abc}${c.xyz}`, count: c.variant_count }))}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="group" />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#c97b2a" name={t("dashboard.chart.col.variants")} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartWithTable>
              )
            ) : (
              <Unavailable />
            )}
          </div>

          <div className="mmi-card">
            <h3>{t("dashboard.risks")}</h3>
            {!data.risks.ok ? (
              <Unavailable />
            ) : risks.length === 0 ? (
              <p>✓ {t("dashboard.no_risks")}</p>
            ) : (
              <table aria-label={t("a11y.risk_table")} className="mmi-table">
                <thead>
                  <tr>
                    <th>{t("common.variant")}</th>
                    <th>{t("common.status")}</th>
                    <th>{t("proposals.explanation")}</th>
                    <th>{t("common.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {risks.map((r, i) => (
                    <tr key={`${r.variant_id}-${i}`}>
                      <td>#{r.variant_id}</td>
                      <td>{t(r.risk_type === "stockout" ? "dashboard.risk_stockout" : r.risk_type === "expiry" ? "dashboard.risk_expiry" : "dashboard.risk_quality")}</td>
                      <td>{String(t(r.explanation_key, r.params ?? {}))}</td>
                      <td>
                        <button type="button" className="mmi-btn mmi-btn-sm mmi-btn-secondary" onClick={() => setDetail(r.variant_id)}>
                          {t("dashboard.risk_open")}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
      {detail !== null && <ProductDetail variantId={detail} onClose={() => setDetail(null)} />}
    </section>
  );
};
