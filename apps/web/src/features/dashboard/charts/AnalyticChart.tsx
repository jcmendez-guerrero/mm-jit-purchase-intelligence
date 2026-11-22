import React from "react";
import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ChartSeries } from "../../../api/client";
import { formatCurrencyEUR, formatDate, formatNumber } from "../../../i18n/formatters";
import { Card } from "../../../ui/Card";
import { ScreenState } from "../../../ui/ScreenState";
import { useChartColors } from "../../../ui/useChartColors";
import { ChartWithTable } from "../ChartWithTable";

type Cell = string | number | null;
const LINE_CHARTS: ReadonlyArray<ChartSeries["key"]> = ["stock_value_history", "demand_forecast"];
const BAND_DRILL = "expiry_bands";

interface Props {
  chart: ChartSeries;
  onRetry: () => void;
  /** Opens the products of one expiry band (a table row or a bar). */
  onDrillBand?: ((band: "expired" | "d0_30" | "d31_60") => void) | undefined;
}

/** One analytical chart with its table (FR-010): the same rows feed both. A chart without data says why, and a failed chart offers a retry; neither draws an empty picture. */
export const AnalyticChart: React.FC<Props> = ({ chart, onRetry, onDrillBand }) => {
  const { t } = useTranslation();
  const colors = useChartColors();
  const title = t(`dashboard.chart.title.${chart.key}`);              // the catalogue owns the text; the server's title_key is only a hint

  if (chart.state === "error") {
    return (
      <Card as="div">
        <h3>{title}</h3>
        <ScreenState state="error" errorHint={t("dashboard.chart.error")} onRetry={onRetry} />
      </Card>
    );
  }
  if (chart.state === "no_data") {
    const reason = String(chart.summary_params?.reason ?? "");
    const range = chart.range_available;
    return (
      <Card as="div">
        <h3>{title}</h3>
        <p role="status">
          {t(`dashboard.chart.no_data.${reason}`, {
            defaultValue: t("dashboard.chart.no_data.default"),
            from: range?.from ? formatDate(`${range.from}T12:00:00`) : "",
            to: range?.to ? formatDate(`${range.to}T12:00:00`) : "",
          })}
        </p>
      </Card>
    );
  }

  const valueAt = chart.columns.indexOf("value");
  const measureAt = valueAt >= 0 ? valueAt : 1;
  const label = (col: string, v: Cell): string => {
    if (v === null) return "—";
    if (col === "day") return formatDate(`${v}T12:00:00`);
    if (col === "value") return formatCurrencyEUR(String(v));
    if (typeof v === "number") return formatNumber(v);
    return t(`dashboard.chart.cell.${col}.${v}`, { defaultValue: String(v) });
  };
  const points = chart.rows.map((r) => ({ name: label(chart.columns[0] ?? "", r[0] ?? null), amount: Number(r[measureAt] ?? 0), band: String(r[0] ?? "") }));
  const best = points.reduce((a, p) => (p.amount > a.amount ? p : a), points[0]!);
  const isBand = chart.key === BAND_DRILL && onDrillBand !== undefined;
  const asBand = (v: string) => (v === "expired" || v === "d0_30" || v === "d31_60" ? v : undefined);
  const range = chart.range_available;

  return (
    <Card as="div">
      <ChartWithTable
        title={title}
        summary={t("dashboard.chart.generic_summary", { count: points.length, max: best ? formatNumber(best.amount, valueAt >= 0 ? 2 : 0) : "", label: best?.name ?? "" })}
        columns={chart.columns.map((c) => t(`dashboard.chart.col.${c}`, { defaultValue: c }))}
        rows={chart.rows.map((r) => r.map((v, i) => label(chart.columns[i] ?? "", v ?? null)))}
        rowAction={isBand ? (i) => {
          const band = asBand(String(chart.rows[i]?.[0] ?? ""));
          return { label: band ? t("dashboard.drill.band_action", { band: label("band", band) }) : "", onClick: () => band && onDrillBand?.(band) };
        } : undefined}
      >
        <ResponsiveContainer width="100%" height="100%">
          {LINE_CHARTS.includes(chart.key) ? (
            <LineChart data={points}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Line dataKey="amount" stroke={colors.primary} strokeWidth={2} dot={false} name={t(`dashboard.chart.col.${chart.columns[measureAt]}`, { defaultValue: "" })} />
            </LineChart>
          ) : (
            <BarChart data={points}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
              <XAxis dataKey="name" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="amount" fill={colors.primary} cursor={isBand ? "pointer" : undefined} name={t(`dashboard.chart.col.${chart.columns[measureAt]}`, { defaultValue: "" })}
                onClick={(p: { band?: string }) => { const b = p.band && asBand(p.band); if (isBand && b) onDrillBand?.(b); }} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </ChartWithTable>
      {range?.from && range.to && <p className="mmi-muted">{t("dashboard.chart.history_range", { from: formatDate(`${range.from}T12:00:00`), to: formatDate(`${range.to}T12:00:00`) })}</p>}
    </Card>
  );
};
