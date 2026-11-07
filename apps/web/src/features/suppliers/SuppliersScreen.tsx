import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage, SupplierSummary } from "../../api/client";
import { formatCurrencyEUR } from "../../i18n/formatters";
import { OverrideEditor } from "./OverrideEditor";
import { SupplierTermsEditor } from "./SupplierTermsEditor";

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
      <div className="mmi-card">
        <h2 id="suppliers-title" style={{ fontSize: "1.3rem", marginBottom: "0.5rem" }}>
          {t("suppliers.title")}
        </h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "0.9rem", marginTop: 0 }}>{t("suppliers.subtitle")}</p>
        {loading && <p>{t("common.loading")}</p>}
        {error && (
          <p role="alert" style={{ color: "var(--color-danger)" }}>
            {error}
          </p>
        )}
        {!loading && suppliers.length === 0 && !error && <p>{t("suppliers.empty")}</p>}
        {suppliers.length > 0 && (
          <div className="mmi-table-wrapper">
            <table className="mmi-table" aria-label={t("a11y.suppliers_table")}>
              <thead>
                <tr>
                  <th scope="col">{t("suppliers.col.name")}</th>
                  <th scope="col">{t("suppliers.col.lead")}</th>
                  <th scope="col">{t("suppliers.col.min")}</th>
                  <th scope="col">{t("suppliers.col.version")}</th>
                  <th scope="col">{t("common.status")}</th>
                </tr>
              </thead>
              <tbody>
                {suppliers.map((s) => (
                  <tr key={s.id}>
                    <th scope="row">
                      <button type="button" className="mmi-btn mmi-btn-link" aria-pressed={selected === s.id} onClick={() => setSelected(s.id)}>
                        {s.name}
                      </button>
                    </th>
                    <td>{s.terms?.lead_time_days ?? "–"}</td>
                    <td>{s.terms?.min_order_value ? formatCurrencyEUR(Number(s.terms.min_order_value)) : "–"}</td>
                    <td>{s.version || "–"}</td>
                    <td>
                      {!s.terms && <span>{t("suppliers.no_terms")}</span>}
                      {s.terms?.preferred && <span className="mmi-badge mmi-badge-petroleo">{t("suppliers.badge.preferred")}</span>}{" "}
                      {s.terms?.disabled && <span className="mmi-badge">{t("suppliers.badge.disabled")}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {current ? (
        <>
          <SupplierTermsEditor supplierId={current.id} supplierName={current.name} canEdit={canEdit} onSaved={() => void load()} />
          <OverrideEditor supplierId={current.id} canEdit={canEdit} />
        </>
      ) : (
        suppliers.length > 0 && <p style={{ marginTop: "1rem" }}>{t("suppliers.select")}</p>
      )}
    </section>
  );
};
