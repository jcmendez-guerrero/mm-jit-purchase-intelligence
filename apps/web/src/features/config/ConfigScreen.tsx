import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api/client";

interface Props {
  userRoles: string[];
}

export const ConfigScreen: React.FC<Props> = ({ userRoles }) => {
  const { t } = useTranslation();
  const [users, setUsers] = useState<any[]>([]);
  const [serviceLevels, setServiceLevels] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = userRoles.includes("admin");

  const loadData = async () => {
    try {
      setLoading(true);
      const sl = await api.getServiceLevels();
      setServiceLevels(sl.history || []);
      if (isAdmin) {
        const r = await api.getRoles();
        setUsers(r.users || []);
      }
    } catch (err: any) {
      setError(err.message || t("common.error"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [isAdmin]);

  const handleRoleToggle = async (userId: string, roleToToggle: string, currentRoles: string[]) => {
    let nextRoles: string[];
    if (currentRoles.includes(roleToToggle)) {
      nextRoles = currentRoles.filter((r) => r !== roleToToggle);
    } else {
      nextRoles = [...currentRoles, roleToToggle];
    }
    // Always keep viewer
    if (!nextRoles.includes("viewer")) nextRoles.push("viewer");

    try {
      await api.updateRoles(userId, nextRoles);
      await loadData();
    } catch (err: any) {
      alert(err.message || t("common.error"));
    }
  };

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

      {isAdmin && (
        <div className="mmi-card">
          <h3 style={{ fontSize: "1.1rem", marginTop: 0 }}>{t("config.user_roles")}</h3>
          <p style={{ color: "var(--color-text-muted)", fontSize: "0.9rem" }}>
            Asignación de roles para control de acceso RBAC
          </p>

          <div className="mmi-table-wrapper">
            <table className="mmi-table">
              <thead>
                <tr>
                  <th>Usuario</th>
                  <th>Roles asignados</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.user_id}>
                    <td style={{ fontWeight: 600 }}>{u.user_id}</td>
                    <td>
                      {(u.roles || []).map((r: string) => (
                        <span key={r} className="mmi-badge mmi-badge-petroleo" style={{ marginRight: "0.3rem" }}>
                          {t(`roles.${r}`)}
                        </span>
                      ))}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "0.3rem" }}>
                        {["buyer", "approver", "admin"].map((r) => {
                          const active = (u.roles || []).includes(r);
                          return (
                            <button
                              key={r}
                              onClick={() => handleRoleToggle(u.user_id, r, u.roles || [])}
                              className={`mmi-btn mmi-btn-sm ${active ? "mmi-btn-primary" : "mmi-btn-secondary"}`}
                            >
                              {active ? `✓ ${t(`roles.${r}`)}` : `+ ${t(`roles.${r}`)}`}
                            </button>
                          );
                        })}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
};
