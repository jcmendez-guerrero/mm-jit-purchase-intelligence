import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";
import { formatCurrencyEUR, formatDate } from "../../i18n/formatters";

interface Props {
  userRoles: string[];
}

export const CostsScreen: React.FC<Props> = ({ userRoles }) => {
  const { t } = useTranslation();
  const [costs, setCosts] = useState<any[]>([]);
  const [writes, setWrites] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const canEdit = userRoles.includes("buyer") || userRoles.includes("admin");

  const loadData = async () => {
    try {
      setLoading(true);
      const [costList, writeList] = await Promise.all([api.getCosts(), api.getCostWrites()]);
      setCosts(costList || []);
      setWrites(writeList || []);
    } catch (err: any) {
      setError(err.message || t("common.error"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleApproveWrite = async (writeId: string) => {
    try {
      await api.approveCostWrite(writeId);
      alert("Cost write enviado a Siweb.");
      loadData();
    } catch (err: any) {
      alert(err.message || t("common.error"));
    }
  };

  return (
    <section aria-labelledby="costs-title">
      <div className="mmi-card">
        <h2 id="costs-title" style={{ fontSize: "1.3rem", marginBottom: "0.5rem" }}>
          {t("costs.title")}
        </h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "0.9rem", marginTop: 0, marginBottom: "1.5rem" }}>
          Tarifas de proveedores y actualizaciones pendientes hacia el ERP Siweb360
        </p>

        {loading && <p style={{ color: "var(--color-text-muted)" }}>{t("common.loading")}</p>}
        {error && <p role="alert" style={{ color: "var(--color-danger)" }}>{error}</p>}

        <h3 style={{ fontSize: "1.1rem", marginTop: "1rem" }}>Costes registrados</h3>
        {!loading && costs.length === 0 && (
          <p style={{ color: "var(--color-text-muted)" }}>No hay costes de proveedores registrados.</p>
        )}

        {!loading && costs.length > 0 && (
          <div className="mmi-table-wrapper">
            <table className="mmi-table">
              <thead>
                <tr>
                  <th>{t("common.variant")}</th>
                  <th>{t("common.supplier")}</th>
                  <th>{t("common.cost")}</th>
                  <th>{t("costs.recargo_label")}</th>
                  <th>{t("costs.verified_at")}</th>
                </tr>
              </thead>
              <tbody>
                {costs.map((c, idx) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: 600 }}>Variante #{c.variant_id}</td>
                    <td>Contacto #{c.supplier_contact_id}</td>
                    <td style={{ fontWeight: 600, color: "var(--color-primary)" }}>
                      {formatCurrencyEUR(c.net_cost)}
                    </td>
                    <td>
                      {c.applies_recargo ? (
                        <span className="mmi-badge mmi-badge-warning">Sí (+req)</span>
                      ) : (
                        <span className="mmi-badge mmi-badge-petroleo">No</span>
                      )}
                    </td>
                    <td style={{ color: "var(--color-text-muted)", fontSize: "0.85rem" }}>
                      {formatDate(c.verified_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="mmi-card">
        <h3 style={{ fontSize: "1.1rem", marginTop: 0 }}>{t("costs.pending_writes")}</h3>
        {!loading && writes.length === 0 && (
          <p style={{ color: "var(--color-text-muted)" }}>No hay actualizaciones pendientes de confirmación.</p>
        )}

        {!loading && writes.length > 0 && (
          <div className="mmi-table-wrapper">
            <table className="mmi-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>{t("common.variant")}</th>
                  <th>{t("common.cost")}</th>
                  <th>{t("common.status")}</th>
                  {canEdit && <th>{t("common.actions")}</th>}
                </tr>
              </thead>
              <tbody>
                {writes.map((w) => (
                  <tr key={w.id}>
                    <td>#{w.id}</td>
                    <td style={{ fontWeight: 600 }}>Variante #{w.variant_id}</td>
                    <td style={{ fontWeight: 600 }}>{formatCurrencyEUR(w.new_cost)}</td>
                    <td>
                      <span className="mmi-badge mmi-badge-warning">{w.status}</span>
                    </td>
                    {canEdit && (
                      <td>
                        <button
                          onClick={() => handleApproveWrite(w.id)}
                          className="mmi-btn mmi-btn-primary mmi-btn-sm"
                        >
                          {t("costs.send_write")}
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
};
