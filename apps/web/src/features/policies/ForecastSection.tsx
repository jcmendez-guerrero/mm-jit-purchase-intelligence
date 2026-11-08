import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, errorMessage, ForecastParameter } from "../../api/client";
import { FormField } from "../../ui/FormField";
import { canEditPolicies } from "./policiesModel";
import { useActionNotice } from "../../ui/NoticeProvider";
import { Button } from "../../ui/Button";
import { useFieldErrors } from "../../ui/useFieldErrors";
import { UnsavedChangesPrompt } from "../../ui/UnsavedChangesPrompt";

interface Props {
  roles: string[];
  parameters: ForecastParameter[];
  onChanged: () => void;
}

export const ForecastSection: React.FC<Props> = ({ roles, parameters, onChanged }) => {
  const { t } = useTranslation();
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useActionNotice();
  const canEdit = canEditPolicies(roles);
  const fe = useFieldErrors();

  const fail = (err: unknown) => setError(errorMessage(err, t("common.error")));

  const save = async (p: ForecastParameter) => {
    setError(null);
    setNotice(null);
    const raw = (values[p.key] ?? p.value).trim().replace(",", ".");
    if (!/^\d+(\.\d+)?$/.test(raw)) {
      const message = t("policies.invalid_field", { field: t(`forecast.param.${p.key}`) });
      fe.flag({ [`par-${p.key}`]: message });
      return setError(message);
    }
    fe.clear();
    try {
      const r = await api.putParameter(p.key, raw, p.revision);
      setNotice(t("forecast.saved", { revision: r.revision }));
      onChanged();
    } catch (err) {
      if (err instanceof ApiError && err.code === "revision_conflict") onChanged();
      fail(err);
    }
  };

  const rerun = async () => {
    setError(null);
    setNotice(null);
    try {
      await api.requestForecast();
      setNotice(t("forecast.rerun_done"));
    } catch (err) {
      fail(err);
    }
  };

  const dirty = canEdit && parameters.some((p) => values[p.key] !== undefined && values[p.key]!.trim().replace(",", ".") !== p.value.replace(",", "."));

  return (
    <div>
      <UnsavedChangesPrompt dirty={dirty} />
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <h3>{t("forecast.parameters")}</h3>
      {parameters.map((p) => (
        <div className="mmi-cluster" key={p.key}>
          <FormField id={`par-${p.key}`} label={t(`forecast.param.${p.key}`, { defaultValue: p.key })} value={values[p.key] ?? p.value.replace(".", ",")} disabled={!canEdit}
                 inputMode="decimal" hint={t("forecast.range", { min: p.min, max: p.max, default: p.default })} error={fe.errors[`par-${p.key}`]} onChange={(v) => { setValues({ ...values, [p.key]: v }); fe.clear(`par-${p.key}`); }} />
          <span className="mmi-muted">{t("forecast.revision", { revision: p.revision })}</span>
          {canEdit && (
            <Button aria-label={`${t("forecast.save")}: ${t(`forecast.param.${p.key}`, { defaultValue: p.key })}`} onClick={() => void save(p)}>
              {t("forecast.save")}
            </Button>
          )}
        </div>
      ))}
      {canEdit && (
        <Button variant="secondary" onClick={() => void rerun()}>
          {t("forecast.rerun")}
        </Button>
      )}
    </div>
  );
};
