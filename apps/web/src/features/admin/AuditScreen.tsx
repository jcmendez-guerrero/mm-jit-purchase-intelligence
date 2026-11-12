import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, AuditQuery, AuditRow, AuditVerify, errorMessage } from "../../api/client";
import { formatDateTime } from "../../i18n/formatters";
import { useActionNotice } from "../../ui/NoticeProvider";
import { Button } from "../../ui/Button";
import { Card as Panel } from "../../ui/Card";
import { DataTable } from "../../ui/DataTable";

/** Admin audit viewer: filter, verify the hash chain and export. Rows hold identifiers, codes and times only. */
export const AuditScreen: React.FC = () => {
  const { t } = useTranslation();
  const [filters, setFilters] = useState<AuditQuery>({ outcome: "" });
  const [rows, setRows] = useState<AuditRow[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [verify, setVerify] = useState<AuditVerify | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [, setNotice] = useActionNotice();

  const load = useCallback(async (q: AuditQuery, next?: string) => {
    setError(null);
    try {
      const page = await api.getAudit(q, next);
      setRows((prev) => (next && prev ? [...prev, ...page.items] : page.items));
      setCursor(page.next_cursor);
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  }, [t]);
  useEffect(() => {
    void load({ outcome: "" });
  }, [load]);

  const doVerify = async () => {
    setError(null);
    try {
      setVerify(await api.verifyAudit());
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  };

  const doExport = async () => {
    setError(null);
    try {
      const { blob, truncated } = await api.exportAudit(filters);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "auditoria.csv";
      a.click();
      URL.revokeObjectURL(url);
      setNotice(truncated ? t("admin.audit.export_truncated") : t("admin.audit.export_done"));
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  };

  const set = (k: keyof AuditQuery) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setFilters({ ...filters, [k]: e.target.value });

  return (
    <Panel className="mmi-mb-4" aria-label={t("admin.audit.title")}>
      <h3 id="audit-title">{t("admin.audit.title")}</h3>
      <p className="mmi-muted mmi-text-sm mmi-mt-0">{t("admin.audit.subtitle")}</p>
      {error && <p className="mmi-error" role="alert">{error}</p>}
      <form onSubmit={(e) => { e.preventDefault(); void load(filters); }}>
        <label className="mmi-mr-3">{t("admin.audit.actor")} <input value={filters.actor ?? ""} onChange={set("actor")} maxLength={120} /></label>
        <label className="mmi-mr-3">{t("admin.audit.action")} <input value={filters.action ?? ""} onChange={set("action")} maxLength={40} /></label>
        <label className="mmi-mr-3">{t("admin.audit.outcome")}{" "}
          <select value={filters.outcome ?? ""} onChange={set("outcome")}>
            <option value="">{t("admin.audit.outcome.all")}</option>
            <option value="allowed">{t("admin.audit.outcome.allowed")}</option>
            <option value="refused">{t("admin.audit.outcome.refused")}</option>
          </select>
        </label>
        <label className="mmi-mr-3">{t("admin.audit.from")} <input type="date" value={filters.from ?? ""} onChange={set("from")} /></label>
        <label className="mmi-mr-3">{t("admin.audit.to")} <input type="date" value={filters.to ?? ""} onChange={set("to")} /></label>
        <Button type="submit" variant="secondary">{t("admin.audit.apply")}</Button>{" "}
        <Button type="button" variant="secondary" onClick={() => void doVerify()}>{t("admin.audit.verify")}</Button>{" "}
        <Button type="button" variant="secondary" onClick={() => void doExport()}>{t("admin.audit.export")}</Button>
      </form>
      {verify && <p role={verify.ok ? "status" : "alert"}>{verify.ok ? t("admin.audit.verify_ok", { count: verify.checked }) : t("admin.audit.verify_broken", { id: verify.first_broken_id })}</p>}
      {rows && (rows.length === 0 ? <p>{t("admin.audit.empty")}</p> : (
        <DataTable
          ariaLabel={t("admin.audit.title")}
          rows={rows}
          rowKey={(r) => r.id}
          pageSize={100}
          columns={[
            { id: "when", header: t("admin.audit.when"), cell: (r) => formatDateTime(r.ts), sortValue: (r) => r.ts },
            { id: "actor", header: t("admin.audit.actor"), cell: (r) => r.actor, sortValue: (r) => r.actor },
            { id: "action", header: t("admin.audit.action"), cell: (r) => r.action, sortValue: (r) => r.action },
            { id: "entity", header: t("admin.audit.entity"), cell: (r) => `${r.entity} ${r.entity_id}` },
            { id: "outcome", header: t("admin.audit.outcome"), cell: (r) => t(`admin.audit.outcome.${r.outcome}`), sortValue: (r) => r.outcome },
            { id: "reason", header: t("admin.audit.reason"), cell: (r) => (r.reason_code ? t(`errors.${r.reason_code}`, { defaultValue: r.reason_code }) : "—") },
          ]}
        />
      ))}
      {cursor && <Button variant="secondary" onClick={() => void load(filters, cursor)}>{t("admin.audit.more")}</Button>}
    </Panel>
  );
};
