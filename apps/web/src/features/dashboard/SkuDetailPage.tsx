import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, DashboardSku, errorMessage } from "../../api/client";
import { formatCurrencyEUR, formatDate, formatNumber } from "../../i18n/formatters";
import { Card } from "../../ui/Card";
import { DataTable } from "../../ui/DataTable";
import { ScreenState } from "../../ui/ScreenState";

/** One product on a page with its own address (/panel/skus/:sku): stock, coverage, demand, forecast, supplier and expiry lots. SKU only; cost appears only when the response carries it. */
export const SkuDetailPage: React.FC = () => {
  const { t } = useTranslation();
  const { sku = "" } = useParams();
  const [d, setD] = useState<DashboardSku | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);

  const load = useCallback(() => {
    setD(null);
    setError(null);
    setMissing(false);
    api
      .getDashboardSku(sku)
      .then(setD)
      .catch((err) => (err instanceof ApiError && err.status === 404 ? setMissing(true) : setError(errorMessage(err, t("common.error")))));
  }, [sku, t]);

  useEffect(load, [load]);

  const back = (
    <Link className="mmi-button mmi-button--secondary mmi-button--small" to="/panel">
      {t("dashboard.sku.back")}
    </Link>
  );

  if (missing) {
    return (
      <section>
        <h2>{t("dashboard.sku.title", { sku })}</h2>
        <p role="status">{t("dashboard.sku.not_found", { sku })}</p>
        {back}
      </section>
    );
  }

  return (
    <section>
      <h2>{t("dashboard.sku.title", { sku })}</h2>
      {back}
      {error && <ScreenState state="error" errorHint={error} onRetry={load} />}
      {!d && !error && <ScreenState state="loading" skeletonLines={4} />}
      {d && (
        <Card as="article" aria-label={t("dashboard.sku.title", { sku: d.sku })}>
          {d.name && <p>{d.name}</p>}
          <p>{d.stock.on_hand === null ? t("dashboard.sku.stock_none") : t("dashboard.sku.stock", { on_hand: formatNumber(d.stock.on_hand) })}</p>
          <p>{d.coverage ? t("dashboard.sku.coverage", { days: formatNumber(d.coverage.days, 1), basis: t(`dashboard.sku.basis.${d.coverage.basis}`) }) : t("dashboard.sku.coverage_none")}</p>
          <p>{t("dashboard.sku.demand", { units: formatNumber(d.demand.units), days: d.demand.days })}</p>
          <p>{d.forecast ? t("dashboard.sku.forecast", { mean: formatNumber(d.forecast.daily_mean, 2), days: d.forecast.days }) : t("dashboard.sku.forecast_none")}</p>
          <p>{d.supplier ? t("dashboard.sku.supplier", { id: d.supplier.id }) : t("dashboard.sku.supplier_none")}</p>
          {d.cost && d.cost.value !== null && (
            <p>{t("dashboard.sku.cost", { value: formatCurrencyEUR(d.cost.value), unit: d.cost.unit_cost === null ? "" : formatCurrencyEUR(d.cost.unit_cost) })}</p>
          )}
          {d.states.length > 0 && (
            <ul>
              {d.states.map((s) => (
                <li key={s}>{t(`dashboard.sku.state.${s}`)}</li>
              ))}
            </ul>
          )}
          <h3>{t("dashboard.sku.lots")}</h3>
          {d.expiry_lots.length === 0 ? (
            <p>{t("dashboard.sku.lots_none")}</p>
          ) : (
            <DataTable
              ariaLabel={t("dashboard.sku.lots")}
              rows={d.expiry_lots}
              rowKey={(l) => l.batch}
              hideToolbar
              columns={[
                { id: "batch", header: t("dashboard.sku.col.batch"), cell: (l) => l.batch, sortValue: (l) => l.batch },
                { id: "quantity", header: t("dashboard.sku.col.quantity"), cell: (l) => formatNumber(l.quantity), sortValue: (l) => l.quantity, align: "end" },
                { id: "expiry", header: t("dashboard.sku.col.expiry"), cell: (l) => (l.expiry_date ? formatDate(l.expiry_date) : ""), sortValue: (l) => l.expiry_date ?? "" },
                { id: "band", header: t("dashboard.sku.col.band"), cell: (l) => t(`dashboard.sku.band.${l.band}`) },
              ]}
            />
          )}
        </Card>
      )}
    </section>
  );
};
