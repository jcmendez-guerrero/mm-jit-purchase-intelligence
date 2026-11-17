import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ChartSeries, DashFilters, errorMessage } from "../../../api/client";
import { ScreenState } from "../../../ui/ScreenState";
import { ExportButton } from "../ExportButton";
import { AnalyticChart } from "./AnalyticChart";

/** The analytical charts besides the demand trend and the ABC/XYZ groups, which the screen already draws from the overview. */
export const SECTION_KEYS: ChartSeries["key"][] = ["expiry_bands", "coverage_buckets", "capital_by_group", "stock_value_history"];

interface Props {
  filters: DashFilters;
  onDrillBand: (band: "expired" | "d0_30" | "d31_60") => void;
  /** Offer "Exportar" under each chart (roles that may see costs). */
  canExport?: boolean | undefined;
}

/** Loads the chart tables for the dashboard filters on their own, so a slow or failing chart never holds back the cards. */
export const ChartsSection: React.FC<Props> = ({ filters, onDrillBand, canExport }) => {
  const { t } = useTranslation();
  const [charts, setCharts] = useState<ChartSeries[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const key = JSON.stringify(filters);

  const load = useCallback(() => {
    let live = true;
    setCharts(null);
    setError(null);
    api
      .getDashboardCharts(JSON.parse(key) as DashFilters, SECTION_KEYS)
      .then((r) => live && setCharts(r.charts))
      .catch((err) => live && setError(errorMessage(err, t("dashboard.chart.error"))));
    return () => {
      live = false;
    };
  }, [key, t]);

  useEffect(load, [load]);

  if (error) return <ScreenState state="error" errorHint={error} onRetry={() => void load()} />;
  if (!charts) return <ScreenState state="loading" skeletonShape="dashboard" skeletonLines={4} />;
  return (
    <>
      {charts.map((c) => (
        <React.Fragment key={c.key}>
          <AnalyticChart chart={c} onRetry={() => void load()} onDrillBand={onDrillBand} />
          {canExport && c.state === "ok" && (
            <ExportButton view={{ kind: "chart", chart: c.key }} filters={filters} label={t("dashboard.export.action")} ariaLabel={t("dashboard.export.chart", { title: t(`dashboard.chart.title.${c.key}`) })} />
          )}
        </React.Fragment>
      ))}
    </>
  );
};
