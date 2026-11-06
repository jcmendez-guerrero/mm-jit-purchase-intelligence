import React from "react";
import { useTranslation } from "react-i18next";
import { UserSession } from "../api/client";

interface Props {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  session: UserSession | null;
  onLogout: () => void;
  onDevLogin: (role: string) => void;
}

export const Navigation: React.FC<Props> = ({ currentTab, onSelectTab, session, onLogout, onDevLogin }) => {
  const { t } = useTranslation();

  const tabs = [
    { id: "dashboard", label: t("nav.dashboard") },
    { id: "quality", label: t("nav.quality") },
    { id: "suppliers", label: t("nav.suppliers") },
    { id: "costs", label: t("nav.costs") },
    { id: "proposals", label: t("nav.proposals") },
    { id: "imports", label: t("nav.imports") },
    { id: "config", label: t("nav.config") },
    ...((session?.roles ?? []).includes("admin") ? [{ id: "admin", label: t("nav.admin") }] : []),
  ];

  return (
    <header className="mmi-header">
      {/* Top logo banner */}
      <div className="mmi-top-bar">
        <div className="mmi-logo-wrapper">
          <img
            src="/logo-horizontal.jpg"
            alt="Mundo Mascotix — Medicamentos Veterinarios"
            className="mmi-logo-img"
          />
        </div>
      </div>

      {/* Main navigation bar (Azul petróleo) */}
      <div className="mmi-nav-bar">
        <nav aria-label={t("a11y.menu")} className="mmi-nav-tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onSelectTab(tab.id)}
              className={`mmi-tab-btn ${currentTab === tab.id ? "active" : ""}`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div aria-label={t("a11y.user_profile")} className="mmi-user-profile">
          {session ? (
            <>
              <div className="mmi-user-chip">
                <span>👤</span>
                <span>{session.user_id}</span>
                <span className="mmi-badge mmi-badge-petroleo" style={{ background: "rgba(255,255,255,0.2)", color: "#fff" }}>
                  {(session.roles || []).join(", ")}
                </span>
              </div>
              <button onClick={onLogout} className="mmi-logout-btn">
                <span>↪</span> {t("nav.logout")}
              </button>
            </>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontSize: "0.85rem", opacity: 0.9 }}>Iniciar sesión:</span>
              <button onClick={() => onDevLogin("viewer")} className="mmi-logout-btn">Lector</button>
              <button onClick={() => onDevLogin("buyer")} className="mmi-logout-btn">Comprador</button>
              <button onClick={() => onDevLogin("approver")} className="mmi-logout-btn">Aprobador</button>
              <button onClick={() => onDevLogin("admin")} className="mmi-logout-btn">Admin</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
