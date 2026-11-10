import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, QueueItem } from "../../api/client";
import { useActionNotice } from "../../ui/NoticeProvider";
import { Button } from "../../ui/Button";
import { Card as Panel } from "../../ui/Card";
import { DataTable } from "../../ui/DataTable";
import { canRetryItem } from "./opsModel";

/** One list for role-mirror items, import jobs, forecast runs and queue dead letters, with a safe retry. */
export const QueuePanel: React.FC = () => {
  const { t } = useTranslation();
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [, setNotice] = useActionNotice();

  const load = useCallback(async () => {
    try {
      setItems((await api.getQueue()).items);
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  }, [t]);
  useEffect(() => {
    void load();
  }, [load]);

  const retry = async (i: QueueItem & { kind: "mirror" | "import" | "forecast" }) => {
    setError(null);
    try {
      await api.retryQueueItem(i.kind, i.id);
      setNotice(t("admin.queue.retry_done"));
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
    await load();
  };

  return (
    <Panel className="mmi-mb-4" aria-label={t("admin.queue.title")}>
      <h4>{t("admin.queue.title")}</h4>
      {error && <p className="mmi-error" role="alert">{error}</p>}
      {items && (items.length === 0 ? <p>{t("admin.queue.empty")}</p> : (
        <DataTable
          ariaLabel={t("admin.queue.title")}
          rows={items}
          rowKey={(i) => `${i.kind}:${i.id}`}
          columns={[
            { id: "kind", header: t("admin.queue.kind"), cell: (i) => t(`admin.queue.kind.${i.kind}`), sortValue: (i) => i.kind },
            { id: "id", header: t("admin.queue.id"), cell: (i) => (i.id.length > 24 ? i.id.slice(0, 8) : i.id), sortValue: (i) => i.id },
            { id: "state", header: t("admin.queue.state"), cell: (i) => <>{t(`admin.queue.state.${i.state}`)}{i.stale ? ` (${t("admin.queue.stale")})` : ""}</>, sortValue: (i) => i.state },
            { id: "attempts", header: t("admin.queue.attempts"), cell: (i) => i.attempts, sortValue: (i) => i.attempts, align: "end" },
            { id: "reason", header: t("admin.queue.reason"), cell: (i) => (i.reason_code ? t(`admin.queue.reason.${i.reason_code}`, { defaultValue: t(`errors.${i.reason_code}`, { defaultValue: i.reason_code }) }) : "—") },
            { id: "retry", header: "", cell: (i) => canRetryItem(i) && <Button variant="secondary" onClick={() => void retry(i)} aria-label={`${t("admin.queue.retry")} ${i.id}`}>{t("admin.queue.retry")}</Button> },
          ]}
        />
      ))}
    </Panel>
  );
};
