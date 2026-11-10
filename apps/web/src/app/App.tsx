import React, { useCallback, useEffect, useRef, useState } from "react";
import { Navigate, Route, Routes, useSearchParams } from "react-router-dom";
import { api, ApiError, onUnauthorized, UserSession } from "../api/client";
import { AdminStatusScreen } from "../features/admin/AdminStatusScreen";
import { AlertsPanel } from "../features/admin/AlertsPanel";
import { AuditScreen } from "../features/admin/AuditScreen";
import { OpsCards } from "../features/admin/OpsCards";
import { QueuePanel } from "../features/admin/QueuePanel";
import { RolesScreen } from "../features/admin/RolesScreen";
import { CostsScreen } from "../features/costs/CostsScreen";
import { DashboardScreen } from "../features/dashboard/DashboardScreen";
import { ImportScreen } from "../features/imports/ImportScreen";
import { LocalLoadScreen } from "../features/localload/LocalLoadScreen";
import { PoliciesScreen } from "../features/policies/PoliciesScreen";
import { ProposalsScreen } from "../features/proposals/ProposalsScreen";
import { QualityScreen } from "../features/quality/QualityScreen";
import { ScenariosScreen } from "../features/scenarios/ScenariosScreen";
import { SuppliersScreen } from "../features/suppliers/SuppliersScreen";
import { NoticeProvider } from "../ui/NoticeProvider";
import { AppShell } from "./AppShell";
import { LoginScreen } from "./LoginScreen";
import { NoAccess } from "./NoAccess";
import { NotFound } from "./NotFound";
import { DEFAULT_PATH } from "./routes";

/** The selected warehouse lives in the address (?almacen=), so a link reproduces the view (FR-002). */
const DashboardRoute: React.FC = () => {
  const [params, setParams] = useSearchParams();
  const raw = params.get("almacen");
  const warehouse = raw !== null && /^\d+$/.test(raw) ? parseInt(raw, 10) : undefined;
  const select = useCallback(
    (id: number | undefined) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (id === undefined) next.delete("almacen");
          else next.set("almacen", String(id));
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );
  return <DashboardScreen selectedWarehouse={warehouse} onSelectWarehouse={select} />;
};

export const App: React.FC = () => {
  const [session, setSession] = useState<UserSession | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [checked, setChecked] = useState(false);
  const [features, setFeatures] = useState<string[]>([]);
  const sessionRef = useRef<UserSession | null>(null);
  sessionRef.current = session;

  useEffect(() => {
    api
      .getMe()
      .then(setSession)
      .catch(() => setSession(null))
      .finally(() => setChecked(true));
  }, []);

  useEffect(() => {
    // The local-only loader exists only in the local environment: ask once per session, and only people who may use it.
    const roles = session?.roles ?? [];
    if (!session || !(roles.includes("buyer") || roles.includes("admin"))) {
      setFeatures([]);
      return;
    }
    api
      .getLocalLoadCapability()
      .then((c) => setFeatures(c.enabled ? ["localLoad"] : []))
      .catch(() => setFeatures([]));
  }, [session]);

  useEffect(() => {
    // A 401 from one call is confirmed with the session probe before the session is declared expired.
    let probing = false;
    onUnauthorized(() => {
      if (probing || !sessionRef.current) return;
      probing = true;
      api
        .getMe()
        .then(setSession)
        .catch((err) => {
          if (err instanceof ApiError && err.status === 401) {
            setSessionExpired(true);
            setSession(null);
          }
        })
        .finally(() => {
          probing = false;
        });
    });
    return () => onUnauthorized(null);
  }, []);

  const handleDevLogin = async (role: string) => {
    const roles = role === "viewer" ? ["viewer"] : ["viewer", role];
    const user = await api.devLogin(`${role}-1`, roles);
    setSessionExpired(false);
    setSession(user);
  };

  const handleLogout = async () => {
    await api.logout();
    setSession(null);
  };

  const userRoles = session?.roles || ["viewer"];

  if (!checked) return <div className="mmi-login" aria-busy="true" />;
  if (!session) return <LoginScreen sessionExpired={sessionExpired} onDevLogin={handleDevLogin} />;

  return (
    <NoticeProvider>
    <Routes>
      <Route element={<AppShell session={session} roles={userRoles} sessionExpired={sessionExpired} onLogout={handleLogout} features={features} />}>
        <Route index element={<Navigate to={DEFAULT_PATH} replace />} />
        <Route path="panel" element={<DashboardRoute />} />
        <Route path="calidad" element={<QualityScreen userRoles={userRoles} showLocalReview={features.includes("localLoad")} />} />
        <Route path="propuestas" element={<ProposalsScreen userRoles={userRoles} />} />
        <Route path="escenarios" element={<ScenariosScreen userRoles={userRoles} />} />
        <Route path="costes" element={<CostsScreen userRoles={userRoles} userId={session?.user_id} />} />
        <Route path="proveedores" element={<SuppliersScreen userRoles={userRoles} />} />
        <Route path="importaciones" element={<ImportScreen userRoles={userRoles} />} />
        <Route path="carga-local" element={features.includes("localLoad") ? <LocalLoadScreen userRoles={userRoles} /> : <NotFound />} />
        <Route path="configuracion" element={<PoliciesScreen userRoles={userRoles} />} />
        <Route
          path="administracion"
          element={
            userRoles.includes("admin") ? (
              <>
                <AdminStatusScreen />
                <OpsCards />
                <QueuePanel />
                <AlertsPanel />
                <RolesScreen />
                <AuditScreen />
              </>
            ) : (
              <NoAccess />
            )
          }
        />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
    </NoticeProvider>
  );
};
