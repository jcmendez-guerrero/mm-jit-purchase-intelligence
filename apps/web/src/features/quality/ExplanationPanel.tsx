import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ForecastExplanation, api, errorMessage } from "../../api/client";
import { formatDate, formatNumber } from "../../i18n/formatters";
import { ScreenState } from "../../ui/ScreenState";

/**
 * Why this product's forecast is what it is (feature 012, FR-009, FR-010): the versions it came from, the demand class, the method and the
 * reason for it, eligibility, the days left out, and where the data came from. A product with no forecast shows no figure, only the fallback.
 */
export const ExplanationPanel: React.FC<{ sku: string }> = ({ sku }) => {
  const { t } = useTranslation();
  const [data, setData] = useState<ForecastExplanation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    api
      .getForecastExplanation(sku)
      .then((d) => alive && setData(d))
      .catch((err) => alive && (setData(null), setError(errorMessage(err, t("common.error")))))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [sku, t]);

  if (loading) return <ScreenState state="loading" skeletonShape="table" skeletonLines={3} />;
  if (error || !data) return <ScreenState state="error" errorHint={error ?? t("common.error")} />;

  const none = t("quality.product.none");
  const provenance = (["observed", "estimated", "manual"] as const)
    .filter((k) => (data.provenance_mix[k] ?? 0) > 0)
    .map((k) => t("quality.explain.provenance_value", { label: t(`quality.provenance.${k}`), n: data.provenance_mix[k] }))
    .join("; ");
  const reasons = data.eligibility_reason_codes.map((c) => t(`quality.explain.reason.${c}`, { defaultValue: c })).join("; ");

  return (
    <section className="mmi-section" aria-label={t("quality.explain.title")}>
      <h4>{t("quality.explain.title")}</h4>
      <dl className="mmi-definition">
        <dt>{t("quality.explain.versions")}</dt>
        <dd>
          {t("quality.explain.model")}: {data.model_version} · {t("quality.explain.dataset")}: {data.dataset_version_id ?? none} · {t("quality.explain.config")}: {data.config_version_id ?? none}
        </dd>
        {data.history_start && data.history_end && (
          <>
            <dt>{t("quality.explain.window")}</dt>
            <dd>{t("quality.explain.window_range", { from: formatDate(data.history_start), to: formatDate(data.history_end) })}</dd>
          </>
        )}
        <dt>{t("quality.explain.class")}</dt>
        <dd>
          {t("quality.explain.class_value", { abc: data.abc ?? "?", xyz: data.xyz ?? "?", pattern: data.pattern ? t(`quality.pattern.${data.pattern}`, { defaultValue: data.pattern }) : none })}
          {data.intermittent && <> · {t("quality.explain.intermittent_note")}</>}
        </dd>
        <dt>{t("quality.explain.method")}</dt>
        <dd>
          {t(`quality.method.${data.method}`, { defaultValue: data.method })} · {t(`quality.explain.method_reason.${data.method_reason_code}`, { defaultValue: data.method_reason_code })}
        </dd>
        <dt>{t("quality.explain.eligibility")}</dt>
        <dd>
          {t(`quality.eligibility.${data.eligibility}`)}
          {reasons && <> · {reasons}</>}
        </dd>
        {data.expected !== null && (
          <>
            <dt>{t("quality.explain.expected")}</dt>
            <dd>{formatNumber(Number(data.expected), 1)}</dd>
          </>
        )}
      </dl>
      {data.eligibility !== "eligible" && <p role="note">{t("quality.not_a_forecast")}</p>}
      <p className="mmi-muted">{t("quality.explain.censored", { n: data.censored_days })}</p>
      <p className="mmi-muted">{t("quality.explain.excluded", { n: data.anomaly_days_excluded })}</p>
      {provenance && (
        <p className="mmi-muted">
          {t("quality.explain.provenance")}: {provenance}
        </p>
      )}
    </section>
  );
};
