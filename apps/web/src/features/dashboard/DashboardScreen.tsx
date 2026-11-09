import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, DashOverview, DrillRequest, errorMessage, RiskItem } from "../../api/client";
import { formatCurrencyEUR, formatDate, formatNumber, formatPercent } from "../../i18n/formatters";
import { DataTable, type Column } from "../../ui/DataTable";
import { FilterBar, type FilterChip } from "../../ui/FilterBar";
import { ScreenState } from "../../ui/ScreenState";
import { SeverityRuler, type Severity } from "../../ui/SeverityRuler";
import { StatusBadge } from "../../ui/StatusBadge";
import { statusInfo } from "../../ui/statusVocabulary";
import { useChartColors } from "../../ui/useChartColors";
import { ChartWithTable } from "./ChartWithTable";
import { ageInDays, coverageDays, forecastStats, isStale, mergeTrend, PERIODS, severitySplitIsReliable, stockoutSeverityCounts, trendStats } from "./dashboardModel";
import { DrillDownPanel } from "./DrillDownPanel";
import { ProductDetail } from "./ProductDetail";
import { SupplierPanel } from "./SupplierPanel";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";

interface Props {
  selectedWarehouse?: number | undefined;
  onSelectWarehouse?: ((id: number | undefined) => void) | undefined;
}

const METRICS = ["wape", "bias", "stockout_rate"] as const;
type AccuracyRow = [string, Record<string, string>];

// The ruler grows once, the first time the dashboard is shown in this page view; refetches and filters never replay it.
let rulerPlayed = false;

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
  useEffect(() => setWarehouse(selectedWarehouse), [selectedWarehouse]); // the address (?almacen=) is the source of truth
  const [category, setCategory] = useState<string>("");
  const [family, setFamily] = useState<string>("");
  const [drill, setDrill] = useState<{ request: DrillRequest; title: string } | null>(null);
  const [supplierOpen, setSupplierOpen] = useState<string | null>(null);
  const [days, setDays] = useState<number>(60);
  const [supplier, setSupplier] = useState<string>("");
  const [detail, setDetail] = useState<number | null>(null);
  const [severity, setSeverity] = useState<Severity | null>(null);
  const colors = useChartColors();
  const [animateRuler] = useState(() => !rulerPlayed);
  useEffect(() => {
    rulerPlayed = true;
  }, []);
  const scope = { warehouse_id: warehouse, category: category || undefined, family: family || undefined, supplier_id: supplier || undefined };
  const openDrill = (request: Omit<DrillRequest, "warehouse_id" | "category" | "family" | "supplier_id">, title: string) => {
    setDetail(null);
    setSupplierOpen(null);
    setDrill({ request: { ...request, ...scope }, title });
  };
  const viewProducts = (kind: DrillRequest["kind"]) => (
    <Button variant="secondary" small onClick={() => openDrill({ kind }, t(`dashboard.drill.title.${kind}`))}>
      {t("dashboard.drill.view")}
    </Button>
  );

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setData(await api.getDashboardOverview({ warehouse_id: warehouse, category: category || undefined, family: family || undefined, days, supplier_id: supplier || undefined }));
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    } finally {
      setLoading(false);
    }
  }, [warehouse, category, family, days, supplier, t]);

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
  const trendData = data?.trend.ok ? data.trend.data : undefined;
  const fstats = trendData ? forecastStats(trendData.estimated) : null;
  const trendRows = trendData ? mergeTrend(trendData) : [];
  const opts = data?.options.ok ? data.options.data : undefined;
  const risks = data?.risks.ok ? (data.risks.data ?? []) : [];
  const cells = data?.abc_xyz.ok ? (data.abc_xyz.data?.cells ?? []) : [];
  const cov = s ? coverageDays(s) : null;
  const severityCounts = stockoutSeverityCounts(risks);
  const splitReliable = severitySplitIsReliable(severityCounts, s?.stockout_risk);
  const shownRisks = severity && splitReliable ? risks.filter((r) => r.risk_type === "stockout" && r.explanation_key === `risk.stockout.${severity}`) : risks;

  const chips: FilterChip[] = [];
  const nameOf = (label: string, value: string) => `${t(label)}: ${value}`;
  if (warehouse !== undefined) chips.push({ key: "warehouse", name: t("dashboard.filter.warehouse"), label: nameOf("dashboard.filter.warehouse", opts?.warehouses.find((w) => w.id === warehouse)?.name ?? String(warehouse)), onRemove: () => pickWarehouse("all") });
  if (category) chips.push({ key: "category", name: t("dashboard.filter.category"), label: nameOf("dashboard.filter.category", t(`dashboard.category.${category}`)), onRemove: () => setCategory("") });
  if (family) chips.push({ key: "family", name: t("dashboard.filter.family"), label: nameOf("dashboard.filter.family", family), onRemove: () => setFamily("") });
  if (supplier) chips.push({ key: "supplier", name: t("dashboard.filter.supplier"), label: nameOf("dashboard.filter.supplier", (data?.suppliers.ok ? data.suppliers.data?.find((x) => x.id === supplier)?.name : undefined) ?? supplier), onRemove: () => setSupplier("") });
  const clearFilters = () => {
    pickWarehouse("all");
    setCategory("");
    setFamily("");
    setSupplier("");
  };

  const riskColumns: Column<RiskItem>[] = [
    { id: "variant", header: t("common.variant"), cell: (r) => String(r.params?.sku ?? t("dashboard.drill.no_sku")), sortValue: (r) => String(r.params?.sku ?? "") },
    { id: "status", header: t("common.status"), cell: (r) => <StatusBadge domain="risk" code={r.risk_type} />, sortValue: (r) => r.risk_type },
    { id: "why", header: t("proposals.explanation"), cell: (r) => String(t(r.explanation_key, r.params ?? {})) },
    {
      id: "actions",
      header: t("common.actions"),
      cell: (r) => (
        <Button variant="secondary" small onClick={() => setDetail(r.variant_id)}>
          {t("dashboard.risk_open")}
        </Button>
      ),
    },
  ];
  const riskTone = (r: RiskItem) => (r.risk_type === "stockout" ? statusInfo("risk", r.explanation_key.replace("risk.stockout.", "")).tone : statusInfo("risk", r.risk_type).tone);

  return (
    <section aria-labelledby="dashboard-title">
      <div className="mmi-dashboard-intro">
        <h2 id="dashboard-title">{t("dashboard.title")}</h2>
        <p className="mmi-muted">{t("dashboard.subtitle")}</p>
      </div>

      <FilterBar chips={chips} onClear={clearFilters}>
        <div className="mmi-filterbar__field">
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
        <div className="mmi-filterbar__field">
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
        {opts?.family_available && (
          <div className="mmi-filterbar__field">
            <label htmlFor="f-family">{t("dashboard.filter.family")}</label>
            <select id="f-family" value={family} onChange={(e) => setFamily(e.target.value)}>
              <option value="">{t("dashboard.filter.all_families")}</option>
              {(opts.families ?? []).map((fam) => (
                <option key={fam.id} value={fam.id}>
                  {fam.id}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="mmi-filterbar__field">
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
        {supplier && (
          <Button variant="secondary" small onClick={() => { setDrill(null); setDetail(null); setSupplierOpen(supplier); }}>
            {t("dashboard.supplier.view")}
          </Button>
        )}
        <div className="mmi-filterbar__field">
          <label htmlFor="f-days">{t("dashboard.filter.days")}</label>
          <select id="f-days" value={days} onChange={(e) => setDays(parseInt(e.target.value, 10))}>
            {PERIODS.map((p) => (
              <option key={p} value={p}>
                {t("dashboard.days", { n: p })}
              </option>
            ))}
          </select>
        </div>
      </FilterBar>
      <p className="mmi-muted">{t("dashboard.filter.supplier_note")}</p>
      {warehouse !== undefined && <p role="note">{t("dashboard.warehouse_informational")}</p>}
      {opts && !opts.family_available && <p className="mmi-muted">{t("dashboard.family_pending")}</p>}
      {s && (
        <p className="mmi-muted">
          {t("dashboard.freshness", { day: formatDate(s.day) })}
          {isStale(s) ? ` · ${t("dashboard.stale", { days: ageInDays(s.day) })}` : ""}
        </p>
      )}
      {loading && !data && <ScreenState state="loading" skeletonShape="dashboard" skeletonLines={5} />}
      {error && <ScreenState state="error" errorHint={error} onRetry={() => void load()} />}

      {data && (
        <>
          <SeverityRuler
            label={t("dashboard.kpi.stockout")}
            counts={severityCounts}
            total={s?.stockout_risk ?? 0}
            splitReliable={splitReliable}
            active={severity}
            onSelect={setSeverity}
            animate={animateRuler}
            action={s ? viewProducts("stockout_risk") : undefined}
          />

          <div className="mmi-figures">
            <div className="mmi-figure" role="group" aria-label={t("dashboard.kpi.value")}>
              <h3 className="mmi-figure__label">{t("dashboard.kpi.value")}</h3>
              {s ? (
                <>
                  <p className="mmi-figure__value">{s.hidden_by_role?.includes("inventory_value") ? t("dashboard.kpi.hidden_by_role") : s.inventory_value == null ? "—" : formatCurrencyEUR(s.inventory_value)}</p>
                  <p className="mmi-figure__note">{t("dashboard.kpi.value_basis")}</p>
                  {s.valued_with_estimate > 0 && <p className="mmi-figure__note">{t("dashboard.kpi.value_estimated", { n: s.valued_with_estimate })}</p>}
                  {s.unvalued_lots > 0 && <p className="mmi-figure__note">{t("dashboard.kpi.value_unvalued", { n: s.unvalued_lots })}</p>}
                  {viewProducts("inventory_value")}
                </>
              ) : (
                <Unavailable />
              )}
            </div>
            <div className="mmi-figure" role="group" aria-label={t("dashboard.kpi.coverage")}>
              <h3 className="mmi-figure__label">{t("dashboard.kpi.coverage")}</h3>
              {s ? (
                <>
                  <p className="mmi-figure__value">{cov === null ? t("dashboard.kpi.coverage_none") : t("dashboard.kpi.coverage_days", { n: formatNumber(cov, 1) })}</p>
                  <p className="mmi-figure__note">{t("dashboard.kpi.coverage_basis", { forecast: s.coverage_basis.forecast, actual: s.coverage_basis.actual_90d })}</p>
                  {s.variants_without_demand > 0 && <p className="mmi-figure__note">{t("dashboard.kpi.coverage_no_demand", { n: s.variants_without_demand })}</p>}
                  {viewProducts("coverage")}
                </>
              ) : (
                <Unavailable />
              )}
            </div>
            <div className="mmi-figure" role="group" aria-label={t("dashboard.kpi.expiring")}>
              <h3 className="mmi-figure__label">{t("dashboard.kpi.expiring")}</h3>
              {s ? (
                <>
                  <p className="mmi-figure__value">{s.hidden_by_role?.includes("expiring_value") ? t("dashboard.kpi.hidden_by_role") : s.expiring_value == null ? "—" : formatCurrencyEUR(s.expiring_value)}</p>
                  <p className="mmi-figure__note">{t("dashboard.kpi.expiry_count", { n: s.expiry_risk })}</p>
                  {viewProducts("expiry_risk")}
                </>
              ) : (
                <Unavailable />
              )}
            </div>
            <div className="mmi-figure" role="group" aria-label={t("dashboard.kpi.spend")}>
              <h3 className="mmi-figure__label">{t("dashboard.kpi.spend")}</h3>
              {data.spend.ok && data.spend.data ? (
                data.spend.data.proposal_id === null ? (
                  <p className="mmi-figure__note">{t("dashboard.kpi.spend_none")}</p>
                ) : (
                  <>
                    <p className="mmi-figure__value">{formatCurrencyEUR(data.spend.data.total)}</p>
                    <p className="mmi-figure__note">{t("dashboard.kpi.spend_week", { week: data.spend.data.week, status: t(`proposals.status.${data.spend.data.status}`, { defaultValue: String(data.spend.data.status) }) })}</p>
                    {data.spend.data.budget !== null && <p className="mmi-figure__note">{t("dashboard.kpi.spend_budget", { value: formatCurrencyEUR(data.spend.data.budget) })}</p>}
                    {data.spend.data.over_budget && <p role="note">{t("dashboard.kpi.spend_over")}</p>}
                    {data.spend.data.by_supplier.length > 0 && (
                      <ul className="mmi-figure__note" aria-label={t("dashboard.supplier.spend_list")}>
                        {data.spend.data.by_supplier.map((b) => (
                          <li key={b.supplier_id}>
                            {b.supplier_name ?? b.supplier_id}: {formatCurrencyEUR(b.total)}{" "}
                            <Button variant="secondary" small onClick={() => { setDrill(null); setDetail(null); setSupplierOpen(b.supplier_id); }}
               aria-label={`${t("dashboard.supplier.view")} ${b.supplier_name ?? b.supplier_id}`}>
                              {t("dashboard.supplier.view")}
                            </Button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                )
              ) : data.spend.error === "hidden_by_role" ? (
                <p className="mmi-figure__note">{t("dashboard.kpi.hidden_by_role")}</p>
              ) : (
                <Unavailable />
              )}
            </div>
          </div>

          <Card as="div">
            <h3>{t("dashboard.accuracy")}</h3>
            {!data.accuracy.ok || !data.accuracy.data ? (
              <Unavailable />
            ) : Object.keys(data.accuracy.data.metrics).length === 0 ? (
              <p>{t("dashboard.accuracy_none")}</p>
            ) : (
              <DataTable
                ariaLabel={t("dashboard.accuracy")}
                rows={Object.entries(data.accuracy.data.metrics)}
                rowKey={([group]) => group}
                hideToolbar
                columns={[
                  { id: "group", header: t("dashboard.chart.col.group"), cell: ([group]) => (group === "all" ? t("dashboard.accuracy.all") : t("dashboard.accuracy.group", { g: group })), sortValue: ([group]) => group },
                  ...METRICS.map((m) => ({
                    id: m,
                    header: t(`dashboard.accuracy.${m}`),
                    cell: (row: AccuracyRow) => (row[1][m] === undefined ? t("dashboard.accuracy.na") : formatPercent(row[1][m], 1)),
                    sortValue: (row: AccuracyRow) => (row[1][m] === undefined ? null : Number(row[1][m])),
                    align: "end" as const,
                  })),
                ]}
              />
            )}
            <p className="mmi-muted">{t("dashboard.accuracy_note")}</p>
          </Card>

          <Card as="div">
            {data.trend.ok && data.trend.data ? (
              stats === null ? (
                <p>{t("dashboard.chart.trend_empty")}</p>
              ) : (
                <ChartWithTable
                  title={t("dashboard.chart.trend")}
                  summary={t("dashboard.chart.trend_summary", { total: stats.total, days: stats.days, max: stats.max, day: formatDate(stats.maxDay) }) +
                    (fstats ? ` ${t("dashboard.chart.forecast_summary", { days: fstats.days, mean: formatNumber(fstats.mean, 1), upper: formatNumber(fstats.upper, 1) })}` : "")}
                  columns={[t("dashboard.chart.col.day"), t("dashboard.chart.col.actual"), ...(fstats ? [t("dashboard.chart.col.forecast"), t("dashboard.chart.col.upper")] : [])]}
                  rows={trendRows.map((p) => [formatDate(p.day), p.actual ?? "—", ...(fstats ? [p.mean === undefined ? "—" : formatNumber(p.mean, 1), p.upper === undefined ? "—" : formatNumber(p.upper, 1)] : [])])}
                  rowAction={(i) => {
                    const day = trendRows[i]?.actual === undefined ? "" : trendRows[i]?.day ?? "";
                    return { label: day ? t("dashboard.drill.day_action", { day: formatDate(day) }) : "", onClick: () => day && openDrill({ kind: "trend_day", day }, t("dashboard.drill.title.trend_day", { day: formatDate(day) })) };
                  }}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={trendRows}>
                      <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
                      <XAxis dataKey="day" tickFormatter={(d: string) => formatDate(d)} />
                      <YAxis allowDecimals={false} />
                      <Tooltip labelFormatter={(d) => formatDate(String(d))} />
                      <Legend />
                      <Bar dataKey="actual" fill={colors.primary} name={t("dashboard.chart.legend_actual")} cursor="pointer"
                        onClick={(p: { day?: string }) => p.day && openDrill({ kind: "trend_day", day: p.day }, t("dashboard.drill.title.trend_day", { day: formatDate(p.day) }))} />
                      {fstats && <Area dataKey="band" fill={colors.secondary} stroke="none" fillOpacity={0.25} name={t("dashboard.chart.legend_band")} />}
                      {fstats && <Line dataKey="mean" stroke={colors.secondary} strokeWidth={2} strokeDasharray="6 4" dot={false} name={t("dashboard.chart.legend_forecast")} />}
                    </ComposedChart>
                  </ResponsiveContainer>
                </ChartWithTable>
              )
            ) : (
              <Unavailable />
            )}
            <p className="mmi-muted">{t("dashboard.chart.trend_note")}</p>
            {trendData && (
              <>
                {fstats && trendData.estimated_basis && <p className="mmi-muted">{t("dashboard.chart.forecast_basis", { variants: trendData.estimated_basis.variants })}</p>}
                {fstats && trendData.estimated_basis && trendData.estimated_basis.seed_assisted > 0 && <p role="note">{t("dashboard.chart.forecast_seeded", { n: trendData.estimated_basis.seed_assisted })}</p>}
                {!fstats && <p className="mmi-muted">{t(trendData.estimated_basis?.reason === "company_wide_only" ? "dashboard.chart.forecast_company_wide" : "dashboard.chart.forecast_none")}</p>}
              </>
            )}
          </Card>

          <Card as="div">
            {data.abc_xyz.ok ? (
              cells.length === 0 ? (
                <p>{t("dashboard.chart.abc_empty")}</p>
              ) : (
                <ChartWithTable
                  title={t("dashboard.chart.abc")}
                  summary={t("dashboard.chart.abc_summary", { count: cells.reduce((n, c) => n + c.variant_count, 0), cells: cells.length })}
                  columns={[t("dashboard.chart.col.group"), t("dashboard.chart.col.variants"), t("dashboard.chart.col.value")]}
                  rows={cells.map((c) => [`${c.abc}${c.xyz}`, c.variant_count, c.value === undefined ? "—" : formatCurrencyEUR(c.value)])}
                  rowAction={(i) => {
                    const c = cells[i];
                    const group = c ? `${c.abc}${c.xyz}` : "";
                    return { label: t("dashboard.drill.group_action", { group }), onClick: () => c && openDrill({ kind: "abc_xyz", abc: c.abc, xyz: c.xyz }, t("dashboard.drill.title.abc_xyz", { group })) };
                  }}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={cells.map((c) => ({ group: `${c.abc}${c.xyz}`, count: c.variant_count }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
                      <XAxis dataKey="group" />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Bar dataKey="count" fill={colors.primary} name={t("dashboard.chart.col.variants")} cursor="pointer"
                        onClick={(p: { group?: string }) => p.group && openDrill({ kind: "abc_xyz", abc: p.group.slice(0, 1), xyz: p.group.slice(1) }, t("dashboard.drill.title.abc_xyz", { group: p.group }))} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartWithTable>
              )
            ) : (
              <Unavailable />
            )}
          </Card>

          <Card as="div">
            <h3>{t("dashboard.risks")}</h3>
            {!data.risks.ok ? (
              <Unavailable />
            ) : risks.length === 0 ? (
              <p>✓ {t("dashboard.no_risks")}</p>
            ) : (
              <DataTable ariaLabel={t("a11y.risk_table")} columns={riskColumns} rows={shownRisks} rowKey={(r) => `${r.variant_id}-${r.risk_type}-${r.explanation_key}`} rowTone={riskTone} />
            )}
          </Card>
        </>
      )}
      {drill !== null && (
        <DrillDownPanel request={drill.request} title={drill.title} onClose={() => setDrill(null)} onOpenProduct={(id) => setDetail(id)} />
      )}
      {supplierOpen !== null && (
        <SupplierPanel
          supplierId={supplierOpen}
          name={(data?.suppliers.ok ? data.suppliers.data?.find((x) => x.id === supplierOpen)?.name : undefined) ?? supplierOpen}
          spend={(data?.spend.ok ? data.spend.data?.by_supplier.find((b) => b.supplier_id === supplierOpen)?.total : undefined) ?? null}
          onClose={() => setSupplierOpen(null)}
        />
      )}
      {detail !== null && <ProductDetail variantId={detail} onClose={() => setDetail(null)} />}
    </section>
  );
};
