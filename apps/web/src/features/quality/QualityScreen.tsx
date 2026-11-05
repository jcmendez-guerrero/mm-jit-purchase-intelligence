import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";

interface Props {
  userRoles: string[];
}

export const QualityScreen: React.FC<Props> = ({ userRoles }) => {
  const { t } = useTranslation();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const canResolve = userRoles.includes("buyer") || userRoles.includes("admin");

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await api.getImportErrors();
      setItems(res.items || []);
    } catch (err: any) {
      setError(err.message || t("common.error"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleResolve = async (id: number, decision: "release" | "ignore") => {
    try {
      await api.resolveImportError(id, decision);
      setItems((prev) => prev.filter((i) => i.id !== id));
    } catch (err: any) {
      alert(err.message || t("common.error"));
    }
  };

  return (
    <section aria-labelledby="quality-title" className="mmi-card">
      <h2 id="quality-title" style={{ fontSize: "1.3rem", marginBottom: "0.5rem" }}>
        {t("quality.title")}
      </h2>
      <p style={{ color: "var(--color-text-muted)", fontSize: "0.9rem", marginTop: 0, marginBottom: "1.5rem" }}>
        {t("quality.quarantine_heading")}
      </p>

      {loading && <p style={{ color: "var(--color-text-muted)" }}>{t("common.loading")}</p>}
      {error && <p role="alert" style={{ color: "var(--color-danger)" }}>{error}</p>}

      {!loading && !error && items.length === 0 && (
        <div style={{ padding: "2rem", textAlign: "center", color: "var(--color-text-muted)" }}>
          <p style={{ margin: 0 }}>✓ {t("quality.quarantine_empty")}</p>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="mmi-table-wrapper">
          <table className="mmi-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>{t("common.variant")}</th>
                <th>{t("quality.movement_reason")}</th>
                <th>{t("quality.codes")}</th>
                <th>{t("quality.created_at")}</th>
                {canResolve && <th>{t("common.actions")}</th>}
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>#{item.id}</td>
                  <td style={{ fontWeight: 600 }}>Variante #{item.variant_id}</td>
                  <td>{item.movement_reason_raw || "—"}</td>
                  <td>
                    {(item.anomaly_codes || []).map((code: string) => (
                      <span key={code} className="mmi-badge mmi-badge-warning" style={{ marginRight: "0.3rem" }}>
                        {code}
                      </span>
                    ))}
                  </td>
                  <td style={{ color: "var(--color-text-muted)", fontSize: "0.85rem" }}>
                    {new Date(item.created_at).toLocaleString("es-ES")}
                  </td>
                  {canResolve && (
                    <td>
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        <button
                          onClick={() => handleResolve(item.id, "release")}
                          className="mmi-btn mmi-btn-primary mmi-btn-sm"
                        >
                          {t("quality.release")}
                        </button>
                        <button
                          onClick={() => handleResolve(item.id, "ignore")}
                          className="mmi-btn mmi-btn-secondary mmi-btn-sm"
                        >
                          {t("quality.ignore")}
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};
