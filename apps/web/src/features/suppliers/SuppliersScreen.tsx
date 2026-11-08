import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, DeactivationPreview, errorMessage, SupplierSummary } from "../../api/client";
import { formatCurrencyEUR } from "../../i18n/formatters";
import { OverrideEditor } from "./OverrideEditor";
import { SupplierTermsEditor } from "./SupplierTermsEditor";
import { BulkAssign } from "./BulkAssign";
import { LinksPanel } from "./LinksPanel";
import { SupplierForm } from "./SupplierForm";
import { SupplierImport } from "./SupplierImport";
import { SupplierReview } from "./SupplierReview";
import { CLASSIFICATIONS, canManage } from "./supplierModel";
import { ConfirmDialog } from "../../ui/ConfirmDialog";
import { ScreenState } from "../../ui/ScreenState";
import { EmptyState } from "../../ui/EmptyState";
import { StatusBadge } from "../../ui/StatusBadge";
import { Card } from "../../ui/Card";
import { Button } from "../../ui/Button";
import { DataTable } from "../../ui/DataTable";

interface Props {
  userRoles: string[];
}

export const SuppliersScreen: React.FC<Props> = ({ userRoles }) => {
  const { t } = useTranslation();
  const [suppliers, setSuppliers] = useState<SupplierSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const canEdit = userRoles.includes("buyer");
  const manage = canManage(userRoles);
  const [filters, setFilters] = useState<{ status: string; classification: string; q: string }>({ status: "", classification: "", q: "" });
  const [mode, setMode] = useState<"create" | "edit" | null>(null);
  const [deactivating, setDeactivating] = useState<DeactivationPreview | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const active = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
      setSuppliers(Object.keys(active).length === 0 ? await api.getSuppliers() : await api.getSuppliersFiltered(active));
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    } finally {
      setLoading(false);
    }
  }, [t, filters]);

  useEffect(() => {
    void load();
  }, [load]);

  const startDeactivate = async (id: string) => {
    setActionError(null);
    try {
      setDeactivating(await api.deactivateSupplier(id, false));
    } catch (err) {
      setActionError(errorMessage(err, t("common.error")));
    }
  };
  const confirmDeactivate = async (id: string) => {
    setDeactivating(null);
    try {
      await api.deactivateSupplier(id, true);
      setNote(t("suppliers.deactivate.done"));
      await load();
    } catch (err) {
      setActionError(errorMessage(err, t("common.error")));
    }
  };
  const reactivate = async (id: string) => {
    setActionError(null);
    try {
      await api.reactivateSupplier(id);
      setNote(t("suppliers.reactivate.done"));
      await load();
    } catch (err) {
      setActionError(errorMessage(err, t("common.error")));
    }
  };

  const current = suppliers.find((s) => s.id === selected) ?? null;

  return (
    <section aria-labelledby="suppliers-title">
      <div className="mmi-split mmi-split--wide-aside">
        <div className="mmi-split__aside">
      <Card as="div">
        <h2 className="mmi-title-lg mmi-mb-2" id="suppliers-title">
          {t("suppliers.title")}
        </h2>
        <p className="mmi-muted mmi-text-sm mmi-mt-0">{t("suppliers.subtitle")}</p>
        <div className="mmi-cluster mmi-mb-2">
          {manage && <Button onClick={() => { setMode("create"); setNote(null); }}>{t("suppliers.manage.new")}</Button>}
          <label>{t("suppliers.filter.status")}{" "}
            <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
              <option value="">{t("suppliers.filter.all")}</option>
              <option value="active">{t("suppliers.status.active")}</option>
              <option value="deactivated">{t("suppliers.status.deactivated")}</option>
            </select>
          </label>
          <label>{t("suppliers.filter.classification")}{" "}
            <select value={filters.classification} onChange={(e) => setFilters({ ...filters, classification: e.target.value })}>
              <option value="">{t("suppliers.filter.all")}</option>
              {CLASSIFICATIONS.map((c) => <option key={c} value={c}>{t(`suppliers.class.${c}`)}</option>)}
            </select>
          </label>
          <label>{t("suppliers.filter.search")}{" "}
            <input type="search" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
          </label>
        </div>
        {note && <p role="status" className="mmi-notice">{note}</p>}
        {loading && <ScreenState state="loading" skeletonShape="table" skeletonLines={4} />}
        {error && <ScreenState state="error" errorHint={error} onRetry={() => { setError(null); setLoading(true); void load(); }} />}
        {!loading && suppliers.length === 0 && !error && <EmptyState title={t("suppliers.empty")} hint="" />}
        {suppliers.length > 0 && (
          <DataTable
            ariaLabel={t("a11y.suppliers_table")}
            rows={suppliers}
            rowKey={(s) => s.id}
            columns={[
              {
                id: "name",
                header: t("suppliers.col.name"),
                cell: (s) => (
                  <Button variant="quiet" aria-pressed={selected === s.id} onClick={() => setSelected(s.id)}>
                    {s.name}
                  </Button>
                ),
                sortValue: (s) => s.name,
              },
              { id: "lead", header: t("suppliers.col.lead"), cell: (s) => s.terms?.lead_time_days ?? "–", sortValue: (s) => s.terms?.lead_time_days ?? null, align: "end" },
              { id: "min", header: t("suppliers.col.min"), cell: (s) => (s.terms?.min_order_value ? formatCurrencyEUR(Number(s.terms.min_order_value)) : "–"), sortValue: (s) => (s.terms?.min_order_value ? Number(s.terms.min_order_value) : null), align: "end" },
              { id: "version", header: t("suppliers.col.version"), cell: (s) => s.version || "–", sortValue: (s) => s.version, align: "end" },
              {
                id: "state",
                header: t("suppliers.col.state"),
                cell: (s) => (
                  <>
                    {s.status === "deactivated" && <StatusBadge domain="tag" code="inactive" />}{" "}
                    {s.classification === "non_purchasing" && <StatusBadge domain="tag" code="non_purchasing" />}
                    {s.classification === "unclassified" && <StatusBadge domain="tag" code="unclassified" />}
                  </>
                ),
              },
              {
                id: "status",
                header: t("common.status"),
                cell: (s) => (
                  <>
                    {!s.terms && <span>{t("suppliers.no_terms")}</span>}
                    {s.terms?.preferred && <StatusBadge domain="tag" code="preferred" />} {s.terms?.disabled && <StatusBadge domain="tag" code="disabled" />}
                  </>
                ),
              },
            ]}
          />
        )}
      </Card>
        </div>
        <div className="mmi-split__main">
      {mode === "create" && <SupplierForm onCancel={() => setMode(null)} onSaved={(saved) => { setMode(null); setSelected(saved.id); setNote(t("suppliers.form.saved")); void load(); }} />}
      {mode === "edit" && current && <SupplierForm supplier={current} onCancel={() => setMode(null)} onSaved={() => { setMode(null); setNote(t("suppliers.form.saved")); void load(); }} />}
      {mode === null && current ? (
        <>
          {manage && (
            <div className="mmi-actions mmi-mb-2">
              <Button variant="secondary" onClick={() => setMode("edit")} disabled={current.status === "deactivated"}>{t("suppliers.manage.edit")}</Button>
              {current.status === "deactivated" ? (
                <Button variant="secondary" onClick={() => void reactivate(current.id)}>{t("suppliers.manage.reactivate")}</Button>
              ) : (
                <Button variant="secondary" onClick={() => void startDeactivate(current.id)}>{t("suppliers.manage.deactivate")}</Button>
              )}
            </div>
          )}
          {actionError && <p role="alert" className="mmi-error">{actionError}</p>}
          <ConfirmDialog
            open={deactivating !== null}
            tone="danger"
            title={t("suppliers.deactivate.title")}
            objectLabel={current.name}
            effect={deactivating && deactivating.open_proposal_lines > 0 ? t("suppliers.deactivate.effect_lines", { count: deactivating.open_proposal_lines }) : t("suppliers.deactivate.effect_none")}
            confirmLabel={t("suppliers.deactivate.confirm")}
            onCancel={() => setDeactivating(null)}
            onConfirm={() => void confirmDeactivate(current.id)}
          />
          <SupplierTermsEditor supplierId={current.id} supplierName={current.name} canEdit={canEdit && current.status !== "deactivated"} onSaved={() => void load()} />
          <OverrideEditor supplierId={current.id} canEdit={canEdit && current.status !== "deactivated"} />
          <LinksPanel supplier={current} canManage={manage} />
          {manage && <BulkAssign supplier={current} onDone={() => void load()} />}
        </>
      ) : (
        mode === null && suppliers.length > 0 && <p className="mmi-mt-4">{t("suppliers.select")}</p>
      )}
      {manage && <SupplierImport suppliers={suppliers} onChanged={() => void load()} />}
      <SupplierReview suppliers={suppliers} onChanged={() => void load()} />
        </div>
      </div>
    </section>
  );
};
