import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminStatus, api, errorMessage, StatusCard } from "../../api/client";
import { formatCurrencyEUR, formatDate, formatDateTime, formatPercent } from "../../i18n/formatters";
import { canRerunJob, freshness, spendShare } from "./statusModel";

function Card<T>({ title, card, children }: { title: string; card: StatusCard<T>; children: (data: T) => React.ReactNode }) {
  const { t } = useTranslation();
  return (
    <section aria-label={title} className="mmi-card" style={{ marginBottom: "1rem" }}>
      <h4>{title}</h4>
      {card.ok ? children(card.data) : <p role="status">{t("admin.status.unavailable")}</p>}
    </section>
  );
}

export const AdminStatusScreen: React.FC = () => {
  const { t } = useTranslation();
  const [status, setStatus] = useState<AdminStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setStatus(await api.getAdminStatus());
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  }, [t]);
  useEffect(() => {
    void load();
  }, [load]);

  const act = async (call: () => Promise<unknown>) => {
    setError(null);
    setNotice(null);
    try {
      await call();
      await load();
      setNotice(t("admin.status.rerun_done"));                 // after the reload, which would otherwise clear it
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  };

  if (!status) return <p>{error ?? t("common.loading")}</p>;
  const now = new Date();
  const c = status.cost;
  return (
    <section aria-labelledby="admin-status-title" style={{ marginBottom: "1.5rem" }}>
      <h3 id="admin-status-title">{t("admin.status.title")} <button type="button" className="mmi-btn" onClick={() => void load()}>{t("admin.status.refresh")}</button></h3>
      {error && <p role="alert" className="mmi-error">{error}</p>}
      {notice && <p role="status">{notice}</p>}

      <Card title={t("admin.status.freshness")} card={status.freshness}>
        {(f) => (
          <div className="mmi-table-wrapper"><table className="mmi-table">
            <thead><tr><th>{t("admin.status.source")}</th><th>{t("admin.status.last")}</th><th>{t("admin.status.rows")}</th><th>{t("admin.status.quarantined")}</th><th>{t("common.status")}</th></tr></thead>
            <tbody>
              {[
                { key: "snapshots", last: f.stock_snapshots.latest_day, rows: f.stock_snapshots.rows, q: null as number | null },
                { key: "movements", last: f.movements.latest_at, rows: f.movements.rows, q: f.movements.quarantined },
                { key: "aggregates", last: f.aggregates.refreshed_at, rows: null as number | null, q: null as number | null },
              ].map((r) => (
                <tr key={r.key}>
                  <th scope="row">{t(`admin.status.source.${r.key}`)}</th>
                  <td>{r.last ? (r.last.length === 10 ? formatDate(r.last) : formatDateTime(r.last)) : "—"}</td>
                  <td>{r.rows ?? "—"}</td>
                  <td>{r.q ?? "—"}</td>
                  <td>{t(`admin.status.${freshness(r.last, now)}`)}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Card>

      <Card title={t("admin.status.jobs")} card={status.import_jobs}>
        {(d) => d.jobs.length === 0 ? <p>{t("admin.status.jobs_empty")}</p> : (
          <div className="mmi-table-wrapper"><table className="mmi-table">
            <thead><tr><th>{t("admin.status.job.dataset")}</th><th>{t("admin.status.job.state")}</th><th>{t("admin.status.job.error")}</th><th /></tr></thead>
            <tbody>
              {d.jobs.map((j) => (
                <tr key={j.id}>
                  <td>{j.name} (v{j.version})</td>
                  <td>{t(`admin.status.job.state.${j.state}`)}</td>
                  <td>{j.error_key ? t(`errors.${j.error_key}`, { defaultValue: j.error_key }) : "—"}</td>
                  <td>{canRerunJob(j.state) && <button type="button" className="mmi-btn" onClick={() => void act(() => api.rerunImportJob(j.id))} aria-label={`${t("admin.status.rerun")} ${j.name}`}>{t("admin.status.rerun")}</button>}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Card>

      <Card title={t("admin.status.runs")} card={status.model_runs}>
        {(d) => (
          <>
            {d.runs.length === 0 ? <p>{t("admin.status.runs_empty")}</p> : (
              <div className="mmi-table-wrapper"><table className="mmi-table">
                <thead><tr><th>{t("common.date")}</th><th>{t("common.status")}</th><th>{t("admin.status.run.through")}</th><th>{t("admin.status.run.eligible")}</th><th>{t("admin.status.run.dataset")}</th></tr></thead>
                <tbody>
                  {d.runs.map((r) => (
                    <tr key={r.id}><td>{formatDateTime(r.started_at)}</td><td>{t(`admin.status.run.status.${r.status}`, { defaultValue: r.status })}</td><td>{formatDate(r.through_day)}</td><td>{r.eligible} / {r.total}</td><td>{r.dataset_version_id ? r.dataset_version_id.slice(0, 8) : "—"}</td></tr>
                  ))}
                </tbody>
              </table></div>
            )}
            <button type="button" className="mmi-btn" onClick={() => void act(() => api.rerunForecast())}>{t("admin.status.rerun_forecast")}</button>
          </>
        )}
      </Card>

      <Card title={t("admin.status.policy")} card={status.policy_history}>
        {(rows) => rows.length === 0 ? <p>{t("admin.status.policy_empty")}</p> : (
          <div className="mmi-table-wrapper"><table className="mmi-table">
            <thead><tr><th>{t("admin.status.policy.variant")}</th><th>{t("admin.status.policy.status")}</th></tr></thead>
            <tbody>{rows.slice(0, 20).map((r) => <tr key={r.id}><td>{r.variant_id}</td><td>{t(`admin.status.policy.status.${r.status}`, { defaultValue: r.status })}</td></tr>)}</tbody>
          </table></div>
        )}
      </Card>

      <Card title={t("admin.status.mirror")} card={status.role_mirror}>
        {(m) => <p>{t("admin.status.mirror_text", { pending: m.pending, failed: m.failed, minutes: Math.ceil(m.oldest_pending_seconds / 60) })}</p>}
      </Card>

      <section aria-label={t("admin.status.cost")} className="mmi-card" style={{ marginBottom: "1rem" }}>
        <h4>{t("admin.status.cost")}</h4>
        <p>{c.estimate_eur > 0
          ? t("admin.status.cost_text", { estimate: formatCurrencyEUR(c.estimate_eur), budget: formatCurrencyEUR(c.budget_eur), share: formatPercent(spendShare(c.estimate_eur, c.budget_eur)) })
          : t("admin.status.cost_unknown")}</p>
        <p>{t("admin.status.guardrails", { min: c.guardrails.min_replicas, max: c.guardrails.max_replicas, par: c.guardrails.job_parallelism })}</p>
      </section>
    </section>
  );
};
