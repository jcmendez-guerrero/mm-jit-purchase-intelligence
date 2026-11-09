import React from "react";
import { useTranslation } from "react-i18next";
import type { ProposalLine } from "../../api/client";
import { formatCurrencyEUR, formatDate, formatNumber } from "../../i18n/formatters";

/** Structured, Spanish-rendered reasoning for one line: quantity, supplier choice, saved terms and ERP conflicts. */
export const ProposalLineExplanation: React.FC<{ line: ProposalLine }> = ({ line }) => {
  const { t } = useTranslation();
  const e = line.explanation;
  const terms = e.terms;
  const known = (prefix: string, key: string) => (t(`${prefix}.${key}`, { defaultValue: "" }) as string) || key;
  const none = t("proposals.why.terms_none");
  return (
    <div className="mmi-explanation" aria-label={t("proposals.why.title")}>
      <h4>{t("proposals.why.title")}</h4>
      <p>
        {t("proposals.why.demand", {
          days: e.horizon_days, demand: formatNumber(e.expected_demand, 1), safety: formatNumber(e.safety_stock, 0), level: formatNumber(Number(e.service_level), 1),
        })}
      </p>
      <p>
        {t("proposals.why.position", { total: e.position.total, on_hand: e.position.on_hand, expiring: e.position.expiring, inbound: e.position.inbound, need: e.need })}
      </p>
      {!e.forecast_eligible && <p>{t("proposals.why.fallback")}</p>}
      {e.forecast_basis === "imported_estimates" && <p role="note">{t("proposals.why.estimate")}</p>}
      {e.clinical_critical && <p>{t("proposals.why.critical")}</p>}
      <p>{t("proposals.why.supplier", { reason: known("proposals.why.supplier_reason", e.supplier.reason) })}</p>
      {terms && (
        <>
          <p>{t("proposals.why.terms", { supplier: terms.supplier_version ?? none, override: terms.override_version ?? none })}</p>
          {terms.fx && (
            <p>{t("proposals.why.fx", { original: formatNumber(Number(terms.fx.original_cost), 2), currency: terms.fx.currency, rate: terms.fx.eur_per_unit.replace(".", ","),
              date: formatDate(new Date(`${terms.fx.published_on}T12:00:00`)) })}</p>
          )}
          {terms.expected_delivery_date &&<p>{t("proposals.why.delivery", { date: formatDate(new Date(`${terms.expected_delivery_date}T12:00:00`)) })}</p>}
          <ul>
            {Object.entries(terms.sources).map(([field, source]) => (
              <li key={field}>{t("proposals.why.source", { field: t(`suppliers.f.${field}`, { defaultValue: field }), source: known("proposals.why.source_value", source) })}</li>
            ))}
            {terms.conflicts.map((c) => (
              <li key={c.field} role="note">
                {t("proposals.why.conflict", {
                  field: t(`suppliers.f.${c.field}`, { defaultValue: c.field }), erp: String(c.erp_value), local: String(c.local_value),
                  winner: known("proposals.why.conflict_winner", c.winner),
                })}
              </li>
            ))}
          </ul>
          {Number(terms.supplier_discount) > 0 && <p>{t("proposals.why.discount", { amount: formatCurrencyEUR(terms.supplier_discount) })}</p>}
        </>
      )}
      {e.constraints.length > 0 && (
        <ul>
          {e.constraints.map((c) => (
            <li key={c}>{known("proposals.why.constraint", c)}</li>
          ))}
        </ul>
      )}
      {e.supplier.alternatives.length > 1 && (
        <div className="mmi-table-wrapper"><table aria-label={t("proposals.why.alternatives")} className="mmi-table">
          <caption>{t("proposals.why.alternatives")}</caption>
          <thead>
            <tr>
              <th>{t("common.supplier")}</th>
              <th>{t("common.cost")}</th>
              <th>{t("common.quantity")}</th>
              <th>{t("common.total")}</th>
              <th>{t("common.lead_time_days")}</th>
            </tr>
          </thead>
          <tbody>
            {e.supplier.alternatives.map((a) => (
              <tr key={a.supplier_id} aria-current={a.chosen ? "true" : undefined}>
                <td>{a.supplier_id}</td>
                <td>{formatCurrencyEUR(a.unit_cost)}</td>
                <td>{a.qty}</td>
                <td>{formatCurrencyEUR(a.line_total)}</td>
                <td>{a.lead_time_days}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
    </div>
  );
};
