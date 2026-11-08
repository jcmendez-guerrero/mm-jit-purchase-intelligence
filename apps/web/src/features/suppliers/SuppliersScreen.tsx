import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, SupplierSummary } from "../../api/client";
import { formatCurrencyEUR } from "../../i18n/formatters";
import { OverrideEditor } from "./OverrideEditor";
import { SupplierTermsEditor } from "./SupplierTermsEditor";
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

  const load = useCallback(async () => {
    try {
      setSuppliers(await api.getSuppliers());
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

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
      {current ? (
        <>
          <SupplierTermsEditor supplierId={current.id} supplierName={current.name} canEdit={canEdit} onSaved={() => void load()} />
          <OverrideEditor supplierId={current.id} canEdit={canEdit} />
        </>
      ) : (
        suppliers.length > 0 && <p className="mmi-mt-4">{t("suppliers.select")}</p>
      )}
        </div>
      </div>
    </section>
  );
};
