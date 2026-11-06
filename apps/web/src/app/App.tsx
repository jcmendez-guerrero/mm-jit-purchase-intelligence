import React, { useEffect, useState } from "react";
import { api, UserSession } from "../api/client";
import { ConfigScreen } from "../features/config/ConfigScreen";
import { CostsScreen } from "../features/costs/CostsScreen";
import { RolesScreen } from "../features/admin/RolesScreen";
import { DashboardScreen } from "../features/dashboard/DashboardScreen";
import { ProposalsScreen } from "../features/proposals/ProposalsScreen";
import { QualityScreen } from "../features/quality/QualityScreen";
import { Navigation } from "./Navigation";

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<string>("dashboard");
  const [session, setSession] = useState<UserSession | null>(null);
  const [selectedWarehouse, setSelectedWarehouse] = useState<number | undefined>(undefined);

  const checkSession = async () => {
    try {
      const data = await api.getMe();
      setSession(data);
    } catch {
      setSession(null);
    }
  };

  useEffect(() => {
    checkSession();
  }, []);

  const handleDevLogin = async (role: string) => {
    const roles = role === "viewer" ? ["viewer"] : ["viewer", role];
    const user = await api.devLogin(`${role}-1`, roles);
    setSession(user);
  };

  const handleLogout = async () => {
    await api.logout();
    setSession(null);
  };

  const userRoles = session?.roles || ["viewer"];

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Navigation
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        session={session}
        onLogout={handleLogout}
        onDevLogin={handleDevLogin}
      />

      <main className="mmi-container" style={{ flex: 1, width: "100%" }}>
        <div style={{ marginBottom: "1.75rem" }}>
          <h1 className="mmi-greeting-title">
            Hola, {session ? session.user_id : "Equipo Mundo Mascotix"}
          </h1>
          <p className="mmi-greeting-sub">
            Inteligencia de inventario y compras semanales · Farmacia Veterinaria
          </p>
        </div>

        {currentTab === "dashboard" && (
          <DashboardScreen
            selectedWarehouse={selectedWarehouse}
            onSelectWarehouse={setSelectedWarehouse}
          />
        )}
        {currentTab === "quality" && <QualityScreen userRoles={userRoles} />}
        {currentTab === "costs" && <CostsScreen userRoles={userRoles} />}
        {currentTab === "proposals" && <ProposalsScreen userRoles={userRoles} />}
        {currentTab === "config" && <ConfigScreen userRoles={userRoles} />}
        {currentTab === "admin" && userRoles.includes("admin") && <RolesScreen />}
      </main>
    </div>
  );
};
