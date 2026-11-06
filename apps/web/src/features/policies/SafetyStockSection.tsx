import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, errorMessage, OverrideRequest, SegmentHistoryRow, StockingSetting } from "../../api/client";
import { formatDate } from "../../i18n/formatters";
import { Field } from "../suppliers/Field";
import { canDecideOverrides, canEditPolicies, parseId } from "./policiesModel";

interface Props {
  roles: string[];
}

export const SafetyStockSection: React.FC<Props> = ({ roles }) => {
  const { t } = useTranslation();
  const [variantText, setVariantText] = useState("");
  const [variant, setVariant] = useState<number | null>(null);
  const [recommended, setRecommended] = useState<number | null | undefined>(undefined);
  const [stocking, setStocking] = useState<StockingSetting | null>(null);
  const [mode, setMode] = useState("standard");
  const [floor, setFloor] = useState("0");
  const [history, setHistory] = useState<SegmentHistoryRow[] | null>(null);
  const [queue, setQueue] = useState<OverrideRequest[]>([]);
  const [field, setField] = useState("safety_stock");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const canEdit = canEditPolicies(roles);
  const canDecide = canDecideOverrides(roles);

  const fail = useCallback((err: unknown) => setError(errorMessage(err, t("common.error"))), [t]);
  const loadQueue = useCallback(async () => {
    try {
      setQueue(await api.getOverrides("pending"));
    } catch (err) {
      fail(err);
    }
  }, [fail]);
  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const lookup = async () => {
    setError(null);
    setNotice(null);
    const id = parseId(variantText);
    if (id === null) return setError(t("policies.variant_invalid"));
    try {
      const [rec, st, hist] = await Promise.all([api.getRecommendation(id), api.getStocking(id), api.getSegmentHistory(id)]);
      setVariant(id);
      setRecommended(rec.safety_stock);
      setStocking(st);
      setMode(st.stocking_mode);
      setFloor(String(st.min_floor_units));
      setHistory(hist.history);
    } catch (err) {
      fail(err);
    }
  };

  const request = async () => {
    setError(null);
    setNotice(null);
    const requested = /^\d+$/.test(value.trim()) ? Number(value.trim()) : null;
    if (variant === null || requested === null) return setError(t("policies.invalid_field", { field: t("safety.requested") }));
    try {
      await api.createOverride({ variant_id: variant, field, requested_value: requested, reason });
      setNotice(t("safety.requested_ok"));
      setValue("");
      setReason("");
      await loadQueue();
    } catch (err) {
      fail(err);
    }
  };

  const decide = async (id: string, action: "approve" | "reject") => {
    setError(null);
    setNotice(null);
    try {
      await api.decideOverride(id, action);
      setNotice(t("safety.decided"));
    } catch (err) {
      fail(err);
    }
    await loadQueue();
  };

  const saveStocking = async () => {
    setError(null);
    setNotice(null);
    if (variant === null || !/^\d+$/.test(floor.trim())) return setError(t("policies.invalid_field", { field: t("safety.floor") }));
    try {
      const r = await api.putStocking(variant, { stocking_mode: mode, min_floor_units: Number(floor.trim()) }, stocking?.revision ?? 0);
      setNotice(t("safety.stocking_saved", { revision: r.revision }));
      setStocking(await api.getStocking(variant));
    } catch (err) {
      if (err instanceof ApiError && err.code === "revision_conflict") setStocking(await api.getStocking(variant));
      fail(err);
    }
  };

  return (
    <div>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}

      <h3>{t("safety.queue")}</h3>
      {queue.length === 0 ? (
        <p>{t("safety.queue_empty")}</p>
      ) : (
        <ul>
          {queue.map((q) => (
            <li key={q.id}>
              {t("safety.queue_row", { variant: q.variant_id, field: t(`safety.field.${q.field}`), recommended: q.recommended_value, requested: q.requested_value, by: q.requested_by })} — {q.reason}
              {canDecide && (
                <>
                  {" "}
                  <button type="button" className="mmi-btn mmi-btn-sm mmi-btn-primary" onClick={() => void decide(q.id, "approve")}>
                    {t("safety.approve")}
                  </button>{" "}
                  <button type="button" className="mmi-btn mmi-btn-sm mmi-btn-secondary" onClick={() => void decide(q.id, "reject")}>
                    {t("safety.reject")}
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      <div style={{ display: "flex", gap: "0.75rem", alignItems: "end", flexWrap: "wrap" }}>
        <Field id="safety-variant" label={t("policies.variant")} value={variantText} onChange={setVariantText} inputMode="numeric" />
        <button type="button" className="mmi-btn mmi-btn-secondary" onClick={() => void lookup()}>
          {t("policies.lookup")}
        </button>
      </div>

      {variant !== null && (
        <>
          <p>{recommended === null || recommended === undefined ? t("safety.recommended_none") : t("safety.recommended", { value: recommended })}</p>

          {canEdit && (
            <fieldset>
              <legend>{t("safety.request_title")}</legend>
              <label htmlFor="safety-field">{t("safety.field")}</label>
              <select id="safety-field" value={field} onChange={(e) => setField(e.target.value)}>
                {["safety_stock", "min", "max"].map((f) => (
                  <option key={f} value={f}>
                    {t(`safety.field.${f}`)}
                  </option>
                ))}
              </select>
              <Field id="safety-value" label={t("safety.requested")} value={value} onChange={setValue} inputMode="numeric" />
              <Field id="safety-reason" label={t("safety.reason")} value={reason} onChange={setReason} />
              <button type="button" className="mmi-btn mmi-btn-primary" onClick={() => void request()}>
                {t("safety.request")}
              </button>
            </fieldset>
          )}

          <fieldset>
            <legend>{t("safety.stocking")}</legend>
            <label htmlFor="stock-mode">{t("safety.stocking")}</label>
            <select id="stock-mode" value={mode} disabled={!canEdit} onChange={(e) => setMode(e.target.value)}>
              {["standard", "always_stocked", "on_request"].map((m) => (
                <option key={m} value={m}>
                  {t(`safety.mode.${m}`)}
                </option>
              ))}
            </select>
            <Field id="stock-floor" label={t("safety.floor")} value={floor} onChange={setFloor} inputMode="numeric" disabled={!canEdit} />
            <p className="mmi-muted">{t("safety.stocking_help")}</p>
            {canEdit && (
              <button type="button" className="mmi-btn mmi-btn-primary" onClick={() => void saveStocking()}>
                {t("safety.stocking_save")}
              </button>
            )}
          </fieldset>

          <h4>{t("safety.history")}</h4>
          {history && history.length === 0 && <p>{t("safety.history_empty")}</p>}
          <ul>
            {(history ?? []).map((h, i) => (
              <li key={i}>
                {t("safety.history_row", {
                  when: formatDate(h.changed_at), abc: h.abc, xyz: h.xyz, pattern: h.pattern, critical: h.critical ? t("safety.critical_suffix") : "",
                  reason: t(`safety.reason_key.${h.reason_key}`, { defaultValue: h.reason_key }),
                })}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
};
