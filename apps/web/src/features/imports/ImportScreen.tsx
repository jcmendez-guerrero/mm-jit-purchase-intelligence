import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, SeedDataset, SeedDryRun, SeedJob, SeedQuarantineRow, SeedUpload, SeedValidation } from "../../api/client";
import { formatCurrencyEUR, formatDateTime } from "../../i18n/formatters";
import { FormField } from "../../ui/FormField";
import { ALL_FIELDS, canImport, fileProblem, hasLiveJob, isQueued, missingFields, REQUIRED_FIELDS, setMapping } from "./importsModel";
import { StatusBadge } from "../../ui/StatusBadge";
import { ScreenState } from "../../ui/ScreenState";
import { EmptyState } from "../../ui/EmptyState";
import { useActionNotice } from "../../ui/NoticeProvider";
import { ConfirmDialog } from "../../ui/ConfirmDialog";
import { Card } from "../../ui/Card";
import { Button } from "../../ui/Button";
import { UnsavedChangesPrompt } from "../../ui/UnsavedChangesPrompt";
import { PageActions } from "../../ui/PageActions";
import { DataTable } from "../../ui/DataTable";
import { Icon } from "../../ui/Icon";

interface Props {
  userRoles: string[];
}

const MAX_BYTES = 5 * 1024 * 1024;

export const ImportScreen: React.FC<Props> = ({ userRoles }) => {
  const { t } = useTranslation();
  const [datasets, setDatasets] = useState<SeedDataset[]>([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [upload, setUpload] = useState<SeedUpload | null>(null);
  const [map, setMap] = useState<Record<string, string>>({});
  const [validation, setValidation] = useState<SeedValidation | null>(null);
  const [quarantine, setQuarantine] = useState<SeedQuarantineRow[]>([]);
  const [dry, setDry] = useState<SeedDryRun | null>(null);
  const [ack, setAck] = useState(false);
  const [jobs, setJobs] = useState<SeedJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [confirming, setConfirming] = useState<"activate" | "rollback" | "reject" | null>(null);
  const [notice, setNotice] = useActionNotice();
  const canEdit = canImport(userRoles);

  const fail = useCallback((err: unknown) => setError(errorMessage(err, t("common.error"))), [t]);
  const loadList = useCallback(async () => {
    try {
      setLoadFailed(false);
      setDatasets((await api.getSeedDatasets()).datasets);
    } catch (err) {
      fail(err);
      setLoadFailed(true);
    } finally {
      setDatasetsLoading(false);
    }
  }, [fail]);
  const loadJobs = useCallback(async () => {
    try {
      setJobs((await api.getSeedJobs()).jobs);
    } catch (err) {
      fail(err);
    }
  }, [fail]);
  useEffect(() => {
    void loadList();
    void loadJobs();
  }, [loadList, loadJobs]);
  const live = hasLiveJob(jobs);
  useEffect(() => {
    if (!live) return;
    const timer = setInterval(() => {                       // while something runs in the background, refresh its status
      void loadJobs();
      void loadList();
    }, 5000);
    return () => clearInterval(timer);
  }, [live, loadJobs, loadList]);

  const clear = () => {
    setError(null);
    setNotice(null);
  };

  const doUpload = async () => {
    clear();
    if (!file) return;
    const problem = fileProblem(file.name, file.size, MAX_BYTES);
    if (problem) return setError(t(problem === "type" ? "imports.refused_type" : "imports.refused_size"));
    try {
      const r = await api.uploadSeed(file, name);
      setUpload(r);
      setMap(r.suggested_mapping);
      setValidation(null);
      setQuarantine([]);
      setDry(null);
      setAck(false);
      setNotice(t("imports.uploaded", { rows: r.row_count }));
      await loadList();
    } catch (err) {
      fail(err);
    }
  };

  const doValidate = async () => {
    clear();
    if (!upload) return;
    try {
      const v = await api.validateSeed(upload.id, map);
      if (isQueued(v)) {
        setNotice(t("imports.background", { rows: v.rows, limit: v.background_over_rows }));
        setValidation(null);
        await loadJobs();
        return;
      }
      setValidation(v);
      setQuarantine((await api.getSeedQuarantine(upload.id)).rows);
      setDry(null);
      await loadList();
    } catch (err) {
      fail(err);
    }
  };

  const doDry = async () => {
    clear();
    if (!upload) return;
    try {
      setDry(await api.dryRunSeed(upload.id));
    } catch (err) {
      fail(err);
    }
  };

  const doActivate = async () => {
    clear();
    if (!upload) return;
    try {
      await api.activateSeed(upload.id, ack);
      setNotice(t("imports.activated"));
      setUpload(null);
      setValidation(null);
      setDry(null);
      await loadList();
    } catch (err) {
      fail(err);
    }
  };

  const doReject = async () => {
    clear();
    if (!upload) return;
    try {
      await api.rejectSeed(upload.id);
      setUpload(null);
      setValidation(null);
      await loadList();
    } catch (err) {
      fail(err);
    }
  };

  const doRollback = async () => {
    clear();
    try {
      await api.rollbackSeed();
      setNotice(t("imports.rolled_back"));
      await loadList();
    } catch (err) {
      fail(err);
    }
  };

  const missing = missingFields(map);

  const dirty = canEdit && upload !== null;

  return (
    <section aria-labelledby="imports-title">
      <UnsavedChangesPrompt dirty={dirty} />
      <ConfirmDialog
        open={confirming !== null}
        tone={confirming === "reject" ? "danger" : "default"}
        title={confirming === "rollback" ? t("imports.confirm.rollback.title") : confirming === "reject" ? t("imports.confirm.reject.title") : t("imports.confirm.activate.title")}
        {...(confirming === "activate" && validation ? { objectLabel: t("imports.confirm.activate.object", { accepted: validation.accepted }) } : {})}
        {...(confirming === "reject" && file ? { objectLabel: t("imports.confirm.reject.object", { name: file.name }) } : {})}
        effect={confirming === "rollback" ? t("imports.confirm.rollback.effect") : confirming === "reject" ? t("imports.confirm.reject.effect") : t("imports.confirm.activate.effect")}
        confirmLabel={confirming === "rollback" ? t("imports.rollback") : confirming === "reject" ? t("imports.reject") : t("imports.activate")}
        onCancel={() => setConfirming(null)}
        onConfirm={() => {
          const kind = confirming;
          setConfirming(null);
          if (kind === "activate") void doActivate();
          if (kind === "rollback") void doRollback();
          if (kind === "reject") void doReject();
        }}
      />
      <Card as="div">
        <h2 id="imports-title">{t("imports.title")}</h2>
        <p className="mmi-muted">{t("imports.subtitle")}</p>
        {error && !loadFailed && <p role="alert">{error}</p>}
        {loadFailed && <ScreenState state="error" errorHint={error ?? ""} onRetry={() => void (async () => { await loadList(); await loadJobs(); })()} />}
        {notice && <p role="status">{notice}</p>}
        {!canEdit && <p className="mmi-muted">{t("imports.read_only")}</p>}

        {canEdit && (
          <>
            <h3>{t("imports.step.template")}</h3>
            <a className="mmi-button mmi-button--secondary" href="/api/imports/template?format=csv" download>
              {t("imports.template_csv")}
            </a>{" "}
            <a className="mmi-button mmi-button--secondary" href="/api/imports/template?format=xlsx" download>
              {t("imports.template_xlsx")}
            </a>

            <h3>{t("imports.step.upload")}</h3>
            <p className="mmi-muted">{t("imports.limits", { mb: MAX_BYTES / (1024 * 1024) })}</p>
            <div className="mmi-cluster">
              <div className="mmi-stack">
                <label htmlFor="imp-file">{t("imports.file")}</label>
                <input id="imp-file" type="file" accept=".csv,.xlsx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              </div>
              <FormField id="imp-name" label={t("imports.name")} value={name} onChange={setName} />
              <PageActions>
                <Button disabled={!file} onClick={() => void doUpload()}>
                  {t("imports.upload")}
                </Button>
              </PageActions>
            </div>
          </>
        )}

        {canEdit && upload && (
          <>
            {upload.duplicate_of && <p role="note">{t("imports.duplicate")}</p>}
            <h3>{t("imports.step.map")}</h3>
            <div className="mmi-table-wrapper"><table aria-label={t("imports.step.map")} className="mmi-table">
              <thead>
                <tr>
                  <th>{t("imports.mapping.header")}</th>
                  <th>{t("imports.mapping.field")}</th>
                  <th>{t("imports.mapping.use")}</th>
                </tr>
              </thead>
              <tbody>
                {upload.headers.map((h) => (
                  <tr key={h}>
                    <td>{h}</td>
                    <td>
                      <select aria-label={`${t("imports.mapping.field")}: ${h}`} value={map[h] ?? ""} onChange={(e) => setMap(setMapping(map, h, e.target.value))}>
                        <option value="">{t("imports.mapping.none")}</option>
                        {ALL_FIELDS.map((f) => (
                          <option key={f} value={f}>
                            {t(`imports.field.${f}`)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>{(REQUIRED_FIELDS as readonly string[]).includes(map[h] ?? "") && <StatusBadge domain="tag" code="required" />}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
            {missing.length > 0 && (
              <ul className="mmi-missing-list" aria-label={t("imports.mapping.use")}>
                {missing.map((f) => (
                  <li key={f}>
                    <Icon name="error" />
                    {t("imports.mapping.missing_one", { field: t(`imports.field.${f}`) })}
                  </li>
                ))}
              </ul>
            )}
            {missing.length > 0 && <p role="alert" id="imp-missing">{t("imports.mapping.missing", { fields: missing.map((f) => t(`imports.field.${f}`)).join(", ") })}</p>}

            <h4>{t("imports.preview")}</h4>
            <div className="mmi-table-wrapper"><table aria-label={t("imports.preview")} className="mmi-table">
              <thead>
                <tr>
                  {Object.values(map).map((f) => (
                    <th key={f}>{t(`imports.field.${f}`)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {upload.preview.map((row, i) => (
                  <tr key={i}>
                    {Object.values(map).map((f) => (
                      <td key={f}>{row[f] ?? ""}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table></div>

            <h3>{t("imports.step.validate")}</h3>
            <Button disabled={missing.length > 0} {...(missing.length > 0 ? { "aria-describedby": "imp-missing" } : {})} onClick={() => void doValidate()}>
              {t("imports.validate")}
            </Button>{" "}
            <Button variant="secondary" onClick={() => setConfirming("reject")}>
              {t("imports.reject")}
            </Button>
          </>
        )}

        {canEdit && validation && upload && (
          <>
            <p role="status">{t("imports.validated", { accepted: validation.accepted, quarantined: validation.quarantined, origin: t(`imports.origin.${validation.origin}`) })}</p>
            <h4>{t("imports.quarantine")}</h4>
            {quarantine.length === 0 ? (
              <p>{t("imports.quarantine_none")}</p>
            ) : (
              <>
                <ul>
                  {quarantine.slice(0, 50).map((q) => (
                    <li key={q.row_no}>
                      {t("imports.quarantine_row", { row: q.row_no })}: {t(`errors.${q.reason_key}`, { defaultValue: q.reason_key })}
                    </li>
                  ))}
                </ul>
                <a className="mmi-button mmi-button--secondary" href={`/api/imports/${upload.id}/quarantine?format=csv`} download>
                  {t("imports.download_csv")}
                </a>{" "}
                <a className="mmi-button mmi-button--secondary" href={`/api/imports/${upload.id}/quarantine?format=xlsx`} download>
                  {t("imports.download_xlsx")}
                </a>
              </>
            )}

            <h3>{t("imports.step.dryrun")}</h3>
            <Button variant="secondary" onClick={() => void doDry()}>
              {t("imports.dryrun")}
            </Button>
            {dry && (
              <div role="region" aria-label={t("imports.step.dryrun")}>
                <p>{t("imports.dryrun_rows", dry.rows)}</p>
                <p>{t("imports.dryrun_gain", { count: dry.variants_gaining_history.length })}</p>
                <p>{t("imports.dryrun_sparse", { count: dry.skipped_sparse.length })}</p>
                {dry.overlap && (dry.overlap.days > 0 ? <p role="note">{t("imports.dryrun_overlap", dry.overlap)}</p> : <p>{t("imports.dryrun_overlap_none")}</p>)}
                {dry.backtest.status === "ok" ? (
                  <div>
                    <p>{t("imports.dryrun_backtest_title", { basis: t(`imports.dryrun_basis.${dry.backtest.basis === "actual_demand_only" ? "actual" : "active"}`) })}</p>
                    <ul>
                      <li>{t("imports.dryrun_backtest_before", { variants: dry.backtest.before.variants, cost: formatCurrencyEUR(dry.backtest.before.cost) })}</li>
                      <li>{t("imports.dryrun_backtest_after", { variants: dry.backtest.after.variants, cost: formatCurrencyEUR(dry.backtest.after.cost) })}</li>
                      <li>{t("imports.dryrun_backtest_delta", { value: formatCurrencyEUR(dry.backtest.delta_cost ?? "0") })}</li>
                    </ul>
                    <p className="mmi-muted">{t("imports.dryrun_backtest_note")}</p>
                  </div>
                ) : (
                  <p className="mmi-muted">{t("imports.dryrun_backtest_insufficient")}</p>
                )}
              </div>
            )}

            <h3>{t("imports.step.activate")}</h3>
            {upload.duplicate_of && (
              <label>
                <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> {t("imports.acknowledge_duplicate")}
              </label>
            )}
            <Button disabled={validation.accepted === 0} onClick={() => setConfirming("activate")}>
              {t("imports.activate")}
            </Button>
          </>
        )}

        <h3>{t("imports.jobs")}</h3>
        <Button variant="secondary" onClick={() => void loadJobs()}>
          {t("imports.jobs_refresh")}
        </Button>
        {jobs.length === 0 ? (
          <p>{t("imports.jobs_empty")}</p>
        ) : (
          <DataTable
            ariaLabel={t("imports.jobs")}
            rows={jobs}
            rowKey={(j) => j.id}
            columns={[
              { id: "dataset", header: t("imports.job.col.dataset"), cell: (j) => `v${j.version} · ${j.name}`, sortValue: (j) => j.name },
              { id: "stage", header: t("imports.job.col.stage"), cell: (j) => t(`imports.job.stage.${j.stage}`, { defaultValue: j.stage }), sortValue: (j) => j.stage },
              { id: "state", header: t("imports.job.col.state"), cell: (j) => t(`imports.job.state.${j.state}`), sortValue: (j) => j.state },
              { id: "queued", header: t("imports.job.col.queued"), cell: (j) => (j.queued_at ? formatDateTime(j.queued_at) : "—"), sortValue: (j) => j.queued_at ?? null },
              { id: "finished", header: t("imports.job.col.finished"), cell: (j) => (j.finished_at ? formatDateTime(j.finished_at) : "—"), sortValue: (j) => j.finished_at ?? null },
              { id: "error", header: t("imports.job.col.error"), cell: (j) => (j.error_key ? t(`errors.${j.error_key}`, { defaultValue: j.error_key }) : "—") },
            ]}
          />
        )}

        <h3>{t("imports.datasets")}</h3>
        {datasets.length === 0 ? (
          datasetsLoading ? <ScreenState state="loading" skeletonLines={3} /> : <EmptyState title={t("imports.none")} hint="" />
        ) : (
          <DataTable
            ariaLabel={t("imports.datasets")}
            rows={datasets}
            rowKey={(d) => d.id}
            columns={[
              { id: "version", header: t("imports.col.version"), cell: (d) => d.version, sortValue: (d) => d.version, align: "end" },
              { id: "status", header: t("imports.col.status"), cell: (d) => <StatusBadge domain="import" code={d.status} />, sortValue: (d) => d.status },
              { id: "origin", header: t("imports.col.origin"), cell: (d) => t(`imports.origin.${d.origin}`), sortValue: (d) => d.origin },
              { id: "rows", header: t("imports.col.rows"), cell: (d) => d.accepted, sortValue: (d) => d.accepted, align: "end" },
              { id: "by", header: t("imports.col.by"), cell: (d) => d.uploader, sortValue: (d) => d.uploader },
            ]}
          />
        )}
        {canEdit && datasets.some((d) => d.status === "active") && (
          <Button variant="secondary" onClick={() => setConfirming("rollback")}>
            {t("imports.rollback")}
          </Button>
        )}
      </Card>
    </section>
  );
};
