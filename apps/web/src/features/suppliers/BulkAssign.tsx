import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, BulkPreview, errorMessage, SupplierSummary } from "../../api/client";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { FormField } from "../../ui/FormField";
import { parseSkuList } from "./supplierModel";

interface Props {
  supplier: SupplierSummary;
  onDone: () => void;
}

/** Assign this supplier to many products: a preview first, then the same preview is applied (nothing changes before that). */
export const BulkAssign: React.FC<Props> = ({ supplier, onDone }) => {
  const { t } = useTranslation();
  const [skus, setSkus] = useState("");
  const [q, setQ] = useState("");
  const [preview, setPreview] = useState<BulkPreview | null>(null);
  const [skip, setSkip] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const criteria = (): { skus?: string[]; q?: string } | null => {
    const list = parseSkuList(skus);
    if (list.length > 0) return { skus: list };
    return q.trim().length >= 2 ? { q: q.trim() } : null;
  };

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    } finally {
      setBusy(false);
    }
  };

  const doPreview = () => run(async () => {
    const c = criteria();
    if (c === null) return setError(t("suppliers.bulk.need_input"));
    setNote(null);
    setSkip(false);
    setPreview(await api.previewBulkLinks(supplier.id, c));
  });

  const doApply = () => run(async () => {
    if (!preview) return;
    const res = await api.applyBulkLinks(supplier.id, preview.batch_id, skip);
    setNote(t("suppliers.bulk.done", { changed: res.changed, skipped: res.skipped_conflicts, no_cost: res.no_cost }));
    setPreview(null);
    setSkus("");
    setQ("");
    onDone();
  });

  const pickFile = (file: File | null) => {
    if (!file) return;
    void run(async () => {
      const parsed = await api.parseAssignmentFile(file);
      const mine = parsed.groups[supplier.id] ?? [];
      const others = Object.entries(parsed.groups).filter(([id]) => id !== supplier.id).reduce((n, [, v]) => n + v.length, 0);
      setSkus(mine.join("\n"));
      setQ("");
      setPreview(null);
      setNote([t("suppliers.bulk.file_loaded", { count: mine.length }), others ? t("suppliers.bulk.file_other", { count: others }) : "", parsed.errors.length ? t("suppliers.bulk.file_errors", { count: parsed.errors.length }) : ""].filter(Boolean).join(" "));
    });
  };

  if (supplier.status === "deactivated") return null;
  return (
    <Card as="section" aria-labelledby="bulk-title">
      <h3 id="bulk-title">{t("suppliers.bulk.title")}</h3>
      <p className="mmi-muted">{t("suppliers.bulk.intro")}</p>
      <label htmlFor="bulk-skus">{t("suppliers.bulk.skus")}</label>
      <textarea id="bulk-skus" rows={4} value={skus} disabled={busy} onChange={(e) => { setSkus(e.target.value); setPreview(null); }} />
      <FormField id="bulk-q" label={t("suppliers.bulk.q")} value={q} onChange={(v) => { setQ(v); setPreview(null); }} disabled={busy} />
      <label htmlFor="bulk-file">{t("suppliers.bulk.file")}</label>
      <input id="bulk-file" type="file" accept=".csv,.txt" disabled={busy} onChange={(e) => pickFile(e.target.files?.[0] ?? null)} />
      <div className="mmi-actions"><Button disabled={busy} onClick={() => void doPreview()}>{t("suppliers.bulk.preview")}</Button></div>
      {preview && (
        <div aria-live="polite">
          <dl className="mmi-counts">
            {([["matched", preview.matched], ["new", preview.new], ["existing", preview.existing], ["conflicts", preview.conflicts]] as const).map(([k, v]) => (
              <div key={k} className="mmi-counts__item"><dt>{t(`suppliers.bulk.${k}`)}</dt><dd>{v}</dd></div>
            ))}
          </dl>
          {preview.unknown.length > 0 && <p>{t("suppliers.bulk.unknown", { list: preview.unknown.slice(0, 10).join(", ") })}</p>}
          {preview.conflicts > 0 && (
            <>
              <p>{t("suppliers.bulk.conflict_list", { list: preview.conflict_skus.slice(0, 10).join(", ") })}</p>
              <label className="mmi-check"><input type="checkbox" checked={skip} onChange={(e) => setSkip(e.target.checked)} />{t("suppliers.bulk.skip_conflicts")}</label>
            </>
          )}
          <div className="mmi-actions">
            <Button disabled={busy || preview.new === 0 || (preview.conflicts > 0 && !skip)} onClick={() => void doApply()}>{t("suppliers.bulk.apply")}</Button>
          </div>
        </div>
      )}
      {error && <p role="alert" className="mmi-error">{error}</p>}
      {note && <p role="status" className="mmi-notice">{note}</p>}
    </Card>
  );
};
