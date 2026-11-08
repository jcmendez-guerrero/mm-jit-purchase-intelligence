import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, errorMessage, SupplierSummary } from "../../api/client";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { FormField } from "../../ui/FormField";
import { CHANNELS, CLASSIFICATIONS, diff, EMPTY_FORM, FISCAL_TYPES, formFrom, SupplierForm as Form, toPayload, validate } from "./supplierModel";

interface Props {
  supplier?: SupplierSummary;
  onSaved: (s: SupplierSummary) => void;
  onCancel: () => void;
}

/** Create or edit a supplier. No tax id, bank data or notes exist here: the platform does not keep them (rule 7). */
export const SupplierForm: React.FC<Props> = ({ supplier, onSaved, onCancel }) => {
  const { t } = useTranslation();
  const original = supplier ? formFrom(supplier) : EMPTY_FORM;
  const [form, setForm] = useState<Form>(original);
  const [errors, setErrors] = useState<Partial<Record<keyof Form, string>>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState(false);
  const set = (key: keyof Form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const fieldError = (key: keyof Form) => (errors[key] ? t(errors[key] as string) : undefined);

  const save = async (confirmDuplicate: boolean) => {
    const problems = validate(form);
    setErrors(problems);
    if (Object.keys(problems).length > 0) return;
    setBusy(true);
    setMessage(null);
    try {
      let saved: SupplierSummary;
      if (supplier) {
        const changes = diff(original, form);
        if (Object.keys(changes).length === 0) {
          setMessage(t("suppliers.form.nothing"));
          return;
        }
        saved = await api.updateSupplier(supplier.id, changes, supplier.supplier_version ?? 1, confirmDuplicate);
      } else {
        saved = await api.createSupplier(toPayload(form), confirmDuplicate);
      }
      onSaved(saved);
    } catch (err) {
      if (err instanceof ApiError && err.code === "supplier_possible_duplicate") setDuplicate(true);
      else if (err instanceof ApiError && err.status === 412) setMessage(t("suppliers.form.conflict"));
      else setMessage(errorMessage(err, t("common.error")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card as="form" aria-labelledby="supplier-form-title" onSubmit={(e: React.FormEvent) => { e.preventDefault(); void save(false); }}>
      <h3 id="supplier-form-title">{supplier ? t("suppliers.form.edit_title") : t("suppliers.form.create_title")}</h3>
      <p className="mmi-muted mmi-text-sm">{t("suppliers.form.privacy")}</p>
      <FormField id="sup-name" label={t("suppliers.form.name")} value={form.name} onChange={set("name")} error={fieldError("name")} disabled={busy} />
      <div className="mmi-field">
        <label htmlFor="sup-fiscal" className="mmi-field__label">{t("suppliers.form.fiscal")}</label>
        <select id="sup-fiscal" value={form.fiscal_type} disabled={busy} onChange={(e) => set("fiscal_type")(e.target.value)}>
          {FISCAL_TYPES.map((x) => <option key={x} value={x}>{t(`suppliers.fiscal.${x}`)}</option>)}
        </select>
      </div>
      <FormField id="sup-country" label={t("suppliers.form.country")} value={form.country} onChange={set("country")} hint={t("suppliers.form.country_hint")} error={fieldError("country")} disabled={busy} />
      <FormField id="sup-currency" label={t("suppliers.form.currency")} value={form.currency} onChange={set("currency")} hint={t("suppliers.form.currency_hint")} error={fieldError("currency")} disabled={busy} />
      <FormField id="sup-days" label={t("suppliers.form.days")} value={form.payment_terms_days} onChange={set("payment_terms_days")} inputMode="numeric" error={fieldError("payment_terms_days")} disabled={busy} />
      <div className="mmi-field">
        <label htmlFor="sup-channel" className="mmi-field__label">{t("suppliers.form.channel")}</label>
        <select id="sup-channel" value={form.order_channel} disabled={busy} onChange={(e) => set("order_channel")(e.target.value)}>
          <option value="">{t("suppliers.channel.none")}</option>
          {CHANNELS.map((x) => <option key={x} value={x}>{t(`suppliers.channel.${x}`)}</option>)}
        </select>
      </div>
      <div className="mmi-field">
        <label htmlFor="sup-class" className="mmi-field__label">{t("suppliers.form.class")}</label>
        <select id="sup-class" value={form.classification} disabled={busy} onChange={(e) => set("classification")(e.target.value)}>
          {CLASSIFICATIONS.map((x) => <option key={x} value={x}>{t(`suppliers.class.${x}`)}</option>)}
        </select>
      </div>
      {duplicate && (
        <div role="alert" className="mmi-notice mmi-notice--warning">
          <p>{t("suppliers.form.duplicate")}</p>
          <Button type="button" variant="secondary" disabled={busy} onClick={() => void save(true)}>{t("suppliers.form.duplicate_confirm")}</Button>
        </div>
      )}
      {message && <p role="alert" className="mmi-error">{message}</p>}
      <div className="mmi-actions">
        <Button type="submit" disabled={busy}>{t("suppliers.form.save")}</Button>
        <Button type="button" variant="secondary" onClick={onCancel}>{t("common.cancel")}</Button>
      </div>
    </Card>
  );
};
