import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertRow, AlertsListing, api, errorMessage, OpsThresholds } from "../../api/client";
import { formatDateTime } from "../../i18n/formatters";
import { useActionNotice } from "../../ui/NoticeProvider";
import { Button } from "../../ui/Button";
import { Card as Panel } from "../../ui/Card";
import { DataTable } from "../../ui/DataTable";
import { canAcknowledge, SETTING_KEYS, sortAlerts, validateThresholds } from "./opsModel";

/** De-duplicated alerts (one per condition and subject) with acknowledgement, and the thresholds that decide them. */
export const AlertsPanel: React.FC = () => {
  const { t } = useTranslation();
  const [listing, setListing] = useState<AlertsListing | null>(null);
  const [settings, setSettings] = useState<OpsThresholds | null>(null);
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [, setNotice] = useActionNotice();

  const load = useCallback(async () => {
    try {
      const [l, s] = await Promise.all([api.getAlerts(), api.getOpsSettings()]);
      setListing(l);
      setSettings(s);
      setDraft({ ...s });
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  }, [t]);
  useEffect(() => {
    void load();
  }, [load]);

  const act = async (call: () => Promise<unknown>, done?: string) => {
    setError(null);
    try {
      await call();
      if (done) setNotice(done);
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
    await load();
  };

  const save = () => {
    const bad = validateThresholds(draft);
    if (bad) return setError(t(bad));
    void act(() => api.saveOpsSettings(draft), t("admin.alerts.settings_saved"));
  };

  return (
    <Panel className="mmi-mb-4" aria-label={t("admin.alerts.title")}>
      <h4>{t("admin.alerts.title")}</h4>
      {error && <p className="mmi-error" role="alert">{error}</p>}
      {listing && !listing.delivery_configured && <p role="status">{t("admin.alerts.no_channel")}</p>}
      {listing && (listing.items.length === 0 ? <p>{t("admin.alerts.empty")}</p> : (
        <DataTable
          ariaLabel={t("admin.alerts.title")}
          rows={sortAlerts(listing.items)}
          rowKey={(a: AlertRow) => a.id}
          columns={[
            { id: "cond", header: t("admin.alerts.condition"), cell: (a) => <>{t(`admin.alerts.cond.${a.condition_key}`)} <span className="mmi-muted">{a.subject}</span></> },
            { id: "sev", header: t("admin.alerts.severity"), cell: (a) => t(`admin.alerts.severity.${a.severity}`), sortValue: (a) => a.severity },
            { id: "state", header: t("admin.alerts.state"), cell: (a) => <>{t(`admin.alerts.state.${a.state}`)}{a.acknowledged_by ? ` · ${t("admin.alerts.acknowledged_by", { who: a.acknowledged_by })}` : ""}</>, sortValue: (a) => a.state },
            { id: "since", header: t("admin.alerts.since"), cell: (a) => formatDateTime(a.opened_at), sortValue: (a) => a.opened_at },
            { id: "ack", header: "", cell: (a) => canAcknowledge(a) && <Button variant="secondary" onClick={() => void act(() => api.acknowledgeAlert(a.id))} aria-label={`${t("admin.alerts.acknowledge")} ${t(`admin.alerts.cond.${a.condition_key}`)}`}>{t("admin.alerts.acknowledge")}</Button> },
          ]}
        />
      ))}
      {settings && (
        <form className="mmi-mt-3" onSubmit={(e) => { e.preventDefault(); save(); }}>
          <h5>{t("admin.alerts.settings")}</h5>
          {SETTING_KEYS.map((k) => (
            <div key={k} className="mmi-mb-2">
              <label>
                {t(`admin.alerts.setting.${k}`)}{" "}
                <input type="number" min={1} step={1} value={draft[k] ?? ""} onChange={(e) => setDraft({ ...draft, [k]: Number(e.target.value) })} />
              </label>
            </div>
          ))}
          <Button type="submit" variant="secondary">{t("common.save")}</Button>
        </form>
      )}
    </Panel>
  );
};
