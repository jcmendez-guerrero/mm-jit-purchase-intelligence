import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, CostRecord, CostWriteRecord, SupplierSummary, errorMessage } from "../../api/client";
import { formatCurrencyEUR, formatDate, formatPercent } from "../../i18n/formatters";
import { FormField } from "../../ui/FormField";
import { canOverride, canRelease, canRequestUpdate, flagKey, parseAmount, parseOpening } from "./costsModel";
import { ScreenState } from "../../ui/ScreenState";
import { EmptyState } from "../../ui/EmptyState";
import { StatusBadge } from "../../ui/StatusBadge";
import { useActionNotice } from "../../ui/NoticeProvider";
import { ConfirmDialog } from "../../ui/ConfirmDialog";
import { Card } from "../../ui/Card";
import { Button } from "../../ui/Button";
import { useFieldErrors } from "../../ui/useFieldErrors";
import { UnsavedChangesPrompt } from "../../ui/UnsavedChangesPrompt";
import { DataTable } from "../../ui/DataTable";
import { PageActions } from "../../ui/PageActions";

interface Props {
  userRoles: string[];
  userId?: string | undefined;
}

export const CostsScreen: React.FC<Props> = ({ userRoles, userId }) => {
  const { t } = useTranslation();
  const [costs, setCosts] = useState<CostRecord[]>([]);
  const [writes, setWrites] = useState<CostWriteRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const fe = useFieldErrors();
  const [releasing, setReleasing] = useState<CostWriteRecord | null>(null);
  const [overriding, setOverriding] = useState<CostWriteRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useActionNotice();
  const [fixing, setFixing] = useState<Record<string, string>>({});
  const [overrideValue, setOverrideValue] = useState<Record<string, string>>({});
  const [overrideReason, setOverrideReason] = useState<Record<string, string>>({});
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([]);
  const [opening, setOpening] = useState({ supplier: "", product: "", variant: "", amount: "", recargo: true });

  const fail = useCallback((err: unknown) => setError(errorMessage(err, t("common.error"))), [t]);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setLoadFailed(false);
      const [costList, writeList] = await Promise.all([api.getCosts(), api.getCostWrites()]);
      setCosts(costList);
      setWrites(writeList);
    } catch (err) {
      fail(err);
      setLoadFailed(true);
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
      const message = t("costs.opening.invalid", { field: t(`costs.opening.field.${p.invalid}`) });
      setError(message);
      fe.flag({ [`op-${p.invalid}`]: message });
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

  /** Checks the value first, so the confirmation never opens for input the screen would refuse. */
  const askOverride = (w: CostWriteRecord) => {
    if (parseAmount(overrideValue[w.id] ?? "") === null) {
      fail(new ApiError(422, "negative_value"));
      return;
    }
    setOverriding(w);
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

  const dirty = opening.product.trim() !== "" || opening.variant.trim() !== "" || opening.amount.trim() !== "" || Object.values(overrideValue).some((v) => v.trim() !== "") || Object.values(overrideReason).some((v) => v.trim() !== "") || Object.values(fixing).some((v) => v.trim() !== "");

  return (
    <section aria-labelledby="costs-title">
      <UnsavedChangesPrompt dirty={dirty} />
      <ConfirmDialog
        open={overriding !== null}
        title={t("costs.confirm.override.title")}
        objectLabel={
          overriding
            ? t("costs.confirm.override.object", {
                product: t("costs.request_label", { product: overriding.product_id }),
                supplier: suppliers.find((s) => s.id === overriding.supplier_id)?.name ?? overriding.supplier_id,
                value: formatCurrencyEUR(parseAmount(overrideValue[overriding.id] ?? "") ?? "0"),
              })
            : ""
        }
        effect={t("costs.confirm.override.effect")}
        confirmLabel={t("costs.override_save")}
        onCancel={() => setOverriding(null)}
        onConfirm={() => {
          const w = overriding;
          setOverriding(null);
          if (w) void override(w);
        }}
      />
      <ConfirmDialog
        open={releasing !== null}
        title={t("costs.confirm.release.title")}
        objectLabel={
          releasing
            ? t("costs.confirm.release.object", {
                product: t("costs.request_label", { product: releasing.product_id }),
                supplier: suppliers.find((s) => s.id === releasing.supplier_id)?.name ?? releasing.supplier_id,
                value: formatCurrencyEUR(releasing.proposed_value),
              })
            : ""
        }
        effect={t("costs.confirm.release.effect")}
        confirmLabel={t("costs.send_write")}
        onCancel={() => setReleasing(null)}
        onConfirm={() => {
          const w = releasing;
          setReleasing(null);
          if (w) void release(w);
        }}
      />
      <Card as="div">
        <h2 id="costs-title">{t("costs.title")}</h2>
        <p className="mmi-muted">{t("costs.subtitle")}</p>
        {loading && <ScreenState state="loading" skeletonShape="table" skeletonLines={3} />}
        {error && !loadFailed && <p role="alert">{error}</p>}
        {loadFailed && <ScreenState state="error" errorHint={error ?? ""} onRetry={() => void load()} />}
        {notice && <p role="status">{notice}</p>}

        <h3>{t("costs.registered")}</h3>
        {!loading && costs.length === 0 && <EmptyState title={t("costs.none")} hint="" />}
        {costs.length > 0 && (
          <DataTable
            ariaLabel={t("costs.registered")}
            rows={costs}
            rowKey={(c) => c.id}
            columns={[
              { id: "product", header: t("common.product"), cell: (c) => `#${c.product_id}`, sortValue: (c) => c.product_id },
              { id: "supplier", header: t("common.supplier"), cell: (c) => c.supplier_id, sortValue: (c) => c.supplier_id },
              { id: "cost", header: t("common.cost"), cell: (c) => formatCurrencyEUR(c.cost_with_recargo), sortValue: (c) => Number(c.cost_with_recargo), align: "end" },
              { id: "source", header: t("costs.source"), cell: (c) => c.source, sortValue: (c) => c.source },
              { id: "verified", header: t("costs.verified_at"), cell: (c) => formatDate(c.verified_at), sortValue: (c) => c.verified_at },
            ]}
          />
        )}
      </Card>

      {canRequestUpdate(userRoles) && (
        <Card as="div">
          <h3>{t("costs.opening.title")}</h3>
          <p className="mmi-muted">{t("costs.opening.help")}</p>
          <div className="mmi-cluster">
            <div className="mmi-stack">
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
            <FormField id="op-product" label={t("costs.opening.product")} value={opening.product} error={fe.errors["op-product"]} onChange={(v) => { setOpening({ ...opening, product: v }); fe.clear("op-product"); }} inputMode="numeric" />
            <FormField id="op-variant" label={t("costs.opening.variant")} value={opening.variant} error={fe.errors["op-variant"]} onChange={(v) => { setOpening({ ...opening, variant: v }); fe.clear("op-variant"); }} inputMode="numeric" />
            <FormField id="op-amount" label={t("costs.opening.amount")} value={opening.amount} error={fe.errors["op-amount"]} onChange={(v) => { setOpening({ ...opening, amount: v }); fe.clear("op-amount"); }} inputMode="decimal" />
            <label>
              <input type="checkbox" checked={opening.recargo} onChange={(e) => setOpening({ ...opening, recargo: e.target.checked })} /> {t("costs.opening.recargo")}
            </label>
          </div>
          <PageActions>
            <Button variant="secondary" onClick={() => void saveOpening()}>
              {t("costs.opening.save")}
            </Button>
          </PageActions>
          <Button onClick={() => void requestUpdate()}>
            {t("costs.opening.request")}
          </Button>
        </Card>
      )}

      <Card as="div">
        <h3>{t("costs.pending_writes")}</h3>
        <p className="mmi-muted">{t("costs.median_explained")}</p>
        {!loading && writes.length === 0 && <EmptyState title={t("costs.no_pending")} hint="" />}
        {writes.map((w) => (
          <Card as="article" key={w.id} aria-label={t("costs.request_label", { product: w.product_id })}>
            <h4>{t("costs.request_label", { product: w.product_id })}</h4>
            <p>
              {t("costs.value_sent")}: <strong>{formatCurrencyEUR(w.proposed_value)}</strong>
              {w.median_cost !== null && w.override && <span> · {t("costs.median_was", { value: formatCurrencyEUR(w.median_cost) })}</span>}
              {w.previous_siweb_value !== null && <span> · {t("costs.erp_current", { value: formatCurrencyEUR(w.previous_siweb_value) })}</span>}
            </p>
            <StatusBadge domain="cost_write" code={w.status} />
            {w.last_error && <p role="note">{w.last_error}</p>}

            <h5>{t("costs.lots_behind")}</h5>
            <div className="mmi-table-wrapper"><table aria-label={t("costs.lots_behind")} className="mmi-table">
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
                          <Button variant="secondary" small onClick={() => void correct(w, l.variant_id, l.lot)}>
                            {t("costs.correct_lot")}
                          </Button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table></div>

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
                <Button variant="secondary" onClick={() => askOverride(w)}>
                  {t("costs.override_save")}
                </Button>
              </fieldset>
            )}

            {canRelease(userRoles, userId, w) && (
              <Button onClick={() => setReleasing(w)}>
                {t("costs.send_write")}
              </Button>
            )}
          </Card>
        ))}
      </Card>
    </section>
  );
};
