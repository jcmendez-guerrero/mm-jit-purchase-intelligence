import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, PolicyAuditItem } from "../../api/client";
import { formatDateTime } from "../../i18n/formatters";
import { Button } from "../../ui/Button";
import { DataTable } from "../../ui/DataTable";

/** A short "field: value" list of the values an audit event holds; empty values and the scope bookkeeping are left out. */
const HIDDEN = new Set(["scope", "key", "valid_from"]);
const summary = (v: unknown): string => {
  if (v === null || typeof v !== "object") return "—";
  const parts = Object.entries(v as Record<string, unknown>).filter(([k, x]) => !HIDDEN.has(k) && x !== null && x !== undefined && x !== "").map(([k, x]) => `${k}: ${String(x)}`);
  return parts.length === 0 ? "—" : parts.join(", ");
};

/** Who changed which rule, and who was refused. Admin only; the gateway never sends free-text detail. */
export const PolicyAudit: React.FC = () => {
  const { t } = useTranslation();
  const [items, setItems] = useState<PolicyAuditItem[] | null>(null);
  const [unavailable, setUnavailable] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const r = await api.getPolicyAudit();
      setItems(r.items);
      setUnavailable(r.unavailable);
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <h3>{t("policies.audit.title")}</h3>
      <p className="mmi-muted">{t("policies.audit.help")}</p>
      {error && <p role="alert">{error}</p>}
      {unavailable.length > 0 && <p role="alert">{t("policies.audit.unavailable", { sources: unavailable.map((s) => t(`policies.audit.source.${s}`, { defaultValue: s })).join(", ") })}</p>}
      <Button variant="secondary" onClick={() => void load()}>
        {t("policies.audit.refresh")}
      </Button>
      {items !== null && (
        <DataTable
          ariaLabel={t("policies.audit.title")}
          rows={items}
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
      )}
    </div>
  );
};
