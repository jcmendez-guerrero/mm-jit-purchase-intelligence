import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, RiskItem, errorMessage } from "../../api/client";

interface Props {
  selectedWarehouse?: number | undefined;
  onSelectWarehouse?: ((id: number | undefined) => void) | undefined;
}

export const DashboardScreen: React.FC<Props> = ({ selectedWarehouse, onSelectWarehouse }) => {
  const { t } = useTranslation();
  const [risks, setRisks] = useState<RiskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [warehouse, setWarehouse] = useState<number | undefined>(selectedWarehouse);

  const loadRisks = async (whId?: number) => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getRisks(whId);
      setRisks(data);
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRisks(warehouse);
  }, [warehouse]);

  const handleWarehouseChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value === "all" ? undefined : parseInt(e.target.value, 10);
    setWarehouse(val);
    if (onSelectWarehouse) onSelectWarehouse(val);
  };

  const stockoutCount = risks.filter((r) => r.risk_type === "stockout").length;
  const expiryCount = risks.filter((r) => r.risk_type === "expiry").length;
  const qualityCount = risks.filter((r) => r.risk_type === "data_quality").length;
  const totalCount = risks.length;

  return (
    <section aria-labelledby="dashboard-title">
      {/* 4 Stat Cards matching the UI style */}
      <div className="mmi-stat-grid">
        <div className="mmi-stat-card">
          <div>
            <div className="mmi-stat-card-header">
              <div className="mmi-stat-card-icon">📦</div>
              <h3 className="mmi-stat-card-title">{t("dashboard.risk_stockout")}</h3>
            </div>
            <div className="mmi-stat-card-value">{stockoutCount}</div>
          </div>
          <p className="mmi-stat-card-desc">Stock agotado o por debajo del punto de pedido</p>
        </div>

        <div className="mmi-stat-card">
          <div>
            <div className="mmi-stat-card-header">
              <div className="mmi-stat-card-icon">⏳</div>
              <h3 className="mmi-stat-card-title">{t("dashboard.risk_expiry")}</h3>
            </div>
            <div className="mmi-stat-card-value">{expiryCount}</div>
          </div>
          <p className="mmi-stat-card-desc">Lotes caducados o en ventana crítica (&lt;60 días)</p>
        </div>

        <div className="mmi-stat-card">
          <div>
            <div className="mmi-stat-card-header">
              <div className="mmi-stat-card-icon">⚠️</div>
              <h3 className="mmi-stat-card-title">{t("dashboard.risk_quality")}</h3>
            </div>
            <div className="mmi-stat-card-value">{qualityCount}</div>
          </div>
          <p className="mmi-stat-card-desc">Movimientos en cuarentena o anomalías de IVA</p>
        </div>

        <div className="mmi-stat-card">
          <div>
            <div className="mmi-stat-card-header">
              <div className="mmi-stat-card-icon">📋</div>
              <h3 className="mmi-stat-card-title">Total alertas</h3>
            </div>
            <div className="mmi-stat-card-value">{totalCount}</div>
          </div>
          <p className="mmi-stat-card-desc">Riesgos consolidados en almacenes activos</p>
        </div>
      </div>

      {/* Main card with warehouse filter & risks table */}
      <div className="mmi-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem", marginBottom: "1rem" }}>
          <h2 id="dashboard-title" style={{ margin: 0, fontSize: "1.3rem" }}>
            {t("dashboard.title")}
          </h2>

          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <label htmlFor="warehouse-select" style={{ fontWeight: 600, fontSize: "0.9rem" }}>
              {t("common.warehouse")}:
            </label>
            <select
              id="warehouse-select"
              aria-label={t("common.warehouse")}
              value={warehouse === undefined ? "all" : warehouse}
              onChange={handleWarehouseChange}
            >
              <option value="all">{t("common.all_warehouses")}</option>
              <option value="1">Almacén Central (1)</option>
              <option value="2">Almacén Norte (2)</option>
              <option value="0">Sin asignar (0)</option>
            </select>
          </div>
        </div>

        {loading && <p style={{ color: "var(--color-text-muted)" }}>{t("common.loading")}</p>}
        {error && <p role="alert" style={{ color: "var(--color-danger)" }}>{error}</p>}

        {!loading && !error && risks.length === 0 && (
          <div style={{ padding: "2rem", textAlign: "center", color: "var(--color-text-muted)" }}>
            <p style={{ margin: 0 }}>✓ {t("dashboard.no_risks")}</p>
          </div>
        )}

        {!loading && risks.length > 0 && (
          <div className="mmi-table-wrapper">
            <table aria-label={t("a11y.risk_table")} className="mmi-table">
              <thead>
                <tr>
                  <th>{t("common.variant")}</th>
                  <th>{t("common.status")}</th>
                  <th>{t("proposals.explanation")}</th>
                </tr>
              </thead>
              <tbody>
                {risks.map((item, idx) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: 600 }}>Variante #{item.variant_id}</td>
                    <td>
                      {item.risk_type === "stockout" && (
                        <span className="mmi-badge mmi-badge-danger">{t("dashboard.risk_stockout")}</span>
                      )}
                      {item.risk_type === "expiry" && (
                        <span className="mmi-badge mmi-badge-warning">{t("dashboard.risk_expiry")}</span>
                      )}
                      {item.risk_type === "data_quality" && (
                        <span className="mmi-badge mmi-badge-petroleo">{t("dashboard.risk_quality")}</span>
                      )}
                    </td>
                    <td style={{ color: "var(--color-text-muted)" }}>
                      {String(t(item.explanation_key, item.params || {}))}
                    </td>
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
