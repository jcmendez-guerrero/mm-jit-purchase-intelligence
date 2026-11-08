import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, CensoringRule, CriticalProduct, DemandExclusion, errorMessage } from "../../api/client";
import { formatDate } from "../../i18n/formatters";
import { FormField } from "../../ui/FormField";
import { canEditPolicies, parseId } from "./policiesModel";
import { useActionNotice } from "../../ui/NoticeProvider";
import { Button } from "../../ui/Button";
import { useFieldErrors } from "../../ui/useFieldErrors";
import { UnsavedChangesPrompt } from "../../ui/UnsavedChangesPrompt";

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
  const [notice, setNotice] = useActionNotice();
  const canEdit = canEditPolicies(roles);
  const fe = useFieldErrors();

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
    if (text !== "" && variant === null) {
      fe.flag({ "ex-variant": t("policies.variant_invalid") });
      return setError(t("policies.variant_invalid"));
    }
    fe.clear();
    return run(() => api.addExclusion({ variant_id: variant, from_day: from, to_day: to, reason }), t("demand.added"));
  };

  const saveRule = (rule: string, text: string, fallback: number) => {
    if (!/^\d+$/.test(text.trim())) {
      const message = t("policies.invalid_field", { field: t(`demand.rule.${rule}`) });
      fe.flag({ [`rule-${rule}`]: message });
      return setError(message);
    }
    fe.clear();
    return run(() => api.putCensoringRule(rule, Number(text.trim() === "" ? fallback : text)), t("demand.rule_saved"));
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

  const dirty = canEdit && (variantText.trim() !== "" || from !== "" || to !== "" || reason.trim() !== "" || rules.some((r) => ruleValue[r.rule] !== undefined && ruleValue[r.rule]!.trim() !== String(r.value)));

  return (
    <div>
      <UnsavedChangesPrompt dirty={dirty} />
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
                  <Button variant="secondary" small onClick={() => void run(() => api.toggleExclusion(x.id, !x.active), t("demand.added"))}>
                    {x.active ? t("demand.deactivate") : t("demand.reactivate")}
                  </Button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        <div className="mmi-cluster">
          <FormField id="ex-variant" label={t("demand.variant_optional")} value={variantText} onChange={(v) => { setVariantText(v); fe.clear("ex-variant"); }} error={fe.errors["ex-variant"]} inputMode="numeric" />
          <FormField id="ex-from" label={t("demand.from")} value={from} onChange={setFrom} type="date" />
          <FormField id="ex-to" label={t("demand.to")} value={to} onChange={setTo} type="date" />
          <FormField id="ex-reason" label={t("demand.reason")} value={reason} onChange={setReason} />
          <Button onClick={() => void add()}>
            {t("demand.add")}
          </Button>
        </div>
      )}

      <h3>{t("demand.rules")}</h3>
      {rules.map((r) => (
        <div className="mmi-cluster" key={r.rule}>
          <FormField id={`rule-${r.rule}`} label={t(`demand.rule.${r.rule}`)} value={ruleValue[r.rule] ?? String(r.value)} disabled={!canEdit} inputMode="numeric"
                 hint={t("forecast.range", { min: r.min, max: r.max, default: r.default })} error={fe.errors[`rule-${r.rule}`]} onChange={(v) => { setRuleValue({ ...ruleValue, [r.rule]: v }); fe.clear(`rule-${r.rule}`); }} />
          {canEdit && (
            <Button onClick={() => void saveRule(r.rule, String(ruleValue[r.rule] ?? r.value), r.value)}>
              {t("demand.rule_save")}
            </Button>
          )}
        </div>
      ))}

      <h3>{t("demand.criticality")}</h3>
      <p className="mmi-muted">{t("demand.criticality_help")}</p>
      {products === null ? (
        <Button variant="secondary" onClick={() => void loadProducts()}>
          {t("policies.load")}
        </Button>
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
