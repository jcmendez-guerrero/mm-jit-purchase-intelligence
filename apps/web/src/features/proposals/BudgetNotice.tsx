import React from "react";
import { useTranslation } from "react-i18next";
import type { ProposalFlags } from "../../api/client";
import { formatCurrencyEUR } from "../../i18n/formatters";

const BOUND = "budget_bound:";

/**
 * What a binding budget did to this proposal: which cap bound, which needed lines were left out and why, and, when a critical product
 * pushes the total over the cap, that a person must decide on the excess. Shown only when a cap changed something.
 */
export const BudgetNotice: React.FC<{ flags: ProposalFlags | null | undefined }> = ({ flags }) => {
  const { t } = useTranslation();
  const deferred = flags?.deferred ?? [];
  const over = Number(flags?.over_budget ?? "0");
  const bound = (flags?.notes ?? []).filter((n) => n.startsWith(BOUND)).map((n) => n.slice(BOUND.length));
  const criticalExcess = (flags?.notes ?? []).includes("critical_over_budget");
  if (deferred.length === 0 && over <= 0 && bound.length === 0) return null;

  const capName = (c: { kind: string; supplier_name?: string | null }) =>
    c.kind === "supplier" ? t("proposals.budget.cap.supplier", { name: c.supplier_name ?? "—" }) : t(`proposals.budget.cap.${c.kind}`, { defaultValue: c.kind });
  const boundName = (b: string) => (b.startsWith("supplier:") ? t("proposals.budget.cap.supplier", { name: b.slice("supplier:".length) || "—" }) : t(`proposals.budget.cap.${b}`, { defaultValue: b }));

  return (
    <section aria-label={t("proposals.budget.title")} className="mmi-muted">
      <h4>{t("proposals.budget.title")}</h4>
      {bound.length > 0 && <p>{t("proposals.budget.bound", { caps: bound.map(boundName).join(", ") })}</p>}
      {deferred.length > 0 && (
        <>
          <p>{t("proposals.budget.deferred_intro", { count: deferred.length })}</p>
          <ul>
            {deferred.map((d, i) => (
              <li key={d.sku ?? i}>
                {t("proposals.budget.deferred_row", {
                  sku: d.sku ?? "—", name: d.product_name ?? "—", qty: d.needed_qty ?? "—", cost: d.estimated_cost === null ? "—" : formatCurrencyEUR(d.estimated_cost),
                  caps: d.bound_by.map(capName).join(", "),
                })}
              </li>
            ))}
          </ul>
        </>
      )}
      {over > 0 && <p role="status">{t("proposals.budget.over", { amount: formatCurrencyEUR(over) })}</p>}
      {criticalExcess && <p role="alert">{t("proposals.budget.critical_excess")}</p>}
    </section>
  );
};
