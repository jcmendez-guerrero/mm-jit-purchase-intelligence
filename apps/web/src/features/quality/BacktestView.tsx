import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { BacktestJob, ProductBacktest, api, errorMessage } from "../../api/client";
import { formatPercent } from "../../i18n/formatters";
import { Button } from "../../ui/Button";
import { FormField } from "../../ui/FormField";
import { ScreenState } from "../../ui/ScreenState";

/**
 * How well the method chosen for a product would have forecast past periods, against the simple baseline (feature 012, FR-016, FR-018).
 * Reading a result is open to everyone; starting a run is for buyers and admins. A run never changes a forecast, proposal or stock figure.
 */
export const BacktestView: React.FC<{ userRoles: string[] }> = ({ userRoles }) => {
  const { t } = useTranslation();
  const [sku, setSku] = useState("");
  const [result, setResult] = useState<ProductBacktest | null>(null);
  const [job, setJob] = useState<BacktestJob | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canStart = userRoles.includes("buyer") || userRoles.includes("admin");
  const code = sku.trim();

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      setResult(await api.getProductBacktest(code));
    } catch (err) {
      setResult(null);
      setError(errorMessage(err, t("common.error")));
    } finally {
      setLoading(false);
    }
  };

  const start = async (scope: "catalogue" | "product") => {
    try {
      setRunning(true);
      setError(null);
      setJob(null);
      setJob(await api.startBacktest(scope, scope === "product" ? code : undefined));
      if (scope === "product") setResult(await api.getProductBacktest(code));
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    } finally {
      setRunning(false);
    }
  };

  const pct = (v: string | null) => (v === null ? t("quality.product.none") : formatPercent(v, 1));

  return (
    <section aria-labelledby="quality-backtest-title" className="mmi-section">
      <h3 id="quality-backtest-title">{t("quality.backtest.title")}</h3>
      <p className="mmi-muted">{t("quality.backtest.hint")}</p>
      <form
        className="mmi-actions"
        onSubmit={(e) => {
          e.preventDefault();
          if (code) void load();
        }}
      >
        <FormField id="backtest-sku" label={t("quality.product.sku")} value={sku} onChange={setSku} maxLength={60} />
        <Button type="submit" loading={loading} disabled={!code}>
          {t("quality.backtest.load")}
        </Button>
        {canStart && (
          <>
            <Button type="button" variant="secondary" loading={running} disabled={!code} onClick={() => void start("product")}>
              {t("quality.backtest.start_product")}
            </Button>
            <Button type="button" variant="secondary" loading={running} onClick={() => void start("catalogue")}>
              {t("quality.backtest.start_catalogue")}
            </Button>
          </>
        )}
      </form>

      {running && <p role="status">{t("quality.backtest.running")}</p>}
      {job && <p role="status">{job.reused ? t("quality.backtest.reused", { products: job.products }) : t("quality.backtest.done", { products: job.products })}</p>}
      {error && <ScreenState state="error" errorHint={error} />}

      {result && (
        <>
          {result.periods === 0 ? (
            <p>{t("quality.backtest.not_assessable")}</p>
          ) : (
            <dl className="mmi-definition">
              <dt>{t("quality.backtest.periods")}</dt>
              <dd>{result.periods}</dd>
              <dt>{t("quality.backtest.wape")}</dt>
              <dd>{pct(result.wape)}</dd>
              <dt>{t("quality.backtest.bias")}</dt>
              <dd>{pct(result.bias)}</dd>
              <dt>{t("quality.backtest.baseline_wape")}</dt>
              <dd>{pct(result.baseline_wape)}</dd>
              <dt>{t("quality.backtest.baseline_bias")}</dt>
              <dd>{pct(result.baseline_bias)}</dd>
            </dl>
          )}
          <p role="note">{result.beats_baseline ? t("quality.backtest.ok") : <strong>{t("quality.backtest.flag")}</strong>}</p>
          <p className="mmi-muted">
            {t("quality.backtest.model")}: {result.model_version}
          </p>
        </>
      )}
    </section>
  );
};
