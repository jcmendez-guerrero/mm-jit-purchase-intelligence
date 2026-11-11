import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, EffectiveValue, errorMessage, OverrideRequest, SegmentHistoryRow, StockingSetting } from "../../api/client";
import { FormField } from "../../ui/FormField";
import { CategoryHistory } from "./CategoryHistory";
import { canDecideOverrides, canEditPolicies } from "./policiesModel";
import { useActionNotice } from "../../ui/NoticeProvider";
import { StatusBadge } from "../../ui/StatusBadge";
import { Button } from "../../ui/Button";
import { useFieldErrors } from "../../ui/useFieldErrors";
import { UnsavedChangesPrompt } from "../../ui/UnsavedChangesPrompt";

interface Props {
  roles: string[];
}

export const SafetyStockSection: React.FC<Props> = ({ roles }) => {
  const { t } = useTranslation();
  const [variantText, setVariantText] = useState("");
  const [variant, setVariant] = useState<string | null>(null);              // the SKU of the product being looked at
  const [recommended, setRecommended] = useState<number | null | undefined>(undefined);
  const [effective, setEffective] = useState<Record<string, EffectiveValue> | null>(null);
  const [stocking, setStocking] = useState<StockingSetting | null>(null);
  const [mode, setMode] = useState("standard");
  const [floor, setFloor] = useState("0");
  const [history, setHistory] = useState<SegmentHistoryRow[] | null>(null);
  const [queue, setQueue] = useState<OverrideRequest[]>([]);
  const [field, setField] = useState("safety_stock");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const fe = useFieldErrors();
  const [notice, setNotice] = useActionNotice();
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
    const id = variantText.trim();
    if (id === "" || id.length > 60) return setError(t("policies.variant_invalid"));
    try {
      const [rec, st, hist] = await Promise.all([api.getRecommendation(id), api.getStocking(id), api.getSegmentHistoryBySku(id)]);
      setVariant(st.sku ?? id);
      setRecommended(rec.safety_stock);
      setEffective(rec.effective ?? null);
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
    if (variant === null || requested === null) {
      const errs: Record<string, string> = {};
      if (variant === null) errs["safety-variant"] = t("policies.variant_invalid");
      if (requested === null) errs["safety-value"] = t("policies.invalid_field", { field: t("safety.requested") });
      fe.flag(errs);
      return setError(requested === null ? errs["safety-value"]! : errs["safety-variant"]!);
    }
    fe.clear();
    try {
      await api.createOverride({ sku: variant, field, requested_value: requested, reason });
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
    if (variant === null || !/^\d+$/.test(floor.trim())) {
      const errs: Record<string, string> = {};
      if (variant === null) errs["safety-variant"] = t("policies.variant_invalid");
      else errs["stock-floor"] = t("policies.invalid_field", { field: t("safety.floor") });
      fe.flag(errs);
      return setError(errs["stock-floor"] ?? errs["safety-variant"]!);
    }
    fe.clear();
    try {
      const r = await api.putStocking(variant, { stocking_mode: mode, min_floor_units: Number(floor.trim()) }, stocking?.revision ?? 0);
      setNotice(t("safety.stocking_saved", { revision: r.revision }));
      setStocking(await api.getStocking(variant));
    } catch (err) {
      if (err instanceof ApiError && err.code === "revision_conflict") setStocking(await api.getStocking(variant));
      fail(err);
    }
  };

  const dirty = canEdit && (value.trim() !== "" || reason.trim() !== "" || (stocking !== null && (mode !== stocking.stocking_mode || floor.trim() !== String(stocking.min_floor_units))));

  return (
    <div>
      <UnsavedChangesPrompt dirty={dirty} />
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}

      <h3>{t("safety.queue")}</h3>
      {queue.length === 0 ? (
        <p>{t("safety.queue_empty")}</p>
      ) : (
        <ul>
          {queue.map((q) => (
            <li key={q.id}>
              {t("safety.queue_row", { sku: q.sku ?? "—", field: t(`safety.field.${q.field}`), recommended: q.recommended_value, requested: q.requested_value, by: q.requested_by })} — {q.reason}
              {q.recommendation_changed && (
                <span role="note">
                  {" "}
                  <StatusBadge domain="tag" code="changed" label={t("safety.queue_changed", { was: q.recommended_value, now: q.current_recommended ?? "—" })} />
                </span>
              )}
              {canDecide && (
                <>
                  {" "}
                  <Button small onClick={() => void decide(q.id, "approve")}>
                    {t("safety.approve")}
                  </Button>{" "}
                  <Button variant="secondary" small onClick={() => void decide(q.id, "reject")}>
                    {t("safety.reject")}
                  </Button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="mmi-cluster">
        <FormField id="safety-variant" label={t("policies.variant")} value={variantText} onChange={(v) => { setVariantText(v); fe.clear("safety-variant"); }} error={fe.errors["safety-variant"]} />
        <Button variant="secondary" onClick={() => void lookup()}>
          {t("policies.lookup")}
        </Button>
      </div>

      {variant !== null && (
        <>
          <p>{recommended === null || recommended === undefined ? t("safety.recommended_none") : t("safety.recommended", { value: recommended })}</p>
          {effective && (
            <ul aria-label={t("safety.effective_title")}>
              {(["safety_stock", "min", "max"] as const).map((f) => {
                const e = effective[f];
                return e ? (
                  <li key={f}>
                    {e.value === null ? t("safety.effective_none", { field: t(`safety.field.${f}`) }) : t("safety.effective_row", { field: t(`safety.field.${f}`), value: e.value, source: t(`safety.effective_source.${e.source}`) })}
                  </li>
                ) : null;
              })}
            </ul>
          )}

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
              <FormField id="safety-value" label={t("safety.requested")} value={value} onChange={(v) => { setValue(v); fe.clear("safety-value"); }} error={fe.errors["safety-value"]} inputMode="numeric" />
              <FormField id="safety-reason" label={t("safety.reason")} value={reason} onChange={setReason} />
              <Button onClick={() => void request()}>
                {t("safety.request")}
              </Button>
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
            <FormField id="stock-floor" label={t("safety.floor")} value={floor} onChange={(v) => { setFloor(v); fe.clear("stock-floor"); }} error={fe.errors["stock-floor"]} inputMode="numeric" disabled={!canEdit} />
            <p className="mmi-muted">{t("safety.stocking_help")}</p>
            {canEdit && (
              <Button onClick={() => void saveStocking()}>
                {t("safety.stocking_save")}
              </Button>
            )}
          </fieldset>

          <h4>{t("safety.history")}</h4>
          <CategoryHistory history={history} />
        </>
      )}
    </div>
  );
};
