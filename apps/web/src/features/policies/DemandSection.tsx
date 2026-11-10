import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, CensoringRule, CriticalProduct, DemandExclusion, errorMessage, EXCLUSION_REASONS } from "../../api/client";
import { formatDate } from "../../i18n/formatters";
import { FormField } from "../../ui/FormField";
import { canEditPolicies } from "./policiesModel";
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

const MAX_DETAIL = 100;

export const DemandSection: React.FC<Props> = ({ roles, exclusions, rules, onChanged }) => {
  const { t } = useTranslation();
  const [skuText, setSkuText] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reasonCode, setReasonCode] = useState("");
  const [detail, setDetail] = useState("");
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
    if (reasonCode === "") {
      const message = t("demand.reason_required");
      fe.flag({ "ex-reason": message });
      return setError(message);
    }
    if (detail.trim().length > MAX_DETAIL) {
      const message = t("demand.detail_too_long", { max: MAX_DETAIL });
      fe.flag({ "ex-detail": message });
      return setError(message);
    }
    fe.clear();
    const sku = skuText.trim();
    return run(
      () => api.addExclusion({ sku: sku === "" ? null : sku, from_day: from, to_day: to, reason_code: reasonCode, ...(detail.trim() ? { detail: detail.trim() } : {}) }),
      t("demand.added"),
    );
  };

  const saveRule = (rule: CensoringRule, text: string) => {
    if (!/^\d+$/.test(text.trim())) {
      const message = t("policies.invalid_field", { field: t(`demand.rule.${rule.rule}`) });
      fe.flag({ [`rule-${rule.rule}`]: message });
      return setError(message);
    }
    fe.clear();
    return run(() => api.putCensoringRule(rule.rule, Number(text.trim() === "" ? rule.value : text), rule.revision), t("demand.rule_saved"));
  };

  const loadProducts = async () => {
    try {
      setProducts((await api.getCriticality()).products);
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  };

  const toggleCritical = async (p: CriticalProduct) => {
    if (p.sku === null) return;
    await run(() => api.setCriticality(p.sku as string, !p.clinical_critical), t("demand.critical_changed"), false);
    await loadProducts();
  };

  const dirty = canEdit && (skuText.trim() !== "" || from !== "" || to !== "" || reasonCode !== "" || detail.trim() !== "" || rules.some((r) => ruleValue[r.rule] !== undefined && ruleValue[r.rule]!.trim() !== String(r.value)));

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
                from: formatDate(x.from_day), to: formatDate(x.to_day), reason: t(`demand.reason.${x.reason_code}`, { defaultValue: x.reason_code }),
                scope: x.sku === null ? t("demand.all_products") : t("demand.sku_n", { sku: x.sku }),
              })}
              {x.detail ? ` — ${x.detail}` : ""}
              {!x.active && ` (${t("demand.inactive")})`}
              {canEdit && (
                <>
                  {" "}
                  <Button variant="secondary" small onClick={() => void run(() => api.toggleExclusion(x.id, !x.active, x.revision), t("demand.added"))}>
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
          <FormField id="ex-sku" label={t("demand.sku_optional")} value={skuText} onChange={setSkuText} />
          <FormField id="ex-from" label={t("demand.from")} value={from} onChange={setFrom} type="date" />
          <FormField id="ex-to" label={t("demand.to")} value={to} onChange={setTo} type="date" />
          <div className="mmi-stack">
            <label htmlFor="ex-reason">{t("demand.reason")}</label>
            <select id="ex-reason" value={reasonCode} onChange={(e) => { setReasonCode(e.target.value); fe.clear("ex-reason"); }} aria-invalid={fe.errors["ex-reason"] ? true : undefined}>
              <option value="">{t("demand.reason_choose")}</option>
              {EXCLUSION_REASONS.map((c) => (
                <option key={c} value={c}>
                  {t(`demand.reason.${c}`)}
                </option>
              ))}
            </select>
            {fe.errors["ex-reason"] && <span role="alert">{fe.errors["ex-reason"]}</span>}
          </div>
          <FormField id="ex-detail" label={t("demand.detail", { max: MAX_DETAIL })} value={detail} onChange={(v) => { setDetail(v); fe.clear("ex-detail"); }} error={fe.errors["ex-detail"]} />
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
            <Button onClick={() => void saveRule(r, String(ruleValue[r.rule] ?? r.value))}>
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
            <li key={p.sku ?? p.name}>
              <label>
                <input type="checkbox" checked={p.clinical_critical} disabled={!canEdit || p.sku === null} onChange={() => void toggleCritical(p)} /> {t("demand.critical_toggle", { name: p.name, sku: p.sku ?? "—" })}
              </label>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
