import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, EffectivePolicy, errorMessage, PolicyDetail, PolicyPreview, PolicySummary } from "../../api/client";
import { formatCurrencyEUR } from "../../i18n/formatters";
import { FormField } from "../../ui/FormField";
import { canEditPolicies, emptyForm, PolicyForm, scopeKeyValid, Scope, toForm, toPayload } from "./policiesModel";
import { useActionNotice } from "../../ui/NoticeProvider";
import { UnsavedChangesPrompt } from "../../ui/UnsavedChangesPrompt";
import { Button } from "../../ui/Button";
import { useFieldErrors } from "../../ui/useFieldErrors";
import { DataTable } from "../../ui/DataTable";
import { PageActions } from "../../ui/PageActions";

interface Props {
  roles: string[];
  policies: PolicySummary[];
  weeklyBudget: string | null;
  weeklyBudgetRevision?: number | undefined;
  orphaned?: number | undefined;
  onChanged: () => void;
}

const RULES = ["service_level", "safety_stock_units", "min_units", "max_units", "replenishment_cadence_days"] as const;

export const PurchasingSection: React.FC<Props> = ({ roles, policies, weeklyBudget, weeklyBudgetRevision = 0, orphaned = 0, onChanged }) => {
  const { t } = useTranslation();
  const [scope, setScope] = useState<Scope>("global");
  const [key, setKey] = useState("*");
  const [detail, setDetail] = useState<PolicyDetail | null>(null);
  const [form, setForm] = useState<PolicyForm>(emptyForm());
  const [preview, setPreview] = useState<PolicyPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useActionNotice();
  const [conflict, setConflict] = useState<number | null>(null);
  const [budget, setBudget] = useState("");
  const [effective, setEffective] = useState<EffectivePolicy | null>(null);
  const [budgetConflict, setBudgetConflict] = useState<number | null>(null);
  const canEdit = canEditPolicies(roles);
  const fe = useFieldErrors();

  const fail = (err: unknown) => setError(errorMessage(err, t("common.error")));
  const reset = () => {
    setError(null);
    setNotice(null);
    setPreview(null);
  };

  const changeScope = (next: Scope) => {
    setScope(next);
    setKey(next === "global" ? "*" : next === "segment" ? "A" : "");
    setDetail(null);
    setEffective(null);
    setForm(emptyForm());
    reset();
  };

  const load = async () => {
    reset();
    setConflict(null);
    if (!scopeKeyValid(scope, key)) return setError(t("policies.key_invalid"));
    try {
      const d = await api.getPolicy(scope, key);
      setDetail(d);
      setForm(toForm(d.current));
      setEffective(scope === "product" ? await api.getEffectivePolicy(key.trim()) : null);      // where each value in force comes from
    } catch (err) {
      fail(err);
    }
  };

  const payload = () => {
    const p = toPayload(form);
    if ("invalid" in p) {
      const message = t("policies.invalid_field", { field: t(`policies.f.${p.invalid}`) });
      setError(message);
      fe.flag({ [`pol-${p.invalid}`]: message });
      return null;
    }
    return p.body;
  };

  const doPreview = async () => {
    reset();
    const body = payload();
    if (body === null) return;
    try {
      setPreview(await api.previewPolicy(scope, key, body));
    } catch (err) {
      fail(err);
    }
  };

  const save = async () => {
    reset();
    const body = payload();
    if (body === null) return;
    try {
      const r = await api.putPolicy(scope, key, body, detail?.revision ?? 0);
      setConflict(null);
      await load();                                   // reload first: loading clears messages, so the confirmation is set after it
      setNotice(t("policies.saved", { revision: r.revision }));
      onChanged();
    } catch (err) {
      if (err instanceof ApiError && err.code === "revision_conflict") setConflict(err.currentVersion ?? detail?.revision ?? 0);
      else fail(err);
    }
  };

  const clear = async () => {
    reset();
    try {
      const r = await api.clearPolicy(scope, key, detail?.revision ?? 0);
      setConflict(null);
      await load();
      setNotice(t("policies.cleared", { revision: r.revision }));
      onChanged();
    } catch (err) {
      if (err instanceof ApiError && err.code === "revision_conflict") setConflict(err.currentVersion ?? detail?.revision ?? 0);
      else fail(err);
    }
  };

  const saveBudget = async () => {
    reset();
    const amount = budget.trim().replace(",", ".");
    if (!/^\d{1,9}(\.\d{1,2})?$/.test(amount)) return setError(t("policies.invalid_field", { field: t("policies.budget.amount") }));
    try {
      await api.putBudgetCap({ period: "week", scope: "global", amount }, weeklyBudgetRevision);
      setBudgetConflict(null);
      setNotice(t("policies.budget.saved"));
      onChanged();
    } catch (err) {
      if (err instanceof ApiError && err.code === "revision_conflict") setBudgetConflict(err.currentVersion ?? weeklyBudgetRevision);
      else fail(err);
    }
  };

  const field = (name: keyof PolicyForm, type: "text" | "date" = "text") => (
    <FormField id={`pol-${name}`} label={t(`policies.f.${name}`)} value={form[name]} type={type} disabled={!canEdit} inputMode={type === "date" ? "text" : "decimal"}
           error={fe.errors[`pol-${name}`]} onChange={(v) => { setForm({ ...form, [name]: v }); fe.clear(`pol-${name}`); }} />
  );

  const dirty = canEdit && detail !== null && JSON.stringify(form) !== JSON.stringify(toForm(detail.current));

  return (
    <div>
      <UnsavedChangesPrompt dirty={dirty} />
      <h3>{t("policies.in_force")}</h3>
      {policies.length === 0 ? (
        <p>{t("policies.none")}</p>
      ) : (
        <ul>
          {policies.map((p) => (
            <li key={`${p.scope}:${p.key ?? "orphan"}:${p.revision}`}>
              {t(`policies.scope.${p.scope}`)} {p.key !== "*" ? `· ${p.key ?? t("policies.orphaned_unknown")}` : ""} — {t("policies.history.revision")} {p.revision}
              {p.orphaned && ` (${t("policies.orphaned")})`}
            </li>
          ))}
        </ul>
      )}
      {orphaned > 0 && <p role="status">{t("policies.orphaned_note", { count: orphaned })}</p>}

      <div className="mmi-cluster">
        <div className="mmi-stack">
          <label htmlFor="pol-scope">{t("policies.scope")}</label>
          <select id="pol-scope" value={scope} onChange={(e) => changeScope(e.target.value as Scope)}>
            {(["global", "segment", "product"] as const).map((s) => (
              <option key={s} value={s}>
                {t(`policies.scope.${s}`)}
              </option>
            ))}
          </select>
        </div>
        {scope !== "global" && <FormField id="pol-key" label={t("policies.key")} value={key} onChange={setKey} />}
        <Button variant="secondary" onClick={() => void load()}>
          {t("policies.load")}
        </Button>
      </div>

      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {conflict !== null && <p role="alert">{t("policies.conflict", { version: conflict })}</p>}
      {!canEdit && <p className="mmi-muted">{t("policies.read_only")}</p>}

      {detail && (
        <>
          <div className="mmi-cluster mmi-cluster--top">
            {field("service_level_pct")}
            {field("safety_stock_units")}
            {field("min_units")}
            {field("max_units")}
            {field("replenishment_cadence_days")}
            {field("valid_from", "date")}
          </div>
          {canEdit && (
            <PageActions>
              <Button variant="secondary" onClick={() => void doPreview()}>
                {t("policies.preview")}
              </Button>
              <Button onClick={() => void save()}>
                {t("policies.save")}
              </Button>
              {detail.revision > 0 && (
                <Button variant="secondary" onClick={() => void clear()}>
                  {t("policies.clear")}
                </Button>
              )}
            </PageActions>
          )}

          {effective && (
            <div role="region" aria-label={t("policies.effective.title")}>
              <h4>{t("policies.effective.title")}</h4>
              <DataTable
                ariaLabel={t("policies.effective.title")}
                rows={RULES.map((r) => ({ rule: r, ...effective.rules[r] }))}
                rowKey={(r) => r.rule}
                columns={[
                  { id: "rule", header: t("policies.effective.rule"), cell: (r) => t(`policies.effective.rule.${r.rule}`), sortValue: (r) => r.rule },
                  { id: "value", header: t("policies.effective.value"), cell: (r) => (r.value === null ? "—" : r.rule === "service_level" ? `${Math.round(parseFloat(r.value) * 10000) / 100} %` : r.value), sortValue: (r) => r.value, align: "end" },
                  { id: "source", header: t("policies.effective.source"), cell: (r) => t(`policies.effective.source.${r.source}`), sortValue: (r) => r.source },
                  { id: "revision", header: t("policies.history.revision"), cell: (r) => r.revision ?? "—", sortValue: (r) => r.revision, align: "end" },
                ]}
              />
            </div>
          )}

          {preview && (
            <div role="region" aria-label={t("policies.preview.title")}>
              <h4>{t("policies.preview.title")}</h4>
              <p>{t("policies.preview.affected", { count: preview.affected_count })}</p>
              <p>
                {t("policies.preview.spend", {
                  before: formatCurrencyEUR(preview.spend_before), after: formatCurrencyEUR(preview.spend_after), delta: formatCurrencyEUR(preview.spend_delta),
                })}
              </p>
              <ul>
                {preview.affected.map((a, i) => (
                  <li key={a.sku ?? i}>{t("policies.preview.row", { sku: a.sku ?? "—", before: a.qty_before, after: a.qty_after })}</li>
                ))}
              </ul>
            </div>
          )}

          <h4>{t("policies.history")}</h4>
          <DataTable
            ariaLabel={t("policies.history")}
            rows={detail.history}
            rowKey={(h) => h.revision}
            columns={[
              { id: "revision", header: t("policies.history.revision"), cell: (h) => h.revision, sortValue: (h) => h.revision, align: "end" },
              { id: "from", header: t("policies.history.from"), cell: (h) => h.valid_from, sortValue: (h) => h.valid_from },
              { id: "level", header: t("policies.f.service_level_pct"), cell: (h) => (h.service_level === null ? "—" : `${Math.round(parseFloat(h.service_level) * 10000) / 100} %`), sortValue: (h) => (h.service_level === null ? null : Number(h.service_level)), align: "end" },
              { id: "min", header: t("policies.f.min_units"), cell: (h) => h.min_units ?? "—", sortValue: (h) => h.min_units ?? null, align: "end" },
              { id: "max", header: t("policies.f.max_units"), cell: (h) => h.max_units ?? "—", sortValue: (h) => h.max_units ?? null, align: "end" },
              { id: "by", header: t("policies.history.by"), cell: (h) => h.changed_by, sortValue: (h) => h.changed_by },
            ]}
          />
        </>
      )}

      <h3>{t("policies.budget")}</h3>
      <p>{weeklyBudget === null ? t("policies.budget.none") : t("policies.budget.current", { value: formatCurrencyEUR(weeklyBudget) })}</p>
      {budgetConflict !== null && <p role="alert">{t("policies.conflict", { version: budgetConflict })}</p>}
      {canEdit && (
        <div className="mmi-cluster">
          <FormField id="pol-budget" label={t("policies.budget.amount")} value={budget} onChange={setBudget} inputMode="decimal" />
          <Button onClick={() => void saveBudget()}>
            {t("policies.budget.save")}
          </Button>
        </div>
      )}
    </div>
  );
};
