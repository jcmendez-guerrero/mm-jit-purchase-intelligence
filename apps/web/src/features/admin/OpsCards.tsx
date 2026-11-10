import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, OpsSummary } from "../../api/client";
import { formatCurrencyEUR, formatDateTime } from "../../i18n/formatters";
import { Card as Panel } from "../../ui/Card";

/** Backup and Azure spend against the shared budget. A missing or old figure is said so, never shown as current. */
export const OpsCards: React.FC = () => {
  const { t } = useTranslation();
  const [data, setData] = useState<OpsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getOpsSummary().then(setData).catch((err) => setError(errorMessage(err, t("common.error"))));
  }, [t]);

  if (error) return <p className="mmi-error" role="alert">{error}</p>;
  if (!data) return null;
  const { backup, cost } = data;
  return (
    <>
      <Panel className="mmi-mb-4" aria-label={t("admin.ops.backup")}>
        <h4>{t("admin.ops.backup")}</h4>
        {!backup.ok ? <p role="status">{t("admin.ops.unavailable")}</p> : (
          <>
            <p>{backup.data.last_success_at ? t("admin.ops.backup_last", { when: formatDateTime(backup.data.last_success_at) }) : t("admin.ops.backup_none")}</p>
            <p role={backup.data.old ? "alert" : "status"}>{backup.data.old ? t("admin.ops.backup_old") : t("admin.ops.backup_ok")}</p>
            <p>{backup.data.last_restore_drill_at ? t("admin.ops.drill_last", { when: formatDateTime(backup.data.last_restore_drill_at) }) : t("admin.ops.drill_none")}</p>
            {backup.data.stale_snapshot && <p role="alert">{t("admin.ops.snapshot_stale")}</p>}
            <p className="mmi-muted mmi-text-sm">{t("admin.ops.captured", { when: formatDateTime(backup.data.captured_at) })}</p>
          </>
        )}
      </Panel>
      <Panel className="mmi-mb-4" aria-label={t("admin.ops.cost")}>
        <h4>{t("admin.ops.cost")}</h4>
        {!cost.ok ? <p role="status">{t("admin.ops.unavailable")}</p> : (
          <>
            <p>{t("admin.ops.cost_text", { mtd: formatCurrencyEUR(cost.data.month_to_date), projected: formatCurrencyEUR(cost.data.projected), budget: formatCurrencyEUR(cost.data.budget), pct: `${cost.data.projected_pct} %` })}</p>
            <p role={cost.data.level === "ok" ? "status" : "alert"}><strong>{t(`admin.ops.cost_level.${cost.data.level}`)}</strong></p>
            {cost.data.projection_is_estimate && <p className="mmi-muted">{t("admin.ops.cost_estimate")}</p>}
            {cost.data.stale_snapshot && <p role="alert">{t("admin.ops.snapshot_stale")}</p>}
            <p className="mmi-muted mmi-text-sm">{t("admin.ops.captured", { when: formatDateTime(cost.data.captured_at) })}</p>
          </>
        )}
      </Panel>
    </>
  );
};
