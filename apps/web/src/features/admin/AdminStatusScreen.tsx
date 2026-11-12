import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminStatus, api, errorMessage, StatusCard } from "../../api/client";
import { formatCurrencyEUR, formatDate, formatDateTime } from "../../i18n/formatters";
import { canRerunJob, freshness, STALE_AFTER_HOURS } from "./statusModel";
import { ScreenState } from "../../ui/ScreenState";
import { useActionNotice } from "../../ui/NoticeProvider";
import { Button } from "../../ui/Button";
import { Card as Panel } from "../../ui/Card";
import { DataTable } from "../../ui/DataTable";

function Card<T>({ title, card, children }: { title: string; card: StatusCard<T>; children: (data: T) => React.ReactNode }) {
  const { t } = useTranslation();
  return (
    <Panel className="mmi-mb-4" aria-label={title}>
      <h4>{title}</h4>
      {card.ok ? children(card.data) : <p role="status">{t("admin.status.unavailable")}</p>}
    </Panel>
  );
}

export const AdminStatusScreen: React.FC = () => {
  const { t } = useTranslation();
  const [status, setStatus] = useState<AdminStatus | null>(null);
  const [limitHours, setLimitHours] = useState(STALE_AFTER_HOURS);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useActionNotice();

  const load = useCallback(async () => {
    try {
      setStatus(await api.getAdminStatus());
      api.getOpsSettings().then((o) => setLimitHours(o.source_stale_hours)).catch(() => undefined);   // keeps the default if thresholds cannot be read
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

  if (!status) return error ? <ScreenState state="error" errorHint={error} onRetry={() => void load()} /> : <ScreenState state="loading" skeletonLines={4} />;
  const now = new Date();
  const c = status.cost;
  return (
    <section className="mmi-mb-5" aria-labelledby="admin-status-title">
      <h3 id="admin-status-title">{t("admin.status.title")} <Button variant="secondary" onClick={() => void load()}>{t("admin.status.refresh")}</Button></h3>
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
                  <td>{t(`admin.status.${freshness(r.last, now, limitHours)}`)}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Card>

      <Card title={t("admin.status.jobs")} card={status.import_jobs}>
        {(d) => d.jobs.length === 0 ? <p>{t("admin.status.jobs_empty")}</p> : (
          <DataTable
            ariaLabel={t("admin.status.jobs")}
            rows={d.jobs}
            rowKey={(j) => j.id}
            columns={[
              { id: "dataset", header: t("admin.status.job.dataset"), cell: (j) => `${j.name} (v${j.version})`, sortValue: (j) => j.name },
              { id: "state", header: t("admin.status.job.state"), cell: (j) => t(`admin.status.job.state.${j.state}`), sortValue: (j) => j.state },
              { id: "error", header: t("admin.status.job.error"), cell: (j) => (j.error_key ? t(`errors.${j.error_key}`, { defaultValue: j.error_key }) : "—") },
              { id: "rerun", header: "", cell: (j) => canRerunJob(j.state) && <Button variant="secondary" onClick={() => void act(() => api.rerunImportJob(j.id))} aria-label={`${t("admin.status.rerun")} ${j.name}`}>{t("admin.status.rerun")}</Button> },
            ]}
          />
        )}
      </Card>

      <Card title={t("admin.status.runs")} card={status.model_runs}>
        {(d) => (
          <>
            {d.runs.length === 0 ? <p>{t("admin.status.runs_empty")}</p> : (
              <DataTable
                ariaLabel={t("admin.status.runs")}
                rows={d.runs}
                rowKey={(r) => r.id}
                columns={[
                  { id: "date", header: t("common.date"), cell: (r) => formatDateTime(r.started_at), sortValue: (r) => r.started_at },
                  { id: "status", header: t("common.status"), cell: (r) => t(`admin.status.run.status.${r.status}`, { defaultValue: r.status }), sortValue: (r) => r.status },
                  { id: "through", header: t("admin.status.run.through"), cell: (r) => formatDate(r.through_day), sortValue: (r) => r.through_day },
                  { id: "eligible", header: t("admin.status.run.eligible"), cell: (r) => `${r.eligible} / ${r.total}`, sortValue: (r) => r.eligible, align: "end" },
                  { id: "dataset", header: t("admin.status.run.dataset"), cell: (r) => (r.dataset_version_id ? r.dataset_version_id.slice(0, 8) : "—") },
                ]}
              />
            )}
            <Button variant="secondary" onClick={() => void act(() => api.rerunForecast())}>{t("admin.status.rerun_forecast")}</Button>
          </>
        )}
      </Card>

      <Card title={t("admin.status.policy")} card={status.policy_history}>
        {(rows) => rows.length === 0 ? <p>{t("admin.status.policy_empty")}</p> : (
          <DataTable
            ariaLabel={t("admin.status.policy")}
            rows={rows.slice(0, 20)}
            rowKey={(r) => r.id}
            columns={[
              { id: "variant", header: t("admin.status.policy.variant"), cell: (r) => r.variant_id, sortValue: (r) => r.variant_id, align: "end" },
              { id: "status", header: t("admin.status.policy.status"), cell: (r) => t(`admin.status.policy.status.${r.status}`, { defaultValue: r.status }), sortValue: (r) => r.status },
            ]}
          />
        )}
      </Card>

      <Card title={t("admin.status.mirror")} card={status.role_mirror}>
        {(m) => <p>{t("admin.status.mirror_text", { pending: m.pending, failed: m.failed, minutes: Math.ceil(m.oldest_pending_seconds / 60) })}</p>}
      </Card>

      <Panel className="mmi-mb-4" aria-label={t("admin.status.cost")}>
        <h4>{t("admin.status.cost")}</h4>
        <p>{t("admin.status.cost_limits", { budget: formatCurrencyEUR(c.budget_eur) })}</p>
        <p>{t("admin.status.guardrails", { min: c.guardrails.min_replicas, max: c.guardrails.max_replicas, par: c.guardrails.job_parallelism })}</p>
      </Panel>
    </section>
  );
};
