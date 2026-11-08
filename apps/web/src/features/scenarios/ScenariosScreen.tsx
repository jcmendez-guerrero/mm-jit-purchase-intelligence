import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, ScenarioDetail, ScenarioListItem, SupplierSummary } from "../../api/client";
import { formatCurrencyEUR, formatDate, formatDateTime, formatPercent } from "../../i18n/formatters";
import { VersionsUsed } from "../proposals/VersionsUsed";
import { FormField } from "../../ui/FormField";
import { canCreate, constraintLabel, emptyForm, emptySupplier, reasonKey, ScenarioForm, SupplierForm, toRequest } from "./scenariosModel";
import { EmptyState } from "../../ui/EmptyState";
import { StatusBadge } from "../../ui/StatusBadge";
import { ScreenState } from "../../ui/ScreenState";
import { useActionNotice } from "../../ui/NoticeProvider";
import { UnsavedChangesPrompt } from "../../ui/UnsavedChangesPrompt";
import { ConfirmDialog } from "../../ui/ConfirmDialog";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { useFieldErrors } from "../../ui/useFieldErrors";
import { PageActions } from "../../ui/PageActions";
import { DataTable } from "../../ui/DataTable";

interface Props {
  userRoles: string[];
}

const SUPPLIER_FIELDS = ["min_order_value", "delivery_charge", "free_delivery_threshold", "lead_time_days", "pack_multiple", "min_order_qty"] as const;

export const ScenariosScreen: React.FC<Props> = ({ userRoles }) => {
  const { t } = useTranslation();
  const [form, setForm] = useState<ScenarioForm>(emptyForm());
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([]);
  const [list, setList] = useState<ScenarioListItem[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [detail, setDetail] = useState<ScenarioDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [confirmingPromote, setConfirmingPromote] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useActionNotice();
  const [key, setKey] = useState(() => crypto.randomUUID());
  const editable = canCreate(userRoles);
  const fe = useFieldErrors();

  const fail = useCallback((err: unknown) => setError(errorMessage(err, t("common.error"))), [t]);
  const loadList = useCallback(async () => {
    try {
      setLoadFailed(false);
      setList((await api.getScenarios()).scenarios);
    } catch (err) {
      fail(err);
      setLoadFailed(true);
    } finally {
      setListLoading(false);
    }
  }, [fail]);
  useEffect(() => {
    void loadList();
    api.getSuppliers().then(setSuppliers).catch(fail);
  }, [loadList, fail]);

  const supplierName = (id: string | null) => (id === null ? t("scenarios.none") : suppliers.find((s) => s.id === id)?.name ?? id);
  const setSupplier = (id: string, patch: Partial<SupplierForm>) =>
    setForm((f) => ({ ...f, suppliers: { ...f.suppliers, [id]: { ...(f.suppliers[id] ?? emptySupplier()), ...patch } } }));

  const compute = async () => {
    setError(null);
    setNotice(null);
    const req = toRequest(form);
    if ("invalid" in req) {
      const field = t(`scenarios.field.${req.invalid}`, { defaultValue: t(`scenarios.supplier.${req.invalid}`, { defaultValue: req.invalid }) });
      const summary = req.supplier ? t("scenarios.invalid_for", { field, supplier: supplierName(req.supplier) }) : t("scenarios.invalid", { field });
      const id = req.supplier ? `sc-${req.supplier}-${req.invalid}` : req.invalid === "name" ? "sc-name" : req.invalid === "budget" ? "sc-budget" : "sc-sl";
      fe.flag({ [id]: req.invalid === "name" ? t("ui.form.required") : summary });
      setError(summary);
      return;
    }
    setBusy(true);
    try {
      setDetail(await api.createScenario(req.body, key));
      setKey(crypto.randomUUID());                         // a new key per submitted scenario; retries of the same click reuse it
      await loadList();
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  };

  const open = async (id: string) => {
    setError(null);
    setNotice(null);
    try {
      setDetail(await api.getScenario(id));
    } catch (err) {
      fail(err);
    }
  };

  const promote = async () => {
    if (!detail) return;
    setError(null);
    try {
      const res = await api.promoteScenario(detail.id);
      const fresh = await api.getScenario(detail.id);
      setDetail(fresh);
      await loadList();
      setNotice(t("scenarios.promoted", { week: res.week }) + (res.superseded.length > 0 ? ` ${t("scenarios.promoted_superseded")}` : ""));
    } catch (err) {
      fail(err);
    }
  };

  const s = detail?.summary ?? null;
  const groups = (detail?.results ?? []).filter((r) => r.lines.length !== 0);
  const dirty = editable && JSON.stringify(form) !== JSON.stringify(emptyForm());

  return (
    <section aria-labelledby="scenarios-title">
      <ConfirmDialog
        open={confirmingPromote && detail !== null}
        title={t("scenarios.confirm.promote.title")}
        objectLabel={detail?.name ?? ""}
        effect={t("scenarios.confirm.promote.effect")}
        confirmLabel={t("scenarios.promote")}
        onCancel={() => setConfirmingPromote(false)}
        onConfirm={() => {
          setConfirmingPromote(false);
          void promote();
        }}
      />
      <UnsavedChangesPrompt dirty={dirty} />
      <h2 id="scenarios-title">{t("scenarios.title")}</h2>
      <p>{t("scenarios.subtitle")}</p>
      {error && !loadFailed && <p role="alert" className="mmi-error">{error}</p>}
      {loadFailed && <ScreenState state="error" errorHint={error ?? ""} onRetry={() => void loadList()} />}
      {notice && <p role="status">{notice}</p>}
      {!editable && <p>{t("scenarios.read_only")}</p>}

      <div className="mmi-split">
        <div className="mmi-split__aside">
      {editable && (
        <Card as="form" id="scenario-form" className="mmi-mb-4" onSubmit={(e) => { e.preventDefault(); void compute(); }} aria-label={t("scenarios.new")}>
          <h3>{t("scenarios.new")}</h3>
          <div className="mmi-cluster mmi-cluster--top">
            <FormField id="sc-name" label={t("scenarios.name")} value={form.name} error={fe.errors["sc-name"]} onChange={(v) => { setForm({ ...form, name: v }); fe.clear("sc-name"); }} />
            <FormField id="sc-budget" label={t("scenarios.budget")} inputMode="decimal" value={form.budget} error={fe.errors["sc-budget"]} onChange={(v) => { setForm({ ...form, budget: v }); fe.clear("sc-budget"); }} />
            <FormField id="sc-sl" label={t("scenarios.service_level")} inputMode="decimal" value={form.service_level_pp} error={fe.errors["sc-sl"]} onChange={(v) => { setForm({ ...form, service_level_pp: v }); fe.clear("sc-sl"); }} />
          </div>
          <h4>{t("scenarios.suppliers")}</h4>
          <p>{t("scenarios.blank_means_no_change")}</p>
          {suppliers.map((sp) => {
            const cur = form.suppliers[sp.id] ?? emptySupplier();
            return (
              <fieldset className="mmi-mb-3" key={sp.id}>
                <legend>{sp.name}</legend>
                <label>
                  <input type="checkbox" checked={cur.disabled} onChange={(e) => setSupplier(sp.id, { disabled: e.target.checked })} /> {t("scenarios.supplier.disabled")}
                </label>
                <div className="mmi-cluster mmi-cluster--top">
                  {SUPPLIER_FIELDS.map((f) => (
                    <FormField key={f} id={`sc-${sp.id}-${f}`} label={t(`scenarios.supplier.${f}`)} inputMode={f.endsWith("days") || f.endsWith("qty") || f === "pack_multiple" ? "numeric" : "decimal"}
                      value={cur[f]} disabled={cur.disabled} error={fe.errors[`sc-${sp.id}-${f}`]} onChange={(v) => { setSupplier(sp.id, { [f]: v }); fe.clear(`sc-${sp.id}-${f}`); }} />
                  ))}
                </div>
              </fieldset>
            );
          })}
          <PageActions>
            <Button type="submit" form="scenario-form" disabled={busy}>{busy ? t("scenarios.computing") : t("scenarios.compute")}</Button>
          </PageActions>
        </Card>
      )}

      <h3>{t("scenarios.list")}</h3>
      {list.length === 0 ? (listLoading ? <ScreenState state="loading" skeletonLines={3} /> : <EmptyState title={t("scenarios.list_empty")} hint="" />) : (
        <DataTable
          ariaLabel={t("scenarios.list")}
          rows={list}
          rowKey={(r) => r.id}
          columns={[
            { id: "name", header: t("scenarios.name"), cell: (r) => r.name, sortValue: (r) => r.name },
            { id: "status", header: t("common.status"), cell: (r) => <StatusBadge domain="scenario" code={r.status} />, sortValue: (r) => r.status },
            { id: "delta", header: t("scenarios.col.delta"), cell: (r) => (r.delta_total === null ? "—" : formatCurrencyEUR(r.delta_total)), sortValue: (r) => (r.delta_total === null ? null : Number(r.delta_total)), align: "end" },
            { id: "date", header: t("common.date"), cell: (r) => formatDateTime(r.created_at), sortValue: (r) => r.created_at },
            { id: "open", header: "", cell: (r) => <Button variant="secondary" onClick={() => void open(r.id)} aria-label={`${t("scenarios.open")} ${r.name}`}>{t("scenarios.open")}</Button> },
          ]}
        />
      )}

        </div>
        <div className="mmi-split__main">
      {detail && s && (
        <Card as="article" className="mmi-mt-4" aria-label={detail.name}>
          <h3>{detail.name} — {t(`scenarios.status.${detail.status}`)}</h3>
          <VersionsUsed dataset={detail.input_versions?.dataset} forecastRun={detail.input_versions?.forecast_run} />
          <h4>{t("scenarios.compare")}</h4>
          <div className="mmi-table-wrapper"><table className="mmi-table">
            <thead><tr><th>{t("scenarios.col.metric")}</th><th>{t("scenarios.col.baseline")}</th><th>{t("scenarios.col.scenario")}</th></tr></thead>
            <tbody>
              <tr><th scope="row">{t("scenarios.metric.total")}</th><td>{formatCurrencyEUR(s.baseline.total)}</td><td>{formatCurrencyEUR(s.scenario.total)}</td></tr>
              <tr><th scope="row">{t("scenarios.metric.over")}</th><td>{formatCurrencyEUR(s.baseline.over_budget)}</td><td>{formatCurrencyEUR(s.scenario.over_budget)}</td></tr>
              <tr><th scope="row">{t("scenarios.metric.lines")}</th><td>{s.baseline.lines}</td><td>{s.scenario.lines}</td></tr>
              {s.scenario.utilisation !== null && (
                <tr><th scope="row">{t("scenarios.col.utilisation")}</th><td>—</td><td>{formatPercent(s.scenario.utilisation)}</td></tr>
              )}
            </tbody>
          </table></div>
          <p><strong>{t("scenarios.delta", { value: formatCurrencyEUR(s.delta_total) })}</strong></p>
          {s.infeasible && (
            <div role="alert">
              <p>{t("scenarios.infeasible", { over: formatCurrencyEUR(s.infeasible.over_by) })}</p>
              {s.infeasible.clinical_critical_variants.length > 0 && <p>{t("scenarios.critical", { ids: s.infeasible.clinical_critical_variants.join(", ") })}</p>}
            </div>
          )}

          <h4>{t("scenarios.changes")}</h4>
          {s.changes.length === 0 ? <p>{t("scenarios.changes_none")}</p> : (
            <ul>
              {s.changes.map((c) => (
                <li key={c.variant_id}>
                  {t("scenarios.change_row", {
                    variant: c.variant_id, from: supplierName(c.supplier_before), to: supplierName(c.supplier_after), qb: c.qty_before, qa: c.qty_after,
                    reasons: c.reasons.map((r) => t(reasonKey(r), { defaultValue: r })).join(", "),
                  })}
                </li>
              ))}
            </ul>
          )}

          <h4>{t("scenarios.binding")}</h4>
          <ul>
            {s.binding.map((b, i) => {
              const { kind, supplier } = constraintLabel(b.key);
              const name = supplier ? supplierName(supplier) : "";
              return <li key={i}>{t(`scenarios.binding.${kind}`, { supplier: name, status: t(`scenarios.binding.status.${b.params.status ?? "shortfall"}`, { defaultValue: "" }), defaultValue: b.key })}</li>;
            })}
          </ul>

          <h4>{t("scenarios.sensitivity")}</h4>
          {detail.sensitivity.length === 0 ? <p>{t("scenarios.sensitivity_none")}</p> : (
            <ul>
              {detail.sensitivity.map((x) => {
                const { kind, supplier } = constraintLabel(x.constraint_key);
                const what = t(`scenarios.binding.${kind}`, { supplier: supplier ? supplierName(supplier) : "", status: "", defaultValue: x.constraint_key });
                return <li key={x.constraint_key}>{t("scenarios.sensitivity_row", { what, delta: formatCurrencyEUR(x.delta), impact: formatCurrencyEUR(x.cost_impact) })}</li>;
              })}
            </ul>
          )}

          <h4>{t("scenarios.groups")}</h4>
          {groups.length === 0 && <p>{t("scenarios.groups_none")}</p>}
          {groups.map((r) => (
            <Card className="mmi-mb-3" key={r.supplier_id} aria-label={t("scenarios.group_title", { name: r.supplier_name ?? supplierName(r.supplier_id) })}>
              <h5>{r.supplier_name ?? supplierName(r.supplier_id)}</h5>
              <div className="mmi-table-wrapper">
                <table className="mmi-table" aria-label={t("scenarios.group_lines", { name: r.supplier_name ?? supplierName(r.supplier_id) })}>
                  <thead><tr><th>{t("common.variant")}</th><th>{t("scenarios.line.qty")}</th><th>{t("scenarios.line.unit_cost")}</th><th>{t("scenarios.line.total")}</th></tr></thead>
                  <tbody>
                    {r.lines.map((ln) => (
                      <tr key={ln.variant_id}>
                        <td>#{ln.variant_id}{ln.clinical_critical ? ` · ${t("scenarios.line.critical")}` : ""}</td>
                        <td>{ln.qty}</td>
                        <td>{formatCurrencyEUR(ln.unit_cost)}</td>
                        <td>{formatCurrencyEUR(ln.line_total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <ul>
                {r.subtotal != null && <li>{t("scenarios.group.subtotal", { value: formatCurrencyEUR(r.subtotal) })}</li>}
                {r.delivery_charge != null && <li>{r.free_delivery ? t("scenarios.group.shipping_free") : t("scenarios.group.shipping", { value: formatCurrencyEUR(r.delivery_charge) })}</li>}
                {r.discount != null && Number(r.discount) > 0 && <li>{t("scenarios.group.discount", { value: formatCurrencyEUR(r.discount) })}</li>}
                <li><strong>{t("scenarios.group.total", { value: formatCurrencyEUR(r.order_total) })}</strong></li>
                <li>{r.expected_delivery ? t("scenarios.group.delivery", { value: formatDate(r.expected_delivery) }) : t("scenarios.group.delivery_unknown")}</li>
                <li>{r.budget_utilisation === null ? t("scenarios.group.utilisation_none") : t("scenarios.group.utilisation", { value: formatPercent(r.budget_utilisation) })}</li>
              </ul>
            </Card>
          ))}

          <div className="mmi-cluster mmi-cluster--top mmi-mt-3">
            {editable && detail.status === "ready" && <Button onClick={() => setConfirmingPromote(true)}>{t("scenarios.promote")}</Button>}
            <a href={`/api/scenarios/${detail.id}/export?format=csv`}>{t("scenarios.export_csv")}</a>
            <a href={`/api/scenarios/${detail.id}/export?format=xlsx`}>{t("scenarios.export_xlsx")}</a>
          </div>
        </Card>
      )}
        </div>
      </div>
    </section>
  );
};
