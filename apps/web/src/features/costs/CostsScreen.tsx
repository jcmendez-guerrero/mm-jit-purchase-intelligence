import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, CostRecord, CostWriteRecord, SupplierSummary, errorMessage } from "../../api/client";
import { formatCurrencyEUR, formatDate, formatPercent } from "../../i18n/formatters";
import { Field } from "../suppliers/Field";
import { canOverride, canRelease, canRequestUpdate, flagKey, parseAmount, parseOpening } from "./costsModel";

interface Props {
  userRoles: string[];
  userId?: string | undefined;
}

export const CostsScreen: React.FC<Props> = ({ userRoles, userId }) => {
  const { t } = useTranslation();
  const [costs, setCosts] = useState<CostRecord[]>([]);
  const [writes, setWrites] = useState<CostWriteRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [fixing, setFixing] = useState<Record<string, string>>({});
  const [overrideValue, setOverrideValue] = useState<Record<string, string>>({});
  const [overrideReason, setOverrideReason] = useState<Record<string, string>>({});
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([]);
  const [opening, setOpening] = useState({ supplier: "", product: "", variant: "", amount: "", recargo: true });

  const fail = useCallback((err: unknown) => setError(errorMessage(err, t("common.error"))), [t]);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [costList, writeList] = await Promise.all([api.getCosts(), api.getCostWrites()]);
      setCosts(costList);
      setWrites(writeList);
    } catch (err) {
      fail(err);
    } finally {
      setLoading(false);
    }
  }, [fail]);

  useEffect(() => {
    void load();
    void api.getSuppliers().then(setSuppliers).catch(() => setSuppliers([]));
  }, [load]);

  const openingInput = () => {
    if (!opening.supplier) {
      setError(t("costs.opening.no_supplier"));
      return null;
    }
    const p = parseOpening(opening.product, opening.variant, opening.amount);
    if ("invalid" in p) {
      setError(t("costs.opening.invalid", { field: t(`costs.opening.field.${p.invalid}`) }));
      return null;
    }
    return p;
  };

  const saveOpening = async () => {
    setError(null);
    setNotice(null);
    const p = openingInput();
    if (!p) return;
    await run(() => api.addOpeningCost({ variant_id: p.variantId, supplier_id: opening.supplier, amount: p.amount, includes_recargo: opening.recargo }), t("costs.opening.saved"));
  };

  const requestUpdate = async () => {
    setError(null);
    setNotice(null);
    const p = openingInput();
    if (!p) return;
    try {
      const r = await api.requestCostUpdate(p.productId, opening.supplier);
      setNotice(t(r.request_id ? "costs.opening.requested" : "costs.opening.not_applicable"));
    } catch (err) {
      fail(err);
    }
    await load();
  };

  const run = async (action: () => Promise<unknown>, done?: string) => {
    setError(null);
    setNotice(null);
    try {
      await action();
      if (done) setNotice(done);
    } catch (err) {
      fail(err);
    }
    await load();
  };

  const release = (w: CostWriteRecord) => run(() => api.approveCostWrite(w.id), t("costs.released"));

  const correct = (w: CostWriteRecord, variantId: number, lot: string) => {
    const key = `${w.id}:${variantId}:${lot}`;
    const amount = parseAmount(fixing[key] ?? "");
    if (amount === null) {
      fail(new ApiError(422, "negative_cost"));
      return Promise.resolve();
    }
    return run(
      () => api.correctLotCost({ variant_id: variantId, supplier_id: w.supplier_id, lot, amount, includes_recargo: true, source: "receipt_correction" }),
      t("costs.lot_corrected"),
    );
  };

  const override = (w: CostWriteRecord) => {
    const value = parseAmount(overrideValue[w.id] ?? "");
    if (value === null) {
      fail(new ApiError(422, "negative_value"));
      return Promise.resolve();
    }
    return run(() => api.overrideCostWrite(w.id, value, overrideReason[w.id] ?? ""), t("costs.override_saved"));
  };

  const pct = (v: string | null) => (v === null ? t("costs.margin_unavailable") : formatPercent(v, 1));

  return (
    <section aria-labelledby="costs-title">
      <div className="mmi-card">
        <h2 id="costs-title">{t("costs.title")}</h2>
        <p className="mmi-muted">{t("costs.subtitle")}</p>
        {loading && <p>{t("common.loading")}</p>}
        {error && <p role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}

        <h3>{t("costs.registered")}</h3>
        {!loading && costs.length === 0 && <p>{t("costs.none")}</p>}
        {costs.length > 0 && (
          <table aria-label={t("costs.registered")} className="mmi-table">
            <thead>
              <tr>
                <th>{t("common.product")}</th>
                <th>{t("common.supplier")}</th>
                <th>{t("common.cost")}</th>
                <th>{t("costs.source")}</th>
                <th>{t("costs.verified_at")}</th>
              </tr>
            </thead>
            <tbody>
              {costs.map((c) => (
                <tr key={c.id}>
                  <td>#{c.product_id}</td>
                  <td>{c.supplier_id}</td>
                  <td>{formatCurrencyEUR(c.cost_with_recargo)}</td>
                  <td>{c.source}</td>
                  <td>{formatDate(c.verified_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {canRequestUpdate(userRoles) && (
        <div className="mmi-card">
          <h3>{t("costs.opening.title")}</h3>
          <p className="mmi-muted">{t("costs.opening.help")}</p>
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "end" }}>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <label htmlFor="op-supplier">{t("costs.opening.supplier")}</label>
              <select id="op-supplier" value={opening.supplier} onChange={(e) => setOpening({ ...opening, supplier: e.target.value })}>
                <option value="">—</option>
                {suppliers.map((sp) => (
                  <option key={sp.id} value={sp.id}>
                    {sp.name}
                  </option>
                ))}
              </select>
            </div>
            <Field id="op-product" label={t("costs.opening.product")} value={opening.product} onChange={(v) => setOpening({ ...opening, product: v })} inputMode="numeric" />
            <Field id="op-variant" label={t("costs.opening.variant")} value={opening.variant} onChange={(v) => setOpening({ ...opening, variant: v })} inputMode="numeric" />
            <Field id="op-amount" label={t("costs.opening.amount")} value={opening.amount} onChange={(v) => setOpening({ ...opening, amount: v })} inputMode="decimal" />
            <label>
              <input type="checkbox" checked={opening.recargo} onChange={(e) => setOpening({ ...opening, recargo: e.target.checked })} /> {t("costs.opening.recargo")}
            </label>
          </div>
          <button type="button" className="mmi-btn mmi-btn-secondary" onClick={() => void saveOpening()}>
            {t("costs.opening.save")}
          </button>{" "}
          <button type="button" className="mmi-btn mmi-btn-primary" onClick={() => void requestUpdate()}>
            {t("costs.opening.request")}
          </button>
        </div>
      )}

      <div className="mmi-card">
        <h3>{t("costs.pending_writes")}</h3>
        <p className="mmi-muted">{t("costs.median_explained")}</p>
        {!loading && writes.length === 0 && <p>{t("costs.no_pending")}</p>}
        {writes.map((w) => (
          <article key={w.id} aria-label={t("costs.request_label", { product: w.product_id })} className="mmi-card">
            <h4>{t("costs.request_label", { product: w.product_id })}</h4>
            <p>
              {t("costs.value_sent")}: <strong>{formatCurrencyEUR(w.proposed_value)}</strong>
              {w.median_cost !== null && w.override && <span> · {t("costs.median_was", { value: formatCurrencyEUR(w.median_cost) })}</span>}
              {w.previous_siweb_value !== null && <span> · {t("costs.erp_current", { value: formatCurrencyEUR(w.previous_siweb_value) })}</span>}
            </p>
            <span className="mmi-badge">{t(`costs.status.${w.status}`, { defaultValue: w.status })}</span>
            {w.last_error && <p role="note">{w.last_error}</p>}

            <h5>{t("costs.lots_behind")}</h5>
            <table aria-label={t("costs.lots_behind")} className="mmi-table">
              <thead>
                <tr>
                  <th>{t("costs.lot")}</th>
                  <th>{t("common.quantity")}</th>
                  <th>{t("costs.lot_cost")}</th>
                  {userRoles.includes("buyer") && <th>{t("common.actions")}</th>}
                </tr>
              </thead>
              <tbody>
                {w.lots.map((l) => {
                  const key = `${w.id}:${l.variant_id}:${l.lot}`;
                  return (
                    <tr key={key}>
                      <td>{l.lot}</td>
                      <td>{l.quantity}</td>
                      <td>{formatCurrencyEUR(l.unit_cost)}</td>
                      {userRoles.includes("buyer") && (
                        <td>
                          <input
                            type="text"
                            inputMode="decimal"
                            aria-label={t("costs.correct_input", { lot: l.lot })}
                            value={fixing[key] ?? ""}
                            onChange={(ev) => setFixing({ ...fixing, [key]: ev.target.value })}
                          />
                          <button type="button" className="mmi-btn mmi-btn-sm" onClick={() => void correct(w, l.variant_id, l.lot)}>
                            {t("costs.correct_lot")}
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>

            <h5>{t("costs.margin_panel")}</h5>
            <ul>
              <li>{t("costs.pvp_used", { value: w.pvp_used === null ? t("costs.margin_unavailable") : formatCurrencyEUR(w.pvp_used) })}</li>
              {w.pvp_age_days != null && <li>{t("costs.pvp_age", { days: w.pvp_age_days })}</li>}
              <li>{t("costs.margin_before", { value: pct(w.margin_before) })}</li>
              <li>{t("costs.margin_after", { value: pct(w.margin_after) })}</li>
              {w.rule_flags.map((f) => (
                <li key={f} role="note">
                  {t(flagKey(f), { defaultValue: f })}
                </li>
              ))}
              {w.tips && (
                <li>
                  {t("costs.tips", { cap: formatPercent(w.tips.cap, 0), atCap: formatCurrencyEUR(w.tips.cost_at_cap), atMin: formatCurrencyEUR(w.tips.cost_at_minimum) })}
                </li>
              )}
            </ul>
            <p className="mmi-muted">{t("costs.pvp_assumption")}</p>

            {w.override && (
              <p role="note">
                {t("costs.override_info", { by: w.override.by, reason: w.override.reason })} {t("costs.override_other_buyer")}
              </p>
            )}

            {canOverride(userRoles, w) && (
              <fieldset>
                <legend>{t("costs.override_title")}</legend>
                <label>
                  {t("costs.override_value")}
                  <input type="text" inputMode="decimal" value={overrideValue[w.id] ?? ""} onChange={(ev) => setOverrideValue({ ...overrideValue, [w.id]: ev.target.value })} />
                </label>
                <label>
                  {t("costs.override_reason")}
                  <input type="text" value={overrideReason[w.id] ?? ""} onChange={(ev) => setOverrideReason({ ...overrideReason, [w.id]: ev.target.value })} />
                </label>
                <button type="button" className="mmi-btn mmi-btn-secondary" onClick={() => void override(w)}>
                  {t("costs.override_save")}
                </button>
              </fieldset>
            )}

            {canRelease(userRoles, userId, w) && (
              <button type="button" className="mmi-btn mmi-btn-primary" onClick={() => void release(w)}>
                {t("costs.send_write")}
              </button>
            )}
          </article>
        ))}
      </div>
    </section>
  );
};
