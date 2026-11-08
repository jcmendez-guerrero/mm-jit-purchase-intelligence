import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, SupplierLinkRow, SupplierSummary } from "../../api/client";
import { formatCurrencyEUR, formatDateTime } from "../../i18n/formatters";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { ConfirmDialog } from "../../ui/ConfirmDialog";
import { DataTable, type Column } from "../../ui/DataTable";
import { EmptyState } from "../../ui/EmptyState";
import { FormField } from "../../ui/FormField";
import { StatusBadge } from "../../ui/StatusBadge";
import { linkPayload } from "./supplierModel";

interface Props {
  supplier: SupplierSummary;
  canManage: boolean;
}

/** Products a supplier offers, by SKU. ERP ids never appear here: people see and type the SKU. */
export const LinksPanel: React.FC<Props> = ({ supplier, canManage }) => {
  const { t } = useTranslation();
  const [rows, setRows] = useState<SupplierLinkRow[]>([]);
  const [sku, setSku] = useState("");
  const [cost, setCost] = useState("");
  const [recargo, setRecargo] = useState(true);
  const [pack, setPack] = useState("");
  const [minQty, setMinQty] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [removing, setRemoving] = useState<SupplierLinkRow | null>(null);
  const writable = canManage && supplier.status !== "deactivated";

  const load = useCallback(async () => {
    try {
      setRows(await api.getSupplierLinks(supplier.id));
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  }, [supplier.id, t]);
  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    setError(null);
    setNote(null);
    if (!sku.trim()) return setError(t("suppliers.links.sku_required"));
    const body = linkPayload({ cost, includesRecargo: recargo, pack, minQty });
    if (body === null) return setError(cost.trim() !== "" && !/^\d+([.,]\d{1,4})?$/.test(cost.trim()) ? t("suppliers.links.cost_invalid") : t("suppliers.links.number_invalid"));
    if (cost.trim() === "") body.cost_source = "inventory_export";
    try {
      const res = await api.putSupplierLink(supplier.id, sku.trim(), body);
      setNote(res.warnings.includes("abnormal_jump") ? `${t("suppliers.links.saved")} ${t("suppliers.links.jump")}` : t("suppliers.links.saved"));
      setSku("");
      setCost("");
      setPack("");
      setMinQty("");
      await load();
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  };

  const remove = async (row: SupplierLinkRow) => {
    try {
      await api.deleteSupplierLink(supplier.id, row.sku ?? "");
      setNote(t("suppliers.links.removed"));
      await load();
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  };

  const columns: Column<SupplierLinkRow>[] = [
    { id: "sku", header: t("suppliers.links.sku"), cell: (r) => <strong>{r.sku ?? "—"}</strong>, sortValue: (r) => r.sku ?? "" },
    { id: "name", header: t("suppliers.links.product"), cell: (r) => r.name ?? "—", sortValue: (r) => r.name ?? "" },
    { id: "cost", header: t("suppliers.links.cost"), cell: (r) => formatCurrencyEUR(Number(r.cost)), sortValue: (r) => Number(r.cost), align: "end" },
    { id: "source", header: t("suppliers.links.source"), cell: (r) => (r.cost_source === "inventory_export" ? <StatusBadge domain="tag" code="source_inventory_export" /> : t(`suppliers.links.source.${r.cost_source}`, { defaultValue: r.cost_source })) },
    { id: "pack", header: t("suppliers.links.pack"), cell: (r) => r.pack_size ?? "–", sortValue: (r) => r.pack_size ?? null, align: "end" },
    { id: "min", header: t("suppliers.links.min"), cell: (r) => r.min_qty ?? "–", sortValue: (r) => r.min_qty ?? null, align: "end" },
    { id: "verified", header: t("suppliers.links.verified"), cell: (r) => formatDateTime(r.verified_at), sortValue: (r) => r.verified_at },
    { id: "erp", header: t("suppliers.links.erp"), cell: (r) => (r.erp_link === "no_link" ? <StatusBadge domain="tag" code="pending_link" /> : t(`suppliers.links.erp.${r.erp_link}`)) },
    ...(writable ? [{ id: "actions", header: t("common.actions"), cell: (r: SupplierLinkRow) => <Button small variant="secondary" onClick={() => setRemoving(r)}>{t("suppliers.links.remove")}</Button> }] : []),
  ];

  return (
    <Card as="section" aria-labelledby="links-title">
      <h3 id="links-title">{t("suppliers.links.title")}</h3>
      <ConfirmDialog open={removing !== null} tone="danger" title={t("suppliers.links.remove_title")} objectLabel={removing?.sku ?? ""} effect={t("suppliers.links.remove_effect")}
        confirmLabel={t("suppliers.links.remove")} onCancel={() => setRemoving(null)} onConfirm={() => { const r = removing; setRemoving(null); if (r) void remove(r); }} />
      {rows.length === 0 ? <EmptyState title={t("suppliers.links.empty")} hint="" /> : <DataTable ariaLabel={t("suppliers.links.title")} columns={columns} rows={rows} rowKey={(r) => r.sku ?? r.name ?? ""} />}
      {writable && (
        <form onSubmit={(e) => { e.preventDefault(); void save(); }}>
          <h4>{t("suppliers.links.add_title")}</h4>
          <FormField id="link-sku" label={t("suppliers.links.sku")} value={sku} onChange={setSku} />
          <FormField id="link-cost" label={t("suppliers.links.cost")} value={cost} onChange={setCost} inputMode="decimal" hint={t("suppliers.links.cost_hint")} />
          <label className="mmi-check"><input type="checkbox" checked={recargo} onChange={(e) => setRecargo(e.target.checked)} />{t("suppliers.links.recargo")}</label>
          <FormField id="link-pack" label={t("suppliers.links.pack")} value={pack} onChange={setPack} inputMode="numeric" />
          <FormField id="link-min" label={t("suppliers.links.min")} value={minQty} onChange={setMinQty} inputMode="numeric" />
          <div className="mmi-actions"><Button type="submit">{t("suppliers.links.add")}</Button></div>
        </form>
      )}
      {error && <p role="alert" className="mmi-error">{error}</p>}
      {note && <p role="status" className="mmi-notice">{note}</p>}
    </Card>
  );
};
