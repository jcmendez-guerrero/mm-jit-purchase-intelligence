import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, SeedDataset, SeedDryRun, SeedQuarantineRow, SeedUpload, SeedValidation } from "../../api/client";
import { Field } from "../suppliers/Field";
import { ALL_FIELDS, canImport, fileProblem, missingFields, setMapping } from "./importsModel";

interface Props {
  userRoles: string[];
}

const MAX_BYTES = 5 * 1024 * 1024;

export const ImportScreen: React.FC<Props> = ({ userRoles }) => {
  const { t } = useTranslation();
  const [datasets, setDatasets] = useState<SeedDataset[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [upload, setUpload] = useState<SeedUpload | null>(null);
  const [map, setMap] = useState<Record<string, string>>({});
  const [validation, setValidation] = useState<SeedValidation | null>(null);
  const [quarantine, setQuarantine] = useState<SeedQuarantineRow[]>([]);
  const [dry, setDry] = useState<SeedDryRun | null>(null);
  const [ack, setAck] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const canEdit = canImport(userRoles);

  const fail = useCallback((err: unknown) => setError(errorMessage(err, t("common.error"))), [t]);
  const loadList = useCallback(async () => {
    try {
      setDatasets((await api.getSeedDatasets()).datasets);
    } catch (err) {
      fail(err);
    }
  }, [fail]);
  useEffect(() => {
    void loadList();
  }, [loadList]);

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

  return (
    <section aria-labelledby="imports-title">
      <div className="mmi-card">
        <h2 id="imports-title">{t("imports.title")}</h2>
        <p className="mmi-muted">{t("imports.subtitle")}</p>
        {error && <p role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
        {!canEdit && <p className="mmi-muted">{t("imports.read_only")}</p>}

        {canEdit && (
          <>
            <h3>{t("imports.step.template")}</h3>
            <a className="mmi-btn mmi-btn-secondary" href="/api/imports/template?format=csv" download>
              {t("imports.template_csv")}
            </a>{" "}
            <a className="mmi-btn mmi-btn-secondary" href="/api/imports/template?format=xlsx" download>
              {t("imports.template_xlsx")}
            </a>

            <h3>{t("imports.step.upload")}</h3>
            <p className="mmi-muted">{t("imports.limits", { mb: MAX_BYTES / (1024 * 1024) })}</p>
            <div style={{ display: "flex", gap: "0.75rem", alignItems: "end", flexWrap: "wrap" }}>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <label htmlFor="imp-file">{t("imports.file")}</label>
                <input id="imp-file" type="file" accept=".csv,.xlsx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              </div>
              <Field id="imp-name" label={t("imports.name")} value={name} onChange={setName} />
              <button type="button" className="mmi-btn mmi-btn-primary" disabled={!file} onClick={() => void doUpload()}>
                {t("imports.upload")}
              </button>
            </div>
          </>
        )}

        {canEdit && upload && (
          <>
            {upload.duplicate_of && <p role="note">{t("imports.duplicate")}</p>}
            <h3>{t("imports.step.map")}</h3>
            <table aria-label={t("imports.step.map")} className="mmi-table">
              <thead>
                <tr>
                  <th>{t("imports.mapping.header")}</th>
                  <th>{t("imports.mapping.field")}</th>
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
                  </tr>
                ))}
              </tbody>
            </table>
            {missing.length > 0 && <p role="alert">{t("imports.mapping.missing", { fields: missing.map((f) => t(`imports.field.${f}`)).join(", ") })}</p>}

            <h4>{t("imports.preview")}</h4>
            <table aria-label={t("imports.preview")} className="mmi-table">
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
            </table>

            <h3>{t("imports.step.validate")}</h3>
            <button type="button" className="mmi-btn mmi-btn-primary" disabled={missing.length > 0} onClick={() => void doValidate()}>
              {t("imports.validate")}
            </button>{" "}
            <button type="button" className="mmi-btn mmi-btn-secondary" onClick={() => void doReject()}>
              {t("imports.reject")}
            </button>
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
                <a className="mmi-btn mmi-btn-secondary" href={`/api/imports/${upload.id}/quarantine?format=csv`} download>
                  {t("imports.download_csv")}
                </a>{" "}
                <a className="mmi-btn mmi-btn-secondary" href={`/api/imports/${upload.id}/quarantine?format=xlsx`} download>
                  {t("imports.download_xlsx")}
                </a>
              </>
            )}

            <h3>{t("imports.step.dryrun")}</h3>
            <button type="button" className="mmi-btn mmi-btn-secondary" onClick={() => void doDry()}>
              {t("imports.dryrun")}
            </button>
            {dry && (
              <div role="region" aria-label={t("imports.step.dryrun")}>
                <p>{t("imports.dryrun_rows", dry.rows)}</p>
                <p>{t("imports.dryrun_gain", { count: dry.variants_gaining_history.length })}</p>
                <p>{t("imports.dryrun_sparse", { count: dry.skipped_sparse.length })}</p>
                <p className="mmi-muted">{t("imports.dryrun_backtest")}</p>
              </div>
            )}

            <h3>{t("imports.step.activate")}</h3>
            {upload.duplicate_of && (
              <label>
                <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> {t("imports.acknowledge_duplicate")}
              </label>
            )}
            <button type="button" className="mmi-btn mmi-btn-primary" disabled={validation.accepted === 0} onClick={() => void doActivate()}>
              {t("imports.activate")}
            </button>
          </>
        )}

        <h3>{t("imports.datasets")}</h3>
        {datasets.length === 0 ? (
          <p>{t("imports.none")}</p>
        ) : (
          <table aria-label={t("imports.datasets")} className="mmi-table">
            <thead>
              <tr>
                <th>{t("imports.col.version")}</th>
                <th>{t("imports.col.status")}</th>
                <th>{t("imports.col.origin")}</th>
                <th>{t("imports.col.rows")}</th>
                <th>{t("imports.col.by")}</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={d.id}>
                  <td>{d.version}</td>
                  <td>{t(`imports.status.${d.status}`)}</td>
                  <td>{t(`imports.origin.${d.origin}`)}</td>
                  <td>{d.accepted}</td>
                  <td>{d.uploader}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {canEdit && datasets.some((d) => d.status === "active") && (
          <button type="button" className="mmi-btn mmi-btn-secondary" onClick={() => void doRollback()}>
            {t("imports.rollback")}
          </button>
        )}
      </div>
    </section>
  );
};
