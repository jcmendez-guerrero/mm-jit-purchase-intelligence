import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ServiceLevelEntry, errorMessage } from "../../api/client";

interface Props {
  userRoles: string[];
}

export const ConfigScreen: React.FC<Props> = () => {
  const { t } = useTranslation();
  const [serviceLevels, setServiceLevels] = useState<ServiceLevelEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const sl = await api.getServiceLevels();
      setServiceLevels(sl.history || []);
    } catch (err) {
      setError(errorMessage(err, t("common.error")));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <section aria-labelledby="config-title">
      <div className="mmi-card">
        <h2 id="config-title" style={{ fontSize: "1.3rem", marginBottom: "0.5rem" }}>
          {t("config.title")}
        </h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "0.9rem", marginTop: 0, marginBottom: "1.5rem" }}>
          Parámetros del sistema y políticas de inventario
        </p>

        {loading && <p style={{ color: "var(--color-text-muted)" }}>{t("common.loading")}</p>}
        {error && <p role="alert" style={{ color: "var(--color-danger)" }}>{error}</p>}

        <h3 style={{ fontSize: "1.1rem" }}>{t("config.service_levels")}</h3>
        {serviceLevels.length === 0 && !loading && (
          <p style={{ color: "var(--color-text-muted)" }}>No hay niveles de servicio configurados.</p>
        )}

        {serviceLevels.length > 0 && (
          <div className="mmi-table-wrapper">
            <table className="mmi-table">
              <thead>
                <tr>
                  <th>Alcance</th>
                  <th>Identificador</th>
                  <th>Objetivo (%)</th>
                  <th>Actualizado por</th>
                </tr>
              </thead>
              <tbody>
                {serviceLevels.map((sl, idx) => (
                  <tr key={idx}>
                    <td>{sl.scope}</td>
                    <td style={{ fontWeight: 600 }}>{sl.scope_key}</td>
                    <td style={{ fontWeight: 600, color: "var(--color-primary)" }}>
                      {(parseFloat(sl.target_level) * 100).toFixed(1)}%
                    </td>
                    <td style={{ color: "var(--color-text-muted)", fontSize: "0.85rem" }}>{sl.updated_by}</td>
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
