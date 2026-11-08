import React, { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, SupplierSummary } from "../../api/client";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { DataTable, type Column } from "../../ui/DataTable";
import { StatusBadge } from "../../ui/StatusBadge";

interface Props {
  suppliers: SupplierSummary[];
  onChanged: () => void;
}

/** Imported suppliers that still need a decision: the import only suggests "no purchases" for obvious expense vendors (the buyer decides). */
export const SupplierImport: React.FC<Props> = ({ suppliers, onChanged }) => {
  const { t } = useTranslation();
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rows = useMemo(
    () => suppliers.filter((s) => s.origin === "imported" && s.status !== "deactivated" && s.classification !== "purchasing"),
    [suppliers],
  );
  if (rows.length === 0) return null;

  const toggle = (id: string) => setPicked((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const allPicked = rows.every((r) => picked.has(r.id));

  const mark = async (classification: "purchasing" | "non_purchasing") => {
    setBusy(true);
    setError(null);
    setNote(null);
    let done = 0;
    let failed = 0;
    for (const s of rows.filter((r) => picked.has(r.id))) {
      try {
        await api.updateSupplier(s.id, { classification }, s.supplier_version ?? 1);
        done += 1;
      } catch (err) {
        failed += 1;
        if (failed === 1) setError(errorMessage(err, t("common.error")));
      }
    }
    setBusy(false);
    setPicked(new Set());
    setNote(t("suppliers.import.done", { count: done }));
    if (failed > 0) setError(t("suppliers.import.failed", { count: failed }));
    onChanged();
  };

  const columns: Column<SupplierSummary>[] = [
    {
      id: "pick",
      header: t("suppliers.import.select"),
      cell: (s) => <input type="checkbox" aria-label={`${t("suppliers.import.select")} ${s.name}`} checked={picked.has(s.id)} onChange={() => toggle(s.id)} />,
    },
    { id: "name", header: t("suppliers.col.name"), cell: (s) => s.name, sortValue: (s) => s.name },
    {
      id: "class",
      header: t("suppliers.filter.classification"),
      cell: (s) => (s.classification === "non_purchasing" ? <StatusBadge domain="tag" code="non_purchasing" /> : <StatusBadge domain="tag" code="unclassified" />),
    },
    { id: "country", header: t("suppliers.import.col.country"), cell: (s) => s.country ?? "–", sortValue: (s) => s.country ?? "" },
    { id: "currency", header: t("suppliers.import.col.currency"), cell: (s) => s.currency ?? "–", sortValue: (s) => s.currency ?? "" },
    { id: "days", header: t("suppliers.import.col.days"), cell: (s) => s.payment_terms_days ?? "–", sortValue: (s) => s.payment_terms_days ?? null, align: "end" },
  ];

  return (
    <Card as="section" aria-labelledby="import-title">
      <h3 id="import-title">{t("suppliers.import.title")}</h3>
      <p className="mmi-muted">{t("suppliers.import.intro")}</p>
      <div className="mmi-actions">
        <Button small variant="secondary" disabled={busy} onClick={() => setPicked(allPicked ? new Set() : new Set(rows.map((r) => r.id)))}>{t("suppliers.import.select_all")}</Button>
        <Button small disabled={busy || picked.size === 0} onClick={() => void mark("purchasing")}>{t("suppliers.import.mark_purchasing")}</Button>
        <Button small variant="secondary" disabled={busy || picked.size === 0} onClick={() => void mark("non_purchasing")}>{t("suppliers.import.mark_non")}</Button>
      </div>
      <DataTable ariaLabel={t("suppliers.import.title")} columns={columns} rows={rows} rowKey={(s) => s.id} />
      {error && <p role="alert" className="mmi-error">{error}</p>}
      {note && <p role="status" className="mmi-notice">{note}</p>}
    </Card>
  );
};
