import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, SupplierReviewItem, SupplierSummary } from "../../api/client";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { EmptyState } from "../../ui/EmptyState";

interface Props {
  suppliers: SupplierSummary[];
  onChanged: () => void;
}

/** Possible duplicates and proposal lines to reassign. A merge is always an explicit choice here, never automatic. */
export const SupplierReview: React.FC<Props> = ({ suppliers, onChanged }) => {
  const { t } = useTranslation();
  const [items, setItems] = useState<SupplierReviewItem[]>([]);
  const [target, setTarget] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const name = (id: string | null) => suppliers.find((s) => s.id === id)?.name ?? "—";

  const load = useCallback(async () => {
    try {
      setItems(await api.getSupplierReviewItems());
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  }, [t]);
  useEffect(() => {
    void load();
  }, [load, suppliers]);

  const resolve = async (item: SupplierReviewItem, decision: "merge_into" | "keep_both" | "ignore") => {
    setError(null);
    try {
      await api.resolveSupplierReviewItem(item.id, decision, decision === "merge_into" ? target[item.id] : undefined);
      setNote(decision === "merge_into" ? t("suppliers.review.merged") : t("suppliers.review.resolved"));
      await load();
      onChanged();
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    }
  };

  return (
    <Card as="section" aria-labelledby="review-title">
      <h3 id="review-title">{t("suppliers.review.title")}</h3>
      {items.length === 0 && !error && <EmptyState title={t("suppliers.review.empty")} hint="" />}
      <ul className="mmi-list">
        {items.map((item) => (
          <li key={item.id}>
            <strong>{t(`suppliers.review.kind.${item.kind}`, { defaultValue: item.kind })}</strong> — {name(item.supplier_id)}
            {item.kind === "payment_terms_unparsed" && <span className="mmi-muted"> {t("suppliers.review.terms_hint")}</span>}
            <div className="mmi-actions">
              {item.kind === "possible_duplicate" && (
                <>
                  <select aria-label={t("suppliers.review.merge_into")} value={target[item.id] ?? ""} onChange={(e) => setTarget({ ...target, [item.id]: e.target.value })}>
                    <option value="">{t("suppliers.review.merge_pick")}</option>
                    {suppliers.filter((s) => s.id !== item.supplier_id && s.status !== "deactivated").map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                  <Button small disabled={!target[item.id]} onClick={() => void resolve(item, "merge_into")}>{t("suppliers.review.merge")}</Button>
                  <Button small variant="secondary" onClick={() => void resolve(item, "keep_both")}>{t("suppliers.review.keep")}</Button>
                </>
              )}
              <Button small variant="secondary" onClick={() => void resolve(item, "ignore")}>{t("suppliers.review.ignore")}</Button>
            </div>
          </li>
        ))}
      </ul>
      {error && <p role="alert" className="mmi-error">{error}</p>}
      {note && <p role="status" className="mmi-notice">{note}</p>}
    </Card>
  );
};
