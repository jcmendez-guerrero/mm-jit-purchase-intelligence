import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, errorMessage, SupplierTermsView } from "../../api/client";
import { formatDate } from "../../i18n/formatters";
import { Field } from "./Field";
import { MAX_DISCOUNT_TIERS, TermsForm, WEEKDAYS, emptyForm, toForm, toPayload, toggleDay } from "./termsModel";

interface Props {
  supplierId: string;
  supplierName: string;
  canEdit: boolean;
  onSaved?: () => void;
}

export const SupplierTermsEditor: React.FC<Props> = ({ supplierId, supplierName, canEdit, onSaved }) => {
  const { t } = useTranslation();
  const [view, setView] = useState<SupplierTermsView | null>(null);
  const [form, setForm] = useState<TermsForm>(emptyForm());
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [conflictVersion, setConflictVersion] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const v = await api.getSupplierTerms(supplierId);
      setView(v);
      setForm(toForm(v.current));
      setConflictVersion(null);
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  }, [supplierId, t]);

  useEffect(() => {
    setError(null);
    setNotice(null);
    void load();
  }, [load]);

  const set = <K extends keyof TermsForm>(key: K, value: TermsForm[K]) => setForm((f) => ({ ...f, [key]: value }));
  const readOnly = !canEdit;

  const save = async () => {
    if (!view) return;
    setError(null);
    setNotice(null);
    try {
      const r = await api.putSupplierTerms(supplierId, toPayload(form), view.version);
      setNotice(t("suppliers.saved", { version: r.version }));
      await load();
      onSaved?.();
    } catch (err) {
      if (err instanceof ApiError && err.code === "revision_conflict") setConflictVersion(err.currentVersion ?? view.version);
      else setError(errorMessage(err, t("common.error")));
    }
  };

  const weekdays = (legendKey: string, name: "order_days" | "delivery_weekdays") => (
    <fieldset style={{ border: "none", padding: 0, margin: 0 }}>
      <legend style={{ fontSize: "0.85rem", fontWeight: 600 }}>{t(legendKey)}</legend>
      {WEEKDAYS.map((d) => (
        <label key={d} style={{ marginRight: "0.6rem" }}>
          <input type="checkbox" disabled={readOnly} checked={form[name].includes(d)} onChange={() => set(name, toggleDay(form[name], d))} /> {t(`suppliers.weekday.${d}`)}
        </label>
      ))}
    </fieldset>
  );

  return (
    <div className="mmi-card" aria-labelledby="terms-title">
      <h3 id="terms-title" style={{ fontSize: "1.1rem", marginTop: 0 }}>
        {t("suppliers.editor.title", { name: supplierName })}
      </h3>
      {readOnly && <p style={{ color: "var(--color-text-muted)" }}>{t("suppliers.editor.read_only")}</p>}
      {error && (
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {conflictVersion !== null && (
        <div role="alert">
          <p>{t("suppliers.conflict", { version: conflictVersion })}</p>
          <button type="button" className="mmi-btn mmi-btn-secondary" onClick={() => void load()}>
            {t("suppliers.reload")}
          </button>
        </div>
      )}

      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.9rem", marginBottom: "1rem" }}>
        <Field id="f-lead" label={t("suppliers.f.lead_time_days")} value={form.lead_time_days} inputMode="numeric" disabled={readOnly} onChange={(v) => set("lead_time_days", v)} />
        <Field id="f-cutoff" label={t("suppliers.f.order_cutoff_time")} value={form.order_cutoff_time} disabled={readOnly} onChange={(v) => set("order_cutoff_time", v)} />
        <Field id="f-min" label={t("suppliers.f.min_order_value")} value={form.min_order_value} inputMode="decimal" disabled={readOnly} onChange={(v) => set("min_order_value", v)} />
        <Field id="f-minq" label={t("suppliers.f.min_qty_for_delivery")} value={form.min_qty_for_delivery} inputMode="numeric" disabled={readOnly} onChange={(v) => set("min_qty_for_delivery", v)} />
        <Field id="f-free" label={t("suppliers.f.free_delivery_threshold")} value={form.free_delivery_threshold} inputMode="decimal" disabled={readOnly} onChange={(v) => set("free_delivery_threshold", v)} />
        <Field id="f-charge" label={t("suppliers.f.delivery_charge")} value={form.delivery_charge} inputMode="decimal" disabled={readOnly} onChange={(v) => set("delivery_charge", v)} />
        <Field id="f-pay" label={t("suppliers.f.payment_terms_days")} value={form.payment_terms_days} inputMode="numeric" disabled={readOnly} onChange={(v) => set("payment_terms_days", v)} />
        <Field id="f-rel" label={t("suppliers.f.reliability")} value={form.reliability} inputMode="numeric" disabled={readOnly} onChange={(v) => set("reliability", v)} />
        <Field id="f-sched" label={t("suppliers.f.delivery_schedule")} value={form.delivery_schedule} disabled={readOnly} onChange={(v) => set("delivery_schedule", v)} />
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "2rem", marginBottom: "1rem" }}>
        {weekdays("suppliers.f.order_days", "order_days")}
        {weekdays("suppliers.f.delivery_weekdays", "delivery_weekdays")}
      </div>

      <div style={{ marginBottom: "1rem" }}>
        <label style={{ marginRight: "1.5rem" }}>
          <input type="checkbox" disabled={readOnly} checked={form.preferred} onChange={(e) => set("preferred", e.target.checked)} /> {t("suppliers.f.preferred")}
        </label>
        <label>
          <input type="checkbox" disabled={readOnly} checked={form.disabled} onChange={(e) => set("disabled", e.target.checked)} /> {t("suppliers.f.disabled")}
        </label>
      </div>

      <fieldset style={{ marginBottom: "1rem" }}>
        <legend style={{ fontWeight: 600 }}>{t("suppliers.discounts")}</legend>
        {form.discounts.map((d, i) => (
          <div key={i} style={{ display: "flex", flexWrap: "wrap", gap: "0.6rem", alignItems: "flex-end", marginBottom: "0.5rem" }}>
            <label>
              {t("suppliers.discount.kind")}{" "}
              <select
                aria-label={`${t("suppliers.discount.kind")} ${i + 1}`}
                disabled={readOnly}
                value={d.kind}
                onChange={(e) => set("discounts", form.discounts.map((x, j) => (j === i ? { ...x, kind: e.target.value as "percent" | "amount" } : x)))}
              >
                <option value="percent">{t("suppliers.discount.percent")}</option>
                <option value="amount">{t("suppliers.discount.amount")}</option>
              </select>
            </label>
            <label>
              {t("suppliers.discount.basis")}{" "}
              <select
                aria-label={`${t("suppliers.discount.basis")} ${i + 1}`}
                disabled={readOnly}
                value={d.basis}
                onChange={(e) => set("discounts", form.discounts.map((x, j) => (j === i ? { ...x, basis: e.target.value as "order_value" | "order_units" } : x)))}
              >
                <option value="order_value">{t("suppliers.discount.order_value")}</option>
                <option value="order_units">{t("suppliers.discount.order_units")}</option>
              </select>
            </label>
            <Field id={`d-thr-${i}`} label={`${t("suppliers.discount.threshold")} ${i + 1}`} value={d.threshold} inputMode="decimal" disabled={readOnly}
              onChange={(v) => set("discounts", form.discounts.map((x, j) => (j === i ? { ...x, threshold: v } : x)))} />
            <Field id={`d-val-${i}`} label={`${t("suppliers.discount.value")} ${i + 1}`} value={d.value} inputMode="decimal" disabled={readOnly}
              onChange={(v) => set("discounts", form.discounts.map((x, j) => (j === i ? { ...x, value: v } : x)))} />
            {!readOnly && (
              <button type="button" className="mmi-btn mmi-btn-secondary" onClick={() => set("discounts", form.discounts.filter((_, j) => j !== i))}>
                {t("suppliers.discount.remove")} {i + 1}
              </button>
            )}
          </div>
        ))}
        {!readOnly && form.discounts.length < MAX_DISCOUNT_TIERS && (
          <button type="button" className="mmi-btn mmi-btn-secondary"
            onClick={() => set("discounts", [...form.discounts, { kind: "percent", basis: "order_value", threshold: "", value: "" }])}>
            {t("suppliers.discount.add")}
          </button>
        )}
      </fieldset>

      {!readOnly && (
        <>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.9rem", marginBottom: "1rem" }}>
            <Field id="f-from" type="date" label={t("suppliers.f.valid_from")} value={form.valid_from} onChange={(v) => set("valid_from", v)} />
            <Field id="f-to" type="date" label={t("suppliers.f.valid_to")} value={form.valid_to} onChange={(v) => set("valid_to", v)} />
            <Field id="f-reason" label={t("suppliers.f.reason")} value={form.reason} onChange={(v) => set("reason", v)} />
          </div>
          <button type="button" className="mmi-btn mmi-btn-primary" onClick={() => void save()}>
            {t("suppliers.save")}
          </button>
        </>
      )}

      {view && view.history.length > 0 && (
        <div style={{ marginTop: "1.5rem" }}>
          <h4 style={{ marginBottom: "0.4rem" }}>{t("suppliers.history")}</h4>
          <div className="mmi-table-wrapper">
            <table className="mmi-table" aria-label={t("a11y.history_table")}>
              <thead>
                <tr>
                  <th scope="col">{t("suppliers.history.version")}</th>
                  <th scope="col">{t("suppliers.history.from")}</th>
                  <th scope="col">{t("suppliers.history.source")}</th>
                  <th scope="col">{t("suppliers.history.by")}</th>
                  <th scope="col">{t("suppliers.history.reason")}</th>
                </tr>
              </thead>
              <tbody>
                {[...view.history].reverse().map((h) => (
                  <tr key={h.version}>
                    <td>{h.version}</td>
                    <td>{formatDate(new Date(h.valid_from))}</td>
                    <td>
                      <span className="mmi-badge mmi-badge-petroleo">{t(`suppliers.source.${h.source}`)}</span>
                    </td>
                    <td>{h.changed_by}</td>
                    <td>{h.reason ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
