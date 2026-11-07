import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, errorMessage, ForecastParameter } from "../../api/client";
import { Field } from "../suppliers/Field";
import { canEditPolicies } from "./policiesModel";

interface Props {
  roles: string[];
  parameters: ForecastParameter[];
  onChanged: () => void;
}

export const ForecastSection: React.FC<Props> = ({ roles, parameters, onChanged }) => {
  const { t } = useTranslation();
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const canEdit = canEditPolicies(roles);

  const fail = (err: unknown) => setError(errorMessage(err, t("common.error")));

  const save = async (p: ForecastParameter) => {
    setError(null);
    setNotice(null);
    const raw = (values[p.key] ?? p.value).trim().replace(",", ".");
    if (!/^\d+(\.\d+)?$/.test(raw)) return setError(t("policies.invalid_field", { field: t(`forecast.param.${p.key}`) }));
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

  return (
    <div>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <h3>{t("forecast.parameters")}</h3>
      {parameters.map((p) => (
        <div key={p.key} style={{ display: "flex", gap: "0.75rem", alignItems: "end", flexWrap: "wrap" }}>
          <Field id={`par-${p.key}`} label={t(`forecast.param.${p.key}`, { defaultValue: p.key })} value={values[p.key] ?? p.value.replace(".", ",")} disabled={!canEdit}
                 inputMode="decimal" hint={t("forecast.range", { min: p.min, max: p.max, default: p.default })} onChange={(v) => setValues({ ...values, [p.key]: v })} />
          <span className="mmi-muted">{t("forecast.revision", { revision: p.revision })}</span>
          {canEdit && (
            <button type="button" className="mmi-btn mmi-btn-primary" aria-label={`${t("forecast.save")}: ${t(`forecast.param.${p.key}`, { defaultValue: p.key })}`} onClick={() => void save(p)}>
              {t("forecast.save")}
            </button>
          )}
        </div>
      ))}
      {canEdit && (
        <button type="button" className="mmi-btn mmi-btn-secondary" onClick={() => void rerun()}>
          {t("forecast.rerun")}
        </button>
      )}
    </div>
  );
};
