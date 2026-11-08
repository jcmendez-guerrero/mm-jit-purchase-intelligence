import React, { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, errorMessage, SupplierTermsView } from "../../api/client";
import { formatDate } from "../../i18n/formatters";
import { focusFirstInvalid, FormField } from "../../ui/FormField";
import { UnsavedChangesPrompt } from "../../ui/UnsavedChangesPrompt";
import { MAX_DISCOUNT_TIERS, TermsForm, WEEKDAYS, emptyForm, toForm, toPayload, toggleDay, validateTerms } from "./termsModel";
import { useActionNotice } from "../../ui/NoticeProvider";
import { StatusBadge } from "../../ui/StatusBadge";
import { Card } from "../../ui/Card";
import { Button } from "../../ui/Button";
import { PageActions } from "../../ui/PageActions";
import { DataTable } from "../../ui/DataTable";

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
  const [baseline, setBaseline] = useState<TermsForm>(emptyForm());
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const formRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useActionNotice();
  const [conflictVersion, setConflictVersion] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const v = await api.getSupplierTerms(supplierId);
      setView(v);
      const loaded = toForm(v.current);
      setForm(loaded);
      setBaseline(loaded);
      setFieldErrors({});
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

  const dirty = canEdit && JSON.stringify(form) !== JSON.stringify(baseline);
  const errorText = (id: string) => (fieldErrors[id] ? t(fieldErrors[id]) : undefined);
  const checkField = (id: string) => () => {
    const found = validateTerms(form)[id];
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
    setNotice(null);
    const found = validateTerms(form);
    setFieldErrors(found);
    if (Object.keys(found).length > 0) {
      // let the messages render, then move focus to the first invalid field
      setTimeout(() => focusFirstInvalid(formRef.current ?? document), 0);
      return;
    }
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
    <fieldset className="mmi-fieldset-plain">
      <legend className="mmi-label">{t(legendKey)}</legend>
      {WEEKDAYS.map((d) => (
        <label className="mmi-mr-2" key={d}>
          <input type="checkbox" disabled={readOnly} checked={form[name].includes(d)} onChange={() => set(name, toggleDay(form[name], d))} /> {t(`suppliers.weekday.${d}`)}
        </label>
      ))}
    </fieldset>
  );

  return (
    <Card as="div" aria-labelledby="terms-title" ref={formRef}>
      <UnsavedChangesPrompt dirty={dirty} />
      <h3 className="mmi-title-md mmi-mt-0" id="terms-title">
        {t("suppliers.editor.title", { name: supplierName })}
      </h3>
      {readOnly && <p className="mmi-muted">{t("suppliers.editor.read_only")}</p>}
      {error && (
        <p className="mmi-error" role="alert">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {conflictVersion !== null && (
        <div role="alert">
          <p>{t("suppliers.conflict", { version: conflictVersion })}</p>
          <Button variant="secondary" onClick={() => void load()}>
            {t("suppliers.reload")}
          </Button>
        </div>
      )}

      <div className="mmi-cluster mmi-mb-4">
        <FormField error={errorText("f-lead")} onBlur={checkField("f-lead")} id="f-lead" label={t("suppliers.f.lead_time_days")} value={form.lead_time_days} inputMode="numeric" disabled={readOnly} onChange={(v) => set("lead_time_days", v)} />
        <FormField error={errorText("f-cutoff")} onBlur={checkField("f-cutoff")} id="f-cutoff" label={t("suppliers.f.order_cutoff_time")} value={form.order_cutoff_time} disabled={readOnly} onChange={(v) => set("order_cutoff_time", v)} />
        <FormField error={errorText("f-min")} onBlur={checkField("f-min")} id="f-min" label={t("suppliers.f.min_order_value")} value={form.min_order_value} inputMode="decimal" disabled={readOnly} onChange={(v) => set("min_order_value", v)} />
        <FormField error={errorText("f-minq")} onBlur={checkField("f-minq")} id="f-minq" label={t("suppliers.f.min_qty_for_delivery")} value={form.min_qty_for_delivery} inputMode="numeric" disabled={readOnly} onChange={(v) => set("min_qty_for_delivery", v)} />
        <FormField error={errorText("f-free")} onBlur={checkField("f-free")} id="f-free" label={t("suppliers.f.free_delivery_threshold")} value={form.free_delivery_threshold} inputMode="decimal" disabled={readOnly} onChange={(v) => set("free_delivery_threshold", v)} />
        <FormField error={errorText("f-charge")} onBlur={checkField("f-charge")} id="f-charge" label={t("suppliers.f.delivery_charge")} value={form.delivery_charge} inputMode="decimal" disabled={readOnly} onChange={(v) => set("delivery_charge", v)} />
        <FormField error={errorText("f-pay")} onBlur={checkField("f-pay")} id="f-pay" label={t("suppliers.f.payment_terms_days")} value={form.payment_terms_days} inputMode="numeric" disabled={readOnly} onChange={(v) => set("payment_terms_days", v)} />
        <FormField error={errorText("f-rel")} onBlur={checkField("f-rel")} id="f-rel" label={t("suppliers.f.reliability")} value={form.reliability} inputMode="numeric" disabled={readOnly} onChange={(v) => set("reliability", v)} />
        <FormField error={errorText("f-sched")} onBlur={checkField("f-sched")} id="f-sched" label={t("suppliers.f.delivery_schedule")} value={form.delivery_schedule} disabled={readOnly} onChange={(v) => set("delivery_schedule", v)} />
      </div>

      <div className="mmi-cluster mmi-cluster--loose mmi-mb-4">
        {weekdays("suppliers.f.order_days", "order_days")}
        {weekdays("suppliers.f.delivery_weekdays", "delivery_weekdays")}
      </div>

      <div className="mmi-mb-4">
        <label className="mmi-mr-5">
          <input type="checkbox" disabled={readOnly} checked={form.preferred} onChange={(e) => set("preferred", e.target.checked)} /> {t("suppliers.f.preferred")}
        </label>
        <label>
          <input type="checkbox" disabled={readOnly} checked={form.disabled} onChange={(e) => set("disabled", e.target.checked)} /> {t("suppliers.f.disabled")}
        </label>
      </div>

      <fieldset className="mmi-mb-4">
        <legend className="mmi-strong">{t("suppliers.discounts")}</legend>
        {form.discounts.map((d, i) => (
          <div className="mmi-cluster mmi-mb-2" key={i}>
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
            <FormField error={errorText(`d-thr-${i}`)} onBlur={checkField(`d-thr-${i}`)} id={`d-thr-${i}`} label={`${t("suppliers.discount.threshold")} ${i + 1}`} value={d.threshold} inputMode="decimal" disabled={readOnly}
              onChange={(v) => set("discounts", form.discounts.map((x, j) => (j === i ? { ...x, threshold: v } : x)))} />
            <FormField error={errorText(`d-val-${i}`)} onBlur={checkField(`d-val-${i}`)} id={`d-val-${i}`} label={`${t("suppliers.discount.value")} ${i + 1}`} value={d.value} inputMode="decimal" disabled={readOnly}
              onChange={(v) => set("discounts", form.discounts.map((x, j) => (j === i ? { ...x, value: v } : x)))} />
            {!readOnly && (
              <Button variant="secondary" onClick={() => set("discounts", form.discounts.filter((_, j) => j !== i))}>
                {t("suppliers.discount.remove")} {i + 1}
              </Button>
            )}
          </div>
        ))}
        {!readOnly && form.discounts.length < MAX_DISCOUNT_TIERS && (
          <Button variant="secondary"
            onClick={() => set("discounts", [...form.discounts, { kind: "percent", basis: "order_value", threshold: "", value: "" }])}>
            {t("suppliers.discount.add")}
          </Button>
        )}
      </fieldset>

      {!readOnly && (
        <>
          <div className="mmi-cluster mmi-mb-4">
            <FormField id="f-from" type="date" label={t("suppliers.f.valid_from")} value={form.valid_from} onChange={(v) => set("valid_from", v)} />
            <FormField id="f-to" type="date" label={t("suppliers.f.valid_to")} value={form.valid_to} onChange={(v) => set("valid_to", v)} />
            <FormField id="f-reason" label={t("suppliers.f.reason")} value={form.reason} onChange={(v) => set("reason", v)} />
          </div>
          <PageActions>
            <Button onClick={() => void save()}>{t("suppliers.save")}</Button>
          </PageActions>
        </>
      )}

      {view && view.history.length > 0 && (
        <div className="mmi-mt-5">
          <h4 className="mmi-mb-2">{t("suppliers.history")}</h4>
          <DataTable
            ariaLabel={t("a11y.history_table")}
            rows={[...view.history].reverse()}
            rowKey={(h) => h.version}
            columns={[
              { id: "version", header: t("suppliers.history.version"), cell: (h) => h.version, sortValue: (h) => h.version, align: "end" },
              { id: "from", header: t("suppliers.history.from"), cell: (h) => formatDate(new Date(h.valid_from)), sortValue: (h) => h.valid_from },
              { id: "source", header: t("suppliers.history.source"), cell: (h) => <StatusBadge domain="tag" code={`source_${h.source}`} label={t(`suppliers.source.${h.source}`)} />, sortValue: (h) => h.source },
              { id: "by", header: t("suppliers.history.by"), cell: (h) => h.changed_by, sortValue: (h) => h.changed_by },
              { id: "reason", header: t("suppliers.history.reason"), cell: (h) => h.reason ?? "" },
            ]}
          />
        </div>
      )}
    </Card>
  );
};
