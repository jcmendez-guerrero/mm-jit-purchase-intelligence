import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, AUDIT_SCOPES, errorMessage, PolicyAuditPage, PolicyAuditQuery } from "../../api/client";
import { formatDateTime } from "../../i18n/formatters";
import { Button } from "../../ui/Button";
import { DataTable } from "../../ui/DataTable";
import { FormField } from "../../ui/FormField";

/** A short "field: value" list of the values an audit event holds; empty values and the scope bookkeeping are left out. */
const HIDDEN = new Set(["scope", "key", "valid_from"]);
const summary = (v: unknown): string => {
  if (v === null || typeof v !== "object") return "—";
  const parts = Object.entries(v as Record<string, unknown>).filter(([k, x]) => !HIDDEN.has(k) && x !== null && x !== undefined && x !== "").map(([k, x]) => `${k}: ${String(x)}`);
  return parts.length === 0 ? "—" : parts.join(", ");
};

/** Who changed which rule, and who was refused. Admin only; the gateway never sends free-text detail. Filtered by what changed, the outcome and the dates; 50 rows a page. */
export const PolicyAudit: React.FC = () => {
  const { t } = useTranslation();
  const [data, setData] = useState<PolicyAuditPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<PolicyAuditQuery>({});
  const [page, setPage] = useState(1);

  const load = useCallback(async (query: PolicyAuditQuery, nextPage: number) => {
    try {
      setError(null);
      setData(await api.getPolicyAudit({ ...query, page: nextPage }));
      setPage(nextPage);
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  }, [t]);

  useEffect(() => {
    void load({}, 1);
  }, [load]);

  const set = (patch: PolicyAuditQuery) => setFilters((f) => ({ ...f, ...patch }));
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div>
      <h3>{t("policies.audit.title")}</h3>
      <p className="mmi-muted">{t("policies.audit.help")}</p>
      {error && <p role="alert">{error}</p>}
      {data && data.unavailable.length > 0 && (
        <p role="alert">{t("policies.audit.unavailable", { sources: data.unavailable.map((s) => t(`policies.audit.source.${s}`, { defaultValue: s })).join(", ") })}</p>
      )}
      <div className="mmi-cluster" role="group" aria-label={t("policies.audit.filters")}>
        <div className="mmi-stack">
          <label htmlFor="audit-scope">{t("policies.audit.scope")}</label>
          <select id="audit-scope" value={filters.scope ?? ""} onChange={(e) => set({ scope: e.target.value })}>
            <option value="">{t("policies.audit.all")}</option>
            {AUDIT_SCOPES.map((s) => (
              <option key={s} value={s}>
                {t(`policies.audit.scope.${s}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="mmi-stack">
          <label htmlFor="audit-outcome">{t("policies.audit.outcome")}</label>
          <select id="audit-outcome" value={filters.outcome ?? ""} onChange={(e) => set({ outcome: e.target.value })}>
            <option value="">{t("policies.audit.all")}</option>
            <option value="accepted">{t("policies.audit.accepted")}</option>
            <option value="refused">{t("policies.audit.refused")}</option>
          </select>
        </div>
        <FormField id="audit-from" label={t("policies.audit.from")} type="date" value={filters.from ?? ""} onChange={(v) => set({ from: v })} />
        <FormField id="audit-to" label={t("policies.audit.to")} type="date" value={filters.to ?? ""} onChange={(v) => set({ to: v })} />
        <Button onClick={() => void load(filters, 1)}>{t("policies.audit.apply")}</Button>
      </div>
      {data !== null && (
        <>
          <DataTable
            ariaLabel={t("policies.audit.title")}
            rows={data.items}
            rowKey={(i) => `${i.at}|${i.action}|${i.entity_id ?? ""}|${i.actor}`}
            emptyTitle={t("policies.audit.empty")}
            columns={[
              { id: "at", header: t("policies.audit.at"), cell: (i) => formatDateTime(i.at), sortValue: (i) => i.at },
              { id: "actor", header: t("policies.audit.actor"), cell: (i) => i.actor, sortValue: (i) => i.actor },
              { id: "action", header: t("policies.audit.action"), cell: (i) => t(`policies.audit.action.${i.action}`, { defaultValue: i.action }), sortValue: (i) => i.action },
              { id: "target", header: t("policies.audit.target"), cell: (i) => i.entity_id ?? "—", sortValue: (i) => i.entity_id ?? "" },
              { id: "before", header: t("policies.audit.before"), cell: (i) => summary(i.before), sortValue: (i) => summary(i.before) },
              { id: "after", header: t("policies.audit.after"), cell: (i) => summary(i.after), sortValue: (i) => summary(i.after) },
              { id: "outcome", header: t("policies.audit.outcome"), cell: (i) => (i.outcome === "refused" ? `${t("policies.audit.refused")} (${i.reason_code ?? ""})` : t("policies.audit.accepted")), sortValue: (i) => i.outcome },
            ]}
          />
          <div className="mmi-cluster" role="navigation" aria-label={t("policies.audit.paging")}>
            <Button variant="secondary" disabled={page <= 1} onClick={() => void load(filters, page - 1)}>{t("policies.audit.previous")}</Button>
            <span>{t("policies.audit.page", { page, pages, total: data.total })}</span>
            <Button variant="secondary" disabled={page >= pages} onClick={() => void load(filters, page + 1)}>{t("policies.audit.next")}</Button>
          </div>
        </>
      )}
    </div>
  );
};
