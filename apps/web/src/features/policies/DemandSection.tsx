import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, CensoringRule, CriticalProduct, DemandExclusion, errorMessage } from "../../api/client";
import { formatDate } from "../../i18n/formatters";
import { Field } from "../suppliers/Field";
import { canEditPolicies, parseId } from "./policiesModel";

interface Props {
  roles: string[];
  exclusions: DemandExclusion[];
  rules: CensoringRule[];
  onChanged: () => void;
}

export const DemandSection: React.FC<Props> = ({ roles, exclusions, rules, onChanged }) => {
  const { t } = useTranslation();
  const [variantText, setVariantText] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");
  const [ruleValue, setRuleValue] = useState<Record<string, string>>({});
  const [products, setProducts] = useState<CriticalProduct[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const canEdit = canEditPolicies(roles);

  const run = async (action: () => Promise<unknown>, done: string, reload = true) => {
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(done);
      if (reload) onChanged();
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  };

  const add = () => {
    const text = variantText.trim();
    const variant = text === "" ? null : parseId(text);
    if (text !== "" && variant === null) return setError(t("policies.variant_invalid"));
    return run(() => api.addExclusion({ variant_id: variant, from_day: from, to_day: to, reason }), t("demand.added"));
  };

  const loadProducts = async () => {
    try {
      setProducts((await api.getCriticality()).products);
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  };

  const toggleCritical = async (p: CriticalProduct) => {
    await run(() => api.setCriticality(p.product_id, !p.clinical_critical), t("demand.critical_changed"), false);
    await loadProducts();
  };

  return (
    <div>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}

      <h3>{t("demand.exclusions")}</h3>
      {exclusions.length === 0 ? (
        <p>{t("demand.exclusions_empty")}</p>
      ) : (
        <ul>
          {exclusions.map((x) => (
            <li key={x.id}>
              {t("demand.row", {
                from: formatDate(x.from_day), to: formatDate(x.to_day), reason: x.reason,
                scope: x.variant_id === null ? t("demand.all_products") : t("demand.variant_n", { n: x.variant_id }),
              })}
              {!x.active && ` (${t("demand.inactive")})`}
              {canEdit && (
                <>
                  {" "}
                  <button type="button" className="mmi-btn mmi-btn-sm mmi-btn-secondary" onClick={() => void run(() => api.toggleExclusion(x.id, !x.active), t("demand.added"))}>
                    {x.active ? t("demand.deactivate") : t("demand.reactivate")}
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "end" }}>
          <Field id="ex-variant" label={t("demand.variant_optional")} value={variantText} onChange={setVariantText} inputMode="numeric" />
          <Field id="ex-from" label={t("demand.from")} value={from} onChange={setFrom} type="date" />
          <Field id="ex-to" label={t("demand.to")} value={to} onChange={setTo} type="date" />
          <Field id="ex-reason" label={t("demand.reason")} value={reason} onChange={setReason} />
          <button type="button" className="mmi-btn mmi-btn-primary" onClick={() => void add()}>
            {t("demand.add")}
          </button>
        </div>
      )}

      <h3>{t("demand.rules")}</h3>
      {rules.map((r) => (
        <div key={r.rule} style={{ display: "flex", gap: "0.75rem", alignItems: "end" }}>
          <Field id={`rule-${r.rule}`} label={t(`demand.rule.${r.rule}`)} value={ruleValue[r.rule] ?? String(r.value)} disabled={!canEdit} inputMode="numeric"
                 hint={t("forecast.range", { min: r.min, max: r.max, default: r.default })} onChange={(v) => setRuleValue({ ...ruleValue, [r.rule]: v })} />
          {canEdit && (
            <button type="button" className="mmi-btn mmi-btn-primary" onClick={() => void run(() => api.putCensoringRule(r.rule, Number(ruleValue[r.rule] ?? r.value)), t("demand.rule_saved"))}>
              {t("demand.rule_save")}
            </button>
          )}
        </div>
      ))}

      <h3>{t("demand.criticality")}</h3>
      <p className="mmi-muted">{t("demand.criticality_help")}</p>
      {products === null ? (
        <button type="button" className="mmi-btn mmi-btn-secondary" onClick={() => void loadProducts()}>
          {t("policies.load")}
        </button>
      ) : (
        <ul>
          {products.map((p) => (
            <li key={p.product_id}>
              <label>
                <input type="checkbox" checked={p.clinical_critical} disabled={!canEdit} onChange={() => void toggleCritical(p)} /> {t("demand.critical_toggle", { name: p.name })}
              </label>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
