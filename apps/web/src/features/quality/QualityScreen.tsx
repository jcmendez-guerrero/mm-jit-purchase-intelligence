import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ImportErrorItem, errorMessage } from "../../api/client";
import { formatDateTime } from "../../i18n/formatters";
import { DataTable, type Column } from "../../ui/DataTable";
import { EmptyState } from "../../ui/EmptyState";
import { ScreenState } from "../../ui/ScreenState";
import { StatusBadge } from "../../ui/StatusBadge";
import { ConfirmDialog } from "../../ui/ConfirmDialog";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";

interface Props {
  userRoles: string[];
}

export const QualityScreen: React.FC<Props> = ({ userRoles }) => {
  const { t } = useTranslation();
  const [items, setItems] = useState<ImportErrorItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [resolving, setResolving] = useState<{ item: ImportErrorItem; decision: "release" | "ignore" } | null>(null);

  const canResolve = userRoles.includes("buyer") || userRoles.includes("admin");

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getImportErrors();
      setItems(res.items || []);
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleResolve = async (id: number, decision: "release" | "ignore") => {
    try {
      setResolveError(null);
      await api.resolveImportError(id, decision);
      setItems((prev) => prev.filter((i) => i.id !== id));
    } catch (err) {
      setResolveError(errorMessage(err, t("common.error")));
    }
  };

  const columns: Column<ImportErrorItem>[] = [
    { id: "id", header: "ID", cell: (i) => `#${i.id}`, sortValue: (i) => i.id },
    { id: "variant", header: t("common.variant"), cell: (i) => <strong>{t("quality.variant_label", { id: i.variant_id })}</strong>, sortValue: (i) => i.variant_id },
    { id: "reason", header: t("quality.movement_reason"), cell: (i) => i.movement_reason_raw || "—", sortValue: (i) => i.movement_reason_raw ?? "" },
    {
      id: "codes",
      header: t("quality.codes"),
      cell: (i) => (
        <span className="mmi-badges">
          {(i.anomaly_codes || []).map((code: string) => (
            <StatusBadge key={code} domain="quarantine" code={code} />
          ))}
        </span>
      ),
    },
    { id: "created", header: t("quality.created_at"), cell: (i) => formatDateTime(i.created_at), sortValue: (i) => i.created_at },
    ...(canResolve
      ? [
          {
            id: "actions",
            header: t("common.actions"),
            cell: (i: ImportErrorItem) => (
              <div className="mmi-actions">
                <Button small onClick={() => setResolving({ item: i, decision: "release" })}>
                  {t("quality.release")}
                </Button>
                <Button variant="secondary" small onClick={() => setResolving({ item: i, decision: "ignore" })}>
                  {t("quality.ignore")}
                </Button>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <Card aria-labelledby="quality-title">
      <ConfirmDialog
        open={resolving !== null}
        tone={resolving?.decision === "ignore" ? "danger" : "default"}
        title={resolving?.decision === "ignore" ? t("quality.confirm.ignore.title") : t("quality.confirm.release.title")}
        objectLabel={resolving ? t("quality.confirm.object", { variant: t("quality.variant_label", { id: resolving.item.variant_id }), id: resolving.item.id }) : ""}
        effect={resolving?.decision === "ignore" ? t("quality.confirm.ignore.effect") : t("quality.confirm.release.effect")}
        confirmLabel={resolving?.decision === "ignore" ? t("quality.ignore") : t("quality.release")}
        onCancel={() => setResolving(null)}
        onConfirm={() => {
          const r = resolving;
          setResolving(null);
          if (r) void handleResolve(r.item.id, r.decision);
        }}
      />
      <h2 id="quality-title">{t("quality.title")}</h2>
      <p className="mmi-muted">{t("quality.quarantine_heading")}</p>

      {loading && <ScreenState state="loading" skeletonShape="table" skeletonLines={4} />}
      {error && <ScreenState state="error" errorHint={error} onRetry={() => void loadData()} />}
      {resolveError && (
        <p role="alert" className="mmi-error">
          {resolveError}
        </p>
      )}
      {!loading && !error && items.length === 0 && <EmptyState title={`✓ ${t("quality.quarantine_empty")}`} hint="" />}
      {!loading && items.length > 0 && <DataTable ariaLabel={t("quality.title")} columns={columns} rows={items} rowKey={(i) => i.id} rowTone={() => "warning"} />}
    </Card>
  );
};
