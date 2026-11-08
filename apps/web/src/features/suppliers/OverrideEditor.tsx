import React, { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, errorMessage, OverrideView } from "../../api/client";
import { focusFirstInvalid, FormField } from "../../ui/FormField";
import { UnsavedChangesPrompt } from "../../ui/UnsavedChangesPrompt";
import { OverrideForm, Tri, overrideToForm, overrideToPayload, sourceKey, validateOverride } from "./termsModel";
import { useActionNotice } from "../../ui/NoticeProvider";
import { StatusBadge } from "../../ui/StatusBadge";
import { Card } from "../../ui/Card";
import { Button } from "../../ui/Button";

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
  const [baseline, setBaseline] = useState<OverrideForm>(overrideToForm(null));
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const formRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useActionNotice();

  const variantId = Number(variant);
  const load = async () => {
    setError(null);
    setNotice(null);
    try {
      const v = await api.getOverrideTerms(variantId, supplierId);
      setView(v);
      const loaded = overrideToForm(v.override);
      setForm(loaded);
      setBaseline(loaded);
      setFieldErrors({});
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  };

  const dirty = canEdit && view !== null && JSON.stringify(form) !== JSON.stringify(baseline);
  const errorText = (id: string) => (fieldErrors[id] ? t(fieldErrors[id]) : undefined);
  const checkField = (id: string) => () => {
    const found = validateOverride(form)[id];
    setFieldErrors((prev) => {
      const next = { ...prev };
      if (found) next[id] = found;
      else delete next[id];
      return next;
    });
  };

  const save = async () => {
    if (!view) return;
    setError(null);
    const found = validateOverride(form);
    setFieldErrors(found);
    if (Object.keys(found).length > 0) {
      setTimeout(() => focusFirstInvalid(formRef.current ?? document), 0);
      return;
    }
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
    <div className="mmi-stack mmi-stack--tight">
      <label className="mmi-label" htmlFor={id}>
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
    <Card as="div" aria-labelledby="override-title" ref={formRef}>
      <UnsavedChangesPrompt dirty={dirty} />
      <h3 className="mmi-title-md mmi-mt-0" id="override-title">
        {t("suppliers.override.title")}
      </h3>
      <p className="mmi-muted mmi-text-sm">{t("suppliers.override.help")}</p>
      <div className="mmi-cluster mmi-mb-4">
        <FormField id="o-variant" label={t("suppliers.override.variant")} value={variant} inputMode="numeric" onChange={setVariant} />
        <Button variant="secondary" disabled={!Number.isInteger(variantId) || variantId < 1} onClick={() => void load()}>
          {t("suppliers.override.load")}
        </Button>
      </div>
      {error && (
        <p className="mmi-error" role="alert">
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
                      <StatusBadge domain="tag" code={sourceKey(view.effective.sources[f]).replace("suppliers.source.", "source_")} label={t(sourceKey(view.effective.sources[f]))} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {view.effective.conflicts.length > 0 && (
            <div className="mmi-mt-3" role="alert">
              <strong>{t("suppliers.override.conflicts")}</strong>
              <ul>
                {view.effective.conflicts.map((c) => (
                  <li key={c.field}>{t("suppliers.override.conflict_line", { field: t(`suppliers.eff.${c.field}`), erp: c.erp_value, local: c.local_value })}</li>
                ))}
              </ul>
            </div>
          )}

          {canEdit && (
            <div className="mmi-mt-4">
              <div className="mmi-cluster mmi-mb-4">
                <FormField error={errorText("o-pack")} onBlur={checkField("o-pack")} id="o-pack" label={t("suppliers.eff.pack_multiple")} value={form.pack_multiple} inputMode="numeric" onChange={(v) => set("pack_multiple", v)} />
                <FormField error={errorText("o-minq")} onBlur={checkField("o-minq")} id="o-minq" label={t("suppliers.eff.min_qty_units")} value={form.min_qty_units} inputMode="numeric" onChange={(v) => set("min_qty_units", v)} />
                <FormField error={errorText("o-lead")} onBlur={checkField("o-lead")} id="o-lead" label={t("suppliers.eff.lead_time_days")} value={form.lead_time_days} inputMode="numeric" onChange={(v) => set("lead_time_days", v)} />
                <FormField error={errorText("o-pay")} onBlur={checkField("o-pay")} id="o-pay" label={t("suppliers.eff.payment_terms_days")} value={form.payment_terms_days} inputMode="numeric" onChange={(v) => set("payment_terms_days", v)} />
                <FormField error={errorText("o-rel")} onBlur={checkField("o-rel")} id="o-rel" label={t("suppliers.eff.reliability")} value={form.reliability} inputMode="numeric" onChange={(v) => set("reliability", v)} />
                {tri("o-pref", t("suppliers.eff.preferred"), "preferred")}
                {tri("o-dis", t("suppliers.eff.disabled"), "disabled")}
                <FormField id="o-reason" label={t("suppliers.f.reason")} value={form.reason} onChange={(v) => set("reason", v)} />
              </div>
              <Button onClick={() => void save()}>
                {t("suppliers.override.save")}
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  );
};
