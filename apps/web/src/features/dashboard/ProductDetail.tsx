import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, ForecastBasis, SegmentHistoryRow, VariantDetail } from "../../api/client";
import { formatDate, formatNumber } from "../../i18n/formatters";
import { CategoryHistory } from "../policies/CategoryHistory";

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
    <aside className="mmi-card" aria-label={t("dashboard.detail.title", { id: variantId })}>
      <h3>
        {t("dashboard.detail.title", { id: variantId })}
        {d ? ` · ${d.variant.sku} · ${d.variant.name}` : ""}
      </h3>
      <button type="button" className="mmi-btn mmi-btn-sm mmi-btn-secondary" onClick={onClose}>
        {t("dashboard.detail.close")}
      </button>
      {error && <p role="alert">{error}</p>}
      {!d && !error && <p>{t("common.loading")}</p>}
      {d && (
        <>
          {d.stock && <p>{t("dashboard.detail.stock", { on_hand: d.stock.on_hand, available: d.stock.available, reserved: d.stock.reserved })}</p>}
          {d.segment && (
            <>
              <p>{t("dashboard.detail.segment", { abc: d.segment.abc, xyz: d.segment.xyz, pattern: d.segment.pattern })}</p>
              <p>{d.segment.forecast_eligible ? t("dashboard.detail.eligible") : t("dashboard.detail.not_eligible", { reasons: d.segment.reasons.join(", ") })}</p>
              {estimateBased && <p role="note" className="mmi-badge mmi-badge-warning">{t("dashboard.detail.estimate_based")}</p>}
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
              <table aria-label={t("dashboard.detail.forecast")} className="mmi-table">
                <thead>
                  <tr>
                    <th>{t("dashboard.detail.forecast_col.horizon")}</th>
                    <th>{t("dashboard.detail.forecast_col.mean")}</th>
                    <th>{t("dashboard.detail.forecast_col.upper")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(basis.horizons ?? []).map((h) => (
                    <tr key={h.days}>
                      <td>{h.days}</td>
                      <td>{formatNumber(h.mean, 1)}</td>
                      <td>{formatNumber(h.upper, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
            <table aria-label={t("dashboard.detail.demand")} className="mmi-table">
              <thead>
                <tr>
                  <th>{t("dashboard.chart.col.day")}</th>
                  <th>{t("dashboard.chart.col.units")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {d.demand.slice(-30).map((r) => (
                  <tr key={`${r.day}-${r.warehouse_id}`}>
                    <td>{formatDate(r.day)}</td>
                    <td>{r.qty}</td>
                    <td>{r.censored ? t("dashboard.detail.censored") : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="mmi-muted">{t("dashboard.detail.data_used", { reconciled: d.history_reconciled === false ? t("dashboard.detail.unreconciled") : "" })}</p>
        </>
      )}
    </aside>
  );
};
