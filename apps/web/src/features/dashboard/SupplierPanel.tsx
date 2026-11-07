import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, SupplierTermsView } from "../../api/client";
import { formatCurrencyEUR } from "../../i18n/formatters";

interface Props {
  supplierId: string;
  name: string;
  spend: string | null;          // this supplier's share of the proposed spend, when a proposal exists
  onClose: () => void;
}

/** Read-only supplier detail from the dashboard (FR-007): the terms in force and the proposed spend. Editing stays in Proveedores. */
export const SupplierPanel: React.FC<Props> = ({ supplierId, name, spend, onClose }) => {
  const { t } = useTranslation();
  const [view, setView] = useState<SupplierTermsView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setView(null);
    setError(null);
    api
      .getSupplierTerms(supplierId)
      .then((v) => live && setView(v))
      .catch((err) => live && setError(errorMessage(err, t("common.error"))));
    return () => {
      live = false;
    };
  }, [supplierId, t]);

  const c = view?.current ?? null;
  const dash = "—";
  return (
    <aside className="mmi-card" aria-label={t("dashboard.supplier.title", { name })}>
      <h3>{t("dashboard.supplier.title", { name })}</h3>
      <button type="button" className="mmi-btn mmi-btn-sm mmi-btn-secondary" onClick={onClose}>
        {t("dashboard.drill.close")}
      </button>
      {error && <p role="alert">{error}</p>}
      {!view && !error && <p>{t("dashboard.loading_state")}</p>}
      {view && !c && <p>{t("dashboard.supplier.no_terms")}</p>}
      {c && (
        <ul>
          <li>{t("dashboard.supplier.lead_time", { value: c.lead_time_days ?? dash })}</li>
          <li>{t("dashboard.supplier.min_order", { value: c.min_order_value === null ? dash : formatCurrencyEUR(c.min_order_value) })}</li>
          <li>{t("dashboard.supplier.delivery_charge", { value: c.delivery_charge === null ? dash : formatCurrencyEUR(c.delivery_charge) })}</li>
          <li>{t("dashboard.supplier.free_delivery", { value: c.free_delivery_threshold === null ? dash : formatCurrencyEUR(c.free_delivery_threshold) })}</li>
          <li>{t("dashboard.supplier.payment", { value: c.payment_terms_days ?? dash })}</li>
          {c.disabled && <li>{t("dashboard.supplier.disabled")}</li>}
        </ul>
      )}
      <p>{spend === null ? t("dashboard.supplier.no_spend") : t("dashboard.supplier.spend", { value: formatCurrencyEUR(spend) })}</p>
    </aside>
  );
};
