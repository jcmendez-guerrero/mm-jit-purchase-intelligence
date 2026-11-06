import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, VariantDetail } from "../../api/client";
import { formatDate } from "../../i18n/formatters";

interface Props {
  variantId: number;
  onClose: () => void;
}

/** Drill-down for one variant: stock, category, recent real demand, why a forecast is or is not used, and the data it rests on (FR-007). */
export const ProductDetail: React.FC<Props> = ({ variantId, onClose }) => {
  const { t } = useTranslation();
  const [d, setD] = useState<VariantDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

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
            </>
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
