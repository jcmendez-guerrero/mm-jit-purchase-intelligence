import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, CENSORING_SEGMENTS, CensoringRule, CriticalProduct, DemandExclusion, errorMessage, EXCLUSION_REASONS } from "../../api/client";
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
  const [scopedScope, setScopedScope] = useState<"segment" | "product">("segment");
  const [scopedKey, setScopedKey] = useState("");
  const [scopedValue, setScopedValue] = useState("");
  const scopeLabel = (r: CensoringRule) => (r.scope === "segment" ? t(`demand.segment.${r.key ?? ""}`, { defaultValue: r.key ?? "" }) : t("demand.sku_n", { sku: r.key ?? t("policies.orphaned_unknown") }));
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

  const ruleId = (r: CensoringRule) => `rule-${r.rule}-${r.scope}-${r.key ?? ""}`;

  const saveRule = (rule: CensoringRule, text: string) => {
    if (!/^\d+$/.test(text.trim())) {
      const message = t("policies.invalid_field", { field: t(`demand.rule.${rule.rule}`) });
      fe.flag({ [ruleId(rule)]: message });
      return setError(message);
    }
    fe.clear();
    const target = rule.scope === "global" || rule.key === null ? undefined : { scope: rule.scope, key: rule.key };
    const value = Number(text.trim() === "" ? rule.value : text);
    return run(() => (target ? api.putCensoringRule(rule.rule, value, rule.revision, target) : api.putCensoringRule(rule.rule, value, rule.revision)), t("demand.rule_saved"));
  };

  /** A rule for one segment or one product (by SKU); its own revision starts at 0 unless one is already listed. */
  const addScopedRule = (base: CensoringRule) => {
    const key = scopedKey.trim();
    if (key === "" || !/^\d+$/.test(scopedValue.trim())) {
      const message = key === "" ? t("demand.rule_key_required") : t("policies.invalid_field", { field: t(`demand.rule.${base.rule}`) });
      fe.flag({ "scoped-rule": message });
      return setError(message);
    }
    fe.clear();
    const existing = rules.find((r) => r.rule === base.rule && r.scope === scopedScope && r.key?.toLowerCase() === key.toLowerCase());
    return run(() => api.putCensoringRule(base.rule, Number(scopedValue.trim()), existing?.revision ?? 0, { scope: scopedScope, key }), t("demand.rule_saved"));
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

  const dirty = canEdit && (skuText.trim() !== "" || from !== "" || to !== "" || reasonCode !== "" || detail.trim() !== "" || scopedKey.trim() !== "" || scopedValue.trim() !== "" || rules.some((r) => ruleValue[ruleId(r)] !== undefined && ruleValue[ruleId(r)]!.trim() !== String(r.value)));

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
        <div className="mmi-cluster" key={ruleId(r)}>
          <FormField id={ruleId(r)} label={r.scope === "global" ? t(`demand.rule.${r.rule}`) : t("demand.rule_scoped_label", { rule: t(`demand.rule.${r.rule}`), scope: scopeLabel(r) })}
                 value={ruleValue[ruleId(r)] ?? String(r.value)} disabled={!canEdit} inputMode="numeric"
                 hint={t("forecast.range", { min: r.min, max: r.max, default: r.default })} error={fe.errors[ruleId(r)]} onChange={(v) => { setRuleValue({ ...ruleValue, [ruleId(r)]: v }); fe.clear(ruleId(r)); }} />
          {canEdit && (
            <Button onClick={() => void saveRule(r, String(ruleValue[ruleId(r)] ?? r.value))}>
              {t("demand.rule_save")}
            </Button>
          )}
        </div>
      ))}
      {canEdit && rules.length > 0 && (
        <div className="mmi-cluster" role="group" aria-label={t("demand.rule_scoped_title")}>
          <div className="mmi-stack">
            <label htmlFor="scoped-scope">{t("demand.rule_scope")}</label>
            <select id="scoped-scope" value={scopedScope} onChange={(e) => { setScopedScope(e.target.value as "segment" | "product"); setScopedKey(""); }}>
              <option value="segment">{t("demand.rule_scope.segment")}</option>
              <option value="product">{t("demand.rule_scope.product")}</option>
            </select>
          </div>
          {scopedScope === "segment" ? (
            <div className="mmi-stack">
              <label htmlFor="scoped-key">{t("demand.rule_key_segment")}</label>
              <select id="scoped-key" value={scopedKey} onChange={(e) => { setScopedKey(e.target.value); fe.clear("scoped-rule"); }}>
                <option value="">{t("demand.rule_key_choose")}</option>
                {CENSORING_SEGMENTS.map((s) => (
                  <option key={s} value={s}>
                    {t(`demand.segment.${s}`)}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <FormField id="scoped-key" label={t("demand.rule_key_sku")} value={scopedKey} onChange={(v) => { setScopedKey(v); fe.clear("scoped-rule"); }} />
          )}
          <FormField id="scoped-value" label={t("demand.rule_value")} value={scopedValue} onChange={(v) => { setScopedValue(v); fe.clear("scoped-rule"); }} inputMode="numeric" error={fe.errors["scoped-rule"]} />
          <Button onClick={() => void addScopedRule(rules[0]!)}>{t("demand.rule_scoped_save")}</Button>
        </div>
      )}

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
