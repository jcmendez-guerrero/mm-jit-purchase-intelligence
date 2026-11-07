import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, errorMessage, OverrideView } from "../../api/client";
import { Field } from "./Field";
import { OverrideForm, Tri, overrideToForm, overrideToPayload, sourceKey } from "./termsModel";

interface Props {
  supplierId: string;
  canEdit: boolean;
}

const EFFECTIVE_FIELDS = ["lead_time_days", "pack_multiple", "min_qty_units", "payment_terms_days", "reliability", "preferred", "disabled"] as const;

export const OverrideEditor: React.FC<Props> = ({ supplierId, canEdit }) => {
  const { t } = useTranslation();
  const [variant, setVariant] = useState("");
  const [view, setView] = useState<OverrideView | null>(null);
  const [form, setForm] = useState<OverrideForm>(overrideToForm(null));
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const variantId = Number(variant);
  const load = async () => {
    setError(null);
    setNotice(null);
    try {
      const v = await api.getOverrideTerms(variantId, supplierId);
      setView(v);
      setForm(overrideToForm(v.override));
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  };

  const save = async () => {
    if (!view) return;
    setError(null);
    try {
      const r = await api.putOverrideTerms(variantId, supplierId, overrideToPayload(form), view.version);
      setNotice(t("suppliers.override.saved", { version: r.version }));
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.code === "revision_conflict") {
        setError(t("suppliers.conflict", { version: err.currentVersion ?? view.version }));
        await load();
      } else setError(errorMessage(err, t("common.error")));
    }
  };

  const set = <K extends keyof OverrideForm>(k: K, v: OverrideForm[K]) => setForm((f) => ({ ...f, [k]: v }));
  const tri = (id: string, label: string, name: "preferred" | "disabled") => (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
      <label htmlFor={id} style={{ fontSize: "0.85rem", fontWeight: 600 }}>
        {label}
      </label>
      <select id={id} disabled={!canEdit} value={form[name]} onChange={(e) => set(name, e.target.value as Tri)}>
        <option value="inherit">{t("suppliers.override.inherit")}</option>
        <option value="yes">{t("suppliers.override.yes")}</option>
        <option value="no">{t("suppliers.override.no")}</option>
      </select>
    </div>
  );

  const shown = (key: (typeof EFFECTIVE_FIELDS)[number]): string => {
    const v = view?.effective[key];
    if (v === null || v === undefined) return t("suppliers.override.none");
    if (typeof v === "boolean") return v ? t("suppliers.override.yes") : t("suppliers.override.no");
    return String(v);
  };

  return (
    <div className="mmi-card" aria-labelledby="override-title">
      <h3 id="override-title" style={{ fontSize: "1.1rem", marginTop: 0 }}>
        {t("suppliers.override.title")}
      </h3>
      <p style={{ color: "var(--color-text-muted)", fontSize: "0.9rem" }}>{t("suppliers.override.help")}</p>
      <div style={{ display: "flex", gap: "0.8rem", alignItems: "flex-end", marginBottom: "1rem" }}>
        <Field id="o-variant" label={t("suppliers.override.variant")} value={variant} inputMode="numeric" onChange={setVariant} />
        <button type="button" className="mmi-btn mmi-btn-secondary" disabled={!Number.isInteger(variantId) || variantId < 1} onClick={() => void load()}>
          {t("suppliers.override.load")}
        </button>
      </div>
      {error && (
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}

      {view && (
        <>
          {view.effective.flags.includes("no_supplier_terms") && <p>{t("suppliers.override.no_supplier_terms")}</p>}
          <h4>{t("suppliers.override.effective")}</h4>
          <div className="mmi-table-wrapper">
            <table className="mmi-table" aria-label={t("a11y.effective_table")}>
              <thead>
                <tr>
                  <th scope="col">{t("suppliers.override.field")}</th>
                  <th scope="col">{t("suppliers.override.value")}</th>
                  <th scope="col">{t("suppliers.override.origin")}</th>
                </tr>
              </thead>
              <tbody>
                {EFFECTIVE_FIELDS.map((f) => (
                  <tr key={f}>
                    <th scope="row">{t(`suppliers.eff.${f}`)}</th>
                    <td>{shown(f)}</td>
                    <td>
                      <span className="mmi-badge mmi-badge-petroleo">{t(sourceKey(view.effective.sources[f]))}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {view.effective.conflicts.length > 0 && (
            <div role="alert" style={{ marginTop: "0.8rem" }}>
              <strong>{t("suppliers.override.conflicts")}</strong>
              <ul>
                {view.effective.conflicts.map((c) => (
                  <li key={c.field}>{t("suppliers.override.conflict_line", { field: t(`suppliers.eff.${c.field}`), erp: c.erp_value, local: c.local_value })}</li>
                ))}
              </ul>
            </div>
          )}

          {canEdit && (
            <div style={{ marginTop: "1rem" }}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.9rem", marginBottom: "1rem" }}>
                <Field id="o-pack" label={t("suppliers.eff.pack_multiple")} value={form.pack_multiple} inputMode="numeric" onChange={(v) => set("pack_multiple", v)} />
                <Field id="o-minq" label={t("suppliers.eff.min_qty_units")} value={form.min_qty_units} inputMode="numeric" onChange={(v) => set("min_qty_units", v)} />
                <Field id="o-lead" label={t("suppliers.eff.lead_time_days")} value={form.lead_time_days} inputMode="numeric" onChange={(v) => set("lead_time_days", v)} />
                <Field id="o-pay" label={t("suppliers.eff.payment_terms_days")} value={form.payment_terms_days} inputMode="numeric" onChange={(v) => set("payment_terms_days", v)} />
                <Field id="o-rel" label={t("suppliers.eff.reliability")} value={form.reliability} inputMode="numeric" onChange={(v) => set("reliability", v)} />
                {tri("o-pref", t("suppliers.eff.preferred"), "preferred")}
                {tri("o-dis", t("suppliers.eff.disabled"), "disabled")}
                <Field id="o-reason" label={t("suppliers.f.reason")} value={form.reason} onChange={(v) => set("reason", v)} />
              </div>
              <button type="button" className="mmi-btn mmi-btn-primary" onClick={() => void save()}>
                {t("suppliers.override.save")}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};
