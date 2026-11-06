import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, errorMessage, PolicyDetail, PolicyPreview, PolicySummary } from "../../api/client";
import { formatCurrencyEUR } from "../../i18n/formatters";
import { Field } from "../suppliers/Field";
import { canEditPolicies, emptyForm, PolicyForm, scopeKeyValid, Scope, toForm, toPayload } from "./policiesModel";

interface Props {
  roles: string[];
  policies: PolicySummary[];
  weeklyBudget: string | null;
  onChanged: () => void;
}

export const PurchasingSection: React.FC<Props> = ({ roles, policies, weeklyBudget, onChanged }) => {
  const { t } = useTranslation();
  const [scope, setScope] = useState<Scope>("global");
  const [key, setKey] = useState("*");
  const [detail, setDetail] = useState<PolicyDetail | null>(null);
  const [form, setForm] = useState<PolicyForm>(emptyForm());
  const [preview, setPreview] = useState<PolicyPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [conflict, setConflict] = useState<number | null>(null);
  const [budget, setBudget] = useState("");
  const canEdit = canEditPolicies(roles);

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
    } catch (err) {
      fail(err);
    }
  };

  const payload = () => {
    const p = toPayload(form);
    if ("invalid" in p) {
      setError(t("policies.invalid_field", { field: t(`policies.f.${p.invalid}`) }));
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

  const saveBudget = async () => {
    reset();
    const amount = budget.trim().replace(",", ".");
    if (!/^\d{1,9}(\.\d{1,2})?$/.test(amount)) return setError(t("policies.invalid_field", { field: t("policies.budget.amount") }));
    try {
      await api.putBudgetCap({ period: "week", scope: "global", amount });
      setNotice(t("policies.budget.saved"));
      onChanged();
    } catch (err) {
      fail(err);
    }
  };

  const field = (name: keyof PolicyForm, type: "text" | "date" = "text") => (
    <Field id={`pol-${name}`} label={t(`policies.f.${name}`)} value={form[name]} type={type} disabled={!canEdit} inputMode={type === "date" ? "text" : "decimal"}
           onChange={(v) => setForm({ ...form, [name]: v })} />
  );

  return (
    <div>
      <h3>{t("policies.in_force")}</h3>
      {policies.length === 0 ? (
        <p>{t("policies.none")}</p>
      ) : (
        <ul>
          {policies.map((p) => (
            <li key={`${p.scope}:${p.key}`}>
              {t(`policies.scope.${p.scope}`)} {p.key !== "*" ? `· ${p.key}` : ""} — {t("policies.history.revision")} {p.revision}
            </li>
          ))}
        </ul>
      )}

      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "end" }}>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <label htmlFor="pol-scope">{t("policies.scope")}</label>
          <select id="pol-scope" value={scope} onChange={(e) => changeScope(e.target.value as Scope)}>
            {(["global", "segment", "product"] as const).map((s) => (
              <option key={s} value={s}>
                {t(`policies.scope.${s}`)}
              </option>
            ))}
          </select>
        </div>
        {scope !== "global" && <Field id="pol-key" label={t("policies.key")} value={key} onChange={setKey} />}
        <button type="button" className="mmi-btn mmi-btn-secondary" onClick={() => void load()}>
          {t("policies.load")}
        </button>
      </div>

      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {conflict !== null && <p role="alert">{t("policies.conflict", { version: conflict })}</p>}
      {!canEdit && <p className="mmi-muted">{t("policies.read_only")}</p>}

      {detail && (
        <>
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            {field("service_level_pct")}
            {field("safety_stock_units")}
            {field("min_units")}
            {field("max_units")}
            {field("replenishment_cadence_days")}
            {field("valid_from", "date")}
          </div>
          {canEdit && (
            <div>
              <button type="button" className="mmi-btn mmi-btn-secondary" onClick={() => void doPreview()}>
                {t("policies.preview")}
              </button>{" "}
              <button type="button" className="mmi-btn mmi-btn-primary" onClick={() => void save()}>
                {t("policies.save")}
              </button>
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
                {preview.affected.map((a) => (
                  <li key={a.variant_id}>{t("policies.preview.row", { variant: a.variant_id, before: a.qty_before, after: a.qty_after })}</li>
                ))}
              </ul>
            </div>
          )}

          <h4>{t("policies.history")}</h4>
          <table aria-label={t("policies.history")} className="mmi-table">
            <thead>
              <tr>
                <th>{t("policies.history.revision")}</th>
                <th>{t("policies.history.from")}</th>
                <th>{t("policies.f.service_level_pct")}</th>
                <th>{t("policies.f.min_units")}</th>
                <th>{t("policies.f.max_units")}</th>
                <th>{t("policies.history.by")}</th>
              </tr>
            </thead>
            <tbody>
              {detail.history.map((h) => (
                <tr key={h.revision}>
                  <td>{h.revision}</td>
                  <td>{h.valid_from}</td>
                  <td>{h.service_level === null ? "—" : `${Math.round(parseFloat(h.service_level) * 10000) / 100} %`}</td>
                  <td>{h.min_units ?? "—"}</td>
                  <td>{h.max_units ?? "—"}</td>
                  <td>{h.changed_by}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <h3>{t("policies.budget")}</h3>
      <p>{weeklyBudget === null ? t("policies.budget.none") : t("policies.budget.current", { value: formatCurrencyEUR(weeklyBudget) })}</p>
      {canEdit && (
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "end" }}>
          <Field id="pol-budget" label={t("policies.budget.amount")} value={budget} onChange={setBudget} inputMode="decimal" />
          <button type="button" className="mmi-btn mmi-btn-primary" onClick={() => void saveBudget()}>
            {t("policies.budget.save")}
          </button>
        </div>
      )}
    </div>
  );
};
