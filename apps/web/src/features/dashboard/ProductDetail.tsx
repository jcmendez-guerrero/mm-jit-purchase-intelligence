import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, ForecastBasis, SegmentHistoryRow, VariantDetail } from "../../api/client";
import { formatDate, formatNumber } from "../../i18n/formatters";
import { CategoryHistory } from "../policies/CategoryHistory";
import { ScreenState } from "../../ui/ScreenState";
import { StatusBadge } from "../../ui/StatusBadge";
import { Card } from "../../ui/Card";
import { Button } from "../../ui/Button";
import { DataTable } from "../../ui/DataTable";

interface Props {
  variantId: number;
  onClose: () => void;
}

/** Drill-down for one variant: stock, category, recent real demand, why a forecast is or is not used, and the data it rests on (FR-007). */
export const ProductDetail: React.FC<Props> = ({ variantId, onClose }) => {
  const { t } = useTranslation();
  const [d, setD] = useState<VariantDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [basis, setBasis] = useState<ForecastBasis | null>(null);
  const [history, setHistory] = useState<SegmentHistoryRow[] | null>(null);
  const estimateBased = basis?.seed_used === true;

  useEffect(() => {
    let live = true;
    api
      .getVariant(variantId)
      .then((v) => live && setD(v))
      .catch((err) => live && setError(errorMessage(err, t("common.error"))));
    return () => {
      live = false;
    };
  }, [variantId, t]);

  useEffect(() => {
    let live = true;
    setHistory(null);
    api
      .getSegmentHistory(variantId)
      .then((h) => live && setHistory(h.history))
      .catch(() => live && setHistory([]));                      // the history is context: if it cannot be read the detail still opens
    return () => {
      live = false;
    };
  }, [variantId]);

  useEffect(() => {
    let live = true;
    setBasis(null);
    api
      .getForecastBasis(variantId)
      .then((b) => live && setBasis(b))
      .catch(() => undefined);                                  // no run yet, or no forecast for this product: nothing to label
    return () => {
      live = false;
    };
  }, [variantId]);

  return (
    <Card as="aside" aria-label={t("dashboard.detail.title", { id: variantId })}>
      <h3>
        {t("dashboard.detail.title", { id: variantId })}
        {d ? ` · ${d.variant.sku} · ${d.variant.name}` : ""}
      </h3>
      <Button variant="secondary" small onClick={onClose}>
        {t("dashboard.detail.close")}
      </Button>
      {error && <ScreenState state="error" errorHint={error} />}
      {!d && !error && <ScreenState state="loading" skeletonLines={4} />}
      {d && (
        <>
          {d.stock && <p>{t("dashboard.detail.stock", { on_hand: d.stock.on_hand, available: d.stock.available, reserved: d.stock.reserved })}</p>}
          {d.segment && (
            <>
              <p>{t("dashboard.detail.segment", { abc: d.segment.abc, xyz: d.segment.xyz, pattern: d.segment.pattern })}</p>
              <p>{d.segment.forecast_eligible ? t("dashboard.detail.eligible") : t("dashboard.detail.not_eligible", { reasons: d.segment.reasons.join(", ") })}</p>
              {estimateBased && <p role="note"><StatusBadge domain="tag" code="estimate" label={t("dashboard.detail.estimate_based")} /></p>}
            </>
          )}
          <h4>{t("dashboard.detail.category_history")}</h4>
          <CategoryHistory history={history} />
          <h4>{t("dashboard.detail.forecast")}</h4>
          {basis === null ? (
            <p>{t("dashboard.detail.forecast_none")}</p>
          ) : (basis.horizons ?? []).length === 0 ? (
            <p>{t("dashboard.detail.forecast_minmax")}</p>
          ) : (
            <>
              <p className="mmi-muted">{t("dashboard.detail.forecast_note")}</p>
              <DataTable
                ariaLabel={t("dashboard.detail.forecast")}
                rows={basis.horizons ?? []}
                rowKey={(h) => h.days}
                hideToolbar
                columns={[
                  { id: "horizon", header: t("dashboard.detail.forecast_col.horizon"), cell: (h) => h.days, sortValue: (h) => h.days, align: "end" },
                  { id: "mean", header: t("dashboard.detail.forecast_col.mean"), cell: (h) => formatNumber(h.mean, 1), sortValue: (h) => h.mean, align: "end" },
                  { id: "upper", header: t("dashboard.detail.forecast_col.upper"), cell: (h) => formatNumber(h.upper, 1), sortValue: (h) => h.upper, align: "end" },
                ]}
              />
            </>
          )}
          <h4>{t("dashboard.detail.risks")}</h4>
          {(d.risks ?? []).length === 0 ? (
            <p>{t("dashboard.detail.no_risks")}</p>
          ) : (
            <ul>
              {(d.risks ?? []).map((r, i) => (
                <li key={`${r.risk_type}-${i}`}>
                  <strong>{t(r.risk_type === "stockout" ? "dashboard.risk_stockout" : r.risk_type === "expiry" ? "dashboard.risk_expiry" : "dashboard.risk_quality")}</strong>: {String(t(r.explanation_key, r.params))}
                </li>
              ))}
            </ul>
          )}
          <h4>{t("dashboard.detail.demand")}</h4>
          {d.demand.length === 0 ? (
            <p>{t("dashboard.detail.no_demand")}</p>
          ) : (
            <DataTable
              ariaLabel={t("dashboard.detail.demand")}
              rows={d.demand.slice(-30)}
              rowKey={(r) => `${r.day}-${r.warehouse_id}`}
              columns={[
                { id: "day", header: t("dashboard.chart.col.day"), cell: (r) => formatDate(r.day), sortValue: (r) => r.day },
                { id: "units", header: t("dashboard.chart.col.units"), cell: (r) => r.qty, sortValue: (r) => r.qty, align: "end" },
                { id: "censored", header: "", cell: (r) => (r.censored ? t("dashboard.detail.censored") : "") },
              ]}
            />
          )}
          <p className="mmi-muted">{t("dashboard.detail.data_used", { reconciled: d.history_reconciled === false ? t("dashboard.detail.unreconciled") : "" })}</p>
        </>
      )}
    </Card>
  );
};
